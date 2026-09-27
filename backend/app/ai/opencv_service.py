"""
opencv_service.py

Handles webcam access and frame acquisition for NexHire.
Provides a clean, reusable interface that downstream modules
(e.g. mediapipe_service.py) can consume without knowing anything
about OpenCV internals.
"""

import logging
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class CameraError(Exception):
    """Raised when the camera cannot be opened or read from."""


@dataclass
class FrameData:
    """Container for a single captured frame and its metadata."""
    frame: np.ndarray          # BGR frame (OpenCV default)
    frame_id: int              # monotonically increasing frame counter
    timestamp_ms: float        # capture timestamp in milliseconds
    width: int
    height: int


class OpenCVService:
    """
    Wraps cv2.VideoCapture to provide continuous, pre-processed frames.

    Usage:
        with OpenCVService(camera_index=0) as cam:
            for frame_data in cam.stream():
                ...  # pass frame_data.frame to mediapipe_service
    """

    def __init__(
        self,
        camera_index: int = 0,
        target_width: Optional[int] = 640,
        target_height: Optional[int] = 480,
        flip_horizontal: bool = True,
        backend: int = cv2.CAP_ANY,
    ) -> None:
        self.camera_index = camera_index
        self.target_width = target_width
        self.target_height = target_height
        self.flip_horizontal = flip_horizontal
        self.backend = backend

        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_counter: int = 0
        self._is_open: bool = False

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def open(self) -> None:
        """Open the camera and validate that it is usable."""
        self._cap = cv2.VideoCapture(self.camera_index, self.backend)

        if not self._cap.isOpened():
            self._cap.release()
            self._cap = None
            raise CameraError(
                f"Unable to open camera at index {self.camera_index}. "
                "Check that it is connected and not in use by another app."
            )

        if self.target_width:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
        if self.target_height:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)

        # Sanity check: try one read to confirm the stream actually works.
        ok, _ = self._cap.read()
        if not ok:
            self.release()
            raise CameraError(
                f"Camera at index {self.camera_index} opened but returned no frames."
            )

        self._frame_counter = 0
        self._is_open = True
        logger.info("Camera %s opened successfully.", self.camera_index)

    def release(self) -> None:
        """Release the camera resource safely."""
        if self._cap is not None:
            self._cap.release()
        self._cap = None
        self._is_open = False
        logger.info("Camera %s released.", self.camera_index)

    def __enter__(self) -> "OpenCVService":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

    @property
    def is_open(self) -> bool:
        return self._is_open and self._cap is not None and self._cap.isOpened()

    # ------------------------------------------------------------------ #
    # Frame acquisition
    # ------------------------------------------------------------------ #
    def read_frame(self) -> Optional[FrameData]:
        """
        Read a single processed frame.
        Returns None if the read failed (e.g. camera disconnected).
        """
        if not self.is_open or self._cap is None:
            raise CameraError("Camera is not open. Call open() first.")

        ok, frame = self._cap.read()
        if not ok or frame is None:
            logger.warning("Failed to read frame from camera %s.", self.camera_index)
            return None

        frame = self._process_frame(frame)
        h, w = frame.shape[:2]
        timestamp_ms = self._cap.get(cv2.CAP_PROP_POS_MSEC)
        self._frame_counter += 1

        return FrameData(
            frame=frame,
            frame_id=self._frame_counter,
            timestamp_ms=timestamp_ms,
            width=w,
            height=h,
        )

    def stream(self) -> Iterator[FrameData]:
        """
        Continuously yield frames until the camera stops working
        or is released. Caller controls when to break the loop.
        """
        while self.is_open:
            frame_data = self.read_frame()
            if frame_data is None:
                break
            yield frame_data

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Apply standard pre-processing: flip + resize."""
        if self.flip_horizontal:
            frame = cv2.flip(frame, 1)

        if self.target_width and self.target_height:
            h, w = frame.shape[:2]
            if (w, h) != (self.target_width, self.target_height):
                frame = cv2.resize(
                    frame,
                    (self.target_width, self.target_height),
                    interpolation=cv2.INTER_LINEAR,
                )
        return frame

    def get_resolution(self) -> Tuple[int, int]:
        if not self.is_open or self._cap is None:
            raise CameraError("Camera is not open.")
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return w, h


# ---------------------------------------------------------------------- #
# Manual test / demo
# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    try:
        with OpenCVService(camera_index=0) as cam:
            logger.info("Resolution: %s", cam.get_resolution())
            for fd in cam.stream():
                cv2.imshow("NexHire - OpenCV Service Test", fd.frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except CameraError as e:
        logger.error("Camera error: %s", e)
    finally:
        cv2.destroyAllWindows()