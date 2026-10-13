"""
mediapipe_service.py

MediaPipe Face Landmarker wrapper (Tasks API, VIDEO running mode).

Responsibility: face landmark detection ONLY.
  - no webcam access
  - no identity, candidate locking, liveness, eye or head logic

Public interface (frozen):
    service = MediaPipeFaceService()
    service.initialize()                         # optional, loads model ONCE
    faces = service.detect_face(frame_rgb, ts)   # -> list[np.ndarray (478, 3)]
    service.close()

Each returned array holds normalized (x, y, z) landmarks of one face
(x, y in [0, 1] relative to the image that was passed in).
"""

from __future__ import annotations

import logging
import threading
import urllib.request
from pathlib import Path
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "face_landmarker.task"


class MediaPipeServiceError(RuntimeError):
    """Raised when the MediaPipe model cannot be prepared or loaded."""


class MediaPipeFaceService:
    def __init__(
        self,
        model_path: Optional[str] = None,
        max_faces: int = 10,
        min_detection_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        auto_download: bool = True,
    ) -> None:
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self.max_faces = int(max_faces)
        self.min_detection_confidence = min_detection_confidence
        self.min_presence_confidence = min_presence_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.auto_download = auto_download

        self._landmarker = None
        self._mp = None
        self._lock = threading.Lock()
        self._last_timestamp_ms = -1
        self.error_count = 0

    # ------------------------------------------------------------------ setup
    @property
    def is_initialized(self) -> bool:
        return self._landmarker is not None

    def _ensure_model_file(self) -> None:
        if self.model_path.exists() and self.model_path.stat().st_size > 0:
            return
        if not self.auto_download:
            raise MediaPipeServiceError(f"Face Landmarker model not found: {self.model_path}")
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.model_path.with_suffix(".part")
        logger.info("Downloading face_landmarker.task (one-time, ~4 MB)...")
        try:
            urllib.request.urlretrieve(MODEL_URL, tmp)
            tmp.replace(self.model_path)
        except Exception as exc:  # network / disk problems
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise MediaPipeServiceError(
                f"Could not download the model. Download it manually from {MODEL_URL} "
                f"and place it at {self.model_path}. Reason: {exc}"
            ) from exc

    def initialize(self) -> None:
        """Load the Face Landmarker once. Safe to call repeatedly."""
        with self._lock:
            if self._landmarker is not None:
                return
            self._ensure_model_file()
            try:
                import mediapipe as mp
                from mediapipe.tasks import python as mp_python
                from mediapipe.tasks.python import vision

                options = vision.FaceLandmarkerOptions(
                    base_options=mp_python.BaseOptions(
                        model_asset_path=str(self.model_path),
                        delegate=mp_python.BaseOptions.Delegate.CPU,
                    ),
                    running_mode=vision.RunningMode.VIDEO,
                    num_faces=self.max_faces,
                    min_face_detection_confidence=self.min_detection_confidence,
                    min_face_presence_confidence=self.min_presence_confidence,
                    min_tracking_confidence=self.min_tracking_confidence,
                    output_face_blendshapes=False,
                    output_facial_transformation_matrixes=False,
                )
                self._landmarker = vision.FaceLandmarker.create_from_options(options)
                self._mp = mp
            except Exception as exc:
                raise MediaPipeServiceError(f"Failed to initialize MediaPipe: {exc}") from exc
            logger.info("MediaPipe Face Landmarker ready (max_faces=%d)", self.max_faces)

    # -------------------------------------------------------------- inference
    def detect_face(self, frame_rgb: np.ndarray, timestamp_ms: int) -> List[np.ndarray]:
        """
        Detect landmarks for ALL faces in an RGB uint8 frame.

        Timestamps are forced to be strictly increasing (required by VIDEO mode).
        Returns [] on empty frames or on a recoverable runtime error.
        """
        if self._landmarker is None:
            self.initialize()
        if frame_rgb is None or frame_rgb.size == 0:
            return []

        with self._lock:
            ts = int(timestamp_ms)
            if ts <= self._last_timestamp_ms:
                ts = self._last_timestamp_ms + 1
            self._last_timestamp_ms = ts

            if frame_rgb.dtype != np.uint8 or not frame_rgb.flags["C_CONTIGUOUS"]:
                frame_rgb = np.ascontiguousarray(frame_rgb, dtype=np.uint8)

            try:
                mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=frame_rgb)
                result = self._landmarker.detect_for_video(mp_image, ts)
            except Exception as exc:
                self.error_count += 1
                if self.error_count <= 3 or self.error_count % 100 == 0:
                    logger.warning("MediaPipe detect failed (%d): %s", self.error_count, exc)
                return []

        faces: List[np.ndarray] = []
        for landmarks in result.face_landmarks or []:
            faces.append(
                np.array([(lm.x, lm.y, lm.z) for lm in landmarks], dtype=np.float32)
            )
        return faces

    # --------------------------------------------------------------- teardown
    def close(self) -> None:
        with self._lock:
            if self._landmarker is not None:
                try:
                    self._landmarker.close()
                except Exception as exc:
                    logger.debug("MediaPipe close error: %s", exc)
                self._landmarker = None
                self._mp = None

    def __enter__(self) -> "MediaPipeFaceService":
        self.initialize()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
