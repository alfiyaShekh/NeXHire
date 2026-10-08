"""
interview_session_controller.py
================================

Orchestrator for the NexHire camera-monitoring pipeline.

This module owns NO detection/tracking/analysis logic of its own. It only
calls the already-implemented modules, reads their outputs defensively,
merges them into one consistent `SessionResult`, drives a session-level
state machine, and produces de-duplicated warnings.

Pipeline it represents:

    Camera -> OpenCV -> MediaPipe -> Candidate Identity -> Candidate Tracker
        -> {Eye Contact, Head Pose, Liveness, Phone Detection}
        -> Session Controller -> Unified Session State

--------------------------------------------------------------------------
ASSUMED UPSTREAM INTERFACES
--------------------------------------------------------------------------
Because the previous modules aren't visible to this file at write time,
the controller talks to them through a small set of "expected" methods
and reads their results with `getattr(...)`-based defensive access rather
than strict attribute/key access. This means:

  * If your real modules already expose these method names, the
    controller works with zero changes.
  * If a name differs slightly (e.g. `detect()` vs `process()`), only the
    thin `_call_*` wrapper for that module needs a one-line edit -- the
    rest of the controller is untouched.
  * Every extraction supports both dict results and dataclass/object
    results with attribute access.

Expected calls (only the ones actually used):

  opencv_service:
      frame = opencv_service.read_frame()                # BGR np.ndarray or None

  mediapipe_service:
      mp_result = mediapipe_service.process(frame)        # holds detected faces

  candidate_identity:
      faces = candidate_identity.identify(frame, mp_result)
          -> list of face-like objects/dicts, each exposing (any of):
             face_id / id, bbox, landmarks, embedding, confidence

  candidate_tracker:
      track_result = candidate_tracker.update(frame, faces)
          -> object/dict exposing (any of):
             candidate_locked, is_locked
             candidate_found, found
             candidate_lost, lost
             face_count, num_faces
             multiple_faces
             tracking_status / status
             locked_face / candidate_face   (the face bound to the candidate)

  eye_contact_service:
      eye_result = eye_contact.analyze(frame, locked_face)
          -> exposes: eye_contact, gaze_direction, blink_detected, confidence, status

  head_pose_service:
      head_result = head_pose.analyze(frame, locked_face)
          -> exposes: yaw, pitch, roll, pose_status/status, confidence

  liveness_detector:
      liveness_result = liveness_detector.check(frame, locked_face, track_result)
          -> exposes: is_live, liveness_status/status, confidence, challenge_status

  phone_detection:
      phone_result = phone_detection.detect(frame)
          -> exposes: phone_detected, confidence, detections/boxes, status

All of these are optional at construction time (dependency injection) --
missing modules simply produce "unavailable" sub-results instead of
crashing the controller.
"""

from __future__ import annotations

import os
import sys

# Ensure this directory is in sys.path so sibling imports work seamlessly
_AI_DIR = os.path.dirname(os.path.abspath(__file__))
if _AI_DIR not in sys.path:
    sys.path.insert(0, _AI_DIR)

import time
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional, List, Dict, Deque, Tuple
from collections import deque

import cv2
import numpy as np

logger = logging.getLogger("nexhire.session_controller")


# ==========================================================================
# ENUMS
# ==========================================================================

class SessionState(str, Enum):
    INITIALIZING = "INITIALIZING"
    WAITING_FOR_CANDIDATE = "WAITING_FOR_CANDIDATE"
    CANDIDATE_LOCKED = "CANDIDATE_LOCKED"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    CANDIDATE_LOST = "CANDIDATE_LOST"
    LIVENESS_CHECK = "LIVENESS_CHECK"
    ACTIVE = "ACTIVE"
    WARNING = "WARNING"
    ENDED = "ENDED"


class LivenessStatus(str, Enum):
    LIVE = "LIVE"
    NOT_LIVE = "NOT_LIVE"
    UNCERTAIN = "UNCERTAIN"
    CANDIDATE_LOST = "CANDIDATE_LOST"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    UNAVAILABLE = "UNAVAILABLE"


class TrackingStatus(str, Enum):
    NOT_LOCKED = "NOT_LOCKED"
    LOCKED_VISIBLE = "LOCKED_VISIBLE"
    LOCKED_GRACE_PERIOD = "LOCKED_GRACE_PERIOD"   # temporarily disappeared
    LOCKED_LOST = "LOCKED_LOST"                    # grace period expired
    UNKNOWN = "UNKNOWN"


class WarningCode(str, Enum):
    NO_CANDIDATE = "NO_CANDIDATE_DETECTED"
    MULTIPLE_FACES = "MULTIPLE_FACES_DETECTED"
    CANDIDATE_GRACE = "CANDIDATE_TEMPORARILY_LOST"
    CANDIDATE_LOST = "CANDIDATE_LOST"
    IDENTITY_UNCERTAIN = "CANDIDATE_IDENTITY_UNCERTAIN"
    LIVENESS_UNCERTAIN = "LIVENESS_UNCERTAIN"
    LIVENESS_FAILED = "LIVENESS_FAILED"
    PHONE_DETECTED = "PHONE_DETECTED"
    FRAME_UNAVAILABLE = "FRAME_UNAVAILABLE"


# ==========================================================================
# SUB-RESULT DATACLASSES (the "Unified Output")
# ==========================================================================

@dataclass
class CandidateInfo:
    candidate_locked: bool = False
    candidate_found: bool = False
    candidate_lost: bool = False
    face_count: int = 0
    multiple_faces: bool = False
    tracking_status: str = TrackingStatus.UNKNOWN.value
    identity_uncertain: bool = False


@dataclass
class LivenessInfo:
    is_live: Optional[bool] = None
    liveness_status: str = LivenessStatus.UNAVAILABLE.value
    liveness_confidence: float = 0.0
    challenge_status: Optional[str] = None


@dataclass
class EyeInfo:
    eye_contact: Optional[bool] = None
    gaze_direction: Optional[str] = None
    blink_detected: Optional[bool] = None
    eye_confidence: float = 0.0
    status: str = "UNAVAILABLE"
    score: float = 0.0
    blink_count: int = 0
    blink_rate_bpm: float = 0.0
    ear_avg: float = 0.0
    horizontal_ratio: float = 0.50
    vertical_ratio: float = 0.50
    is_blinking: bool = False


@dataclass
class HeadPoseInfo:
    yaw: Optional[float] = None
    pitch: Optional[float] = None
    roll: Optional[float] = None
    pose_status: str = "UNAVAILABLE"
    pose_confidence: float = 0.0


@dataclass
class PhoneInfo:
    phone_detected: bool = False
    phone_confidence: float = 0.0
    phone_detections: List[Any] = field(default_factory=list)
    status: str = "UNAVAILABLE"


@dataclass
class SessionInfo:
    session_state: str = SessionState.INITIALIZING.value
    warnings: List[str] = field(default_factory=list)
    timestamp: float = 0.0
    frame_ok: bool = True


@dataclass
class SessionResult:
    candidate: CandidateInfo
    liveness: LivenessInfo
    eye: EyeInfo
    head: HeadPoseInfo
    phone: PhoneInfo
    session: SessionInfo

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate": asdict(self.candidate),
            "liveness": asdict(self.liveness),
            "eye": asdict(self.eye),
            "head": asdict(self.head),
            "phone": asdict(self.phone),
            "session": asdict(self.session),
        }


# ==========================================================================
# SMALL DEFENSIVE HELPERS
# ==========================================================================

def _get(obj: Any, *names: str, default: Any = None) -> Any:
    """
    Read the first matching attribute/key found on `obj`, trying each name
    in `names`. Works for dicts, dataclasses, and plain objects alike.
    Never raises.
    """
    if obj is None:
        return default
    for name in names:
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
        else:
            if hasattr(obj, name):
                return getattr(obj, name)
    return default


def _safe_call(fn, *args, **kwargs):
    """Call fn defensively; log and return None on failure instead of raising."""
    if fn is None:
        return None
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - intentional broad guard at boundary
        logger.exception("Upstream module call failed: %s", exc)
        return None


# ==========================================================================
# WARNING DEBOUNCER
# ==========================================================================

class WarningDebouncer:
    """
    Prevents a single noisy frame from spamming the warning list.

    A warning code is only *emitted* once it has been requested on at
    least `min_consecutive_frames` of the last `window` calls, and it is
    only *cleared* once it stops being requested for `min_consecutive_frames`
    in a row. This does not affect candidate-lock/lost decisions -- those
    stability rules already live in candidate_tracker; this class only
    smooths the human-facing warning strings.
    """

    def __init__(self, min_consecutive_frames: int = 3, window: int = 10):
        self.min_consecutive_frames = min_consecutive_frames
        self.window = window
        self._history: Dict[str, Deque[bool]] = {}
        self._active: Dict[str, bool] = {}

    def update(self, requested_codes: List[str]) -> List[str]:
        requested_set = set(requested_codes)
        all_codes = requested_set | set(self._history.keys())

        confirmed: List[str] = []
        for code in all_codes:
            hist = self._history.setdefault(code, deque(maxlen=self.window))
            hist.append(code in requested_set)

            recent_true = sum(1 for v in list(hist)[-self.min_consecutive_frames:] if v)
            recent_false = sum(1 for v in list(hist)[-self.min_consecutive_frames:] if not v)

            was_active = self._active.get(code, False)
            if not was_active and recent_true >= self.min_consecutive_frames:
                self._active[code] = True
            elif was_active and recent_false >= self.min_consecutive_frames:
                self._active[code] = False

            if self._active.get(code, False):
                confirmed.append(code)

        return confirmed


# ==========================================================================
# MAIN CONTROLLER
# ==========================================================================

class InterviewSessionController:
    """
    Orchestrates the existing NexHire modules into one unified,
    per-frame interview session state.

    All upstream modules are injected (dependency injection). Any of them
    may be `None`; the controller degrades gracefully rather than crashing.
    """

    def __init__(
        self,
        opencv_service: Any = None,
        mediapipe_service: Any = None,
        candidate_identity: Any = None,
        candidate_tracker: Any = None,
        eye_contact_service: Any = None,
        head_pose_service: Any = None,
        liveness_detector: Any = None,
        phone_detection_service: Any = None,
        warning_min_consecutive_frames: int = 3,
        warning_window: int = 10,
    ) -> None:
        self.opencv_service = opencv_service
        self.mediapipe_service = mediapipe_service
        self.candidate_identity = candidate_identity
        self.candidate_tracker = candidate_tracker
        self.eye_contact_service = eye_contact_service
        self.head_pose_service = head_pose_service
        self.liveness_detector = liveness_detector
        self.phone_detection_service = phone_detection_service

        self._debouncer = WarningDebouncer(
            min_consecutive_frames=warning_min_consecutive_frames,
            window=warning_window,
        )

        self._state: SessionState = SessionState.INITIALIZING
        self._ever_locked: bool = False
        self._last_result: Optional[SessionResult] = None
        self._frame_count: int = 0

    # ----------------------------------------------------------------
    # PUBLIC API
    # ----------------------------------------------------------------

    def start_session(self) -> None:
        """Reset internal state and move to WAITING_FOR_CANDIDATE."""
        self._state = SessionState.WAITING_FOR_CANDIDATE
        self._ever_locked = False
        self._last_result = None
        self._frame_count = 0
        self._debouncer = WarningDebouncer(
            self._debouncer.min_consecutive_frames, self._debouncer.window
        )
        logger.info("Interview session started.")

    def end_session(self) -> SessionResult:
        """Explicitly end the session. This is the only place identity resets."""
        self._state = SessionState.ENDED
        result = self._build_result(
            candidate=CandidateInfo(),
            liveness=LivenessInfo(),
            eye=EyeInfo(),
            head=HeadPoseInfo(),
            phone=PhoneInfo(),
            frame_ok=True,
            forced_warnings=[],
        )
        self._last_result = result
        logger.info("Interview session ended.")
        return result

    def process_frame(self, frame: Optional[Any] = None) -> SessionResult:
        """
        Run one iteration of the pipeline for a single frame and return the
        unified SessionResult. If `frame` is not supplied, it is pulled from
        opencv_service.read_frame() when available.
        """
        self._frame_count += 1

        if self._state == SessionState.ENDED:
            # Session explicitly ended: do not process further, return last state.
            return self._last_result or self.end_session()

        # ---- 1. Acquire frame -------------------------------------------------
        if frame is None and self.opencv_service is not None:
            frame = _safe_call(getattr(self.opencv_service, "read_frame", None))

        if frame is None:
            result = self._build_result(
                candidate=CandidateInfo(tracking_status=TrackingStatus.UNKNOWN.value),
                liveness=LivenessInfo(liveness_status=LivenessStatus.UNAVAILABLE.value),
                eye=EyeInfo(),
                head=HeadPoseInfo(),
                phone=PhoneInfo(),
                frame_ok=False,
                forced_warnings=[WarningCode.FRAME_UNAVAILABLE.value],
            )
            self._last_result = result
            return result

        bgr_frame = getattr(frame, "frame", frame)
        frame_id = getattr(frame, "frame_id", self._frame_count)
        timestamp_ms = getattr(frame, "timestamp_ms", int(time.time() * 1000))

        if not isinstance(bgr_frame, np.ndarray) and bgr_frame is not None and not hasattr(bgr_frame, "shape"):
            # Mock or dummy non-ndarray frame for quick tests
            bgr_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # ---- 2. MediaPipe landmark/detection pass -----------------------------
        mp_result = None
        if self.mediapipe_service is not None:
            try:
                mp_result = self.mediapipe_service.process(bgr_frame, frame_id)
            except TypeError:
                mp_result = _safe_call(getattr(self.mediapipe_service, "process", None), bgr_frame)
            except Exception as exc:
                logger.debug("MediaPipe service call exception: %s", exc)

        # ---- 3 & 4. Candidate identity & Tracker ------------------------------
        track_result = None
        faces = getattr(mp_result, "faces", []) if mp_result is not None else []

        if self.candidate_tracker is not None:
            # Auto-lock if candidate identity is not yet locked and exactly 1 face is present
            identity = getattr(self.candidate_tracker, "identity", None)
            is_locked = getattr(identity, "is_locked", False) if identity else False
            if not is_locked and mp_result is not None and getattr(mp_result, "num_faces", 0) == 1:
                _safe_call(getattr(self.candidate_tracker, "request_lock", None), mp_result)

            if hasattr(self.candidate_tracker, "process"):
                track_result = _safe_call(self.candidate_tracker.process, mp_result)
            elif hasattr(self.candidate_tracker, "update"):
                if self.candidate_identity is not None and hasattr(self.candidate_identity, "identify"):
                    faces = _safe_call(getattr(self.candidate_identity, "identify", None), bgr_frame, mp_result) or faces
                track_result = _safe_call(self.candidate_tracker.update, bgr_frame, faces)

        candidate_info = self._extract_candidate_info(track_result, faces)
        locked_face = _get(track_result, "locked_face", "candidate_face", "target_face", "locked_candidate_landmarks")

        # ---- 5. Downstream analyses -----------------------------------------
        eye_result = None
        if self.eye_contact_service is not None:
            if hasattr(self.eye_contact_service, "analyze"):
                try:
                    eye_result = self.eye_contact_service.analyze(track_result)
                except (TypeError, AttributeError):
                    eye_result = _safe_call(self.eye_contact_service.analyze, bgr_frame, locked_face)

        head_result = None
        if self.head_pose_service is not None:
            if hasattr(self.head_pose_service, "analyze"):
                try:
                    head_result = self.head_pose_service.analyze(track_result)
                except (TypeError, AttributeError):
                    head_result = _safe_call(self.head_pose_service.analyze, bgr_frame, locked_face)

        liveness_result = None
        if self.liveness_detector is not None:
            if hasattr(self.liveness_detector, "analyze"):
                try:
                    liveness_result = self.liveness_detector.analyze(track_result, eye_result, head_result, timestamp_ms)
                except (TypeError, AttributeError):
                    liveness_result = _safe_call(self.liveness_detector.analyze, track_result)
            elif hasattr(self.liveness_detector, "check"):
                liveness_result = _safe_call(self.liveness_detector.check, bgr_frame, locked_face, track_result)

        phone_result = None
        if self.phone_detection_service is not None:
            phone_result = _safe_call(getattr(self.phone_detection_service, "detect", None), bgr_frame)

        eye_info = self._extract_eye_info(eye_result)
        head_info = self._extract_head_info(head_result)
        liveness_info = self._extract_liveness_info(
            liveness_result, candidate_info
        )
        phone_info = self._extract_phone_info(phone_result)

        result = self._build_result(
            candidate=candidate_info,
            liveness=liveness_info,
            eye=eye_info,
            head=head_info,
            phone=phone_info,
            frame_ok=True,
            forced_warnings=[],
        )
        self._last_result = result
        return result

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def last_result(self) -> Optional[SessionResult]:
        return self._last_result

    # ----------------------------------------------------------------
    # EXTRACTION: turn raw upstream results into unified sub-dataclasses
    # ----------------------------------------------------------------

    def _extract_candidate_info(self, track_result: Any, faces: List[Any]) -> CandidateInfo:
        face_count = _get(track_result, "face_count", "num_faces", default=None)
        if face_count is None:
            face_count = len(faces) if faces else 0

        locked = bool(_get(track_result, "candidate_locked", "is_locked", default=False))
        found = bool(_get(track_result, "candidate_found", "found", default=False))
        lost = bool(_get(track_result, "candidate_lost", "lost", default=False))
        multiple = bool(
            _get(track_result, "multiple_faces", default=(face_count is not None and face_count > 1))
        )
        uncertain = bool(_get(track_result, "identity_uncertain", "uncertain", default=False))

        raw_status = _get(track_result, "tracking_status", "status", default=None)
        if raw_status is not None:
            tracking_status = str(raw_status)
        else:
            # Derive a sensible status if the tracker didn't supply one.
            if not locked:
                tracking_status = TrackingStatus.NOT_LOCKED.value
            elif locked and found and not lost:
                tracking_status = TrackingStatus.LOCKED_VISIBLE.value
            elif locked and lost:
                tracking_status = TrackingStatus.LOCKED_LOST.value
            elif locked and not found and not lost:
                # Locked, momentarily not found, but tracker hasn't declared
                # it fully lost yet => treat as within grace period.
                tracking_status = TrackingStatus.LOCKED_GRACE_PERIOD.value
            else:
                tracking_status = TrackingStatus.UNKNOWN.value

        if locked:
            self._ever_locked = True

        return CandidateInfo(
            candidate_locked=locked,
            candidate_found=found,
            candidate_lost=lost,
            face_count=int(face_count or 0),
            multiple_faces=multiple,
            tracking_status=tracking_status,
            identity_uncertain=uncertain,
        )

    def _extract_eye_info(self, eye_result: Any) -> EyeInfo:
        if eye_result is None:
            return EyeInfo()
        return EyeInfo(
            eye_contact=_get(eye_result, "eye_contact", "looking_at_screen"),
            gaze_direction=_get(eye_result, "gaze_direction", "gaze"),
            blink_detected=_get(eye_result, "blink_detected", "blink"),
            eye_confidence=float(_get(eye_result, "confidence", "eye_confidence", default=0.0) or 0.0),
            status=str(_get(eye_result, "status", default="OK")),
            score=float(_get(eye_result, "score", default=0.0) or 0.0),
            blink_count=int(_get(eye_result, "blink_count", default=0) or 0),
            blink_rate_bpm=float(_get(eye_result, "blink_rate_bpm", default=0.0) or 0.0),
            ear_avg=float(_get(eye_result, "ear_avg", default=0.0) or 0.0),
            horizontal_ratio=float(_get(eye_result, "horizontal_ratio", default=0.50) or 0.50),
            vertical_ratio=float(_get(eye_result, "vertical_ratio", default=0.50) or 0.50),
            is_blinking=bool(_get(eye_result, "is_blinking", default=False)),
        )

    def _extract_head_info(self, head_result: Any) -> HeadPoseInfo:
        if head_result is None:
            return HeadPoseInfo()
        return HeadPoseInfo(
            yaw=_get(head_result, "yaw"),
            pitch=_get(head_result, "pitch"),
            roll=_get(head_result, "roll"),
            pose_status=str(_get(head_result, "pose_status", "status", default="OK")),
            pose_confidence=float(_get(head_result, "confidence", "pose_confidence", default=0.0) or 0.0),
        )

    def _extract_liveness_info(self, liveness_result: Any, candidate_info: CandidateInfo) -> LivenessInfo:
        # Liveness must never be inferred from "face present" alone.
        if candidate_info.multiple_faces:
            return LivenessInfo(
                is_live=None,
                liveness_status=LivenessStatus.MULTIPLE_FACES.value,
                liveness_confidence=0.0,
                challenge_status=_get(liveness_result, "challenge_status"),
            )
        if candidate_info.candidate_lost or not candidate_info.candidate_found:
            if candidate_info.candidate_locked:
                return LivenessInfo(
                    is_live=None,
                    liveness_status=LivenessStatus.CANDIDATE_LOST.value,
                    liveness_confidence=0.0,
                    challenge_status=_get(liveness_result, "challenge_status"),
                )

        if liveness_result is None:
            return LivenessInfo(liveness_status=LivenessStatus.UNAVAILABLE.value)

        is_live = _get(liveness_result, "is_live")
        raw_status = _get(liveness_result, "liveness_status", "status")
        if raw_status is not None:
            status = str(raw_status)
        elif is_live is True:
            status = LivenessStatus.LIVE.value
        elif is_live is False:
            status = LivenessStatus.NOT_LIVE.value
        else:
            status = LivenessStatus.UNCERTAIN.value

        return LivenessInfo(
            is_live=is_live,
            liveness_status=status,
            liveness_confidence=float(_get(liveness_result, "confidence", "liveness_confidence", default=0.0) or 0.0),
            challenge_status=_get(liveness_result, "challenge_status"),
        )

    def _extract_phone_info(self, phone_result: Any) -> PhoneInfo:
        if phone_result is None:
            return PhoneInfo()
        detections = _get(phone_result, "phone_detections", "detections", "boxes", default=[]) or []
        return PhoneInfo(
            phone_detected=bool(_get(phone_result, "phone_detected", "detected", default=len(detections) > 0)),
            phone_confidence=float(_get(phone_result, "confidence", "phone_confidence", default=0.0) or 0.0),
            phone_detections=list(detections),
            status=str(_get(phone_result, "status", default="OK")),
        )

    # ----------------------------------------------------------------
    # STATE MACHINE + WARNINGS + RESULT ASSEMBLY
    # ----------------------------------------------------------------

    def _compute_warning_codes(
        self,
        candidate: CandidateInfo,
        liveness: LivenessInfo,
        phone: PhoneInfo,
        frame_ok: bool,
    ) -> List[str]:
        codes: List[str] = []

        if not frame_ok:
            codes.append(WarningCode.FRAME_UNAVAILABLE.value)
            return codes  # nothing else is meaningful without a frame

        if candidate.face_count == 0 and not candidate.candidate_locked:
            codes.append(WarningCode.NO_CANDIDATE.value)

        if candidate.multiple_faces:
            codes.append(WarningCode.MULTIPLE_FACES.value)

        if candidate.candidate_locked and candidate.tracking_status == TrackingStatus.LOCKED_GRACE_PERIOD.value:
            codes.append(WarningCode.CANDIDATE_GRACE.value)

        if candidate.candidate_locked and (
            candidate.candidate_lost or candidate.tracking_status == TrackingStatus.LOCKED_LOST.value
        ):
            codes.append(WarningCode.CANDIDATE_LOST.value)

        if candidate.identity_uncertain:
            codes.append(WarningCode.IDENTITY_UNCERTAIN.value)

        if liveness.liveness_status == LivenessStatus.UNCERTAIN.value:
            codes.append(WarningCode.LIVENESS_UNCERTAIN.value)
        elif liveness.liveness_status == LivenessStatus.NOT_LIVE.value:
            codes.append(WarningCode.LIVENESS_FAILED.value)

        if phone.phone_detected:
            codes.append(WarningCode.PHONE_DETECTED.value)

        return codes

    def _compute_state(
        self,
        candidate: CandidateInfo,
        liveness: LivenessInfo,
        confirmed_warnings: List[str],
        frame_ok: bool,
    ) -> SessionState:
        if self._state == SessionState.ENDED:
            return SessionState.ENDED

        if not frame_ok:
            # Don't downgrade a locked candidate just because one frame failed;
            # surface it as a warning state instead of losing lock info.
            return SessionState.WARNING if self._ever_locked else SessionState.INITIALIZING

        if not candidate.candidate_locked:
            if candidate.face_count > 1:
                return SessionState.MULTIPLE_FACES
            return SessionState.WAITING_FOR_CANDIDATE

        # From here on, candidate.candidate_locked is True and stays True
        # (identity is never reset except via end_session/start_session).

        if candidate.candidate_lost or candidate.tracking_status == TrackingStatus.LOCKED_LOST.value:
            return SessionState.CANDIDATE_LOST

        if candidate.multiple_faces:
            # Locked candidate still tracked, but extra people are visible.
            return SessionState.MULTIPLE_FACES

        if liveness.liveness_status in (
            LivenessStatus.UNCERTAIN.value,
            LivenessStatus.NOT_LIVE.value,
        ):
            return SessionState.LIVENESS_CHECK

        if confirmed_warnings:
            return SessionState.WARNING

        return SessionState.ACTIVE

    def _build_result(
        self,
        candidate: CandidateInfo,
        liveness: LivenessInfo,
        eye: EyeInfo,
        head: HeadPoseInfo,
        phone: PhoneInfo,
        frame_ok: bool,
        forced_warnings: List[str],
    ) -> SessionResult:
        raw_codes = forced_warnings + self._compute_warning_codes(candidate, liveness, phone, frame_ok)
        confirmed = self._debouncer.update(raw_codes) if self._state != SessionState.ENDED else raw_codes

        new_state = self._compute_state(candidate, liveness, confirmed, frame_ok)
        self._state = new_state

        session_info = SessionInfo(
            session_state=new_state.value,
            warnings=confirmed,
            timestamp=time.time(),
            frame_ok=frame_ok,
        )

        return SessionResult(
            candidate=candidate,
            liveness=liveness,
            eye=eye,
            head=head,
            phone=phone,
            session=session_info,
        )


# ==========================================================================
# HUD & VISUALIZATION
# ==========================================================================

def draw_session_hud(
    frame: np.ndarray,
    result: SessionResult,
    phone_boxes: Optional[List[Tuple[int, int, int, int]]] = None,
) -> np.ndarray:
    """
    Draw a real-time HUD telemetry overlay with Gaze Radar onto the OpenCV frame.
    """
    h, w = frame.shape[:2]
    canvas = frame.copy()

    # Draw semi-transparent header bar & side panel
    overlay = canvas.copy()
    cv2.rectangle(overlay, (0, 0), (w, 54), (16, 18, 24), -1)
    cv2.rectangle(overlay, (0, h - 36), (w, h), (16, 18, 24), -1)
    # Side telemetry card
    cv2.rectangle(overlay, (12, 64), (390, 275), (16, 18, 24), -1)
    cv2.addWeighted(overlay, 0.82, canvas, 0.18, 0, canvas)
    cv2.rectangle(canvas, (12, 64), (390, 275), (60, 68, 85), 1)

    # 1. Header: State & Status badge
    state_str = result.session.session_state
    state_colors = {
        SessionState.ACTIVE.value: (60, 210, 60),            # Green
        SessionState.WAITING_FOR_CANDIDATE.value: (240, 180, 0),  # Cyan/Yellow
        SessionState.INITIALIZING.value: (240, 180, 0),
        SessionState.WARNING.value: (0, 165, 255),            # Orange
        SessionState.MULTIPLE_FACES.value: (50, 50, 230),     # Red
        SessionState.CANDIDATE_LOST.value: (50, 50, 230),     # Red
        SessionState.LIVENESS_CHECK.value: (220, 100, 255),   # Magenta
    }
    badge_color = state_colors.get(state_str, (180, 180, 180))

    cv2.putText(canvas, "NexHire AI Proctor", (16, 34), cv2.FONT_HERSHEY_DUPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(canvas, f"STATUS: {state_str}", (w - 340, 34), cv2.FONT_HERSHEY_DUPLEX, 0.65, badge_color, 2, cv2.LINE_AA)

    # 2. Side Telemetry Panel
    y = 90
    line_h = 24

    # Candidate tracking
    cand = result.candidate
    cand_text = f"Candidate: {'LOCKED' if cand.candidate_locked else 'SEARCHING'} ({cand.tracking_status})"
    cand_col = (60, 220, 60) if cand.candidate_locked and cand.candidate_found else (0, 165, 255)
    cv2.putText(canvas, cand_text, (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, cand_col, 1, cv2.LINE_AA)
    y += line_h

    # Faces count
    face_text = f"Faces: {cand.face_count}"
    face_col = (255, 255, 255) if cand.face_count == 1 else ((50, 50, 240) if cand.face_count > 1 else (180, 180, 180))
    cv2.putText(canvas, face_text, (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, face_col, 1, cv2.LINE_AA)
    y += line_h

    # Eye contact & Gaze
    eye = result.eye
    eye_str = "YES" if eye.eye_contact else ("BLINK" if eye.is_blinking or eye.blink_detected else ("NO" if eye.eye_contact is False else "N/A"))
    eye_col = (60, 220, 60) if eye.eye_contact else ((0, 220, 255) if eye.is_blinking else (0, 80, 255))
    gaze_dir = eye.gaze_direction or "N/A"
    cv2.putText(canvas, f"Eye Contact: {eye_str} ({gaze_dir})", (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, eye_col, 1, cv2.LINE_AA)
    y += line_h

    # Focus Score & Blinks / BPM
    score_pct = int(eye.score * 100)
    cv2.putText(canvas, f"Focus Score: {score_pct}% | Blinks: {eye.blink_count} ({eye.blink_rate_bpm:.1f} BPM)", (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (170, 200, 255), 1, cv2.LINE_AA)
    y += line_h

    # Head Pose
    head = result.head
    yaw_str = f"{head.yaw:+.1f}°" if head.yaw is not None else "N/A"
    pitch_str = f"{head.pitch:+.1f}°" if head.pitch is not None else "N/A"
    cv2.putText(canvas, f"Head Pose: Y:{yaw_str} P:{pitch_str} ({head.pose_status})", (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (230, 230, 230), 1, cv2.LINE_AA)
    y += line_h

    # Liveness
    live = result.liveness
    live_str = live.liveness_status
    live_col = (60, 220, 60) if live.is_live else ((0, 165, 255) if live.is_live is None else (50, 50, 230))
    cv2.putText(canvas, f"Liveness: {live_str}", (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, live_col, 1, cv2.LINE_AA)
    y += line_h

    # Phone detection
    phone = result.phone
    phone_col = (50, 50, 240) if phone.phone_detected else (60, 220, 60)
    phone_str = "DETECTED!" if phone.phone_detected else "CLEAR"
    cv2.putText(canvas, f"Phone: {phone_str}", (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, phone_col, 1, cv2.LINE_AA)

    # 3. Gaze Radar Widget (Embedded in Top-Right of Card)
    radar_x = 295
    radar_y = 78
    radar_size = 80
    rcx = radar_x + radar_size // 2
    rcy = radar_y + radar_size // 2

    # Background box & crosshair
    cv2.rectangle(canvas, (radar_x, radar_y), (radar_x + radar_size, radar_y + radar_size), (26, 28, 36), -1)
    cv2.rectangle(canvas, (radar_x, radar_y), (radar_x + radar_size, radar_y + radar_size), (65, 72, 88), 1)
    cv2.line(canvas, (radar_x, rcy), (radar_x + radar_size, rcy), (46, 50, 62), 1)
    cv2.line(canvas, (rcx, radar_y), (rcx, radar_y + radar_size), (46, 50, 62), 1)

    # Safe attention target box
    target_box = 13
    cv2.rectangle(canvas, (rcx - target_box, rcy - target_box), (rcx + target_box, rcy + target_box), (0, 160, 70), 1)

    # Map horizontal & vertical ratio to radar dot
    dot_x = int(radar_x + eye.horizontal_ratio * radar_size)
    dot_y = int(radar_y + eye.vertical_ratio * radar_size)
    dot_x = max(radar_x + 4, min(radar_x + radar_size - 4, dot_x))
    dot_y = max(radar_y + 4, min(radar_y + radar_size - 4, dot_y))

    # Glowing radar dot
    cv2.circle(canvas, (dot_x, dot_y), 5, eye_col, -1)
    cv2.circle(canvas, (dot_x, dot_y), 7, (255, 255, 255), 1)
    cv2.putText(canvas, "GAZE RADAR", (radar_x + 5, radar_y + radar_size + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (140, 145, 160), 1, cv2.LINE_AA)

    # 4. Warnings alert box if any active
    if result.session.warnings:
        warn_text = " | ".join(result.session.warnings)
        cv2.rectangle(canvas, (12, 288), (w - 12, 322), (0, 0, 180), -1)
        cv2.putText(canvas, f"WARNING: {warn_text}", (20, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

    # 5. Footer shortcuts
    footer_text = "[Q] Quit  |  [R] Reset Lock  |  [C] Trigger Blink Challenge"
    cv2.putText(canvas, footer_text, (18, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1, cv2.LINE_AA)

    return canvas


# ==========================================================================
# LIVE CAMERA RUNNER
# ==========================================================================

def run_live_session(camera_index: int = 0) -> None:
    """
    Launches a live webcam monitoring session with real-time HUD telemetry overlays.
    """
    logger.info("Initializing NexHire live session...")

    # Imports with sibling module resolution
    try:
        from opencv_service import OpenCVService, CameraError
        from mediapipe_service import MediaPipeService
        from candidate_identity import CandidateIdentityManager
        from candidate_tracker import CandidateTracker
        from eye_contact import EyeContactAnalyzer
        from head_pose import HeadPoseEstimator
        from liveness_detector import LivenessDetector, ChallengeType
        from phone_detection import PhoneDetector
    except ImportError:
        from app.ai.opencv_service import OpenCVService, CameraError
        from app.ai.mediapipe_service import MediaPipeService
        from app.ai.candidate_identity import CandidateIdentityManager
        from app.ai.candidate_tracker import CandidateTracker
        from app.ai.eye_contact import EyeContactAnalyzer
        from app.ai.head_pose import HeadPoseEstimator
        from app.ai.liveness_detector import LivenessDetector, ChallengeType
        from app.ai.phone_detection import PhoneDetector

    # Resolve model path relative to this script directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(current_dir, "models", "face_landmarker.task")

    if not os.path.exists(model_path):
        # Fallback to local models/ in current working directory
        model_path = "models/face_landmarker.task"

    print("=" * 60)
    print("  NexHire AI Interview Proctor - Live Camera Feed")
    print(f"  Face Model Path : {model_path}")
    print("  Controls        : [Q] Quit  [R] Reset Lock  [C] Challenge")
    print("=" * 60)

    # Initialize sub-services
    mediapipe_svc = MediaPipeService(model_path=model_path)
    try:
        mediapipe_svc.load()
    except Exception as exc:
        logger.error("Failed to load Face Landmarker model: %s", exc)

    identity_mgr = CandidateIdentityManager()
    tracker = CandidateTracker(identity_manager=identity_mgr)
    eye_svc = EyeContactAnalyzer()
    head_svc = HeadPoseEstimator()
    liveness_svc = LivenessDetector()

    # Optional PhoneDetector
    phone_svc = None
    try:
        phone_svc = PhoneDetector()
        phone_svc.load()
    except Exception as e:
        logger.info("Phone detection optional module not loaded: %s", e)

    controller = InterviewSessionController(
        mediapipe_service=mediapipe_svc,
        candidate_identity=identity_mgr,
        candidate_tracker=tracker,
        eye_contact_service=eye_svc,
        head_pose_service=head_svc,
        liveness_detector=liveness_svc,
        phone_detection_service=phone_svc,
    )
    controller.start_session()

    try:
        with OpenCVService(camera_index=camera_index) as cam:
            logger.info("Webcam started at index %d. Press 'q' in window to exit.", camera_index)
            
            for fd in cam.stream():
                result = controller.process_frame(frame=fd)
                hud_frame = draw_session_hud(fd.frame, result)
                
                cv2.imshow("NexHire - AI Interview Monitor", hud_frame)
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord("q") or key == 27:  # 'q' or ESC
                    break
                elif key == ord("r"):  # Reset candidate lock
                    tracker.reset()
                    controller.start_session()
                    logger.info("Candidate lock reset requested by user.")
                elif key == ord("c"):  # Trigger liveness challenge
                    liveness_svc.request_challenge(ChallengeType.BLINK, fd.timestamp_ms)
                    logger.info("Blink challenge requested.")

    except CameraError as exc:
        logger.error("Camera access failed: %s", exc)
        print(f"\n[ERROR] Could not open camera at index {camera_index}: {exc}")
        print("Please check that your webcam is connected and not being used by another application.")
    except KeyboardInterrupt:
        logger.info("Live session interrupted by user.")
    finally:
        controller.end_session()
        if mediapipe_svc.is_loaded:
            mediapipe_svc.close()
        if phone_svc and phone_svc.is_loaded:
            phone_svc.close()
        cv2.destroyAllWindows()
        logger.info("Live session finished. Window closed.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_live_session(camera_index=0)