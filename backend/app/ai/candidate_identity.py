"""
candidate_identity.py

Handles candidate identity only.

InsightFace is used:
    1. When the candidate starts the interview.
    2. When identity must be re-verified after the candidate
       disappears.

It is NOT intended to run continuously on every webcam frame.
"""

from typing import Optional

import numpy as np
from insightface.app import FaceAnalysis


# ============================================================
# SETTINGS
# ============================================================

IDENTITY_MATCH_THRESHOLD = 0.60

MIN_FACE_BOX_SIDE_PX = 60

INSIGHTFACE_DET_SIZE = (320, 320)


# ============================================================
# MODEL
# ============================================================

_identity_app = None


def _get_identity_app():

    global _identity_app

    if _identity_app is None:

        print("Loading InsightFace identity model...")

        _identity_app = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"]
        )

        _identity_app.prepare(
            ctx_id=-1,
            det_size=INSIGHTFACE_DET_SIZE
        )

        print("InsightFace identity model loaded.")

    return _identity_app


# ============================================================
# CANDIDATE IDENTITY
# ============================================================

class CandidateIdentity:

    def __init__(
        self,
        embedding: np.ndarray
    ):

        self.embedding = normalize_embedding(
            embedding
        )

    @classmethod
    def from_frame(
        cls,
        rgb_frame: np.ndarray,
        face_landmarks
    ) -> Optional["CandidateIdentity"]:

        embedding = generate_embedding(
            rgb_frame,
            face_landmarks
        )

        if embedding is None:
            return None

        return cls(
            embedding
        )

    def matches(
        self,
        embedding: Optional[np.ndarray]
    ) -> bool:

        if embedding is None:
            return False

        similarity = compare_embeddings(
            self.embedding,
            embedding
        )

        return similarity >= IDENTITY_MATCH_THRESHOLD

    def similarity(
        self,
        embedding: Optional[np.ndarray]
    ) -> float:

        if embedding is None:
            return 0.0

        return compare_embeddings(
            self.embedding,
            embedding
        )


# ============================================================
# MEDIAPIPE LANDMARKS → BOX
# ============================================================

def _landmarks_to_face_box(
    rgb_frame,
    face_landmarks
):

    if not face_landmarks:
        return None

    h, w, _ = rgb_frame.shape

    xs = [
        lm.x
        for lm in face_landmarks
    ]

    ys = [
        lm.y
        for lm in face_landmarks
    ]

    if not xs or not ys:
        return None

    left = max(
        int(min(xs) * w),
        0
    )

    right = min(
        int(max(xs) * w),
        w - 1
    )

    top = max(
        int(min(ys) * h),
        0
    )

    bottom = min(
        int(max(ys) * h),
        h - 1
    )

    if right <= left or bottom <= top:
        return None

    return (
        left,
        top,
        right,
        bottom
    )


# ============================================================
# FIND CORRESPONDING INSIGHTFACE FACE
# ============================================================

def _find_matching_face(
    rgb_frame,
    face_landmarks,
    insight_faces
):

    target_box = _landmarks_to_face_box(
        rgb_frame,
        face_landmarks
    )

    if target_box is None:
        return None

    tx1, ty1, tx2, ty2 = target_box

    target_cx = (
        tx1 + tx2
    ) / 2

    target_cy = (
        ty1 + ty2
    ) / 2

    target_size = max(
        tx2 - tx1,
        ty2 - ty1,
        1
    )

    best_face = None
    best_distance = float("inf")

    for face in insight_faces:

        bbox = face.bbox

        fx1 = float(bbox[0])
        fy1 = float(bbox[1])
        fx2 = float(bbox[2])
        fy2 = float(bbox[3])

        face_cx = (
            fx1 + fx2
        ) / 2

        face_cy = (
            fy1 + fy2
        ) / 2

        distance = (
            (
                target_cx - face_cx
            ) ** 2
            +
            (
                target_cy - face_cy
            ) ** 2
        ) ** 0.5

        normalized_distance = (
            distance / target_size
        )

        if normalized_distance < best_distance:

            best_distance = normalized_distance
            best_face = face

    return best_face


# ============================================================
# GENERATE EMBEDDING
# ============================================================

def generate_embedding(
    rgb_frame: np.ndarray,
    face_landmarks
) -> Optional[np.ndarray]:

    if not face_landmarks:
        return None

    box = _landmarks_to_face_box(
        rgb_frame,
        face_landmarks
    )

    if box is None:
        return None

    left, top, right, bottom = box

    if (
        right - left < MIN_FACE_BOX_SIDE_PX
        or
        bottom - top < MIN_FACE_BOX_SIDE_PX
    ):
        return None

    try:

        app = _get_identity_app()

        faces = app.get(
            rgb_frame
        )

        if not faces:
            return None

        matched_face = _find_matching_face(
            rgb_frame,
            face_landmarks,
            faces
        )

        if matched_face is None:
            return None

        embedding = (
            matched_face.normed_embedding
        )

        if embedding is None:
            return None

        return normalize_embedding(
            embedding
        )

    except Exception as error:

        print(
            "Identity verification error:",
            error
        )

        return None


# ============================================================
# NORMALIZE
# ============================================================

def normalize_embedding(
    embedding
):

    embedding = np.asarray(
        embedding,
        dtype=np.float32
    )

    norm = np.linalg.norm(
        embedding
    )

    if norm == 0:
        return embedding

    return embedding / norm


# ============================================================
# COMPARE
# ============================================================

def compare_embeddings(
    reference,
    candidate
):

    reference = normalize_embedding(
        reference
    )

    candidate = normalize_embedding(
        candidate
    )

    return float(
        np.dot(
            reference,
            candidate
        )
    )