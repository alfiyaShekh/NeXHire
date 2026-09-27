"""
candidate_identity.py

Owns the decision of WHO the candidate is for this interview session.
This module is intentionally narrow:
    - It decides whether/when a candidate may be locked.
    - It stores a reference "signature" for the locked candidate.
    - It answers "does this face plausibly match the locked candidate?"

LIMITATION (by design, stated explicitly per requirements):
    The signature used here is a normalized facial-geometry descriptor
    derived from MediaPipe Face Landmarker points (relative distances
    between stable landmarks, scaled by inter-ocular distance). This is
    a lightweight heuristic, NOT a trained biometric face-recognition
    embedding (e.g. FaceNet/ArcFace). Two different people can produce
    similar geometric ratios, and the same person can drift in the
    descriptor under extreme pose/expression changes. Geometric
    similarity alone is therefore never treated as proof of identity —
    it is only ever used as a heuristic gate, and callers (see
    candidate_tracker.py) must treat inconclusive matches as
    "ambiguous", not as confirmed re-identification. For production-
    grade re-acquisition after long absences, integrate a real face
    recognition model; this module deliberately does not claim to
    provide that.
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

from mediapipe_service import FaceResult, FrameResult, Landmark

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Stable landmark indices (MediaPipe Face Landmarker / 478-point mesh):
# left eye outer, right eye outer, left eye inner, right eye inner,
# nose tip, left mouth corner, right mouth corner, chin.
_SIGNATURE_LANDMARK_INDICES: Tuple[int, ...] = (33, 263, 133, 362, 1, 61, 291, 152)
_LEFT_EYE_OUTER = 33
_RIGHT_EYE_OUTER = 263


class IdentityError(Exception):
    """Raised on invalid identity operations (e.g. lock with bad state)."""


@dataclass
class MatchResult:
    """Result of comparing a live face against the locked reference."""
    distance: float          # lower = more similar (geometric heuristic only)
    is_match: bool           # distance below threshold
    is_biometric_proof: bool = False  # always False here; see module docstring


class CandidateIdentityManager:
    """
    Tracks the "who" for a single interview session.

    Usage:
        identity = CandidateIdentityManager()
        if identity.try_lock(frame_result):
            ...  # locked
        match = identity.match(some_face_result)
    """

    def __init__(self, match_distance_threshold: float = 0.18) -> None:
        self.match_distance_threshold = match_distance_threshold

        self._locked: bool = False
        self._reference_descriptor: Optional[np.ndarray] = None
        self._reference_landmarks: Optional[List[Landmark]] = None
        self._locked_frame_id: Optional[int] = None
        self._locked_at_ts: Optional[float] = None

    # ------------------------------------------------------------------ #
    # Locking
    # ------------------------------------------------------------------ #
    @property
    def is_locked(self) -> bool:
        return self._locked

    def try_lock(self, frame_result: FrameResult) -> bool:
        """
        Attempt to lock the candidate identity.

        Locking is only permitted when exactly one face is visible
        (requirement: never select randomly among multiple faces).
        Returns True if locking succeeded, False otherwise. Does
        nothing if already locked (call reset() first to re-lock).
        """
        if self._locked:
            logger.info("Lock requested but identity is already locked. Ignoring.")
            return False

        if frame_result.num_faces == 0:
            logger.info("Lock rejected: no face visible.")
            return False

        if frame_result.num_faces > 1:
            logger.info(
                "Lock rejected: %d faces visible; exactly one is required to lock.",
                frame_result.num_faces,
            )
            return False

        face = frame_result.faces[0]
        descriptor = self.compute_descriptor(face.landmarks)
        if descriptor is None:
            logger.warning("Lock rejected: could not compute descriptor from landmarks.")
            return False

        self._reference_descriptor = descriptor
        self._reference_landmarks = face.landmarks
        self._locked_frame_id = frame_result.frame_id
        self._locked_at_ts = time.time()
        self._locked = True

        logger.info("Candidate locked at frame_id=%s.", frame_result.frame_id)
        return True

    def reset(self) -> None:
        """
        Explicitly clear the locked identity. Must only be called on
        deliberate request or when a new interview session begins —
        never automatically by tracking logic.
        """
        self._locked = False
        self._reference_descriptor = None
        self._reference_landmarks = None
        self._locked_frame_id = None
        self._locked_at_ts = None
        logger.info("Candidate identity reset.")

    @property
    def reference_landmarks(self) -> Optional[List[Landmark]]:
        return self._reference_landmarks

    # ------------------------------------------------------------------ #
    # Matching (heuristic only — see module docstring)
    # ------------------------------------------------------------------ #
    def match(self, face: FaceResult) -> MatchResult:
        """
        Compare a candidate face against the locked reference.

        Returns a MatchResult with a heuristic distance. This is NOT
        biometric verification (see module docstring) — callers must
        treat close/borderline distances as ambiguous rather than as
        confirmed identity.
        """
        if not self._locked or self._reference_descriptor is None:
            raise IdentityError("Cannot match: no candidate is locked.")

        descriptor = self.compute_descriptor(face.landmarks)
        if descriptor is None:
            return MatchResult(distance=float("inf"), is_match=False)

        distance = float(np.linalg.norm(descriptor - self._reference_descriptor))
        is_match = distance <= self.match_distance_threshold
        return MatchResult(distance=distance, is_match=is_match)

    # ------------------------------------------------------------------ #
    # Geometric descriptor helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def compute_descriptor(landmarks: Sequence[Landmark]) -> Optional[np.ndarray]:
        """
        Build a scale-normalized geometric signature from a fixed set
        of stable landmarks: pairwise distances among them, divided by
        inter-ocular distance. Heuristic only — see module docstring.
        """
        if not landmarks:
            return None

        try:
            points = {
                idx: np.array([landmarks[idx].x, landmarks[idx].y])
                for idx in _SIGNATURE_LANDMARK_INDICES
            }
        except IndexError:
            logger.warning("Landmark set too small to compute descriptor.")
            return None

        inter_ocular = np.linalg.norm(points[_LEFT_EYE_OUTER] - points[_RIGHT_EYE_OUTER])
        if inter_ocular < 1e-6:
            logger.warning("Degenerate inter-ocular distance; cannot normalize descriptor.")
            return None

        distances = []
        indices = _SIGNATURE_LANDMARK_INDICES
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                d = np.linalg.norm(points[indices[i]] - points[indices[j]])
                distances.append(d / inter_ocular)

        return np.array(distances, dtype=np.float32)

    @staticmethod
    def compute_centroid(landmarks: Sequence[Landmark]) -> Optional[Tuple[float, float]]:
        """Mean (x, y) of all landmarks — used by the tracker for spatial continuity."""
        if not landmarks:
            return None
        xs = [lm.x for lm in landmarks]
        ys = [lm.y for lm in landmarks]
        return (sum(xs) / len(xs), sum(ys) / len(ys))