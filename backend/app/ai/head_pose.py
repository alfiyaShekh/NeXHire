"""
head_pose.py

Head pose (yaw / pitch / roll in degrees) from MediaPipe landmarks that the core
pipeline already produced. No detector, no identity, no liveness, no camera.
Call it only for the verified/locked candidate (state.analysis_allowed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

# generic 3D face model (mm): nose tip, chin, image-left eye corner, image-right eye
# corner, image-left mouth corner, image-right mouth corner
_MODEL_POINTS = np.array(
    [
        (0.0, 0.0, 0.0),
        (0.0, -330.0, -65.0),
        (-225.0, 170.0, -135.0),
        (225.0, 170.0, -135.0),
        (-150.0, -150.0, -125.0),
        (150.0, -150.0, -125.0),
    ],
    dtype=np.float64,
)


@dataclass(frozen=True)
class HeadPoseResult:
    yaw: float = 0.0        # left/right (deg)
    pitch: float = 0.0      # up/down (deg)
    roll: float = 0.0       # tilt (deg)
    facing_camera: bool = False
    valid: bool = False


class HeadPoseEstimator:
    def __init__(self, max_yaw: float = 25.0, max_pitch: float = 20.0, smoothing: float = 0.5) -> None:
        self.max_yaw = max_yaw
        self.max_pitch = max_pitch
        self.smoothing = smoothing          # EMA weight of the new sample
        self.reset()

    def reset(self) -> None:
        self._smooth: Optional[np.ndarray] = None

    @staticmethod
    def _wrap(angle: float) -> float:
        angle = (angle + 180.0) % 360.0 - 180.0
        if angle > 90.0:
            angle -= 180.0
        elif angle < -90.0:
            angle += 180.0
        return angle

    def estimate(self, landmarks: np.ndarray, aspect: float = 16 / 9) -> HeadPoseResult:
        img_h = 1000.0
        img_w = img_h * aspect
        pts = landmarks[:, :2].astype(np.float64) * np.array([img_w, img_h])

        eye_a, eye_b = pts[33], pts[263]          # order by image x so left/right is consistent
        mouth_a, mouth_b = pts[61], pts[291]
        if eye_a[0] > eye_b[0]:
            eye_a, eye_b = eye_b, eye_a
        if mouth_a[0] > mouth_b[0]:
            mouth_a, mouth_b = mouth_b, mouth_a
        image_points = np.array([pts[1], pts[152], eye_a, eye_b, mouth_a, mouth_b], dtype=np.float64)

        cam = np.array([[img_w, 0, img_w / 2], [0, img_w, img_h / 2], [0, 0, 1]], dtype=np.float64)
        try:
            ok, rvec, _ = cv2.solvePnP(
                _MODEL_POINTS, image_points, cam, np.zeros((4, 1)), flags=cv2.SOLVEPNP_ITERATIVE
            )
            if not ok:
                return HeadPoseResult()
            rot, _ = cv2.Rodrigues(rvec)
            angles = cv2.RQDecomp3x3(rot)[0]
        except cv2.error:
            return HeadPoseResult()

        sample = np.array([self._wrap(angles[1]), self._wrap(angles[0]), self._wrap(angles[2])])
        if self._smooth is None:
            self._smooth = sample
        else:
            self._smooth = self.smoothing * sample + (1 - self.smoothing) * self._smooth
        yaw, pitch, roll = (float(v) for v in self._smooth)
        return HeadPoseResult(
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            facing_camera=abs(yaw) <= self.max_yaw and abs(pitch) <= self.max_pitch,
            valid=True,
        )
