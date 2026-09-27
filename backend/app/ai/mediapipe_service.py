"""
mediapipe_service.py

Wraps the MediaPipe Face Landmarker (Tasks API) to detect and return
landmark data for ALL faces visible in a frame supplied by
opencv_service.py. No identity/locking/tracking logic lives here —
that belongs in future candidate_identity.py / candidate_tracker.py.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class FaceLandmarkerError(Exception):
    """Raised on model load or inference failures."""


@dataclass
class Landmark:
    x: float
    y: float
    z: float


@dataclass
class FaceResult:
    """Structured landmark output for a single detected face."""
    face_index: int
    landmarks: List[Landmark]                       # 478 normalized landmarks
    blendshapes: Optional[List[dict]] = None         # [{category_name, score}, ...]
    transformation_matrix: Optional[np.ndarray] = None


@dataclass
class FrameResult:
    """Structured output for one processed frame (may contain many faces)."""
    frame_id: int
    timestamp_ms: int
    num_faces: int
    faces: List[FaceResult] = field(default_factory=list)


class MediaPipeService:
    """
    Runs MediaPipe's Face Landmarker on frames from OpenCVService.

    Usage:
        mp_service = MediaPipeService(model_path="models/face_landmarker.task")
        mp_service.load()
        result = mp_service.process(frame_data.frame, frame_data.frame_id)
        for face in result.faces:
            ...
        mp_service.close()
    """

    def __init__(
        self,
        model_path: str = "models/face_landmarker.task",
        num_faces: int = 5,
        min_face_detection_confidence: float = 0.5,
        min_face_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        output_face_blendshapes: bool = True,
        output_facial_transformation_matrixes: bool = False,
        running_mode: str = "VIDEO",  # "IMAGE" | "VIDEO" | "LIVE_STREAM"
    ) -> None:
        self.model_path = model_path
        self.num_faces = num_faces
        self.min_face_detection_confidence = min_face_detection_confidence
        self.min_face_presence_confidence = min_face_presence_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.output_face_blendshapes = output_face_blendshapes
        self.output_facial_transformation_matrixes = output_facial_transformation_matrixes
        self.running_mode = running_mode

        self._landmarker: Optional[mp_vision.FaceLandmarker] = None
        self._start_time_ms = int(time.time() * 1000)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def load(self) -> None:
        """Load the Face Landmarker model. Must be called before process()."""
        try:
            base_options = mp_python.BaseOptions(model_asset_path=self.model_path)

            mode_map = {
                "IMAGE": mp_vision.RunningMode.IMAGE,
                "VIDEO": mp_vision.RunningMode.VIDEO,
                "LIVE_STREAM": mp_vision.RunningMode.LIVE_STREAM,
            }
            if self.running_mode not in mode_map:
                raise FaceLandmarkerError(f"Invalid running_mode: {self.running_mode}")

            options = mp_vision.FaceLandmarkerOptions(
                base_options=base_options,
                running_mode=mode_map[self.running_mode],
                num_faces=self.num_faces,
                min_face_detection_confidence=self.min_face_detection_confidence,
                min_face_presence_confidence=self.min_face_presence_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                output_face_blendshapes=self.output_face_blendshapes,
                output_facial_transformation_matrixes=self.output_facial_transformation_matrixes,
            )
            self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)
            logger.info("Face Landmarker model loaded from %s", self.model_path)
        except Exception as e:
            raise FaceLandmarkerError(f"Failed to load model at {self.model_path}: {e}") from e

    def close(self) -> None:
        """Release the landmarker's resources."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
            logger.info("Face Landmarker closed.")

    def __enter__(self) -> "MediaPipeService":
        self.load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    @property
    def is_loaded(self) -> bool:
        return self._landmarker is not None

    # ------------------------------------------------------------------ #
    # Inference
    # ------------------------------------------------------------------ #
    def process(self, bgr_frame: np.ndarray, frame_id: int = 0) -> FrameResult:
        """
        Run face landmark detection on a single BGR frame (as produced
        by opencv_service.OpenCVService).

        Handles zero faces and multiple faces safely.
        """
        if not self.is_loaded or self._landmarker is None:
            raise FaceLandmarkerError("Model not loaded. Call load() first.")

        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        timestamp_ms = int(time.time() * 1000) - self._start_time_ms

        try:
            if self.running_mode == "IMAGE":
                detection_result = self._landmarker.detect(mp_image)
            elif self.running_mode == "VIDEO":
                detection_result = self._landmarker.detect_for_video(mp_image, timestamp_ms)
            else:
                raise FaceLandmarkerError(
                    "LIVE_STREAM mode requires detect_async() with a result callback; "
                    "use process_async() instead."
                )
        except Exception as e:
            logger.error("Inference failed on frame %s: %s", frame_id, e)
            return FrameResult(frame_id=frame_id, timestamp_ms=timestamp_ms, num_faces=0, faces=[])

        return self._to_frame_result(detection_result, frame_id, timestamp_ms)

    def process_async(self, bgr_frame: np.ndarray, frame_id: int = 0) -> None:
        """For LIVE_STREAM mode: submit a frame for async detection."""
        if not self.is_loaded or self._landmarker is None:
            raise FaceLandmarkerError("Model not loaded. Call load() first.")
        if self.running_mode != "LIVE_STREAM":
            raise FaceLandmarkerError("process_async() requires running_mode='LIVE_STREAM'.")

        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        timestamp_ms = int(time.time() * 1000) - self._start_time_ms
        self._landmarker.detect_async(mp_image, timestamp_ms)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _to_frame_result(self, detection_result, frame_id: int, timestamp_ms: int) -> FrameResult:
        faces: List[FaceResult] = []

        face_landmarks_list = detection_result.face_landmarks or []
        blendshapes_list = detection_result.face_blendshapes or []
        matrices_list = detection_result.facial_transformation_matrixes or []

        for idx, face_landmarks in enumerate(face_landmarks_list):
            landmarks = [Landmark(x=lm.x, y=lm.y, z=lm.z) for lm in face_landmarks]

            blendshapes = None
            if idx < len(blendshapes_list):
                blendshapes = [
                    {"category_name": bs.category_name, "score": bs.score}
                    for bs in blendshapes_list[idx]
                ]

            matrix = None
            if idx < len(matrices_list):
                matrix = np.array(matrices_list[idx])

            faces.append(
                FaceResult(
                    face_index=idx,
                    landmarks=landmarks,
                    blendshapes=blendshapes,
                    transformation_matrix=matrix,
                )
            )

        return FrameResult(
            frame_id=frame_id,
            timestamp_ms=timestamp_ms,
            num_faces=len(faces),
            faces=faces,
        )


# ---------------------------------------------------------------------- #
# Manual test / demo (requires opencv_service.py in the same folder)
# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    from opencv_service import OpenCVService, CameraError

    try:
        with OpenCVService(camera_index=0) as cam, MediaPipeService(
            model_path="models/face_landmarker.task", running_mode="VIDEO"
        ) as face_service:
            for frame_data in cam.stream():
                result = face_service.process(frame_data.frame, frame_data.frame_id)
                logger.info(
                    "Frame %s: %s face(s) detected", result.frame_id, result.num_faces
                )
                cv2.imshow("NexHire - MediaPipe Service Test", frame_data.frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except (CameraError, FaceLandmarkerError) as e:
        logger.error("Error: %s", e)
    finally:
        cv2.destroyAllWindows()