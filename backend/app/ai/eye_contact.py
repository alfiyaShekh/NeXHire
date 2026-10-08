"""
eye_contact.py
===============

Advanced Eye Contact, Gaze Direction, Blink Detection, and Confidence Analysis
for the NexHire AI Interview Platform.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Sequence, Tuple, Any

logger = logging.getLogger("nexhire.eye_contact")


# ============================================================
# MEDIAPIPE FACE MESH INDICES (478 LANDMARKS MODEL)
# ============================================================

# 6-point EAR contours: [outer_corner, upper_1, upper_2, inner_corner, lower_2, lower_1]
LEFT_EYE_CONTOUR = (33, 160, 158, 133, 153, 144)
RIGHT_EYE_CONTOUR = (263, 385, 387, 362, 373, 380)

# Iris center landmarks (Points 468 & 473)
LEFT_IRIS_CENTER = 468
RIGHT_IRIS_CENTER = 473

# Upper and Lower Eyelid Centers for vertical gaze
LEFT_EYE_TOP = 159
LEFT_EYE_BOTTOM = 145
RIGHT_EYE_TOP = 386
RIGHT_EYE_BOTTOM = 374

# Eye corner landmarks
LEFT_EYE_INNER = 133
LEFT_EYE_OUTER = 33
RIGHT_EYE_INNER = 362
RIGHT_EYE_OUTER = 263

_MAX_LANDMARK_INDEX = 477


# ============================================================
# CALIBRATED THRESHOLDS & BOUNDS
# ============================================================

# Eye Aspect Ratio threshold below which eyes are considered closed
EAR_BLINK_THRESHOLD = 0.19

# Frame count limits for natural blink vs prolonged closure
MIN_BLINK_FRAMES = 1
MAX_BLINK_FRAMES = 16  # ~500ms at 30fps

# Iris position bounds: 0.0 (far left/top) to 1.0 (far right/bottom)
H_RATIO_LEFT_THRESH = 0.42    # < 0.42 means looking left
H_RATIO_RIGHT_THRESH = 0.58   # > 0.58 means looking right

V_RATIO_UP_THRESH = 0.38      # < 0.38 means looking up
V_RATIO_DOWN_THRESH = 0.62    # > 0.62 means looking down

# Smoothing factor for Exponential Moving Average (0 < alpha <= 1)
SMOOTHING_ALPHA = 0.40


# ============================================================
# RESULT DATA STRUCTURE
# ============================================================

@dataclass
class EyeContactResult:
    """
    Structured outcome of the eye contact and gaze analysis.
    Supports both boolean checks and rich telemetry metrics.
    """
    eye_contact: Optional[bool]     # Primary flag: True if looking at screen
    looking_at_screen: bool         # Alias for eye_contact
    score: float                    # 0.0 to 1.0 (Gaze focus centrality)
    confidence: float               # 0.0 to 1.0 (Multi-factor overall confidence)
    status: str                     # Human readable status description
    gaze_direction: Optional[str]   # "CENTER", "UP-LEFT", "LEFT", "BLINK", etc.
    blink_detected: bool            # True on the single frame a blink finishes
    is_blinking: bool               # True if eyes are currently closed during a blink
    blink_count: int = 0            # Cumulative blinks
    blink_rate_bpm: float = 0.0     # Blinks per minute (rolling 60s)
    ear_avg: float = 0.0            # Average EAR across both eyes
    ear_left: float = 0.0           # Left eye EAR
    ear_right: float = 0.0          # Right eye EAR
    horizontal_ratio: float = 0.50  # 0.0 (left) to 1.0 (right), 0.5 = center
    vertical_ratio: float = 0.50    # 0.0 (top) to 1.0 (bottom), 0.5 = center
    eyes_open: Optional[bool] = None

    def __repr__(self) -> str:
        return (
            f"EyeContactResult("
            f"eye_contact={self.eye_contact}, "
            f"gaze='{self.gaze_direction}', "
            f"score={self.score:.2f}, "
            f"conf={self.confidence:.2f}, "
            f"blinks={self.blink_count}, "
            f"bpm={self.blink_rate_bpm:.1f}, "
            f"status='{self.status}')"
        )


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _distance_2d(p1, p2) -> float:
    """Calculate 2D Euclidean distance between two MediaPipe landmarks."""
    dx = p1.x - p2.x
    dy = p1.y - p2.y
    return (dx * dx + dy * dy) ** 0.5


def _calculate_ear(landmarks: Sequence[Any], contour_indices: Sequence[int]) -> float:
    """
    Compute Eye Aspect Ratio (EAR) using standard 6-point formulation:
    EAR = (|p2 - p6| + |p3 - p5|) / (2 * |p1 - p4|)
    """
    try:
        p1 = landmarks[contour_indices[0]]  # Outer corner
        p2 = landmarks[contour_indices[1]]  # Top 1
        p3 = landmarks[contour_indices[2]]  # Top 2
        p4 = landmarks[contour_indices[3]]  # Inner corner
        p5 = landmarks[contour_indices[4]]  # Bottom 2
        p6 = landmarks[contour_indices[5]]  # Bottom 1

        v1 = _distance_2d(p2, p6)
        v2 = _distance_2d(p3, p5)
        h = _distance_2d(p1, p4)

        if h < 1e-6:
            return 0.0

        return (v1 + v2) / (2.0 * h)
    except (IndexError, TypeError, AttributeError):
        return 0.0


def _calculate_gaze_ratios(landmarks: Sequence[Any]) -> Tuple[float, float]:
    """
    Compute coordinate-invariant horizontal and vertical iris position ratios.
    Returns: (h_ratio, v_ratio)
    h_ratio: 0.0 (Far Left) -> 0.5 (Center) -> 1.0 (Far Right) in image space
    v_ratio: 0.0 (Far Up)   -> 0.5 (Center) -> 1.0 (Far Down) in image space
    """
    try:
        # Left Eye Landmarks
        l_iris = landmarks[LEFT_IRIS_CENTER]
        l_inner = landmarks[LEFT_EYE_INNER]
        l_outer = landmarks[LEFT_EYE_OUTER]
        l_top = landmarks[LEFT_EYE_TOP]
        l_bot = landmarks[LEFT_EYE_BOTTOM]

        # Right Eye Landmarks
        r_iris = landmarks[RIGHT_IRIS_CENTER]
        r_inner = landmarks[RIGHT_EYE_INNER]
        r_outer = landmarks[RIGHT_EYE_OUTER]
        r_top = landmarks[RIGHT_EYE_TOP]
        r_bot = landmarks[RIGHT_EYE_BOTTOM]

        # Left Eye Horizontal Ratio
        l_x_min = min(l_inner.x, l_outer.x)
        l_x_max = max(l_inner.x, l_outer.x)
        l_w = max(1e-6, l_x_max - l_x_min)
        l_h_ratio = (l_iris.x - l_x_min) / l_w

        # Right Eye Horizontal Ratio
        r_x_min = min(r_inner.x, r_outer.x)
        r_x_max = max(r_inner.x, r_outer.x)
        r_w = max(1e-6, r_x_max - r_x_min)
        r_h_ratio = (r_iris.x - r_x_min) / r_w

        h_ratio = max(0.0, min(1.0, (l_h_ratio + r_h_ratio) / 2.0))

        # Vertical Ratio
        l_y_min = min(l_top.y, l_bot.y)
        l_y_max = max(l_top.y, l_bot.y)
        l_h = max(1e-6, l_y_max - l_y_min)
        l_v_ratio = (l_iris.y - l_y_min) / l_h

        r_y_min = min(r_top.y, r_bot.y)
        r_y_max = max(r_top.y, r_bot.y)
        r_h = max(1e-6, r_y_max - r_y_min)
        r_v_ratio = (r_iris.y - r_y_min) / r_h

        v_ratio = max(0.0, min(1.0, (l_v_ratio + r_v_ratio) / 2.0))

        return h_ratio, v_ratio

    except (IndexError, TypeError, AttributeError):
        return 0.50, 0.50


# ============================================================
# STATEFUL EYE ANALYZER CLASS
# ============================================================

class EyeContactAnalyzer:
    """
    Maintains temporal state for:
      - Exponential Moving Average (EMA) smoothing of gaze and EAR
      - Debounced blink detection & Blinks Per Minute (BPM)
      - Multi-factor confidence & Focus Centrality %
    """

    def __init__(
        self,
        ear_closed_threshold: float = EAR_BLINK_THRESHOLD,
        smoothing_alpha: float = SMOOTHING_ALPHA,
    ) -> None:
        self.ear_closed_threshold = ear_closed_threshold
        self.smoothing_alpha = smoothing_alpha
        self.reset()

    def reset(self) -> None:
        """Reset all counters and tracking history."""
        self.blink_count: int = 0
        self.consecutive_closed_frames: int = 0
        self.blink_timestamps: Deque[float] = deque(maxlen=200)

        # Smoothed values for jitter reduction
        self.smooth_h_ratio: float = 0.50
        self.smooth_v_ratio: float = 0.50
        self.smooth_ear: float = 0.28
        self.smooth_confidence: float = 1.0

    def analyze(self, tracker_result_or_landmarks: Any) -> EyeContactResult:
        """
        Main analysis method. Accepts either:
          1. TrackerResult object (from candidate_tracker.py)
          2. Raw list/sequence of MediaPipe Landmarks
        """
        landmarks = None
        status = "tracking"

        # Case 1: TrackerResult object passed
        if hasattr(tracker_result_or_landmarks, "tracking_status"):
            tracking_status = getattr(tracker_result_or_landmarks, "tracking_status")
            status_val = getattr(tracking_status, "value", str(tracking_status)).lower()

            if status_val in ("not_locked", "candidate_lost"):
                self.reset()
                return self._empty_result(status_val)

            if status_val in ("ambiguous", "reacquiring"):
                return self._empty_result(status_val)

            landmarks = getattr(tracker_result_or_landmarks, "locked_candidate_landmarks", None)
        # Case 2: Direct list/sequence of landmarks passed
        elif isinstance(tracker_result_or_landmarks, (list, tuple)):
            landmarks = tracker_result_or_landmarks

        if not landmarks or len(landmarks) <= _MAX_LANDMARK_INDEX:
            return self._empty_result("insufficient_landmarks")

        return self._compute(landmarks, status)

    def _empty_result(self, status: str) -> EyeContactResult:
        return EyeContactResult(
            eye_contact=None,
            looking_at_screen=False,
            score=0.0,
            confidence=0.0,
            status=status,
            gaze_direction=None,
            blink_detected=False,
            is_blinking=False,
            blink_count=self.blink_count,
            blink_rate_bpm=0.0,
            ear_avg=0.0,
            ear_left=0.0,
            ear_right=0.0,
            horizontal_ratio=0.50,
            vertical_ratio=0.50,
            eyes_open=None,
        )

    def _compute(self, landmarks: Sequence[Any], status: str) -> EyeContactResult:
        current_time = time.time()

        # 1. Eye Aspect Ratio (EAR)
        ear_left = _calculate_ear(landmarks, LEFT_EYE_CONTOUR)
        ear_right = _calculate_ear(landmarks, RIGHT_EYE_CONTOUR)
        ear_avg = (ear_left + ear_right) / 2.0

        self.smooth_ear = (
            self.smoothing_alpha * ear_avg +
            (1.0 - self.smoothing_alpha) * self.smooth_ear
        )

        # 2. Blink Detection State Machine
        is_closed = ear_avg < self.ear_closed_threshold
        is_blinking = False
        blink_detected = False

        if is_closed:
            self.consecutive_closed_frames += 1
            if self.consecutive_closed_frames <= MAX_BLINK_FRAMES:
                is_blinking = True
        else:
            if MIN_BLINK_FRAMES <= self.consecutive_closed_frames <= MAX_BLINK_FRAMES:
                self.blink_count += 1
                self.blink_timestamps.append(current_time)
                blink_detected = True
            self.consecutive_closed_frames = 0

        # Rolling Blinks Per Minute (BPM) over 60 seconds
        cutoff_time = current_time - 60.0
        while self.blink_timestamps and self.blink_timestamps[0] < cutoff_time:
            self.blink_timestamps.popleft()

        blink_rate_bpm = float(len(self.blink_timestamps))

        # 3. Iris & 8-Way Gaze Direction
        raw_h, raw_v = _calculate_gaze_ratios(landmarks)

        self.smooth_h_ratio = (
            self.smoothing_alpha * raw_h +
            (1.0 - self.smoothing_alpha) * self.smooth_h_ratio
        )
        self.smooth_v_ratio = (
            self.smoothing_alpha * raw_v +
            (1.0 - self.smoothing_alpha) * self.smooth_v_ratio
        )

        if is_closed and self.consecutive_closed_frames > MAX_BLINK_FRAMES:
            gaze_direction = "EYES_CLOSED"
            looking_at_screen = False
            status_desc = "Eyes Closed"
        elif is_blinking:
            gaze_direction = "BLINK"
            looking_at_screen = True  # Natural blink during attention
            status_desc = "Blinking"
        else:
            is_left = self.smooth_h_ratio < H_RATIO_LEFT_THRESH
            is_right = self.smooth_h_ratio > H_RATIO_RIGHT_THRESH
            is_up = self.smooth_v_ratio < V_RATIO_UP_THRESH
            is_down = self.smooth_v_ratio > V_RATIO_DOWN_THRESH

            if is_up and is_left:
                gaze_direction = "UP-LEFT"
                looking_at_screen = False
                status_desc = "Looking Up-Left"
            elif is_up and is_right:
                gaze_direction = "UP-RIGHT"
                looking_at_screen = False
                status_desc = "Looking Up-Right"
            elif is_down and is_left:
                gaze_direction = "DOWN-LEFT"
                looking_at_screen = False
                status_desc = "Looking Down-Left"
            elif is_down and is_right:
                gaze_direction = "DOWN-RIGHT"
                looking_at_screen = False
                status_desc = "Looking Down-Right"
            elif is_up:
                gaze_direction = "UP"
                looking_at_screen = False
                status_desc = "Looking Up"
            elif is_down:
                gaze_direction = "DOWN"
                looking_at_screen = False
                status_desc = "Looking Down"
            elif is_left:
                gaze_direction = "LEFT"
                looking_at_screen = False
                status_desc = "Looking Left"
            elif is_right:
                gaze_direction = "RIGHT"
                looking_at_screen = False
                status_desc = "Looking Right"
            else:
                gaze_direction = "CENTER"
                looking_at_screen = True
                status_desc = "Looking at Screen"

        # 4. Multi-Factor Confidence & Focus Centrality
        h_dev = abs(self.smooth_h_ratio - 0.50)
        v_dev = abs(self.smooth_v_ratio - 0.50)
        gaze_centrality = max(0.0, 1.0 - (h_dev * 3.2 + v_dev * 2.5))

        openness_score = min(1.0, max(0.0, (ear_avg - 0.12) / 0.18))
        symmetry_diff = abs(ear_left - ear_right)
        symmetry_score = max(0.0, 1.0 - (symmetry_diff / 0.08))

        if blink_rate_bpm == 0:
            blink_score = 0.90
        elif 10.0 <= blink_rate_bpm <= 26.0:
            blink_score = 1.00
        else:
            blink_score = max(0.40, 1.0 - abs(blink_rate_bpm - 18.0) / 25.0)

        raw_confidence = (
            0.45 * gaze_centrality +
            0.25 * openness_score +
            0.15 * symmetry_score +
            0.15 * blink_score
        )

        if not looking_at_screen and gaze_direction != "BLINK":
            raw_confidence *= 0.50

        self.smooth_confidence = (
            self.smoothing_alpha * raw_confidence +
            (1.0 - self.smoothing_alpha) * self.smooth_confidence
        )

        return EyeContactResult(
            eye_contact=looking_at_screen,
            looking_at_screen=looking_at_screen,
            score=round(gaze_centrality, 2),
            confidence=round(max(0.0, min(1.0, self.smooth_confidence)), 2),
            status=status_desc,
            gaze_direction=gaze_direction,
            blink_detected=blink_detected,
            is_blinking=is_blinking,
            blink_count=self.blink_count,
            blink_rate_bpm=round(blink_rate_bpm, 1),
            ear_avg=round(ear_avg, 3),
            ear_left=round(ear_left, 3),
            ear_right=round(ear_right, 3),
            horizontal_ratio=round(self.smooth_h_ratio, 3),
            vertical_ratio=round(self.smooth_v_ratio, 3),
            eyes_open=not is_closed,
        )


# ============================================================
# MODULE LEVEL CONVENIENCE FUNCTIONS
# ============================================================

_global_eye_analyzer = EyeContactAnalyzer()

def analyze_eye_contact(candidate_landmarks: Any) -> EyeContactResult:
    """Direct entry point for evaluating eye contact."""
    return _global_eye_analyzer.analyze(candidate_landmarks)

def reset_eye_tracking() -> None:
    """Reset the global analyzer state."""
    _global_eye_analyzer.reset()
