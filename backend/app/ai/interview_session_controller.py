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

import time
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional, List, Dict, Deque
from collections import deque

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
        if frame is None:
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

        # ---- 2. MediaPipe landmark/detection pass -----------------------------
        mp_result = _safe_call(getattr(self.mediapipe_service, "process", None), frame)

        # ---- 3. Candidate identity: raw face candidates ------------------------
        faces = _safe_call(
            getattr(self.candidate_identity, "identify", None), frame, mp_result
        )
        if faces is None:
            faces = []

        # ---- 4. Candidate tracker: locking / recovery / grace period ----------
        track_result = _safe_call(
            getattr(self.candidate_tracker, "update", None), frame, faces
        )

        candidate_info = self._extract_candidate_info(track_result, faces)
        locked_face = _get(track_result, "locked_face", "candidate_face", "target_face")

        # ---- 5. Downstream analyses (only meaningful once a candidate exists) --
        eye_result = _safe_call(
            getattr(self.eye_contact_service, "analyze", None), frame, locked_face
        )
        head_result = _safe_call(
            getattr(self.head_pose_service, "analyze", None), frame, locked_face
        )
        liveness_result = _safe_call(
            getattr(self.liveness_detector, "check", None), frame, locked_face, track_result
        )
        phone_result = _safe_call(
            getattr(self.phone_detection_service, "detect", None), frame
        )

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
            eye_contact=_get(eye_result, "eye_contact", "is_eye_contact"),
            gaze_direction=_get(eye_result, "gaze_direction", "gaze"),
            blink_detected=_get(eye_result, "blink_detected", "blink"),
            eye_confidence=float(_get(eye_result, "confidence", "eye_confidence", default=0.0) or 0.0),
            status=str(_get(eye_result, "status", default="OK")),
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
# EXAMPLE USAGE
# ==========================================================================

if __name__ == "__main__":
    # Wire up with whatever concrete module instances your app already
    # constructs elsewhere (import paths are illustrative only).
    #
    # from opencv_service import OpenCVService
    # from mediapipe_service import MediaPipeService
    # from candidate_identity import CandidateIdentity
    # from candidate_tracker import CandidateTracker
    # from eye_contact import EyeContactService
    # from head_pose import HeadPoseService
    # from liveness_detector import LivenessDetector
    # from phone_detection import PhoneDetectionService
    #
    # controller = InterviewSessionController(
    #     opencv_service=OpenCVService(),
    #     mediapipe_service=MediaPipeService(),
    #     candidate_identity=CandidateIdentity(),
    #     candidate_tracker=CandidateTracker(),
    #     eye_contact_service=EyeContactService(),
    #     head_pose_service=HeadPoseService(),
    #     liveness_detector=LivenessDetector(),
    #     phone_detection_service=PhoneDetectionService(),
    # )
    # controller.start_session()
    # try:
    #     while True:
    #         result = controller.process_frame()
    #         print(result.to_dict())
    #         if result.session.session_state == SessionState.ENDED.value:
    #             break
    # finally:
    #     controller.end_session()

    logging.basicConfig(level=logging.INFO)
    controller = InterviewSessionController()  # no modules injected -> safe no-op run
    controller.start_session()
    result = controller.process_frame(frame=object())  # dummy non-None "frame"
    print(result.to_dict())
    controller.end_session()