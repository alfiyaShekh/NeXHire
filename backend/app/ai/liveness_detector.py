"""
liveness_detector.py

Estimates whether the LOCKED CANDIDATE appears to be a live person, by
aggregating behavioral signals (blink, head movement, facial-landmark
movement) over a configurable observation window, and/or by evaluating
an explicit challenge-response ("please blink" / "please turn left").

INPUT CONTRACT (no existing module is modified):
    analyze() takes the already-computed outputs of the existing
    pipeline for the SAME frame:
        - tracker_result : candidate_tracker.TrackerResult
        - eye_result     : eye_contact.EyeContactResult
        - head_result    : head_pose.HeadPoseResult
        - timestamp_ms   : float  (caller-supplied; TrackerResult does
          not carry a timestamp, so this module accepts it explicitly
          rather than modifying candidate_tracker.py. Pass the
          originating FrameResult.timestamp_ms from mediapipe_service.)

    Because eye_contact.py and head_pose.py already refuse to compute
    real values for any candidate that isn't confidently TRACKING (see
    their own gating), this module automatically inherits "never
    analyze the wrong face": if tracker_result.tracking_status is not
    TRACKING, eye_result/head_result are already uncertain/empty, and
    a challenge can only succeed against values computed for the
    locked candidate.

LIMITATIONS (stated explicitly, per requirements):
    - Blinking or head movement alone is NEVER treated as guaranteed
      proof of a real person; LIVE requires either (a) an explicitly
      solved challenge, or (b) more than one independent passive
      signal type observed within the window.
    - This module does NOT claim protection against every photo,
      video, screen-replay, or deepfake attack — it only reports
      behavioral evidence for/against a static or non-responsive
      input. A sufficiently good video replay could pass a passive
      check; challenge-response narrows, but does not eliminate, that
      risk.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, List, Optional, Sequence, Tuple

from candidate_tracker import TrackerResult, TrackingStatus
from eye_contact import EyeContactResult
from head_pose import HeadPoseResult
from mediapipe_service import Landmark

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LivenessStatus(str, Enum):
    LIVE = "LIVE"
    NOT_LIVE = "NOT_LIVE"
    UNCERTAIN = "UNCERTAIN"
    CANDIDATE_LOST = "CANDIDATE_LOST"
    MULTIPLE_FACES = "MULTIPLE_FACES"


class ChallengeType(str, Enum):
    BLINK = "blink"
    TURN_LEFT = "turn_head_left"
    TURN_RIGHT = "turn_head_right"
    LOOK_UP = "look_up"
    LOOK_DOWN = "look_down"


class ChallengeStatus(str, Enum):
    NONE = "none"
    PENDING = "pending"
    SUCCESS = "success"
    TIMEOUT = "timeout"


_CHALLENGE_TO_POSE_STATUS = {
    ChallengeType.TURN_LEFT: "looking_left",
    ChallengeType.TURN_RIGHT: "looking_right",
    ChallengeType.LOOK_UP: "looking_up",
    ChallengeType.LOOK_DOWN: "looking_down",
}


@dataclass
class LivenessResult:
    is_live: Optional[bool]
    liveness_status: str
    confidence: float
    blink_signal: bool
    head_movement_signal: bool
    facial_movement_signal: bool
    challenge_status: str
    candidate_present: bool
    reason: str


@dataclass
class _WindowSample:
    timestamp_ms: float
    blink: bool
    head_moved: bool
    facial_moved: bool


class LivenessDetector:
    """
    Usage (passive monitoring):
        liveness = LivenessDetector()
        result = liveness.analyze(tracker_result, eye_result, head_result, timestamp_ms)

    Usage (challenge-response):
        liveness.request_challenge(ChallengeType.BLINK, timestamp_ms)
        # keep calling analyze() each frame; result.challenge_status
        # becomes "success" or "timeout".
    """

    def __init__(
        self,
        observation_window_ms: float = 8000.0,
        min_signal_types_for_live: int = 2,
        facial_movement_threshold: float = 0.004,
        head_movement_delta_deg: float = 6.0,
        challenge_timeout_ms: float = 6000.0,
        max_confidence: float = 0.9,
    ) -> None:
        self.observation_window_ms = observation_window_ms
        self.min_signal_types_for_live = min_signal_types_for_live
        self.facial_movement_threshold = facial_movement_threshold
        self.head_movement_delta_deg = head_movement_delta_deg
        self.challenge_timeout_ms = challenge_timeout_ms
        self.max_confidence = max_confidence

        self._window: Deque[_WindowSample] = deque()
        self._window_start_ms: Optional[float] = None

        self._prev_landmarks: Optional[List[Landmark]] = None
        self._prev_pose: Optional[Tuple[float, float, float]] = None

        self._active_challenge: Optional[ChallengeType] = None
        self._challenge_deadline_ms: Optional[float] = None
        self._challenge_status: ChallengeStatus = ChallengeStatus.NONE

    # ------------------------------------------------------------------ #
    # Challenge-response control
    # ------------------------------------------------------------------ #
    def request_challenge(self, challenge: ChallengeType, timestamp_ms: float) -> bool:
        """
        Start a challenge (e.g. "please blink"). Only meaningful while a
        candidate is actively, confidently locked — the caller should
        check candidate_present on a recent result first. Returns True
        if the challenge was started.
        """
        self._active_challenge = challenge
        self._challenge_deadline_ms = timestamp_ms + self.challenge_timeout_ms
        self._challenge_status = ChallengeStatus.PENDING
        logger.info("Liveness challenge requested: %s", challenge.value)
        return True

    def cancel_challenge(self) -> None:
        self._active_challenge = None
        self._challenge_deadline_ms = None
        self._challenge_status = ChallengeStatus.NONE

    def reset(self) -> None:
        """Explicitly clear all accumulated evidence and any challenge."""
        self._window.clear()
        self._window_start_ms = None
        self._prev_landmarks = None
        self._prev_pose = None
        self.cancel_challenge()
        logger.info("Liveness detector reset.")

    # ------------------------------------------------------------------ #
    # Per-frame analysis
    # ------------------------------------------------------------------ #
    def analyze(
        self,
        tracker_result: TrackerResult,
        eye_result: EyeContactResult,
        head_result: HeadPoseResult,
        timestamp_ms: float,
    ) -> LivenessResult:
        status = tracker_result.tracking_status

        if status == TrackingStatus.NOT_LOCKED:
            self.reset()
            return self._result(
                LivenessStatus.UNCERTAIN, 0.0, False, False, False,
                candidate_present=False, reason="No candidate locked yet.",
            )

        if status == TrackingStatus.CANDIDATE_LOST:
            # Requirement: losing the candidate must NOT automatically
            # imply "live". Evidence gathered before the loss no longer
            # applies to whoever might appear next, so it is discarded.
            self.reset()
            return self._result(
                LivenessStatus.CANDIDATE_LOST, 0.0, False, False, False,
                candidate_present=False, reason="Locked candidate is not visible (grace period expired).",
            )

        if status == TrackingStatus.AMBIGUOUS:
            # Multiple faces plausibly match the locked candidate this
            # frame; identity is not reliably resolved, so no signal is
            # attributed to anyone. Window is preserved, not reset.
            return self._result(
                LivenessStatus.MULTIPLE_FACES, 0.0, False, False, False,
                candidate_present=False, reason="Multiple faces present; candidate identity is ambiguous this frame.",
            )

        if status == TrackingStatus.REACQUIRING:
            # Candidate temporarily not visible, within the tracker's
            # grace period. Preserve window; do not fabricate signals.
            self._check_challenge_timeout(timestamp_ms)
            return self._result(
                LivenessStatus.UNCERTAIN, 0.0, False, False, False,
                candidate_present=False, reason="Candidate temporarily not visible.",
            )

        # status == TRACKING: candidate confidently identified this frame.
        return self._analyze_tracking_frame(tracker_result, eye_result, head_result, timestamp_ms)

    # ------------------------------------------------------------------ #
    # Core logic (only reached while confidently tracking the candidate)
    # ------------------------------------------------------------------ #
    def _analyze_tracking_frame(
        self,
        tracker_result: TrackerResult,
        eye_result: EyeContactResult,
        head_result: HeadPoseResult,
        timestamp_ms: float,
    ) -> LivenessResult:
        blink_signal = bool(eye_result.blink_detected)
        head_movement_signal = self._detect_head_movement(head_result)
        facial_movement_signal = self._detect_facial_movement(tracker_result.locked_candidate_landmarks)

        if self._window_start_ms is None:
            self._window_start_ms = timestamp_ms
        self._window.append(_WindowSample(timestamp_ms, blink_signal, head_movement_signal, facial_movement_signal))
        self._prune_window(timestamp_ms)

        challenge_status = self._evaluate_challenge(eye_result, head_result, timestamp_ms)

        if self._active_challenge is not None or challenge_status in (ChallengeStatus.SUCCESS, ChallengeStatus.TIMEOUT):
            return self._challenge_driven_result(
                challenge_status, blink_signal, head_movement_signal, facial_movement_signal
            )

        return self._passive_result(
            timestamp_ms, blink_signal, head_movement_signal, facial_movement_signal
        )

    def _challenge_driven_result(
        self,
        challenge_status: ChallengeStatus,
        blink_signal: bool,
        head_movement_signal: bool,
        facial_movement_signal: bool,
    ) -> LivenessResult:
        challenge_name = self._active_challenge.value if self._active_challenge else "unknown"
        if challenge_status == ChallengeStatus.SUCCESS:
            return self._result(
                LivenessStatus.LIVE, self.max_confidence, blink_signal, head_movement_signal,
                facial_movement_signal, candidate_present=True,
                reason=f"Challenge '{challenge_name}' completed by the locked candidate.",
                challenge_status=challenge_status,
            )
        if challenge_status == ChallengeStatus.TIMEOUT:
            return self._result(
                LivenessStatus.UNCERTAIN, 0.1, blink_signal, head_movement_signal,
                facial_movement_signal, candidate_present=True,
                reason=f"Challenge '{challenge_name}' was not completed in time.",
                challenge_status=challenge_status,
            )
        # PENDING
        return self._result(
            LivenessStatus.UNCERTAIN, 0.2, blink_signal, head_movement_signal,
            facial_movement_signal, candidate_present=True,
            reason=f"Waiting for candidate to complete challenge '{challenge_name}'.",
            challenge_status=challenge_status,
        )

    def _passive_result(
        self,
        timestamp_ms: float,
        blink_signal: bool,
        head_movement_signal: bool,
        facial_movement_signal: bool,
    ) -> LivenessResult:
        any_blink = any(s.blink for s in self._window)
        any_head = any(s.head_moved for s in self._window)
        any_facial = any(s.facial_moved for s in self._window)
        signal_types_present = sum([any_blink, any_head, any_facial])

        window_complete = (
            self._window_start_ms is not None
            and (timestamp_ms - self._window_start_ms) >= self.observation_window_ms
        )

        if signal_types_present >= self.min_signal_types_for_live:
            confidence = min(self.max_confidence, 0.5 + 0.2 * signal_types_present)
            return self._result(
                LivenessStatus.LIVE, confidence, blink_signal, head_movement_signal, facial_movement_signal,
                candidate_present=True,
                reason=f"{signal_types_present} independent movement signal type(s) observed within the window.",
            )

        if signal_types_present == 0 and window_complete:
            return self._result(
                LivenessStatus.NOT_LIVE, 0.4, blink_signal, head_movement_signal, facial_movement_signal,
                candidate_present=True,
                reason="No blink, head movement, or facial movement observed over the full observation window.",
            )

        reason = (
            "Some movement observed but not enough independent signal types yet."
            if signal_types_present > 0
            else "Observation window still filling; no movement observed yet."
        )
        return self._result(
            LivenessStatus.UNCERTAIN, 0.3 * signal_types_present, blink_signal, head_movement_signal,
            facial_movement_signal, candidate_present=True, reason=reason,
        )

    # ------------------------------------------------------------------ #
    # Signal extraction
    # ------------------------------------------------------------------ #
    def _detect_head_movement(self, head_result: HeadPoseResult) -> bool:
        if head_result.status != "tracking" or head_result.yaw is None:
            return False

        current = (head_result.yaw, head_result.pitch, head_result.roll)
        moved = False
        if self._prev_pose is not None:
            d_yaw = abs(current[0] - self._prev_pose[0])
            d_pitch = abs(current[1] - self._prev_pose[1])
            moved = d_yaw >= self.head_movement_delta_deg or d_pitch >= self.head_movement_delta_deg
        self._prev_pose = current
        return moved

    def _detect_facial_movement(self, landmarks: Optional[Sequence[Landmark]]) -> bool:
        if not landmarks:
            return False

        moved = False
        if self._prev_landmarks is not None and len(self._prev_landmarks) == len(landmarks):
            total = 0.0
            for a, b in zip(self._prev_landmarks, landmarks):
                total += ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
            mean_displacement = total / len(landmarks)
            moved = mean_displacement >= self.facial_movement_threshold
        self._prev_landmarks = list(landmarks)
        return moved

    # ------------------------------------------------------------------ #
    # Challenge evaluation
    # ------------------------------------------------------------------ #
    def _evaluate_challenge(
        self, eye_result: EyeContactResult, head_result: HeadPoseResult, timestamp_ms: float
    ) -> ChallengeStatus:
        if self._active_challenge is None:
            return self._challenge_status

        if self._challenge_deadline_ms is not None and timestamp_ms > self._challenge_deadline_ms:
            self._challenge_status = ChallengeStatus.TIMEOUT
            self._active_challenge = None
            return self._challenge_status

        matched = False
        if self._active_challenge == ChallengeType.BLINK:
            matched = bool(eye_result.blink_detected)
        else:
            expected_pose = _CHALLENGE_TO_POSE_STATUS.get(self._active_challenge)
            matched = head_result.status == "tracking" and head_result.pose_status == expected_pose

        if matched:
            self._challenge_status = ChallengeStatus.SUCCESS
            self._active_challenge = None

        return self._challenge_status

    def _check_challenge_timeout(self, timestamp_ms: float) -> None:
        """Allow a challenge to time out even while the candidate is briefly unresolved."""
        if self._active_challenge is not None and self._challenge_deadline_ms is not None:
            if timestamp_ms > self._challenge_deadline_ms:
                self._challenge_status = ChallengeStatus.TIMEOUT
                self._active_challenge = None

    # ------------------------------------------------------------------ #
    # Window / result helpers
    # ------------------------------------------------------------------ #
    def _prune_window(self, timestamp_ms: float) -> None:
        cutoff = timestamp_ms - self.observation_window_ms
        while self._window and self._window[0].timestamp_ms < cutoff:
            self._window.popleft()

    def _result(
        self,
        status: LivenessStatus,
        confidence: float,
        blink_signal: bool,
        head_movement_signal: bool,
        facial_movement_signal: bool,
        candidate_present: bool,
        reason: str,
        challenge_status: Optional[ChallengeStatus] = None,
    ) -> LivenessResult:
        is_live = True if status == LivenessStatus.LIVE else (False if status == LivenessStatus.NOT_LIVE else None)
        return LivenessResult(
            is_live=is_live,
            liveness_status=status.value,
            confidence=round(min(confidence, self.max_confidence), 3),
            blink_signal=blink_signal,
            head_movement_signal=head_movement_signal,
            facial_movement_signal=facial_movement_signal,
            challenge_status=(challenge_status or self._challenge_status).value,
            candidate_present=candidate_present,
            reason=reason,
        )