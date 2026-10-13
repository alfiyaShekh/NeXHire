"""
candidate_identity.py

Identity ONLY. No liveness, no tracking state, no camera, no MediaPipe.

  - InsightFace buffalo_l, CPUExecutionProvider, loaded ONCE (lazy) and kept in memory
  - embeddings are generated ON DEMAND (candidate creation / re-verification)
  - cosine similarity matching
  - cheap geometric signature helper (landmark ratios) used by the tracker as a
    free "something changed" trigger, never as a final identity decision

Scope note: this is a session-local "is it still the same person" check for a mock
interview, not a general-purpose biometric recognition system.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------- types
@dataclass
class CandidateIdentity:
    embedding: np.ndarray            # L2-normalized, shape (512,)
    num_samples: int
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class VerificationResult:
    status: str                      # MATCH | MISMATCH | NO_FACE | ERROR
    similarity: Optional[float] = None

    @property
    def matched(self) -> bool:
        return self.status == "MATCH"

    @property
    def conclusive(self) -> bool:
        return self.status in ("MATCH", "MISMATCH")


# ------------------------------------------------------------------- helpers
def crop_region(
    frame_bgr: np.ndarray,
    bbox_norm: Tuple[float, float, float, float],
    margin: float = 0.35,
    min_size: int = 48,
) -> Optional[np.ndarray]:
    """Crop a (copied) region around a normalized bbox with a relative margin."""
    h, w = frame_bgr.shape[:2]
    x1, y1, x2, y2 = bbox_norm
    bw, bh = (x2 - x1) * w, (y2 - y1) * h
    px1 = int(max(0, x1 * w - bw * margin))
    py1 = int(max(0, y1 * h - bh * margin))
    px2 = int(min(w, x2 * w + bw * margin))
    py2 = int(min(h, y2 * h + bh * margin))
    if px2 - px1 < min_size or py2 - py1 < min_size:
        return None
    return frame_bgr[py1:py2, px1:px2].copy()


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    return (vec / norm).astype(np.float32) if norm > 1e-9 else vec.astype(np.float32)


# ------------------------------------------------------------------- manager
class CandidateIdentityManager:
    def __init__(
        self,
        model_name: str = "buffalo_l",
        det_size: Tuple[int, int] = (320, 320),
        match_threshold: float = 0.40,
        enroll_consistency: float = 0.50,
        min_det_score: float = 0.5,
    ) -> None:
        self.model_name = model_name
        self.det_size = det_size
        self.match_threshold = match_threshold
        self.enroll_consistency = enroll_consistency
        self.min_det_score = min_det_score

        self._app = None
        self._load_lock = threading.Lock()
        self._infer_lock = threading.Lock()

    # ------------------------------------------------------------- model load
    @property
    def is_loaded(self) -> bool:
        return self._app is not None

    def load(self) -> None:
        """Load InsightFace once. Idempotent and thread-safe."""
        if self._app is not None:
            return
        with self._load_lock:
            if self._app is not None:
                return
            t0 = time.perf_counter()
            from insightface.app import FaceAnalysis  # lazy import (heavy)

            app = FaceAnalysis(
                name=self.model_name,
                providers=["CPUExecutionProvider"],
                allowed_modules=["detection", "recognition"],  # skip landmarks/genderage
            )
            app.prepare(ctx_id=-1, det_size=self.det_size)
            self._app = app
            logger.info("InsightFace %s loaded in %.1fs", self.model_name, time.perf_counter() - t0)

    # -------------------------------------------------------------- embedding
    def generate_embedding(self, face_image_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        Embedding of the largest face found in a face crop (BGR).
        Returns None if no face is found or inference fails.
        """
        if face_image_bgr is None or face_image_bgr.size == 0:
            return None
        self.load()
        try:
            with self._infer_lock:
                faces = self._app.get(face_image_bgr)
        except Exception as exc:
            logger.warning("InsightFace inference failed: %s", exc)
            return None
        faces = [f for f in faces if float(getattr(f, "det_score", 1.0)) >= self.min_det_score]
        if not faces:
            return None
        best = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        emb = getattr(best, "normed_embedding", None)
        if emb is None:
            emb = getattr(best, "embedding", None)
        if emb is None:
            return None
        return _normalize(np.asarray(emb, dtype=np.float32))

    # --------------------------------------------------------------- identity
    def create_identity(self, face_images_bgr: Sequence[np.ndarray]) -> Optional[CandidateIdentity]:
        """Average several crops into one identity. Rejects inconsistent samples."""
        embeddings: List[np.ndarray] = []
        for img in face_images_bgr:
            emb = self.generate_embedding(img)
            if emb is not None:
                embeddings.append(emb)
        if len(embeddings) < 2:
            return None

        mean = _normalize(np.mean(embeddings, axis=0))
        if min(self.compare(e, mean) for e in embeddings) < self.enroll_consistency:
            logger.info("Enrollment rejected: samples are not consistent")
            return None
        return CandidateIdentity(embedding=mean, num_samples=len(embeddings))

    @staticmethod
    def compare(emb_a: np.ndarray, emb_b: np.ndarray) -> float:
        """Cosine similarity of two embeddings."""
        denom = float(np.linalg.norm(emb_a) * np.linalg.norm(emb_b))
        return float(np.dot(emb_a, emb_b) / denom) if denom > 1e-9 else 0.0

    def match(self, embedding: np.ndarray, identity: CandidateIdentity) -> Tuple[bool, float]:
        sim = self.compare(embedding, identity.embedding)
        return sim >= self.match_threshold, sim

    def verify(self, face_image_bgr: np.ndarray, identity: CandidateIdentity) -> VerificationResult:
        """Verify a face crop against the LOCKED identity (on-demand)."""
        try:
            emb = self.generate_embedding(face_image_bgr)
        except Exception as exc:  # e.g. insightface not installed
            logger.error("Identity verification error: %s", exc)
            return VerificationResult("ERROR")
        if emb is None:
            return VerificationResult("NO_FACE")
        matched, sim = self.match(emb, identity)
        return VerificationResult("MATCH" if matched else "MISMATCH", sim)

    # ------------------------------------------------- geometric signature
    _SIG_PAIRS = ((168, 1), (1, 13), (61, 291), (10, 152), (133, 362), (13, 152))

    @staticmethod
    def geometric_signature(landmarks: np.ndarray, aspect: float = 1.0) -> np.ndarray:
        """Facial proportion ratios (scaled by inter-ocular distance). Very cheap."""
        pts = landmarks[:, :2] * np.array([aspect, 1.0], dtype=np.float32)
        iod = float(np.linalg.norm(pts[33] - pts[263])) + 1e-6
        return np.array(
            [np.linalg.norm(pts[a] - pts[b]) / iod for a, b in CandidateIdentityManager._SIG_PAIRS],
            dtype=np.float32,
        )

    @staticmethod
    def geometric_distance(sig_a: np.ndarray, sig_b: np.ndarray) -> float:
        """Mean relative difference between two signatures (0 = identical)."""
        return float(np.mean(np.abs(sig_a - sig_b) / (np.abs(sig_b) + 1e-6)))
