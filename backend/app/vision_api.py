
from contextlib import asynccontextmanager
import logging
import threading
import time

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .ai.candidate_identity import CandidateIdentityManager
from .ai.candidate_tracker import CandidateTracker, TrackerConfig
from .ai.eye_contact import EyeContactAnalyzer
from .ai.head_pose import HeadPoseEstimator
from .ai.liveness_detector import LivenessDetector
from .ai.mediapipe_service import MediaPipeFaceService


from .auth import router as auth_router
from .database import ensure_database_indexes, close_database

import os

from pydantic import BaseModel, Field

from .ai.question_generator import generate_interview_questions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nexhire.vision_api")


class VisionProcessor:
    """Processes browser-supplied frames. Never opens a webcam itself."""

    def __init__(self):
        self.lock = threading.RLock()
        self.mp_service = MediaPipeFaceService(max_faces=4)
        self.identity = CandidateIdentityManager()
        self.liveness = LivenessDetector()
        self.tracker = CandidateTracker(
            identity_manager=self.identity,
            liveness=self.liveness,
            config=TrackerConfig(
                auto_lock=True,
                require_liveness=False,
            ),
        )
        self.eye = EyeContactAnalyzer()
        self.head = HeadPoseEstimator()
        self.last_timestamp_ms = 0
        self.was_analyzing = False
        self.initialized = False

    def initialize(self):
        self.mp_service.initialize()
        # InsightFace loads in the tracker's identity worker.
        self.tracker.warmup_async()
        self.initialized = True
        logger.info("NexHire vision processor initialized")

    def process_frame(self, frame_bgr: np.ndarray) -> dict:
        if not self.initialized:
            raise RuntimeError("Vision processor is not initialized")

        height, width = frame_bgr.shape[:2]
        aspect = width / float(height)

        # Limit inference resolution while preserving frame proportions.
        target_width = min(width, 480)
        target_height = max(1, int(height * target_width / width))
        small = cv2.resize(
            frame_bgr,
            (target_width, target_height),
            interpolation=cv2.INTER_AREA,
        )
        frame_rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        with self.lock:
            # MediaPipe VIDEO mode requires increasing timestamps.
            timestamp_ms = max(
                int(time.monotonic() * 1000),
                self.last_timestamp_ms + 1,
            )
            self.last_timestamp_ms = timestamp_ms

            faces = self.mp_service.detect_face(frame_rgb, timestamp_ms)

            # CandidateTracker remains the only authority for identity,
            # locking, multiple faces, loss and recovery.
            candidate = self.tracker.update(
                frame_bgr,
                faces,
                timestamp_ms,
            )

            head_result = None
            eye_result = None

            if (
                candidate.analysis_allowed
                and candidate.candidate_landmarks is not None
            ):
                landmarks = candidate.candidate_landmarks
                head_result = self.head.estimate(landmarks, aspect)
                eye_result = self.eye.update(
                    landmarks,
                    timestamp_ms,
                    aspect,
                    head_pose=head_result,
                    accumulate=False,
                )
                self.was_analyzing = True
            else:
                if self.was_analyzing:
                    self.eye.suspend()
                    self.head.reset()
                    self.was_analyzing = False

            live = candidate.liveness

            return {
                "timestamp_ms": timestamp_ms,
                "face_count": candidate.face_count,
                "candidate": {
                    "status": candidate.status.value,
                    "locked": candidate.locked,
                    "verified": candidate.verified,
                    "analysis_allowed": candidate.analysis_allowed,
                    "message": candidate.message,
                    "enrollment_progress": round(
                        candidate.enrollment_progress, 3
                    ),
                    "missed_frames": candidate.missed_frames,
                },
                "liveness": {
                    "status": live.status.value,
                    "score": round(live.score, 3),
                    "blink_count": live.blink_count,
                    "evidence": live.evidence,
                    "note": "Heuristic only; not production-grade anti-spoofing.",
                },
                "eye_contact": {
                    "state": (
                        eye_result.state.value
                        if eye_result is not None
                        else "UNKNOWN"
                    ),
                    "valid": (
                        eye_result.valid
                        if eye_result is not None
                        else False
                    ),
                    "ratio": (
                        round(eye_result.eye_contact_ratio, 3)
                        if eye_result is not None
                        else 0.0
                    ),
                },
                "head_pose": {
                    "valid": (
                        head_result.valid
                        if head_result is not None
                        else False
                    ),
                    "yaw": (
                        round(head_result.yaw, 2)
                        if head_result is not None
                        and head_result.valid
                        else None
                    ),
                    "pitch": (
                        round(head_result.pitch, 2)
                        if head_result is not None
                        and head_result.valid
                        else None
                    ),
                    "roll": (
                        round(head_result.roll, 2)
                        if head_result is not None
                        and head_result.valid
                        else None
                    ),
                    "facing_camera": (
                        head_result.facing_camera
                        if head_result is not None
                        and head_result.valid
                        else None
                    ),
                },
            }

    def reset_candidate(self):
        """Explicit reset only; never reset identity automatically."""
        with self.lock:
            self.tracker.reset()
            self.eye.reset()
            self.head.reset()
            self.was_analyzing = False

    def close(self):
        with self.lock:
            self.tracker.close()
            self.mp_service.close()


processor = VisionProcessor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    processor.initialize()
    yield
    processor.close()


app = FastAPI(
    
    title="NexHire Vision API",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(auth_router)
class GenerateQuestionsRequest(BaseModel):
    role: str = Field(min_length=1, max_length=100)
    experience: str = Field(min_length=1, max_length=50)
    interviewType: str = Field(pattern="^(Technical|HR|Mixed)$")
    difficulty: str = Field(pattern="^(Easy|Medium|Hard)$")
    questionCount: int = Field(ge=5, le=20)
    skills: list[str] = Field(default_factory=list, max_length=30)


@app.post("/api/interview/generate-questions")
def generate_questions_endpoint(request: GenerateQuestionsRequest):
    try:
        questions = generate_interview_questions(
            role=request.role.strip(),
            experience=request.experience.strip(),
            interview_type=request.interviewType,
            difficulty=request.difficulty,
            question_count=request.questionCount,
            skills=request.skills,
        )

        return {
            "success": True,
            "role": request.role,
            "interviewType": request.interviewType,
            "difficulty": request.difficulty,
            "questions": questions,
        }

    except Exception:
        logger.exception("Interview question generation failed")
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not generate interview questions. "
                "Check the backend terminal and Gemini configuration."
            ),
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/vision/health")
def health():
    return {
        "status": "ok",
        "service": "nexhire-vision",
        "initialized": processor.initialized,
    }


@app.post("/api/vision/frame")
def analyze_frame(file: UploadFile = File(...)):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=415,
            detail="Upload a JPEG, PNG or WebP frame.",
        )

    # Limit compressed upload size to 2 MB.
    data = file.file.read(2 * 1024 * 1024 + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty frame.")
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Frame exceeds 2 MB.")

    image_array = np.frombuffer(data, dtype=np.uint8)
    frame_bgr = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if frame_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid image frame.")

    try:
        result = processor.process_frame(frame_bgr)
        return {"success": True, "result": result}
    except Exception:
        logger.exception("Frame processing failed")
        raise HTTPException(
            status_code=500,
            detail="Frame processing failed. Check the backend terminal.",
        )


@app.post("/api/vision/reset")
def reset_candidate():
    processor.reset_candidate()
    return {"success": True, "message": "Candidate reset explicitly."}
