import os
import mediapipe as mp


# ============================================================
# MODEL PATH
# ============================================================

MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "face_landmarker.task"
)


# ============================================================
# MEDIAPIPE SETUP
# ============================================================

BaseOptions = mp.tasks.BaseOptions

FaceLandmarker = mp.tasks.vision.FaceLandmarker

FaceLandmarkerOptions = (
    mp.tasks.vision.FaceLandmarkerOptions
)

VisionRunningMode = (
    mp.tasks.vision.RunningMode
)


# ============================================================
# FACE LANDMARKER OPTIONS
# ============================================================

options = FaceLandmarkerOptions(
    base_options=BaseOptions(
        model_asset_path=MODEL_PATH
    ),
    running_mode=VisionRunningMode.VIDEO,
    num_faces=1
)


# ============================================================
# CREATE MEDIAPIPE LANDMARKER
# ============================================================

landmarker = FaceLandmarker.create_from_options(
    options
)


# ============================================================
# FACE DETECTION FUNCTION
# ============================================================

def detect_face(rgb_frame, timestamp):
    """
    Receive an RGB frame from OpenCV
    and detect facial landmarks using MediaPipe.
    """

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )

    results = landmarker.detect_for_video(
        mp_image,
        timestamp
    )

    return results.face_landmarks


if __name__ == "__main__":
    try:
        from app.ai.opencv_service import run_face_detection
    except ImportError:
        from opencv_service import run_face_detection

    run_face_detection()