"""
candidate_tracker.py

Maintains the locked candidate throughout the interview.

Important rule:

Once a candidate is locked, no other person can replace them.

Identity verification is performed only:
    - when starting the interview
    - when the candidate returns after being absent
    - when the system explicitly needs to verify identity

Normal movement is handled by MediaPipe landmarks only.
"""

from enum import Enum, auto
from typing import List, Optional, Tuple

from app.ai import candidate_identity as identity_module


# ============================================================
# SETTINGS
# ============================================================

MISSED_FRAME_TOLERANCE = 3


# ============================================================
# STATUS
# ============================================================

class CandidateStatus(Enum):

    WAITING_FOR_CANDIDATE = auto()

    CANDIDATE_SELECTED = auto()

    CANDIDATE_LOCKED = auto()

    CANDIDATE_PRESENT = auto()

    CANDIDATE_NOT_DETECTED = auto()

    DIFFERENT_PERSON_DETECTED = auto()

    MULTIPLE_FACES_DETECTED = auto()

    CANDIDATE_UNCERTAIN = auto()


# ============================================================
# TRACKER
# ============================================================

class CandidateTracker:

    def __init__(
        self,
        identity_backend=identity_module
    ):

        self._identity_backend = identity_backend

        self.reset_candidate()

    # ========================================================
    # RESET
    # ========================================================

    def reset_candidate(self):

        self.status = (
            CandidateStatus.WAITING_FOR_CANDIDATE
        )

        self.locked_identity = None

        self.interview_started = False

        self._pending_candidate_landmarks = None

        self._candidate_was_present = False

        self._consecutive_missed_frames = 0

        # When True, the next visible face MUST be
        # identity verified.
        self._identity_verification_required = False

    # ========================================================
    # START INTERVIEW
    # ========================================================

    def start_interview(
        self,
        rgb_frame
    ):

        if self.status != (
            CandidateStatus.CANDIDATE_SELECTED
        ):

            raise RuntimeError(
                "Cannot start interview. "
                "Exactly one candidate must be selected."
            )

        if self._pending_candidate_landmarks is None:

            raise RuntimeError(
                "Candidate landmarks are unavailable."
            )

        # ----------------------------------------------------
        # CREATE IDENTITY ONCE
        # ----------------------------------------------------

        identity = (
            self._identity_backend
            .CandidateIdentity
            .from_frame(
                rgb_frame,
                self._pending_candidate_landmarks
            )
        )

        if identity is None:

            self.status = (
                CandidateStatus.CANDIDATE_UNCERTAIN
            )

            raise RuntimeError(
                "Could not create candidate identity. "
                "Please face the camera clearly."
            )

        # ----------------------------------------------------
        # LOCK CANDIDATE
        # ----------------------------------------------------

        self.locked_identity = identity

        self.interview_started = True

        self._candidate_was_present = True

        self._identity_verification_required = False

        self._consecutive_missed_frames = 0

        self.status = (
            CandidateStatus.CANDIDATE_LOCKED
        )

        print(
            "Candidate identity locked."
        )

        return self.status

    # ========================================================
    # PROCESS FRAME
    # ========================================================

    def process_frame(
        self,
        rgb_frame,
        all_face_landmarks: List
    ) -> Tuple[
        CandidateStatus,
        Optional[object]
    ]:

        if not self.interview_started:

            return self._process_pre_interview(
                all_face_landmarks
            )

        return self._process_post_interview(
            rgb_frame,
            all_face_landmarks
        )

    # ========================================================
    # PRE-INTERVIEW
    # ========================================================

    def _process_pre_interview(
        self,
        all_face_landmarks
    ):

        count = len(
            all_face_landmarks
        )

        if count == 0:

            self.status = (
                CandidateStatus.CANDIDATE_NOT_DETECTED
            )

            self._pending_candidate_landmarks = None

            return self.status, None

        if count >= 2:

            self.status = (
                CandidateStatus.MULTIPLE_FACES_DETECTED
            )

            self._pending_candidate_landmarks = None

            return self.status, None

        # Exactly one face.

        self._pending_candidate_landmarks = (
            all_face_landmarks[0]
        )

        self.status = (
            CandidateStatus.CANDIDATE_SELECTED
        )

        return (
            self.status,
            self._pending_candidate_landmarks
        )

    # ========================================================
    # AFTER INTERVIEW
    # ========================================================

    def _process_post_interview(
        self,
        rgb_frame,
        all_face_landmarks
    ):

        if self.locked_identity is None:

            raise RuntimeError(
                "Interview started without locked identity."
            )

        # ----------------------------------------------------
        # NO FACE
        # ----------------------------------------------------

        if len(all_face_landmarks) == 0:

            self._consecutive_missed_frames += 1

            self._candidate_was_present = False

            # The next person who appears MUST be verified.

            self._identity_verification_required = True

            if (
                self._consecutive_missed_frames
                >= MISSED_FRAME_TOLERANCE
            ):

                self.status = (
                    CandidateStatus.CANDIDATE_NOT_DETECTED
                )

            return self.status, None

        # ----------------------------------------------------
        # MULTIPLE FACES
        # ----------------------------------------------------

        if len(all_face_landmarks) >= 2:

            candidate_landmarks = (
                self._verify_faces(
                    rgb_frame,
                    all_face_landmarks
                )
            )

            if candidate_landmarks is not None:

                self._candidate_was_present = True

                self._identity_verification_required = False

                self._consecutive_missed_frames = 0

                self.status = (
                    CandidateStatus.CANDIDATE_PRESENT
                )

                return (
                    self.status,
                    candidate_landmarks
                )

            self._candidate_was_present = False

            self._identity_verification_required = True

            self.status = (
                CandidateStatus.MULTIPLE_FACES_DETECTED
            )

            return self.status, None

        # ----------------------------------------------------
        # EXACTLY ONE FACE
        # ----------------------------------------------------

        face = all_face_landmarks[0]

        # ----------------------------------------------------
        # VERIFY ONLY WHEN REQUIRED
        # ----------------------------------------------------

        if self._identity_verification_required:

            embedding = (
                self._identity_backend
                .generate_embedding(
                    rgb_frame,
                    face
                )
            )

            if embedding is None:

                self.status = (
                    CandidateStatus.CANDIDATE_UNCERTAIN
                )

                return self.status, None

            # -----------------------------------------------
            # ORIGINAL CANDIDATE?
            # -----------------------------------------------

            if self.locked_identity.matches(
                embedding
            ):

                self._candidate_was_present = True

                self._identity_verification_required = False

                self._consecutive_missed_frames = 0

                self.status = (
                    CandidateStatus.CANDIDATE_PRESENT
                )

                print(
                    "Original candidate verified."
                )

                return (
                    self.status,
                    face
                )

            # -----------------------------------------------
            # DIFFERENT PERSON
            # -----------------------------------------------

            self._candidate_was_present = False

            self._identity_verification_required = True

            self.status = (
                CandidateStatus.DIFFERENT_PERSON_DETECTED
            )

            # NEVER pass B's landmarks downstream.

            return self.status, None

        # ----------------------------------------------------
        # FAST PATH
        #
        # Candidate has already been verified and has not
        # disappeared.
        #
        # NO INSIGHTFACE HERE.
        # ----------------------------------------------------

        self._candidate_was_present = True

        self._consecutive_missed_frames = 0

        self.status = (
            CandidateStatus.CANDIDATE_PRESENT
        )

        return (
            self.status,
            face
        )

    # ========================================================
    # VERIFY MULTIPLE FACES
    # ========================================================

    def _verify_faces(
        self,
        rgb_frame,
        all_face_landmarks
    ):

        for face in all_face_landmarks:

            embedding = (
                self._identity_backend
                .generate_embedding(
                    rgb_frame,
                    face
                )
            )

            if embedding is None:
                continue

            if self.locked_identity.matches(
                embedding
            ):

                return face

        return None