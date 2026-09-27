"""
head_pose.py

Estimates head orientation (yaw / pitch / roll) for the LOCKED
CANDIDATE only, via solvePnP against a fixed set of facial landmarks.

Input contract: this module consumes a candidate_tracker.TrackerResult
(NOT a raw FrameResult) — face selection is fully delegated to
candidate_tracker.py / candidate_identity.py. It never looks at
frame_result.faces directly and never picks a face on its own.

LIMITATION (stated explicitly, per requirements):
    Without a calibrated camera (real focal length / lens distortion),
    the camera matrix used here is an approximation based on the
    frame's pixel dimensions. Absolute yaw/pitch/roll values are
    therefore estimates, not metrology-grade measurements — though
    they are stable enough to detect relative movement and classify
    coarse orientation states. Head pose alone does NOT prove liveness
    (a photo can be tilted); this module only supplies pose signals
    for liveness_detector.py to combine with other checks later.
"""

import logging
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Sequence, Tuple

import cv2
import numpy as np

from candidate_tracker import TrackerResult, TrackingStatus
from mediapipe_service import Landmark

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Classic 6-point head-pose landmark set (MediaPipe face-mesh indices)
# paired with a generic 3D face model (arbitrary units, roughly mm).
_POSE_LANDMARK_IDX = {
    "nose_tip": 1,
    "chin": 152,
    "left_eye_outer": 33,
    "right_eye_outer": 263,
    "left_mouth_corner": 61,
    "right_mouth_corner": 291,
}

_MODEL_POINTS_3D = np.array(
    [
        (0.0, 0.0, 0.0),        # nose tip
        (0.0, -330.0, -65.0),   # chin
        (-225.0, 170.0, -135.0),  # left eye outer corner
        (225.0, 170.0, -135.0),   # right eye outer corner
        (-150.0, -150.0, -125.0),  # left mouth corner
        (150.0, -150.0, -125.0),   # right mouth corner
    ],
    dtype=np.float64,
)

_MAX_LANDMARK_INDEX = max(_POSE_LANDMARK_IDX.values())

# The 3D model above uses a Y-up / Z-toward-camera convention (matching
# common head-pose-estimation references), while OpenCV's camera space
# is Y-down / Z-into-scene. A perfectly frontal face therefore does NOT
# solve to the identity rotation — it solves to a 180-degree rotation
# about the X axis. This fixed correction removes that baked-in offset
# so that "frontal" reliably decodes to yaw/pitch/roll near zero.
_FRONTAL_CORRECTION = np.diag([1.0, -1.0, -1.0])


@dataclass
class HeadPoseResult:
    yaw: Optional[float]     # degrees, +right / -left
    pitch: Optional[float]   # degrees, +up / -down (see _rotation_matrix_to_euler)
    roll: Optional[float]    # degrees, +clockwise tilt
    pose_status: str         # looking_forward | looking_left/right/up/down | tilted | unavailable
    confidence: float        # 0.0 (unavailable) .. 1.0
    status: str              # mirrors TrackingStatus, or "insufficient_landmarks" / "solve_failed"


class HeadPoseEstimator:
    """
    Usage:
        estimator = HeadPoseEstimator(frame_width=640, frame_height=480)
        result = estimator.analyze(tracker_result)  # from CandidateTracker.process()
    """

    def __init__(
        self,
        frame_width: int = 640,
        frame_height: int = 480,
        yaw_threshold_deg: float = 15.0,
        pitch_threshold_deg: float = 12.0,
        roll_threshold_deg: float = 15.0,
        smoothing_window: int = 5,
        max_reprojection_error_px: float = 15.0,
    ) -> None:
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.yaw_threshold_deg = yaw_threshold_deg
        self.pitch_threshold_deg = pitch_threshold_deg
        self.roll_threshold_deg = roll_threshold_deg
        self.max_reprojection_error_px = max_reprojection_error_px

        focal_length = float(frame_width)
        center = (frame_width / 2.0, frame_height / 2.0)
        self._camera_matrix = np.array(
            [
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1],
            ],
            dtype=np.float64,
        )
        self._dist_coeffs = np.zeros((4, 1), dtype=np.float64)  # assume no lens distortion

        self._yaw_history: Deque[float] = deque(maxlen=smoothing_window)
        self._pitch_history: Deque[float] = deque(maxlen=smoothing_window)
        self._roll_history: Deque[float] = deque(maxlen=smoothing_window)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def analyze(self, tracker_result: TrackerResult) -> HeadPoseResult:
        """
        Estimate head pose for the currently locked candidate.

        Gating rules (never analyze the wrong / an arbitrary person):
            - NOT_LOCKED / CANDIDATE_LOST -> unavailable, smoothing reset.
            - AMBIGUOUS -> identity not reliably resolved; unavailable,
              smoothing buffer preserved (no new sample appended).
            - REACQUIRING -> candidate not currently visible; unavailable,
              smoothing buffer preserved.
            - TRACKING -> compute from locked_candidate_landmarks.
        """
        status = tracker_result.tracking_status

        if status in (TrackingStatus.NOT_LOCKED, TrackingStatus.CANDIDATE_LOST):
            self._reset_state()
            return self._empty_result(status.value)

        if status in (TrackingStatus.AMBIGUOUS, TrackingStatus.REACQUIRING):
            # Don't fabricate a reading and don't pollute the smoothing
            # window with a guess; just report unavailable this frame.
            return self._empty_result(status.value)

        # status == TRACKING
        landmarks = tracker_result.locked_candidate_landmarks
        if not landmarks or len(landmarks) <= _MAX_LANDMARK_INDEX:
            logger.warning("Insufficient landmarks for head-pose analysis.")
            return self._empty_result("insufficient_landmarks")

        return self._compute(landmarks)

    # ------------------------------------------------------------------ #
    # Core computation (only reached for a confidently tracked candidate)
    # ------------------------------------------------------------------ #
    def _compute(self, landmarks: Sequence[Landmark]) -> HeadPoseResult:
        image_points = np.array(
            [
                self._pixel(landmarks[_POSE_LANDMARK_IDX["nose_tip"]]),
                self._pixel(landmarks[_POSE_LANDMARK_IDX["chin"]]),
                self._pixel(landmarks[_POSE_LANDMARK_IDX["left_eye_outer"]]),
                self._pixel(landmarks[_POSE_LANDMARK_IDX["right_eye_outer"]]),
                self._pixel(landmarks[_POSE_LANDMARK_IDX["left_mouth_corner"]]),
                self._pixel(landmarks[_POSE_LANDMARK_IDX["right_mouth_corner"]]),
            ],
            dtype=np.float64,
        )

        success, rotation_vec, translation_vec = cv2.solvePnP(
            _MODEL_POINTS_3D,
            image_points,
            self._camera_matrix,
            self._dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not success:
            logger.warning("solvePnP failed to converge for head pose.")
            return self._empty_result("solve_failed")

        rotation_matrix, _ = cv2.Rodrigues(rotation_vec)
        rotation_matrix = rotation_matrix @ _FRONTAL_CORRECTION
        raw_pitch, raw_yaw, raw_roll = self._rotation_matrix_to_euler(rotation_matrix)

        confidence = self._estimate_confidence(
            image_points, rotation_vec, translation_vec
        )

        self._yaw_history.append(raw_yaw)
        self._pitch_history.append(raw_pitch)
        self._roll_history.append(raw_roll)

        # Smoothed values are what drive classification, so a single
        # noisy frame cannot flip pose_status on its own.
        yaw = sum(self._yaw_history) / len(self._yaw_history)
        pitch = sum(self._pitch_history) / len(self._pitch_history)
        roll = sum(self._roll_history) / len(self._roll_history)

        pose_status = self._classify(yaw, pitch, roll)

        return HeadPoseResult(
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            pose_status=pose_status,
            confidence=confidence,
            status=TrackingStatus.TRACKING.value,
        )

    def _classify(self, yaw: float, pitch: float, roll: float) -> str:
        """Single dominant label; yaw/pitch take priority over roll tilt."""
        if abs(yaw) > self.yaw_threshold_deg:
            return "looking_right" if yaw > 0 else "looking_left"
        if abs(pitch) > self.pitch_threshold_deg:
            return "looking_up" if pitch > 0 else "looking_down"
        if abs(roll) > self.roll_threshold_deg:
            return "tilted"
        return "looking_forward"

    def _estimate_confidence(
        self,
        image_points: np.ndarray,
        rotation_vec: np.ndarray,
        translation_vec: np.ndarray,
    ) -> float:
        """Lower reprojection error -> higher confidence in the solved pose."""
        projected, _ = cv2.projectPoints(
            _MODEL_POINTS_3D, rotation_vec, translation_vec, self._camera_matrix, self._dist_coeffs
        )
        projected = projected.reshape(-1, 2)
        error = float(np.mean(np.linalg.norm(projected - image_points, axis=1)))
        confidence = 1.0 - min(error / self.max_reprojection_error_px, 1.0)
        return max(0.0, confidence)

    # ------------------------------------------------------------------ #
    # Geometry helpers
    # ------------------------------------------------------------------ #
    def _pixel(self, landmark: Landmark) -> Tuple[float, float]:
        return (landmark.x * self.frame_width, landmark.y * self.frame_height)

    @staticmethod
    def _rotation_matrix_to_euler(r: np.ndarray) -> Tuple[float, float, float]:
        """
        Decompose a rotation matrix into (pitch, yaw, roll) in degrees.
        Uses the standard X-Y-Z convention; falls back to a gimbal-lock
        safe branch when cos(pitch) ~ 0.
        """
        sy = (r[0, 0] ** 2 + r[1, 0] ** 2) ** 0.5
        singular = sy < 1e-6

        if not singular:
            pitch = np.arctan2(-r[2, 0], sy)
            yaw = np.arctan2(r[1, 0], r[0, 0])
            roll = np.arctan2(r[2, 1], r[2, 2])
        else:
            pitch = np.arctan2(-r[2, 0], sy)
            yaw = np.arctan2(-r[1, 2], r[1, 1])
            roll = 0.0

        return (np.degrees(pitch), np.degrees(yaw), np.degrees(roll))

    # ------------------------------------------------------------------ #
    # State management
    # ------------------------------------------------------------------ #
    def _reset_state(self) -> None:
        self._yaw_history.clear()
        self._pitch_history.clear()
        self._roll_history.clear()

    @staticmethod
    def _empty_result(status: str) -> HeadPoseResult:
        return HeadPoseResult(
            yaw=None,
            pitch=None,
            roll=None,
            pose_status="unavailable",
            confidence=0.0,
            status=status,
        )