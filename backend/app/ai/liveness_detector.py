"""
liveness_detector.py

Lightweight, landmark-based liveness HEURISTIC.

IMPORTANT: this is NOT production-grade biometric anti-spoofing. It only looks for
signs of a live face in MediaPipe landmarks and can be fooled by a video replay,
a moving photo or a mask. It is meant to catch the simple case of a still photo
held up to the camera.

Evidence signals (2-of-3 rule by default):
  1. blink      - eye-aspect-ratio dips and recovers
  2. movement   - natural micro/macro motion of the nose relative to face width
  3. depth      - face-scale (size/depth) variation over the recent window

Liveness is NOT identity: it never identifies people, never selects or switches
candidates. The tracker feeds it only the selected/locked candidate's landmarks
and resets it when the candidate is lost. A LIVE verdict is valid for a limited
window and then expires unless it is re-established.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Dict, Optional, Tuple

import numpy as np


class LivenessStatus(str, Enum):
    UNKNOWN = "UNKNOWN"      # no data yet
    CHECKING = "CHECKING"    # collecting evidence
    LIVE = "LIVE"            # enough evidence, still inside validity window
    EXPIRED = "EXPIRED"      # was live, validity window elapsed


@dataclass(frozen=True)
class LivenessState:
    status: LivenessStatus = LivenessStatus.UNKNOWN
    score: float = 0.0                                   # active evidence / 3
    evidence: Dict[str, bool] = field(default_factory=dict)
    blink_count: int = 0
    valid_for_s: float = 0.0

    @property
    def is_live(self) -> bool:
        return self.status == LivenessStatus.LIVE


class LivenessDetector:
    # (p1 outer/inner corner, p2, p3 upper lid, p4 opposite corner, p5, p6 lower lid)
    _RIGHT_EYE = (33, 160, 158, 133, 153, 144)
    _LEFT_EYE = (362, 385, 387, 263, 373, 380)
    _NOSE_TIP, _FACE_LEFT, _FACE_RIGHT = 1, 234, 454

    def __init__(
        self,
        window_s: float = 4.0,
        validity_s: float = 15.0,
        required_evidence: int = 2,
        blink_ttl_s: float = 8.0,
        movement_threshold: float = 0.004,   # nose-position std / face width
        scale_threshold: float = 0.03,       # (max-min)/mean face width
        blink_ratio: float = 0.75,           # EAR < ratio * baseline => closed
        max_blink_frames: int = 10,
    ) -> None:
        self.window_s = window_s
        self.validity_s = validity_s
        self.required_evidence = required_evidence
        self.blink_ttl_s = blink_ttl_s
        self.movement_threshold = movement_threshold
        self.scale_threshold = scale_threshold
        self.blink_ratio = blink_ratio
        self.max_blink_frames = max_blink_frames
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        self._ear_hist: Deque[float] = deque(maxlen=100)
        self._samples: Deque[Tuple[float, float, float, float]] = deque()  # t, nx, ny, width
        self._closed_frames = 0
        self._last_blink_t: Optional[float] = None
        self._blink_count = 0
        self._live_until = 0.0
        self._was_live = False
        self._has_data = False
        self._last_evidence: Dict[str, bool] = {"blink": False, "movement": False, "depth": False}

    # ---------------------------------------------------------------- signals
    @staticmethod
    def _ear(pts: np.ndarray, idx: Tuple[int, ...]) -> float:
        p1, p2, p3, p4, p5, p6 = (pts[i] for i in idx)
        horiz = np.linalg.norm(p1 - p4) + 1e-6
        return float((np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / (2.0 * horiz))

    def _update_blink(self, ear: float, t: float) -> None:
        baseline = float(np.percentile(self._ear_hist, 80)) if len(self._ear_hist) >= 15 else None
        if baseline is None:
            self._ear_hist.append(ear)
            return
        if ear < self.blink_ratio * baseline:
            self._closed_frames += 1          # do not pollute the baseline while closed
            return
        if 1 <= self._closed_frames <= self.max_blink_frames:
            self._last_blink_t = t
            self._blink_count += 1
        self._closed_frames = 0
        self._ear_hist.append(ear)

    def _window_evidence(self) -> Tuple[bool, bool]:
        if len(self._samples) < 10:
            return False, False
        arr = np.array(self._samples, dtype=np.float32)
        movement = float(np.hypot(arr[:, 1].std(), arr[:, 2].std()))
        widths = arr[:, 3]
        scale = float((widths.max() - widths.min()) / (widths.mean() + 1e-6))
        return movement >= self.movement_threshold, scale >= self.scale_threshold

    # ----------------------------------------------------------------- public
    def update(self, landmarks: np.ndarray, timestamp_ms: float, aspect: float = 1.0) -> LivenessState:
        """Feed landmarks of the selected/locked candidate ONLY."""
        t = timestamp_ms / 1000.0
        self._has_data = True
        pts = landmarks[:, :2] * np.array([aspect, 1.0], dtype=np.float32)

        width = float(np.linalg.norm(pts[self._FACE_LEFT] - pts[self._FACE_RIGHT])) + 1e-6
        nose = pts[self._NOSE_TIP]
        self._samples.append((t, float(nose[0] / width), float(nose[1] / width), width))
        while self._samples and t - self._samples[0][0] > self.window_s:
            self._samples.popleft()

        ear = 0.5 * (self._ear(pts, self._RIGHT_EYE) + self._ear(pts, self._LEFT_EYE))
        self._update_blink(ear, t)

        movement, depth = self._window_evidence()
        blink = self._last_blink_t is not None and (t - self._last_blink_t) <= self.blink_ttl_s
        self._last_evidence = {"blink": blink, "movement": movement, "depth": depth}

        if sum(self._last_evidence.values()) >= self.required_evidence:
            self._live_until = t + self.validity_s
            self._was_live = True
        return self.state(timestamp_ms)

    def state(self, timestamp_ms: float) -> LivenessState:
        """Current verdict (also handles expiry when no new landmarks arrive)."""
        t = timestamp_ms / 1000.0
        if not self._has_data:
            return LivenessState()
        active = sum(self._last_evidence.values())
        if t < self._live_until:
            status = LivenessStatus.LIVE
        elif self._was_live:
            status = LivenessStatus.EXPIRED
        else:
            status = LivenessStatus.CHECKING
        return LivenessState(
            status=status,
            score=active / 3.0,
            evidence=dict(self._last_evidence),
            blink_count=self._blink_count,
            valid_for_s=max(0.0, self._live_until - t),
        )
