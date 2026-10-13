"""
eye_contact.py

Landmark-based eye-contact analysis for the VERIFIED / LOCKED candidate only.

Input  : the (478, 3) MediaPipe landmark array that CandidateTracker already exposes as
         CandidateState.candidate_landmarks (only non-None for analysis_allowed frames
         once the candidate is locked). Optionally the HeadPoseResult computed by
         head_pose.HeadPoseEstimator from the SAME landmarks.
Output : EyeContactResult (frozen dataclass) + running session statistics.

What this module does NOT do (by design):
  - no face detection / no model loading / no camera access
  - no candidate selection, locking or identity (CandidateTracker owns that)
  - no liveness and no blink COUNTING (LivenessDetector owns that; read
    CandidateState.liveness.blink_count instead). Only a cheap "eyes open / closed"
    flag is computed here, because iris landmarks are unreliable while the lids are shut.

Method (cheap, ~50 float ops per call):
  * iris centre (landmarks 468 / 473) is projected onto each eye's corner-to-corner axis
    -> horizontal ratio (0.5 = centred) and a roll-compensated vertical offset, both
    normalised by eye width; the two eyes are averaged and EMA-smoothed.
  * eye contact = gaze inside an elliptical tolerance around the (optionally calibrated)
    centre AND head facing the camera (HeadPoseResult.facing_camera when provided,
    otherwise a landmark nose-offset proxy).
  * hysteresis + time debounce so blinks / jitter do not flip the state.

Thresholds are generic defaults. Webcam position, glasses and individual anatomy shift
the iris offsets, so call start_calibration() while the candidate looks at the camera.

Thread-safety: not thread-safe on its own. opencv_service.py guards every call with a
single lock.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Deque, List, Optional, Tuple

import numpy as np


# --------------------------------------------------------------------- types
class EyeContactState(str, Enum):
    UNKNOWN = "UNKNOWN"            # no verified candidate / not enough data / calibrating
    EYE_CONTACT = "EYE_CONTACT"
    LOOKING_AWAY = "LOOKING_AWAY"
    EYES_CLOSED = "EYES_CLOSED"    # closed longer than a blink


@dataclass
class EyeContactConfig:
    h_tolerance: float = 0.12        # horizontal iris offset (fraction of eye width) still "contact"
    v_tolerance: float = 0.10        # vertical iris offset (fraction of eye width) still "contact"
    release_ratio: float = 0.80      # hysteresis: while away, must come back inside 80% of tolerance
    away_confirm_s: float = 0.40     # look-away must persist this long to be reported
    return_confirm_s: float = 0.15   # contact must persist this long to be reported
    closed_limit_s: float = 1.0      # eyes closed longer than this -> EYES_CLOSED (shorter = blink)
    closed_ratio: float = 0.55       # closed if lid opening < ratio * personal open baseline
    default_openness: float = 0.28   # baseline until enough samples exist
    smoothing: float = 0.5           # EMA weight of the newest sample
    turn_proxy_max: float = 0.09     # fallback head-turn limit (nose offset / face width)
    invalid_hold_s: float = 1.0      # unusable landmarks for this long -> UNKNOWN
    max_dt_s: float = 0.5            # cap on time credited per update (gaps are not counted)
    calibration_s: float = 1.5
    calibration_min_samples: int = 8


@dataclass(frozen=True)
class EyeContactResult:
    state: EyeContactState = EyeContactState.UNKNOWN
    valid: bool = False                  # this update had usable iris landmarks
    gaze_h: float = 0.0                  # horizontal offset from centre (eye widths, + = image right)
    gaze_v: float = 0.0                  # vertical offset from centre (eye widths, + = down)
    gaze_offset: float = 0.0             # normalised distance: <= 1.0 is inside the tolerance ellipse
    head_ok: Optional[bool] = None       # head facing camera (None if no sample yet)
    eyes_open: bool = True
    eye_openness: float = 0.0            # lid opening / eye width
    calibrated: bool = False
    calibrating: bool = False
    calibration_progress: float = 0.0
    current_away_s: float = 0.0          # length of the current look-away spell
    # running session statistics (only advance while update(..., accumulate=True))
    eye_contact_ratio: float = 0.0       # contact_s / analyzed_s
    contact_s: float = 0.0
    away_s: float = 0.0
    closed_s: float = 0.0
    analyzed_s: float = 0.0
    away_events: int = 0
    longest_away_s: float = 0.0
    timestamp_ms: int = 0

    @property
    def is_eye_contact(self) -> bool:
        return self.state == EyeContactState.EYE_CONTACT

    @property
    def is_looking_away(self) -> bool:
        return self.state == EyeContactState.LOOKING_AWAY


@dataclass(frozen=True)
class EyeContactSummary:
    analyzed_s: float = 0.0
    contact_s: float = 0.0
    away_s: float = 0.0
    closed_s: float = 0.0
    eye_contact_ratio: float = 0.0
    away_events: int = 0
    longest_away_s: float = 0.0


# ------------------------------------------------------------------ analyzer
class EyeContactAnalyzer:
    # (corner at image-left, corner at image-right, upper lid, lower lid, iris centre)
    _EYES = ((33, 133, 159, 145, 468), (362, 263, 386, 374, 473))
    _NOSE, _FACE_A, _FACE_B = 1, 234, 454
    _MIN_LANDMARKS = 478                       # iris landmarks are indices 468..477

    def __init__(self, config: Optional[EyeContactConfig] = None) -> None:
        self.cfg = config or EyeContactConfig()
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        """Forget everything: calibration, tracking state and session statistics."""
        self._center = np.zeros(2, dtype=np.float64)
        self._calibrated = False
        self._cancel_calibration()
        self._open_hist: Deque[float] = deque(maxlen=150)
        self._reset_tracking()
        self.reset_session_stats()
        self._last_result = self._build(0, False)

    def reset_session_stats(self) -> None:
        """Zero the statistics only (call when the interview actually starts)."""
        self._contact_s = 0.0
        self._away_s = 0.0
        self._closed_s = 0.0
        self._away_events = 0
        self._longest_away = 0.0
        if self._state == EyeContactState.LOOKING_AWAY and self._last_t is not None:
            self._state_since = self._last_t

    def suspend(self) -> None:
        """
        Call when the candidate cannot be analysed (lost, unverified, multiple faces ...).
        Clears smoothing / debounce / continuity so nothing is carried across the gap and
        no time is credited for it. Calibration and statistics are kept.
        """
        self._reset_tracking()
        self._cancel_calibration()
        self._last_result = self._build(self._last_ms, False)

    def _reset_tracking(self) -> None:
        self._state = EyeContactState.UNKNOWN
        self._state_since: Optional[float] = None
        self._pending: Optional[Tuple[EyeContactState, float]] = None
        self._smooth: Optional[np.ndarray] = None
        self._closed_since: Optional[float] = None
        self._last_t: Optional[float] = None
        self._last_valid_t: Optional[float] = None
        self._last_ms = 0

    # ------------------------------------------------------------ calibration
    def start_calibration(self) -> None:
        """Candidate should look at the camera; finishes after ~calibration_s of good samples."""
        self._cancel_calibration()
        self._calibrating = True
        self._set_state_quiet(EyeContactState.UNKNOWN)

    def _cancel_calibration(self) -> None:
        self._calibrating = False
        self._cal_samples: List[Tuple[float, float]] = []
        self._cal_start: Optional[float] = None
        self._cal_progress = 0.0

    @property
    def is_calibrating(self) -> bool:
        return self._calibrating

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated

    def _calibrate_step(self, t: float, usable: bool, h_dev: float, v: float) -> None:
        if usable:
            if self._cal_start is None:
                self._cal_start = t
            self._cal_samples.append((h_dev, v))
        if self._cal_start is None:
            return
        elapsed = t - self._cal_start
        n = len(self._cal_samples)
        self._cal_progress = min(1.0, elapsed / self.cfg.calibration_s,
                                 n / float(self.cfg.calibration_min_samples))
        if n >= self.cfg.calibration_min_samples and elapsed >= self.cfg.calibration_s:
            self._center = np.median(np.array(self._cal_samples, dtype=np.float64), axis=0)
            self._calibrated = True
            self._cancel_calibration()
            self._smooth = None

    # ---------------------------------------------------------------- measure
    def _measure(self, landmarks: Optional[np.ndarray], aspect: float):
        """-> (h_ratio, v_offset, openness, turn_proxy) or None if unusable."""
        if landmarks is None or landmarks.ndim != 2 or landmarks.shape[0] < self._MIN_LANDMARKS:
            return None
        pts = landmarks[:, :2].astype(np.float64) * np.array([aspect, 1.0])
        hs, vs, opens = [], [], []
        for a, b, up, lo, iris in self._EYES:
            axis = pts[b] - pts[a]
            width = float(np.linalg.norm(axis))
            if width < 1e-6:
                return None
            u = axis / width
            n = np.array([-u[1], u[0]])                      # perpendicular, + = image down
            h = float(np.dot(pts[iris] - pts[a], u) / width)
            if not -0.1 <= h <= 1.1:                         # iris far outside the eye -> bad data
                return None
            v = float(np.dot(pts[iris] - 0.5 * (pts[a] + pts[b]), n) / width)
            hs.append(h)
            vs.append(v)
            opens.append(float(np.linalg.norm(pts[up] - pts[lo]) / width))
        face_w = abs(pts[self._FACE_B][0] - pts[self._FACE_A][0]) + 1e-6
        turn = float((pts[self._NOSE][0] - 0.5 * (pts[self._FACE_A][0] + pts[self._FACE_B][0])) / face_w)
        return float(np.mean(hs)), float(np.mean(vs)), float(np.mean(opens)), turn

    def _head_ok(self, head_pose: Any, turn: float) -> bool:
        # duck-typed: anything exposing .valid and .facing_camera (head_pose.HeadPoseResult)
        if head_pose is not None and bool(getattr(head_pose, "valid", False)):
            return bool(getattr(head_pose, "facing_camera", False))
        return abs(turn) <= self.cfg.turn_proxy_max

    # ----------------------------------------------------------------- update
    def update(
        self,
        landmarks: np.ndarray,
        timestamp_ms: float,
        aspect: float = 1.0,
        head_pose: Any = None,
        accumulate: bool = True,
    ) -> EyeContactResult:
        """
        landmarks: CandidateState.candidate_landmarks of the verified/locked candidate.
        aspect:    frame width / height (same convention as the other modules).
        head_pose: optional HeadPoseResult for the same candidate.
        accumulate: False -> state is still computed (live HUD) but statistics do not advance
                    (e.g. session not RUNNING).
        """
        cfg = self.cfg
        t = timestamp_ms / 1000.0
        dt = 0.0 if self._last_t is None else min(max(t - self._last_t, 0.0), cfg.max_dt_s)
        self._last_t = t
        self._last_ms = int(timestamp_ms)

        m = self._measure(landmarks, aspect)
        if m is None:
            if (
                self._state != EyeContactState.UNKNOWN
                and self._last_valid_t is not None
                and t - self._last_valid_t > cfg.invalid_hold_s
            ):
                self._set_state(EyeContactState.UNKNOWN, t, accumulate)
            self._last_result = self._build(self._last_ms, False)
            return self._last_result

        h, v, openness, turn = m
        self._last_valid_t = t

        # --- eyes open / closed (personal baseline) ---------------------------------
        self._open_hist.append(openness)
        baseline = (
            float(np.percentile(self._open_hist, 75))
            if len(self._open_hist) >= 20
            else cfg.default_openness
        )
        closed = openness < cfg.closed_ratio * baseline
        if closed:
            if self._closed_since is None:
                self._closed_since = t
        else:
            self._closed_since = None
        closed_for = 0.0 if self._closed_since is None else t - self._closed_since

        head_ok = self._head_ok(head_pose, turn)

        # --- calibration (no classification / statistics meanwhile) -----------------
        if self._calibrating:
            self._calibrate_step(t, (not closed) and head_ok, h - 0.5, v)
            self._last_result = self._build(self._last_ms, True, 0.0, 0.0, 0.0, head_ok, not closed, openness)
            return self._last_result

        # --- gaze (smoothed; iris is unreliable while the eye is closed) -------------
        if not closed:
            raw = np.array([h - 0.5, v], dtype=np.float64)
            self._smooth = raw if self._smooth is None else (
                cfg.smoothing * raw + (1.0 - cfg.smoothing) * self._smooth
            )
        if self._smooth is not None:
            dev = self._smooth - self._center
            dev_h, dev_v = float(dev[0]), float(dev[1])
        else:
            dev_h = dev_v = 0.0
        dev_norm = math.hypot(dev_h / cfg.h_tolerance, dev_v / cfg.v_tolerance)

        # --- state machine --------------------------------------------------------------
        if closed:
            if closed_for >= cfg.closed_limit_s:
                self._set_state(EyeContactState.EYES_CLOSED, t, accumulate)
            # shorter than closed_limit_s: a blink -> hold the previous state
        else:
            limit = cfg.release_ratio if self._state == EyeContactState.LOOKING_AWAY else 1.0
            desired = (
                EyeContactState.EYE_CONTACT
                if (dev_norm <= limit and head_ok)
                else EyeContactState.LOOKING_AWAY
            )
            self._debounce(desired, t, accumulate)

        # --- statistics ---------------------------------------------------------------
        if accumulate and dt > 0.0:
            if self._state == EyeContactState.EYE_CONTACT:
                self._contact_s += dt
            elif self._state == EyeContactState.LOOKING_AWAY:
                self._away_s += dt
            elif self._state == EyeContactState.EYES_CLOSED:
                self._closed_s += dt
        if accumulate and self._state == EyeContactState.LOOKING_AWAY and self._state_since is not None:
            self._longest_away = max(self._longest_away, t - self._state_since)

        self._last_result = self._build(
            self._last_ms, True, dev_h, dev_v, dev_norm, head_ok, not closed, openness
        )
        return self._last_result

    # ------------------------------------------------------------ transitions
    def _debounce(self, desired: EyeContactState, t: float, accumulate: bool) -> None:
        if self._state == desired:
            self._pending = None
            return
        if self._state == EyeContactState.UNKNOWN:
            self._set_state(desired, t, accumulate)
            return
        if self._pending is None or self._pending[0] != desired:
            self._pending = (desired, t)
        need = (
            self.cfg.away_confirm_s
            if desired == EyeContactState.LOOKING_AWAY
            else self.cfg.return_confirm_s
        )
        if t - self._pending[1] >= need:
            self._set_state(desired, t, accumulate)

    def _set_state(self, new: EyeContactState, t: float, accumulate: bool) -> None:
        if new == self._state:
            return
        self._state = new
        self._state_since = t
        self._pending = None
        if new == EyeContactState.LOOKING_AWAY and accumulate:
            self._away_events += 1

    def _set_state_quiet(self, new: EyeContactState) -> None:
        self._state = new
        self._state_since = None
        self._pending = None

    # ---------------------------------------------------------------- results
    def _build(
        self,
        ts_ms: int,
        valid: bool,
        dev_h: float = 0.0,
        dev_v: float = 0.0,
        dev_norm: float = 0.0,
        head_ok: Optional[bool] = None,
        eyes_open: bool = True,
        openness: float = 0.0,
    ) -> EyeContactResult:
        analyzed = self._contact_s + self._away_s + self._closed_s
        away_now = 0.0
        if (
            self._state == EyeContactState.LOOKING_AWAY
            and self._state_since is not None
            and self._last_t is not None
        ):
            away_now = max(0.0, self._last_t - self._state_since)
        return EyeContactResult(
            state=self._state,
            valid=valid,
            gaze_h=dev_h,
            gaze_v=dev_v,
            gaze_offset=dev_norm,
            head_ok=head_ok,
            eyes_open=eyes_open,
            eye_openness=openness,
            calibrated=self._calibrated,
            calibrating=self._calibrating,
            calibration_progress=self._cal_progress,
            current_away_s=away_now,
            eye_contact_ratio=(self._contact_s / analyzed) if analyzed > 0 else 0.0,
            contact_s=self._contact_s,
            away_s=self._away_s,
            closed_s=self._closed_s,
            analyzed_s=analyzed,
            away_events=self._away_events,
            longest_away_s=self._longest_away,
            timestamp_ms=int(ts_ms),
        )

    def snapshot(self) -> EyeContactResult:
        """Most recent result (UNKNOWN after suspend() / reset())."""
        return self._last_result

    def summary(self) -> EyeContactSummary:
        analyzed = self._contact_s + self._away_s + self._closed_s
        return EyeContactSummary(
            analyzed_s=analyzed,
            contact_s=self._contact_s,
            away_s=self._away_s,
            closed_s=self._closed_s,
            eye_contact_ratio=(self._contact_s / analyzed) if analyzed > 0 else 0.0,
            away_events=self._away_events,
            longest_away_s=self._longest_away,
        )