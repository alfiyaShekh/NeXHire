"""
eye_contact.py

Analyzes eye direction using MediaPipe face landmarks.

IMPORTANT:
This module does NOT:
    - open the webcam
    - read frames
    - run MediaPipe
    - identify the candidate

It receives the already-verified candidate landmarks from
candidate_tracker.py.
"""

from typing import Optional


# ============================================================
# MEDIAPIPE LANDMARK INDICES
# ============================================================

# Left eye landmarks
LEFT_EYE = [
    33,
    133,
    159,
    145,
    160,
    144,
    158,
    153
]

# Right eye landmarks
RIGHT_EYE = [
    362,
    263,
    386,
    374,
    387,
    373,
    385,
    380
]


# ============================================================
# RESULT
# ============================================================

class EyeContactResult:

    def __init__(
        self,
        looking_at_screen: bool,
        score: float,
        status: str
    ):

        self.looking_at_screen = looking_at_screen

        self.score = score

        self.status = status

    def __repr__(self):

        return (
            f"EyeContactResult("
            f"looking_at_screen={self.looking_at_screen}, "
            f"score={self.score:.2f}, "
            f"status='{self.status}')"
        )


# ============================================================
# MAIN FUNCTION
# ============================================================

def analyze_eye_contact(
    candidate_landmarks
) -> Optional[EyeContactResult]:
    """
    Analyze eye contact for the verified candidate.

    Parameters
    ----------
    candidate_landmarks:
        MediaPipe landmarks belonging ONLY to the locked
        candidate.

    Returns
    -------
    EyeContactResult or None
    """

    if candidate_landmarks is None:

        return None

    if len(candidate_landmarks) == 0:

        return None

    # --------------------------------------------------------
    # For the first implementation we determine whether the
    # eyes are sufficiently open and approximately centered.
    #
    # We will improve gaze estimation after confirming that
    # landmark data is flowing correctly.
    # --------------------------------------------------------

    left_eye = _get_landmarks(
        candidate_landmarks,
        LEFT_EYE
    )

    right_eye = _get_landmarks(
        candidate_landmarks,
        RIGHT_EYE
    )

    if left_eye is None or right_eye is None:

        return EyeContactResult(
            looking_at_screen=False,
            score=0.0,
            status="Eyes not detected"
        )

    # --------------------------------------------------------
    # Calculate eye openness.
    # --------------------------------------------------------

    left_openness = _eye_openness(
        left_eye
    )

    right_openness = _eye_openness(
        right_eye
    )

    average_openness = (
        left_openness +
        right_openness
    ) / 2.0

    # --------------------------------------------------------
    # Simple initial threshold.
    #
    # This is NOT the final gaze algorithm.
    # It is used to verify the complete data pipeline first.
    # --------------------------------------------------------

    if average_openness < 0.015:

        return EyeContactResult(
            looking_at_screen=False,
            score=0.0,
            status="Eyes closed"
        )

    return EyeContactResult(
        looking_at_screen=True,
        score=min(
            average_openness * 20.0,
            1.0
        ),
        status="Looking at screen"
    )


# ============================================================
# GET LANDMARKS
# ============================================================

def _get_landmarks(
    candidate_landmarks,
    indices
):

    try:

        return [
            candidate_landmarks[index]
            for index in indices
        ]

    except (IndexError, TypeError):

        return None


# ============================================================
# DISTANCE
# ============================================================

def _distance(point_a, point_b):

    dx = (
        point_a.x -
        point_b.x
    )

    dy = (
        point_a.y -
        point_b.y
    )

    return (
        dx * dx +
        dy * dy
    ) ** 0.5


# ============================================================
# EYE OPENNESS
# ============================================================

def _eye_openness(
    eye
):

    if len(eye) < 6:

        return 0.0

    # Vertical eye distances
    vertical_1 = _distance(
        eye[2],
        eye[4]
    )

    vertical_2 = _distance(
        eye[3],
        eye[5]
    )

    # Horizontal eye distance
    horizontal = _distance(
        eye[0],
        eye[1]
    )

    if horizontal == 0:

        return 0.0

    return (
        vertical_1 +
        vertical_2
    ) / (
        2.0 *
        horizontal
    )