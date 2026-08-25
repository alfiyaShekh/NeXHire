"""
eye_contact.py

Advanced Eye Contact, Gaze Direction, Blink Detection, and Confidence Analysis
for the NexHire AI Interview Platform.

Key Features:
- Coordinate-Invariant 3D Iris Landmark Tracking (Left: 468, Right: 473)
- Accurate Left / Right / Up / Down / Center Gaze Direction Detection
- 6-Point Eye Aspect Ratio (EAR) for both eyes
- Debounced Blink Detector with Real-Time Blinks Per Minute (BPM)
- Dynamic Multi-factor Confidence Score & Focus Centrality
- Exponential Moving Average (EMA) smoothing for rock-solid stability
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Tuple


# ============================================================
# MEDIAPIPE FACE MESH INDICES (478 LANDMARKS MODEL)
# ============================================================

# Left eye 6-point EAR contour
# [outer_corner, upper_1, upper_2, inner_corner, lower_2, lower_1]
LEFT_EYE_CONTOUR = [33, 160, 158, 133, 153, 144]

# Right eye 6-point EAR contour
RIGHT_EYE_CONTOUR = [263, 385, 387, 362, 373, 380]

# Iris landmarks
LEFT_IRIS_CENTER = 468
RIGHT_IRIS_CENTER = 473

# Upper and Lower Eyelid Center for vertical gaze
LEFT_EYE_TOP = 159
LEFT_EYE_BOTTOM = 145
RIGHT_EYE_TOP = 386
RIGHT_EYE_BOTTOM = 374

# Eye corners
LEFT_EYE_INNER = 133
LEFT_EYE_OUTER = 33
RIGHT_EYE_INNER = 362
RIGHT_EYE_OUTER = 263


# ============================================================
# CALIBRATED THRESHOLDS & BOUNDS
# ============================================================

# Eye Aspect Ratio threshold for blink detection
EAR_BLINK_THRESHOLD = 0.19

# Frame counts for blink vs prolonged closure
MIN_BLINK_FRAMES = 1
MAX_BLINK_FRAMES = 16  # ~500ms at 30fps

# Gaze ratio bounds (Iris position in eye frame)
# Normalized from 0.0 (far left) to 1.0 (far right)
H_RATIO_LEFT_THRESH = 0.42    # < 0.42 means looking left
H_RATIO_RIGHT_THRESH = 0.58   # > 0.58 means looking right

# Normalized from 0.0 (top) to 1.0 (bottom)
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
    """
    looking_at_screen: bool
    score: float                # 0.0 to 1.0 (Gaze focus centrality)
    confidence: float           # 0.0 to 1.0 (Multi-factor overall confidence)
    status: str                 # Human readable status description
    gaze_direction: str         # "CENTER", "LEFT", "RIGHT", "UP", "DOWN", "UP-LEFT", "UP-RIGHT", "DOWN-LEFT", "DOWN-RIGHT", "BLINK", "EYES_CLOSED"
    blink_count: int            # Total blinks detected
    blink_rate_bpm: float       # Blinks per minute (rolling 60s)
    ear_avg: float              # Average EAR
    ear_left: float             # Left eye EAR
    ear_right: float            # Right eye EAR
    horizontal_ratio: float     # 0.0 (left) to 1.0 (right), 0.5 = center
    vertical_ratio: float       # 0.0 (top) to 1.0 (bottom), 0.5 = center
    is_blinking: bool           # True if eyes are currently closed

    def __repr__(self) -> str:
        return (
            f"EyeContactResult("
            f"looking_at_screen={self.looking_at_screen}, "
            f"gaze='{self.gaze_direction}', "
            f"score={self.score:.2f}, "
            f"confidence={self.confidence:.2f}, "
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


def _calculate_ear(landmarks, contour_indices: List[int]) -> float:
    """
    Compute Eye Aspect Ratio (EAR) using standard 6-point formulation:
    EAR = (|p2 - p6| + |p3 - p5|) / (2 * |p1 - p4|)
    """
    try:
        p1 = landmarks[contour_indices[0]]  # Corner 1
        p2 = landmarks[contour_indices[1]]  # Top 1
        p3 = landmarks[contour_indices[2]]  # Top 2
        p4 = landmarks[contour_indices[3]]  # Corner 2
        p5 = landmarks[contour_indices[4]]  # Bottom 2
        p6 = landmarks[contour_indices[5]]  # Bottom 1

        v1 = _distance_2d(p2, p6)
        v2 = _distance_2d(p3, p5)
        h = _distance_2d(p1, p4)

        if h < 1e-6:
            return 0.0

        return (v1 + v2) / (2.0 * h)
    except (IndexError, TypeError):
        return 0.0


def _calculate_gaze_ratios(
    landmarks
) -> Tuple[float, float]:
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

        # --- Left Eye Horizontal Ratio (Normalized to image coordinates) ---
        l_x_min = min(l_inner.x, l_outer.x)
        l_x_max = max(l_inner.x, l_outer.x)
        l_w = max(1e-6, l_x_max - l_x_min)
        l_h_ratio = (l_iris.x - l_x_min) / l_w

        # --- Right Eye Horizontal Ratio (Normalized to image coordinates) ---
        r_x_min = min(r_inner.x, r_outer.x)
        r_x_max = max(r_inner.x, r_outer.x)
        r_w = max(1e-6, r_x_max - r_x_min)
        r_h_ratio = (r_iris.x - r_x_min) / r_w

        # Combined Horizontal Ratio
        h_ratio = max(0.0, min(1.0, (l_h_ratio + r_h_ratio) / 2.0))

        # --- Vertical Ratio (Normalized to image coordinates) ---
        l_y_min = min(l_top.y, l_bot.y)
        l_y_max = max(l_top.y, l_bot.y)
        l_h = max(1e-6, l_y_max - l_y_min)
        l_v_ratio = (l_iris.y - l_y_min) / l_h

        r_y_min = min(r_top.y, r_bot.y)
        r_y_max = max(r_top.y, r_bot.y)
        r_h = max(1e-6, r_y_max - r_y_min)
        r_v_ratio = (r_iris.y - r_y_min) / r_h

        # Combined Vertical Ratio
        v_ratio = max(0.0, min(1.0, (l_v_ratio + r_v_ratio) / 2.0))

        return h_ratio, v_ratio

    except (IndexError, TypeError, AttributeError):
        return 0.50, 0.50


# ============================================================
# STATEFUL EYE TRACKER CLASS
# ============================================================

class EyeTracker:
    """
    Maintains temporal state for blink counting, blink rate (BPM),
    smoothed gaze tracking, and dynamic multi-factor confidence scoring.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all counters and tracking history."""
        self.blink_count: int = 0
        self.consecutive_closed_frames: int = 0
        self.blink_timestamps = deque(maxlen=200)

        # Smoothed values for jitter reduction
        self.smooth_h_ratio: float = 0.50
        self.smooth_v_ratio: float = 0.50
        self.smooth_ear: float = 0.28
        self.smooth_confidence: float = 1.0

        self.last_frame_time: float = time.time()

    def process(self, candidate_landmarks) -> Optional[EyeContactResult]:
        """
        Analyze a frame of MediaPipe candidate landmarks.
        """
        if candidate_landmarks is None or len(candidate_landmarks) < 468:
            return None

        current_time = time.time()

        # ----------------------------------------------------
        # 1. Eye Aspect Ratio (EAR)
        # ----------------------------------------------------
        ear_left = _calculate_ear(candidate_landmarks, LEFT_EYE_CONTOUR)
        ear_right = _calculate_ear(candidate_landmarks, RIGHT_EYE_CONTOUR)
        ear_avg = (ear_left + ear_right) / 2.0

        # Exponential moving average for EAR
        self.smooth_ear = (
            SMOOTHING_ALPHA * ear_avg +
            (1.0 - SMOOTHING_ALPHA) * self.smooth_ear
        )

        # ----------------------------------------------------
        # 2. Blink Detection State Machine
        # ----------------------------------------------------
        is_closed = ear_avg < EAR_BLINK_THRESHOLD
        is_blinking = False

        if is_closed:
            self.consecutive_closed_frames += 1
            if self.consecutive_closed_frames <= MAX_BLINK_FRAMES:
                is_blinking = True
        else:
            # Check if this frame marks the end of a valid blink
            if (
                MIN_BLINK_FRAMES <=
                self.consecutive_closed_frames <=
                MAX_BLINK_FRAMES
            ):
                self.blink_count += 1
                self.blink_timestamps.append(current_time)

            self.consecutive_closed_frames = 0

        # Compute rolling Blinks Per Minute (BPM) over last 60 seconds
        cutoff_time = current_time - 60.0
        while (
            self.blink_timestamps and
            self.blink_timestamps[0] < cutoff_time
        ):
            self.blink_timestamps.popleft()

        recent_blinks = len(self.blink_timestamps)
        blink_rate_bpm = float(recent_blinks)

        # ----------------------------------------------------
        # 3. Iris & Gaze Direction
        # ----------------------------------------------------
        raw_h_ratio, raw_v_ratio = _calculate_gaze_ratios(
            candidate_landmarks
        )

        # Smooth gaze ratios
        self.smooth_h_ratio = (
            SMOOTHING_ALPHA * raw_h_ratio +
            (1.0 - SMOOTHING_ALPHA) * self.smooth_h_ratio
        )
        self.smooth_v_ratio = (
            SMOOTHING_ALPHA * raw_v_ratio +
            (1.0 - SMOOTHING_ALPHA) * self.smooth_v_ratio
        )

        # Classify gaze direction with combined 2D quadrant classification
        if is_closed and self.consecutive_closed_frames > MAX_BLINK_FRAMES:
            gaze_direction = "EYES_CLOSED"
            looking_at_screen = False
            status = "Eyes Closed"
        elif is_blinking:
            gaze_direction = "BLINK"
            looking_at_screen = True  # Natural blink during attention
            status = "Blinking"
        else:
            # Horizontal state
            is_left = self.smooth_h_ratio < H_RATIO_LEFT_THRESH
            is_right = self.smooth_h_ratio > H_RATIO_RIGHT_THRESH

            # Vertical state
            is_up = self.smooth_v_ratio < V_RATIO_UP_THRESH
            is_down = self.smooth_v_ratio > V_RATIO_DOWN_THRESH

            if is_up and is_left:
                gaze_direction = "UP-LEFT"
                looking_at_screen = False
                status = "Looking Up-Left"
            elif is_up and is_right:
                gaze_direction = "UP-RIGHT"
                looking_at_screen = False
                status = "Looking Up-Right"
            elif is_down and is_left:
                gaze_direction = "DOWN-LEFT"
                looking_at_screen = False
                status = "Looking Down-Left"
            elif is_down and is_right:
                gaze_direction = "DOWN-RIGHT"
                looking_at_screen = False
                status = "Looking Down-Right"
            elif is_up:
                gaze_direction = "UP"
                looking_at_screen = False
                status = "Looking Up"
            elif is_down:
                gaze_direction = "DOWN"
                looking_at_screen = False
                status = "Looking Down"
            elif is_left:
                gaze_direction = "LEFT"
                looking_at_screen = False
                status = "Looking Left"
            elif is_right:
                gaze_direction = "RIGHT"
                looking_at_screen = False
                status = "Looking Right"
            else:
                gaze_direction = "CENTER"
                looking_at_screen = True
                status = "Looking at Screen"

        # ----------------------------------------------------
        # 4. Multi-Factor Confidence & Eye Contact Score
        # ----------------------------------------------------
        # Factor A: Gaze Centrality (0.0 to 1.0)
        h_dev = abs(self.smooth_h_ratio - 0.50)
        v_dev = abs(self.smooth_v_ratio - 0.50)
        gaze_centrality = max(0.0, 1.0 - (h_dev * 3.2 + v_dev * 2.5))

        # Factor B: Eye Openness Stability
        openness_score = min(1.0, max(0.0, (ear_avg - 0.12) / 0.18))

        # Factor C: Left/Right Eye Symmetry
        symmetry_diff = abs(ear_left - ear_right)
        symmetry_score = max(0.0, 1.0 - (symmetry_diff / 0.08))

        # Factor D: Blink Regularity Score (10 - 26 BPM optimal)
        if blink_rate_bpm == 0:
            blink_score = 0.90
        elif 10.0 <= blink_rate_bpm <= 26.0:
            blink_score = 1.00
        else:
            blink_score = max(0.40, 1.0 - abs(blink_rate_bpm - 18.0) / 25.0)

        # Weighted combined confidence score
        raw_confidence = (
            0.45 * gaze_centrality +
            0.25 * openness_score +
            0.15 * symmetry_score +
            0.15 * blink_score
        )

        if not looking_at_screen and gaze_direction != "BLINK":
            # Penalize confidence when actively looking away
            raw_confidence *= 0.50

        # Smooth confidence score
        self.smooth_confidence = (
            SMOOTHING_ALPHA * raw_confidence +
            (1.0 - SMOOTHING_ALPHA) * self.smooth_confidence
        )

        # Primary Eye Contact Score (0.0 to 1.0)
        eye_contact_score = round(gaze_centrality, 2)
        final_confidence = round(max(0.0, min(1.0, self.smooth_confidence)), 2)

        return EyeContactResult(
            looking_at_screen=looking_at_screen,
            score=eye_contact_score,
            confidence=final_confidence,
            status=status,
            gaze_direction=gaze_direction,
            blink_count=self.blink_count,
            blink_rate_bpm=round(blink_rate_bpm, 1),
            ear_avg=round(ear_avg, 3),
            ear_left=round(ear_left, 3),
            ear_right=round(ear_right, 3),
            horizontal_ratio=round(self.smooth_h_ratio, 3),
            vertical_ratio=round(self.smooth_v_ratio, 3),
            is_blinking=is_blinking
        )


# ============================================================
# GLOBAL INSTANCE & MODULE ENTRY POINT
# ============================================================

_global_eye_tracker = EyeTracker()


def analyze_eye_contact(
    candidate_landmarks
) -> Optional[EyeContactResult]:
    """
    Main entry point for evaluating eye contact from MediaPipe landmarks.
    """
    return _global_eye_tracker.process(candidate_landmarks)


def reset_eye_tracking():
    """Reset the global eye tracking history and blink counter."""
    _global_eye_tracker.reset()