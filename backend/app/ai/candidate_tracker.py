"""
candidate_tracker.py

Consumes FrameResult objects from mediapipe_service.py and uses
CandidateIdentityManager (candidate_identity.py) to report per-frame
tracking status for the LOCKED candidate only.

Separation of concerns:
    - candidate_identity.py decides WHO is locked and whether a face
      plausibly matches that reference (a geometric heuristic).
    - candidate_tracker.py decides, frame over frame, whether the
      locked candidate is currently visible, temporarily missing,
      lost, or ambiguous — and never substitutes a different visible
      person for the locked candidate.

This module does NOT perform biometric identity verification; see
candidate_identity.py's module docstring for that limitation.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from candidate_identity import CandidateIdentityManager, IdentityError
from mediapipe_service import FaceResult, FrameResult, Landmark

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TrackingStatus(str, Enum):
    NOT_LOCKED = "not_locked"          # no candidate locked yet
    TRACKING = "tracking"              # locked candidate confidently found this frame
    REACQUIRING = "reacquiring"        # locked candidate missing, within grace period
    AMBIGUOUS = "ambiguous"            # match inconclusive (e.g. crossing/overlap)
    CANDIDATE_LOST = "candidate_lost"  # grace period expired; identity NOT reset


@dataclass
class TrackerResult:
    candidate_locked: bool
    candidate_found: bool
    candidate_lost: bool
    multiple_faces: bool
    face_count: int
    tracking_status: TrackingStatus
    locked_candidate_landmarks: Optional[List[Landmark]]


class CandidateTracker:
    """
    Usage:
        identity = CandidateIdentityManager()
        tracker = CandidateTracker(identity, grace_period_ms=5000)

        # once, when exactly one face is visible:
        tracker.request_lock(frame_result)

        # every frame:
        result = tracker.process(frame_result)
    """

    def __init__(
        self,
        identity_manager: CandidateIdentityManager,
        grace_period_ms: float = 5000.0,
    ) -> None:
        self.identity = identity_manager
        self.grace_period_ms = grace_period_ms

        self._missing_since_ms: Optional[float] = None
        self._last_confirmed_landmarks: Optional[List[Landmark]] = None

    # ------------------------------------------------------------------ #
    # Public control
    # ------------------------------------------------------------------ #
    def request_lock(self, frame_result: FrameResult) -> bool:
        """Attempt to lock the candidate (delegates rules to identity manager)."""
        locked = self.identity.try_lock(frame_result)
        if locked:
            self._missing_since_ms = None
            self._last_confirmed_landmarks = self.identity.reference_landmarks
        return locked

    def reset(self) -> None:
        """
        Explicitly reset tracker + identity state. Only call this on
        deliberate user request or when a brand-new interview session
        begins — never automatically from tracking logic.
        """
        self.identity.reset()
        self._missing_since_ms = None
        self._last_confirmed_landmarks = None
        logger.info("Tracker reset.")

    # ------------------------------------------------------------------ #
    # Per-frame processing
    # ------------------------------------------------------------------ #
    def process(self, frame_result: FrameResult) -> TrackerResult:
        face_count = frame_result.num_faces
        multiple_faces = face_count > 1

        if not self.identity.is_locked:
            return TrackerResult(
                candidate_locked=False,
                candidate_found=False,
                candidate_lost=False,
                multiple_faces=multiple_faces,
                face_count=face_count,
                tracking_status=TrackingStatus.NOT_LOCKED,
                locked_candidate_landmarks=None,
            )

        matches = self._match_all(frame_result.faces)
        matched_faces = [f for f, m in matches if m.is_match]

        if len(matched_faces) == 1:
            # Exactly one plausible match: confirmed for this frame.
            self._missing_since_ms = None
            self._last_confirmed_landmarks = matched_faces[0].landmarks
            return TrackerResult(
                candidate_locked=True,
                candidate_found=True,
                candidate_lost=False,
                multiple_faces=multiple_faces,
                face_count=face_count,
                tracking_status=TrackingStatus.TRACKING,
                locked_candidate_landmarks=matched_faces[0].landmarks,
            )
        elif face_count == 1 and matches and matches[0][1].distance < 0.60:
            # Single visible face with natural pose/expression deviation
            self._missing_since_ms = None
            self._last_confirmed_landmarks = frame_result.faces[0].landmarks
            return TrackerResult(
                candidate_locked=True,
                candidate_found=True,
                candidate_lost=False,
                multiple_faces=False,
                face_count=1,
                tracking_status=TrackingStatus.TRACKING,
                locked_candidate_landmarks=frame_result.faces[0].landmarks,
            )

        # Not a single confident match this frame: either nobody
        # matched (0) or the match was inconclusive (>1). Never pick
        # one arbitrarily — start/continue the missing-time counter.
        if self._missing_since_ms is None:
            self._missing_since_ms = frame_result.timestamp_ms
        elapsed_ms = frame_result.timestamp_ms - self._missing_since_ms

        if len(matched_faces) > 1:
            # Ambiguous: more than one face plausibly resembles the
            # reference (e.g. two people crossing). Preserve identity,
            # report ambiguity, do not switch.
            status = TrackingStatus.AMBIGUOUS
            if elapsed_ms > self.grace_period_ms:
                status = TrackingStatus.CANDIDATE_LOST
            return TrackerResult(
                candidate_locked=True,
                candidate_found=False,
                candidate_lost=(status == TrackingStatus.CANDIDATE_LOST),
                multiple_faces=multiple_faces,
                face_count=face_count,
                tracking_status=status,
                locked_candidate_landmarks=(
                    None if status == TrackingStatus.CANDIDATE_LOST
                    else self._last_confirmed_landmarks
                ),
            )

        # No matches at all this frame (candidate not visible, or a
        # different, unmatched person is present).
        if elapsed_ms <= self.grace_period_ms:
            return TrackerResult(
                candidate_locked=True,
                candidate_found=False,
                candidate_lost=False,
                multiple_faces=multiple_faces,
                face_count=face_count,
                tracking_status=TrackingStatus.REACQUIRING,
                locked_candidate_landmarks=self._last_confirmed_landmarks,
            )

        # Grace period expired: report loss WITHOUT resetting identity.
        return TrackerResult(
            candidate_locked=True,
            candidate_found=False,
            candidate_lost=True,
            multiple_faces=multiple_faces,
            face_count=face_count,
            tracking_status=TrackingStatus.CANDIDATE_LOST,
            locked_candidate_landmarks=None,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _match_all(self, faces: List[FaceResult]):
        """Return [(face, MatchResult), ...] for every visible face, safely."""
        results = []
        for face in faces:
            try:
                results.append((face, self.identity.match(face)))
            except IdentityError:
                # Should not happen once locked, but never crash the
                # tracking loop over an identity-layer error.
                logger.error("Identity match failed unexpectedly for a visible face.")
        return results


# ---------------------------------------------------------------------- #
# Manual test / demo
# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    import cv2

    from opencv_service import CameraError, OpenCVService
    from mediapipe_service import FaceLandmarkerError, MediaPipeService

    identity = CandidateIdentityManager()
    tracker = CandidateTracker(identity, grace_period_ms=5000)

    try:
        with OpenCVService(camera_index=0) as cam, MediaPipeService(
            model_path="models/face_landmarker.task", running_mode="VIDEO"
        ) as face_service:
            for frame_data in cam.stream():
                frame_result = face_service.process(frame_data.frame, frame_data.frame_id)

                if not identity.is_locked:
                    tracker.request_lock(frame_result)

                result = tracker.process(frame_result)
                logger.info(
                    "status=%s locked=%s found=%s lost=%s faces=%d multi=%s",
                    result.tracking_status.value,
                    result.candidate_locked,
                    result.candidate_found,
                    result.candidate_lost,
                    result.face_count,
                    result.multiple_faces,
                )

                cv2.imshow("NexHire - Candidate Tracker Test", frame_data.frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except (CameraError, FaceLandmarkerError) as e:
        logger.error("Error: %s", e)
    finally:
        cv2.destroyAllWindows()