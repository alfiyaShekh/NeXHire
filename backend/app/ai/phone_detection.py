"""
phone_detection.py

Detects mobile phones ("cell phone") visible in a raw OpenCV BGR frame,
independently of face tracking / candidate identity / liveness.

MODEL ASSUMPTION (stated explicitly, per requirements):
    This module expects an Ultralytics YOLO model (the `ultralytics`
    pip package). The default model_path "yolov8n.pt" is Ultralytics'
    small, COCO-pretrained checkpoint, which already includes a
    "cell phone" class (COCO class id 67) — no custom training or
    local model file is required for basic use. Ultralytics will
    auto-download that checkpoint on first use if it isn't already
    cached locally. No local model path is invented here; if you have
    your own weights (e.g. fine-tuned for phones specifically), pass
    that file's path as model_path instead.

LIMITATION:
    This is standard object detection, not a guarantee. It can miss
    partially occluded or unusual-angle phones, and — like any object
    detector — is not claimed to be perfectly accurate. Confidence
    thresholds are configurable so callers can tune precision/recall.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# COCO label(s) considered a "phone". Matched case-insensitively against
# whatever label strings the loaded model reports.
_PHONE_LABELS = {"cell phone", "mobile phone", "phone"}


class PhoneDetectionError(Exception):
    """Raised on model load or inference failures."""


@dataclass
class PhoneDetection:
    label: str
    confidence: float
    bounding_box: Tuple[int, int, int, int]  # (x1, y1, x2, y2) in pixel coords


@dataclass
class PhoneDetectionResult:
    phone_detected: bool
    detections: List[PhoneDetection] = field(default_factory=list)
    confidence: Optional[float] = None          # max confidence among phone detections
    bounding_boxes: List[Tuple[int, int, int, int]] = field(default_factory=list)
    status: str = "ok"                          # "ok" | "invalid_frame" | "not_loaded" | "error"


class PhoneDetector:
    """
    Usage:
        detector = PhoneDetector(model_path="yolov8n.pt", confidence_threshold=0.5)
        detector.load()
        result = detector.detect(bgr_frame)   # bgr_frame from opencv_service.py
        detector.close()

    This module does not touch candidate identity/tracking and does not
    use its results to identify who the candidate is.
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.5,
        target_labels=_PHONE_LABELS,
    ) -> None:
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.target_labels = {label.lower() for label in target_labels}

        self._model = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def load(self) -> None:
        """Load the YOLO model. Must be called before detect()."""
        try:
            from ultralytics import YOLO  # imported lazily: no hard dependency at module import time
        except ImportError as e:
            raise PhoneDetectionError(
                "The 'ultralytics' package is required for phone detection. "
                "Install it with: pip install ultralytics"
            ) from e

        try:
            self._model = YOLO(self.model_path)
        except Exception as e:
            raise PhoneDetectionError(
                f"Failed to load YOLO model '{self.model_path}': {e}"
            ) from e

        logger.info("Phone detection model loaded: %s", self.model_path)

    def close(self) -> None:
        self._model = None

    def __enter__(self) -> "PhoneDetector":
        self.load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    # ------------------------------------------------------------------ #
    # Detection
    # ------------------------------------------------------------------ #
    def detect(self, bgr_frame: Optional[np.ndarray]) -> PhoneDetectionResult:
        """
        Run phone detection on a single BGR frame (as produced by
        opencv_service.OpenCVService). Never raises on a bad/missing
        frame or an inference error — always returns a safe result.
        """
        if bgr_frame is None or bgr_frame.size == 0:
            logger.warning("Phone detection received an empty/invalid frame.")
            return PhoneDetectionResult(phone_detected=False, status="invalid_frame")

        if not self.is_loaded or self._model is None:
            raise PhoneDetectionError("Model not loaded. Call load() first.")

        try:
            results = self._model.predict(
                source=bgr_frame, conf=self.confidence_threshold, verbose=False
            )
        except Exception as e:
            logger.error("Phone detection inference failed: %s", e)
            return PhoneDetectionResult(phone_detected=False, status="error")

        detections = self._extract_phone_detections(results)
        bounding_boxes = [d.bounding_box for d in detections]
        max_confidence = max((d.confidence for d in detections), default=None)

        return PhoneDetectionResult(
            phone_detected=len(detections) > 0,
            detections=detections,
            confidence=max_confidence,
            bounding_boxes=bounding_boxes,
            status="ok",
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _extract_phone_detections(self, results) -> List[PhoneDetection]:
        detections: List[PhoneDetection] = []
        if not results:
            return detections

        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return detections

        names = getattr(result, "names", {}) or {}

        for box in boxes:
            try:
                cls_id = int(box.cls[0])
                confidence = float(box.conf[0])
                label = str(names.get(cls_id, f"class_{cls_id}"))
            except (IndexError, TypeError, ValueError):
                continue

            if label.lower() not in self.target_labels:
                continue
            if confidence < self.confidence_threshold:
                continue

            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            detections.append(
                PhoneDetection(
                    label=label,
                    confidence=confidence,
                    bounding_box=(x1, y1, x2, y2),
                )
            )

        return detections


# ---------------------------------------------------------------------- #
# Manual test / demo
# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    import cv2

    from opencv_service import CameraError, OpenCVService

    try:
        with OpenCVService(camera_index=0) as cam, PhoneDetector(
            model_path="yolov8n.pt", confidence_threshold=0.5
        ) as detector:
            for frame_data in cam.stream():
                result = detector.detect(frame_data.frame)
                if result.phone_detected:
                    logger.info(
                        "Phone detected: confidence=%.2f boxes=%s",
                        result.confidence, result.bounding_boxes,
                    )
                cv2.imshow("NexHire - Phone Detection Test", frame_data.frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except (CameraError, PhoneDetectionError) as e:
        logger.error("Error: %s", e)
    finally:
        cv2.destroyAllWindows()