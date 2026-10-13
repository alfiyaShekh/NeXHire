"""
candidate_tracker.py

CandidateTracker is the single authority for candidate state.

Consumes MediaPipe landmarks (all faces) and manages selection, locking, identity
verification, liveness, loss/recovery and multi-face handling.

Hard rules enforced here:
  * never picks faces[0] blindly; a candidate is only selected when EXACTLY one
    face is visible
  * the locked identity never changes automatically; a different face is reported
    as DIFFERENT_PERSON_DETECTED and is never accepted
  * >= 2 faces -> MULTIPLE_FACES_DETECTED, downstream analysis blocked
  * InsightFace runs ON DEMAND in a dedicated single worker thread, never in the
    per-frame path (the AI loop only submits jobs and polls results)
  * liveness is only fed the selected/locked and verified candidate
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np

from .candidate_identity import (
    CandidateIdentity,
    CandidateIdentityManager,
    VerificationResult,
    crop_region,
)
from .liveness_detector import LivenessDetector, LivenessState

logger = logging.getLogger(__name__)

BBox = Tuple[float, float, float, float]


class CandidateStatus(str, Enum):
    WAITING_FOR_CANDIDATE = "WAITING_FOR_CANDIDATE"
    CANDIDATE_SELECTED = "CANDIDATE_SELECTED"
    CANDIDATE_LOCKED = "CANDIDATE_LOCKED"
    CANDIDATE_PRESENT = "CANDIDATE_PRESENT"
    CANDIDATE_NOT_DETECTED = "CANDIDATE_NOT_DETECTED"
    DIFFERENT_PERSON_DETECTED = "DIFFERENT_PERSON_DETECTED"
    MULTIPLE_FACES_DETECTED = "MULTIPLE_FACES_DETECTED"
    CANDIDATE_UNCERTAIN = "CANDIDATE_UNCERTAIN"


@dataclass
class TrackerConfig:
    grace_frames: int = 20             # AI frames without a face before NOT_DETECTED
    reverify_gap_frames: int = 6       # gap that forces identity re-verification
    selection_min_frames: int = 10     # stable single-face frames before sampling
    enroll_samples: int = 3
    enroll_interval_frames: int = 8
    min_face_width: float = 0.08       # normalized; smaller faces are ignored for selection
    reverify_interval_s: float = 6.0   # periodic soft re-verification
    verify_cooldown_s: float = 1.0
    bbox_iou_min: float = 0.15         # continuity guard between consecutive frames
    geometry_trigger: float = 0.30     # geometric change that triggers re-verification
    crop_margin: float = 0.35
    locked_banner_frames: int = 15     # frames CANDIDATE_LOCKED is shown before PRESENT
    auto_lock: bool = True             # False -> call request_lock() to lock deliberately
    require_liveness: bool = False     # gate analysis on LIVE status


@dataclass
class CandidateState:
    """Result object consumed by every downstream module."""
    status: CandidateStatus = CandidateStatus.WAITING_FOR_CANDIDATE
    face_count: int = 0
    locked: bool = False
    verified: bool = False
    analysis_allowed: bool = False      # True only for verified, locked, single candidate
    candidate_landmarks: Optional[np.ndarray] = None   # None unless analysis_allowed or selecting
    candidate_bbox: Optional[BBox] = None
    face_boxes: List[BBox] = field(default_factory=list)
    similarity: Optional[float] = None
    liveness: LivenessState = field(default_factory=LivenessState)
    enrollment_progress: float = 0.0
    missed_frames: int = 0
    message: str = ""
    timestamp_ms: int = 0


@dataclass
class _Job:
    kind: str                           # "enroll" | "verify"
    future: Future
    generation: int
    epoch: int
    geometry: Optional[np.ndarray] = None


def landmarks_bbox(landmarks: np.ndarray) -> BBox:
    xs, ys = landmarks[:, 0], landmarks[:, 1]
    return (
        float(np.clip(xs.min(), 0, 1)),
        float(np.clip(ys.min(), 0, 1)),
        float(np.clip(xs.max(), 0, 1)),
        float(np.clip(ys.max(), 0, 1)),
    )


def _iou(a: BBox, b: BBox) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 1e-9 else 0.0


class CandidateTracker:
    def __init__(
        self,
        identity_manager: Optional[CandidateIdentityManager] = None,
        liveness: Optional[LivenessDetector] = None,
        config: Optional[TrackerConfig] = None,
    ) -> None:
        self.identity = identity_manager or CandidateIdentityManager()
        self.liveness = liveness or LivenessDetector()
        self.cfg = config or TrackerConfig()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="identity")
        self._lock = threading.RLock()
        self._generation = 0
        self._lock_requested = False
        self._init_state()

    # ------------------------------------------------------------------ setup
    def warmup_async(self) -> None:
        """Preload InsightFace in the identity thread so the camera never waits for it."""
        self._executor.submit(self._safe_load)

    def _safe_load(self) -> None:
        try:
            self.identity.load()
        except Exception as exc:
            logger.error("InsightFace could not be loaded: %s", exc)

    def _init_state(self) -> None:
        self._identity: Optional[CandidateIdentity] = None
        self._locked_geometry: Optional[np.ndarray] = None
        self._status = CandidateStatus.WAITING_FOR_CANDIDATE
        self._verified = False
        self._different = False
        self._verify_due = False
        self._missed = 0
        self._epoch = 0
        self._frame_index = 0
        self._selection_frames = 0
        self._enroll_crops: List[np.ndarray] = []
        self._enroll_geo: List[np.ndarray] = []
        self._pending: Optional[_Job] = None
        self._last_bbox: Optional[BBox] = None
        self._last_submit_t = -1e9
        self._last_verified_t = 0.0
        self._last_similarity: Optional[float] = None
        self._locked_frames = 0
        self._message = ""

    def reset(self) -> None:
        """Explicit user reset: forget the locked identity and start over."""
        with self._lock:
            self._generation += 1            # invalidates in-flight identity jobs
            self._lock_requested = False
            self.liveness.reset()
            self._init_state()

    def request_lock(self) -> None:
        """Deliberate lock when auto_lock is False (still requires exactly one face)."""
        with self._lock:
            self._lock_requested = True

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    @property
    def is_locked(self) -> bool:
        return self._identity is not None

    # ----------------------------------------------------------------- update
    def update(self, frame_bgr: np.ndarray, faces: List[np.ndarray], timestamp_ms: int) -> CandidateState:
        """
        frame_bgr: full-resolution frame used only for on-demand identity crops.
        faces:     list of MediaPipe landmark arrays (all visible faces).
        """
        with self._lock:
            self._frame_index += 1
            h, w = frame_bgr.shape[:2]
            aspect = w / float(h)
            now = timestamp_ms / 1000.0
            n = len(faces)
            boxes = [landmarks_bbox(f) for f in faces]

            if n != 1:
                self._epoch += 1             # any face-count change invalidates pending jobs
            self._poll_job(now)

            if self._identity is None:
                state = self._update_unlocked(frame_bgr, faces, boxes, aspect, timestamp_ms)
            else:
                state = self._update_locked(frame_bgr, faces, boxes, aspect, timestamp_ms)
            return state

    # ---------------------------------------------------------- unlocked flow
    def _update_unlocked(self, frame, faces, boxes, aspect, ts) -> CandidateState:
        cfg, n = self.cfg, len(faces)
        now = ts / 1000.0

        if n == 0:
            self._clear_selection()
            self._status = CandidateStatus.WAITING_FOR_CANDIDATE
            self._message = "No face detected. Please sit in front of the camera."
            return self._build(n, None, None, boxes, ts)

        if n >= 2:
            self._clear_selection()
            self._status = CandidateStatus.MULTIPLE_FACES_DETECTED
            self._message = "Multiple faces detected. Only the candidate may be visible."
            return self._build(n, None, None, boxes, ts)

        face, bbox = faces[0], boxes[0]
        if bbox[2] - bbox[0] < cfg.min_face_width:
            self._clear_selection()
            self._status = CandidateStatus.WAITING_FOR_CANDIDATE
            self._message = "Please move closer to the camera."
            return self._build(n, None, bbox, boxes, ts)

        # exactly one usable face: candidate selection
        self._status = CandidateStatus.CANDIDATE_SELECTED
        self._message = "Candidate selected. Hold still while identity is created."
        self._selection_frames += 1
        self._last_bbox = bbox
        self.liveness.update(face, ts, aspect)

        if (
            self._pending is None
            and self._selection_frames >= cfg.selection_min_frames
            and len(self._enroll_crops) < cfg.enroll_samples
            and (self._selection_frames - cfg.selection_min_frames) % cfg.enroll_interval_frames == 0
        ):
            crop = crop_region(frame, bbox, cfg.crop_margin)
            if crop is not None:
                self._enroll_crops.append(crop)
                self._enroll_geo.append(CandidateIdentityManager.geometric_signature(face, aspect))

        if (
            self._pending is None
            and len(self._enroll_crops) >= cfg.enroll_samples
            and (cfg.auto_lock or self._lock_requested)
        ):
            self._pending = _Job(
                "enroll",
                self._executor.submit(self.identity.create_identity, list(self._enroll_crops)),
                self._generation,
                self._epoch,
                geometry=np.mean(self._enroll_geo, axis=0),
            )
            self._last_submit_t = now

        return self._build(n, face, bbox, boxes, ts)

    def _clear_selection(self) -> None:
        self._selection_frames = 0
        self._enroll_crops.clear()
        self._enroll_geo.clear()
        self._last_bbox = None
        self.liveness.reset()

    # ----------------------------------------------------------- locked flow
    def _update_locked(self, frame, faces, boxes, aspect, ts) -> CandidateState:
        cfg, n = self.cfg, len(faces)
        now = ts / 1000.0

        if n == 0:
            self._missed += 1
            self._different = False
            if self._missed >= cfg.reverify_gap_frames:
                self._verified = False
                self._verify_due = True
            if self._missed > cfg.grace_frames:
                if self._status != CandidateStatus.CANDIDATE_NOT_DETECTED:
                    self.liveness.reset()    # re-established after candidate loss
                self._status = CandidateStatus.CANDIDATE_NOT_DETECTED
                self._message = "Candidate not detected."
            else:
                self._status = CandidateStatus.CANDIDATE_UNCERTAIN
                self._message = "Candidate temporarily out of view..."
            return self._build(0, None, None, boxes, ts)

        if n >= 2:
            # cannot tell who is who without guessing -> block and require re-verification
            self._status = CandidateStatus.MULTIPLE_FACES_DETECTED
            self._message = "Multiple faces detected. Analysis paused."
            self._verified = False
            self._verify_due = True
            self._different = False
            self._missed = 0
            return self._build(n, None, None, boxes, ts)

        face, bbox = faces[0], boxes[0]
        self._missed = 0

        # cheap continuity checks that can only *request* verification
        if self._verified:
            if self._last_bbox is not None and _iou(bbox, self._last_bbox) < cfg.bbox_iou_min:
                self._verified, self._verify_due = False, True
            elif self._locked_geometry is not None:
                geo = CandidateIdentityManager.geometric_signature(face, aspect)
                if CandidateIdentityManager.geometric_distance(geo, self._locked_geometry) > cfg.geometry_trigger:
                    self._verify_due = True
            if now - self._last_verified_t > cfg.reverify_interval_s:
                self._verify_due = True      # soft periodic check, status unchanged until result
        self._last_bbox = bbox

        if self._verify_due and self._pending is None and now - self._last_submit_t >= cfg.verify_cooldown_s:
            crop = crop_region(frame, bbox, cfg.crop_margin)
            if crop is not None:
                self._pending = _Job(
                    "verify",
                    self._executor.submit(self.identity.verify, crop, self._identity),
                    self._generation,
                    self._epoch,
                )
                self._last_submit_t = now

        if self._verified:
            self._locked_frames += 1
            self.liveness.update(face, ts, aspect)
            if self._locked_frames <= cfg.locked_banner_frames:
                self._status = CandidateStatus.CANDIDATE_LOCKED
                self._message = "Candidate locked."
            else:
                self._status = CandidateStatus.CANDIDATE_PRESENT
                self._message = ""
        elif self._different:
            self._status = CandidateStatus.DIFFERENT_PERSON_DETECTED
            self._message = "A different person is in view. Analysis blocked."
        else:
            self._status = CandidateStatus.CANDIDATE_UNCERTAIN
            self._message = "Verifying candidate identity..."
        return self._build(1, face, bbox, boxes, ts)

    # ------------------------------------------------------------ job results
    def _poll_job(self, now: float) -> None:
        job = self._pending
        if job is None or not job.future.done():
            return
        self._pending = None
        try:
            result = job.future.result()
        except Exception as exc:
            logger.error("Identity job failed: %s", exc)
            result = None

        # stale result (reset, or face count changed since submission) -> discard
        if job.generation != self._generation or job.epoch != self._epoch:
            return

        if job.kind == "enroll":
            if isinstance(result, CandidateIdentity) and self._identity is None:
                self._identity = result
                self._locked_geometry = job.geometry
                self._verified, self._different, self._verify_due = True, False, False
                self._locked_frames, self._missed = 0, 0
                self._last_verified_t = now
                self._lock_requested = False
                logger.info("Candidate locked (%d samples)", result.num_samples)
            else:
                self._enroll_crops.clear()   # retry sampling
                self._enroll_geo.clear()
                self._selection_frames = 0
            return

        if isinstance(result, VerificationResult):
            if result.similarity is not None:
                self._last_similarity = result.similarity
            if result.matched:
                self._verified, self._different, self._verify_due = True, False, False
                self._last_verified_t = now
            elif result.status == "MISMATCH":
                self._verified, self._different, self._verify_due = False, True, True
            else:                            # NO_FACE / ERROR: stay unverified, retry later
                self._verified, self._verify_due = False, True

    # ----------------------------------------------------------- result build
    def _build(self, n, face, bbox, boxes, ts) -> CandidateState:
        locked = self._identity is not None
        allowed = locked and self._verified and n == 1 and self._status in (
            CandidateStatus.CANDIDATE_LOCKED,
            CandidateStatus.CANDIDATE_PRESENT,
        )
        live = self.liveness.state(ts)
        if allowed and self.cfg.require_liveness and not live.is_live:
            allowed = False
        progress = 1.0 if locked else min(1.0, len(self._enroll_crops) / float(self.cfg.enroll_samples))
        return CandidateState(
            status=self._status,
            face_count=n,
            locked=locked,
            verified=self._verified and n == 1,
            analysis_allowed=allowed,
            candidate_landmarks=face if (allowed or not locked) and n == 1 else None,
            candidate_bbox=bbox if n == 1 else None,
            face_boxes=list(boxes),
            similarity=self._last_similarity,
            liveness=live,
            enrollment_progress=progress,
            missed_frames=self._missed,
            message=self._message,
            timestamp_ms=ts,
        )
