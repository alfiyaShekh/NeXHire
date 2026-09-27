"""
eye_contact.py

Analyzes eye contact / gaze / blink state for the LOCKED CANDIDATE only.

Input contract: this module consumes a candidate_tracker.TrackerResult
(NOT a raw FrameResult), so face selection is entirely delegated to
candidate_tracker.py / candidate_identity.py. This module never looks
at frame_result.faces directly and never picks a face on its own.

LIMITATION (stated explicitly, per requirements):
    Gaze/eye-contact here is estimated from 2D facial landmarks (eye
    contour + iris position) with no camera calibration, no 3D eyeball
    model, and no head-pose compensation. It is a useful signal, not
    ground-truth gaze tracking — e.g. it can be fooled by head tilt or
    unusual lighting/occlusion. It should be combined with head_pose.py
    and, later, liveness_detector.py rather than trusted in isolation.
"""

import logging
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Sequence

from candidate_tracker import TrackerResult, TrackingStatus
from mediapipe_service import Landmark

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Standard MediaPipe face-mesh eye landmark indices.
# 6-point sets follow the classic EAR (Eye Aspect Ratio) layout:
# [outer_corner, top_1, top_2, inner_corner, bottom_1, bottom_2]
_LEFT_EYE_EAR_IDX = (33, 160, 158, 133, 153, 144)
_RIGHT_EYE_EAR_IDX = (263, 385, 387, 362, 380, 373)

# Iris landmarks are present because face_landmarker.task outputs the
# full 478-point mesh (468 mesh points + 10 iris points).
_LEFT_IRIS_CENTER_IDX = 468
_RIGHT_IRIS_CENTER_IDX = 473

# Horizontal eye corners (outer, inner) reused for gaze ratio.
_LEFT_EYE_H_IDX = (33, 133)
_RIGHT_EYE_H_IDX = (263, 362)
# Vertical eyelid landmarks (top, bottom) reused for gaze ratio.
_LEFT_EYE_V_IDX = (159, 145)
_RIGHT_EYE_V_IDX = (386, 374)

_MAX_LANDMARK_INDEX = 477  # highest index we ever access


@dataclass
class EyeContactResult:
    eye_contact: Optional[bool]
    gaze_direction: Optional[str]   # "center" | "left" | "right" | "up" | "down" | None
    blink_detected: bool
    eyes_open: Optional[bool]
    confidence: float               # 0.0 (unavailable) .. ~0.85 (heuristic ceiling)
    status: str                     # mirrors TrackingStatus, or "insufficient_landmarks"


class EyeContactAnalyzer:
    """
    Usage:
        analyzer = EyeContactAnalyzer()
        result = analyzer.analyze(tracker_result)  # from CandidateTracker.process()
    """

    def __init__(
        self,
        ear_closed_threshold: float = 0.21,
        gaze_center_tolerance: float = 0.18,
        smoothing_window: int = 5,
        max_blink_closed_frames: int = 4,
    ) -> None:
        self.ear_closed_threshold = ear_closed_threshold
        self.gaze_center_tolerance = gaze_center_tolerance
        self.smoothing_window = smoothing_window
        self.max_blink_closed_frames = max_blink_closed_frames

        self._gaze_history: Deque[bool] = deque(maxlen=smoothing_window)
        self._consecutive_closed_frames: int = 0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def analyze(self, tracker_result: TrackerResult) -> EyeContactResult:
        """
        Analyze eye contact for the currently locked candidate.

        Gating rules (never analyze the wrong / an arbitrary person):
            - NOT_LOCKED / CANDIDATE_LOST -> unavailable, state reset.
            - AMBIGUOUS -> identity not reliably resolved this frame;
              return an uncertain result rather than guessing.
            - REACQUIRING -> candidate not currently visible; uncertain.
            - TRACKING -> compute from locked_candidate_landmarks.
        """
        status = tracker_result.tracking_status

        if status in (TrackingStatus.NOT_LOCKED, TrackingStatus.CANDIDATE_LOST):
            self._reset_state()
            return self._empty_result(status.value)

        if status == TrackingStatus.AMBIGUOUS:
            # Requirement: only continue analyzing the locked candidate if
            # it can be reliably identified. Ambiguous match == not reliable.
            return self._empty_result(TrackingStatus.AMBIGUOUS.value)

        if status == TrackingStatus.REACQUIRING:
            # Candidate not currently visible; do not fabricate a reading.
            return self._empty_result(TrackingStatus.REACQUIRING.value)

        # status == TRACKING
        landmarks = tracker_result.locked_candidate_landmarks
        if not landmarks or len(landmarks) <= _MAX_LANDMARK_INDEX:
            logger.warning("Insufficient landmarks for eye-contact analysis.")
            return self._empty_result("insufficient_landmarks")

        return self._compute(landmarks)

    # ------------------------------------------------------------------ #
    # Core computation (only reached for a confidently tracked candidate)
    # ------------------------------------------------------------------ #
    def _compute(self, landmarks: Sequence[Landmark]) -> EyeContactResult:
        left_ear = self._eye_aspect_ratio(landmarks, _LEFT_EYE_EAR_IDX)
        right_ear = self._eye_aspect_ratio(landmarks, _RIGHT_EYE_EAR_IDX)
        avg_ear = (left_ear + right_ear) / 2.0
        eyes_open = avg_ear >= self.ear_closed_threshold

        blink_detected = self._update_blink_state(eyes_open)

        gaze_direction: Optional[str] = None
        is_centered = False
        if eyes_open:
            gaze_direction, is_centered = self._estimate_gaze(landmarks)

        self._gaze_history.append(bool(eyes_open and is_centered))
        # Smoothed eye contact: majority of the recent window must be
        # "centered + open" so a single noisy frame or a brief blink
        # doesn't flip eye_contact to False.
        eye_contact = (
            sum(self._gaze_history) >= (len(self._gaze_history) / 2.0)
            if self._gaze_history
            else None
        )

        return EyeContactResult(
            eye_contact=eye_contact,
            gaze_direction=gaze_direction if eyes_open else "eyes_closed",
            blink_detected=blink_detected,
            eyes_open=eyes_open,
            confidence=0.85,  # heuristic ceiling — see module docstring
            status=TrackingStatus.TRACKING.value,
        )

    def _update_blink_state(self, eyes_open: bool) -> bool:
        """
        Debounced blink detection: a blink is reported on the frame the
        eyes REOPEN after a short closure (1..max_blink_closed_frames).
        A closure longer than that is treated as "eyes closed", not a
        blink, and is not reported as one.
        """
        if not eyes_open:
            self._consecutive_closed_frames += 1
            return False

        was_closed_briefly = 0 < self._consecutive_closed_frames <= self.max_blink_closed_frames
        self._consecutive_closed_frames = 0
        return was_closed_briefly

    def _estimate_gaze(self, landmarks: Sequence[Landmark]):
        """
        Approximate gaze direction from iris position relative to eye
        corners/eyelids, averaged across both eyes. Returns
        (direction, is_centered). See module docstring for limitations.
        """
        h_ratio = self._avg_ratio(
            landmarks, _LEFT_EYE_H_IDX, _RIGHT_EYE_H_IDX, _LEFT_IRIS_CENTER_IDX, _RIGHT_IRIS_CENTER_IDX, axis="x"
        )
        v_ratio = self._avg_ratio(
            landmarks, _LEFT_EYE_V_IDX, _RIGHT_EYE_V_IDX, _LEFT_IRIS_CENTER_IDX, _RIGHT_IRIS_CENTER_IDX, axis="y"
        )

        if h_ratio is None or v_ratio is None:
            return None, False

        h_dev = h_ratio - 0.5
        v_dev = v_ratio - 0.5

        if abs(h_dev) <= self.gaze_center_tolerance and abs(v_dev) <= self.gaze_center_tolerance:
            return "center", True

        # Dominant axis wins to keep the label single-valued.
        if abs(h_dev) >= abs(v_dev):
            direction = "right" if h_dev > 0 else "left"
        else:
            direction = "down" if v_dev > 0 else "up"
        return direction, False

    # ------------------------------------------------------------------ #
    # Geometry helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _eye_aspect_ratio(landmarks: Sequence[Landmark], idx) -> float:
        """Classic EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)."""
        p1, p2, p3, p4, p5, p6 = (landmarks[i] for i in idx)

        def dist(a: Landmark, b: Landmark) -> float:
            return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

        horizontal = dist(p1, p4)
        if horizontal < 1e-6:
            return 1.0  # degenerate geometry -> assume open rather than divide by ~0
        return (dist(p2, p6) + dist(p3, p5)) / (2.0 * horizontal)

    @staticmethod
    def _avg_ratio(
        landmarks: Sequence[Landmark],
        left_pair,
        right_pair,
        left_iris_idx: int,
        right_iris_idx: int,
        axis: str,
    ) -> Optional[float]:
        """
        Normalized position of the iris between two reference landmarks
        (e.g. outer/inner corner for x, top/bottom lid for y), 0..1,
        averaged across both eyes.
        """
        def ratio(a_idx: int, b_idx: int, iris_idx: int) -> Optional[float]:
            a = getattr(landmarks[a_idx], axis)
            b = getattr(landmarks[b_idx], axis)
            iris = getattr(landmarks[iris_idx], axis)
            span = b - a
            if abs(span) < 1e-6:
                return None
            return (iris - a) / span

        left_ratio = ratio(left_pair[0], left_pair[1], left_iris_idx)
        right_ratio = ratio(right_pair[0], right_pair[1], right_iris_idx)

        valid = [r for r in (left_ratio, right_ratio) if r is not None]
        if not valid:
            return None
        return sum(valid) / len(valid)

    # ------------------------------------------------------------------ #
    # State management
    # ------------------------------------------------------------------ #
    def _reset_state(self) -> None:
        self._gaze_history.clear()
        self._consecutive_closed_frames = 0

    @staticmethod
    def _empty_result(status: str) -> EyeContactResult:
        return EyeContactResult(
            eye_contact=None,
            gaze_direction=None,
            blink_detected=False,
            eyes_open=None,
            confidence=0.0,
            status=status,
        )