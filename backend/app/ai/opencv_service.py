"""
opencv_service.py

NexHire runtime entry point (webcam + HUD + session coordination).

Run (from the folder that CONTAINS the package directory, or directly from inside it):

    python -m <package>.opencv_service
    python opencv_service.py                  # also works; the package is bootstrapped below

Threads
  main thread     : camera read -> latest-frame slot -> HUD -> imshow -> keys -> session
  "nexhire-ai"    : newest frame -> resize -> MediaPipeFaceService.detect_face
                    -> CandidateTracker.update -> (gated) HeadPoseEstimator + EyeContactAnalyzer
  "identity"      : owned by CandidateTracker (InsightFace, on demand only)

Frame hand-off is a SINGLE slot (LatestFrameBuffer): the AI worker always takes the newest
frame and old frames are overwritten, so a slow AI loop never builds a backlog.

Audio / Whisper is intentionally absent. Later it can run in its own worker, subscribe via
runtime.session.add_listener(...) and contribute to the final report through
runtime.register_report_provider("audio", fn). Nothing in the vision path needs to change.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    # `python opencv_service.py` from inside the package folder: make the relative
    # imports of the existing modules (candidate_tracker uses `from .x import`) work.
    import importlib

    _pkg_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(_pkg_dir.parent))
    __package__ = _pkg_dir.name
    importlib.import_module(__package__)

import argparse
import json
import logging
import platform
import queue
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Deque, Dict, Optional, Tuple

import cv2
import numpy as np

from .candidate_identity import CandidateIdentityManager
from .candidate_tracker import CandidateState, CandidateStatus, CandidateTracker, TrackerConfig
from .eye_contact import EyeContactAnalyzer, EyeContactResult, EyeContactState
from .head_pose import HeadPoseEstimator, HeadPoseResult
from .interview_session_controller import InterviewSessionController, SessionSnapshot, SessionState
from .liveness_detector import LivenessDetector
from .mediapipe_service import MediaPipeFaceService, MediaPipeServiceError

log = logging.getLogger("nexhire.runtime")


# ======================================================================= config
@dataclass
class RuntimeConfig:
    camera_index: int = 0
    cam_width: int = 1280
    cam_height: int = 720
    cam_fps: int = 30
    mirror: bool = True                 # selfie view; applied BEFORE any processing (consistent)
    display_width: int = 960            # HUD is drawn on a downscaled copy (cheaper)
    ai_width: int = 480                 # AI frame ~480x270 for 16:9
    ai_fps: float = 20.0                # MediaPipe + tracker
    eye_fps: float = 12.0               # eye contact
    head_fps: float = 12.0              # head pose
    max_faces: int = 4                  # >= 2 is all that is needed to detect "multiple faces"
    session_duration_s: float = 600.0
    opencv_threads: int = 2             # leave cores for MediaPipe / ONNX
    init_budget_s: float = 10.0         # startup target (only used for the diagnostic line)
    report_path: Optional[str] = None
    window_name: str = "NexHire"


# ================================================================ small utilities
class LatestFrameBuffer:
    """Single-slot, newest-wins frame hand-off. Never queues."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._frame: Optional[np.ndarray] = None
        self._ts_ms = 0
        self._seq = 0
        self._closed = False

    def put(self, frame: np.ndarray, ts_ms: int) -> None:
        with self._cond:
            self._frame, self._ts_ms = frame, ts_ms
            self._seq += 1
            self._cond.notify_all()

    def latest(self) -> Optional[Tuple[np.ndarray, int, int]]:
        with self._cond:
            return None if self._frame is None else (self._frame, self._ts_ms, self._seq)

    def wait_newer(self, last_seq: int, timeout: float) -> Optional[Tuple[np.ndarray, int, int]]:
        with self._cond:
            if not self._closed and self._seq <= last_seq:
                self._cond.wait(timeout)
            if self._closed or self._frame is None or self._seq <= last_seq:
                return None
            return self._frame, self._ts_ms, self._seq

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()


class FpsMeter:
    def __init__(self, window_s: float = 1.5) -> None:
        self._window = window_s
        self._t: Deque[float] = deque()
        self._lock = threading.Lock()

    def tick(self) -> None:
        now = time.monotonic()
        with self._lock:
            self._t.append(now)
            while self._t and now - self._t[0] > self._window:
                self._t.popleft()

    @property
    def fps(self) -> float:
        with self._lock:
            if len(self._t) < 2:
                return 0.0
            span = self._t[-1] - self._t[0]
            return (len(self._t) - 1) / span if span > 0 else 0.0


class RateGate:
    """Lets a cheap analyzer run at ~`fps` while the AI loop ticks faster."""

    def __init__(self, fps: float) -> None:
        self.interval = 1.0 / max(1e-3, fps)
        self._next = 0.0

    def due(self, now: float) -> bool:
        if now < self._next:
            return False
        nxt = self._next + self.interval
        self._next = nxt if nxt >= now else now + self.interval
        return True

    def reset(self) -> None:
        self._next = 0.0


# ================================================================ result boundary
@dataclass
class FrameResult:
    """Vision-side result published by the AI worker. Audio will get its own result type."""
    seq: int = 0
    timestamp_ms: int = 0
    candidate: CandidateState = field(default_factory=CandidateState)
    eye: EyeContactResult = field(default_factory=EyeContactResult)
    head: HeadPoseResult = field(default_factory=HeadPoseResult)
    analysis_active: bool = False       # eye/head were computed for the verified candidate
    mediapipe_ms: float = 0.0
    ai_ms: float = 0.0


class ResultHolder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._res = FrameResult()

    def set(self, res: FrameResult) -> None:
        with self._lock:
            self._res = res

    def get(self) -> FrameResult:
        with self._lock:
            return self._res

    def clear(self) -> None:
        self.set(FrameResult())


class SessionMetrics:
    """Time-in-status and head-pose statistics, accumulated only while the session RUNS."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._status_s: Dict[str, float] = {}
            self._tracked_s = 0.0
            self._analyzed_s = 0.0
            self._head_valid_s = 0.0
            self._head_facing_s = 0.0
            self._yaw_w = 0.0
            self._pitch_w = 0.0

    def add(self, status: str, dt: float, analyzed: bool, head: Optional[HeadPoseResult]) -> None:
        if dt <= 0.0:
            return
        with self._lock:
            self._status_s[status] = self._status_s.get(status, 0.0) + dt
            self._tracked_s += dt
            if analyzed:
                self._analyzed_s += dt
                if head is not None and head.valid:
                    self._head_valid_s += dt
                    self._yaw_w += abs(head.yaw) * dt
                    self._pitch_w += abs(head.pitch) * dt
                    if head.facing_camera:
                        self._head_facing_s += dt

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            hv = self._head_valid_s
            return {
                "tracked_s": round(self._tracked_s, 2),
                "analyzed_s": round(self._analyzed_s, 2),
                "analysis_blocked_s": round(max(0.0, self._tracked_s - self._analyzed_s), 2),
                "seconds_per_status": {k: round(v, 2) for k, v in self._status_s.items()},
                "head_pose": {
                    "valid_s": round(hv, 2),
                    "facing_camera_ratio": round(self._head_facing_s / hv, 3) if hv > 0 else 0.0,
                    "mean_abs_yaw_deg": round(self._yaw_w / hv, 1) if hv > 0 else 0.0,
                    "mean_abs_pitch_deg": round(self._pitch_w / hv, 1) if hv > 0 else 0.0,
                },
            }


@dataclass
class InitTimings:
    mediapipe_s: float = 0.0
    insightface_s: float = 0.0
    camera_s: float = 0.0
    total_wall_s: float = 0.0


# ===================================================================== AI worker
class AIWorker(threading.Thread):
    def __init__(
        self,
        cfg: RuntimeConfig,
        buffer: LatestFrameBuffer,
        mp_service: MediaPipeFaceService,
        tracker: CandidateTracker,
        eye: EyeContactAnalyzer,
        head_est: HeadPoseEstimator,
        session: InterviewSessionController,
        metrics: SessionMetrics,
        results: ResultHolder,
        ai_size: Tuple[int, int],
    ) -> None:
        super().__init__(name="nexhire-ai", daemon=True)
        self.cfg, self.buffer, self.mp, self.tracker = cfg, buffer, mp_service, tracker
        self.eye, self.head_est, self.session = eye, head_est, session
        self.metrics, self.results, self.ai_size = metrics, results, ai_size
        self.lock = threading.RLock()          # guards tracker/eye/head across main-thread commands
        self.stop_event = threading.Event()
        self.fps = FpsMeter()
        self._eye_gate = RateGate(cfg.eye_fps)
        self._head_gate = RateGate(cfg.head_fps)
        self._head = HeadPoseResult()
        self._eye = EyeContactResult()
        self._analyzing = False
        self._last_ts: Optional[int] = None
        self._errors = 0

    # ------------------------------------------------------- main-thread commands
    def reset_analysis(self) -> None:
        """Call with self.lock held."""
        self.eye.reset()
        self.head_est.reset()
        self._head, self._eye = HeadPoseResult(), self.eye.snapshot()
        self._eye_gate.reset()
        self._head_gate.reset()
        self._analyzing = False
        self._last_ts = None

    # ---------------------------------------------------------------- thread loop
    def run(self) -> None:
        interval = 1.0 / max(1.0, self.cfg.ai_fps)
        last_seq, next_t = 0, 0.0
        while not self.stop_event.is_set():
            item = self.buffer.wait_newer(last_seq, timeout=0.25)
            if item is None:
                continue
            delay = next_t - time.monotonic()
            if delay > 0:
                if self.stop_event.wait(delay):
                    break
                item = self.buffer.latest() or item        # newest frame after the pacing sleep
            frame, ts, seq = item
            last_seq = seq
            next_t = time.monotonic() + interval           # start-to-start pacing
            try:
                self._process(frame, ts, seq)
            except Exception as exc:                        # never let the worker die silently
                self._errors += 1
                if self._errors <= 3 or self._errors % 100 == 0:
                    log.exception("AI worker error (%d): %s", self._errors, exc)

    def _process(self, frame: np.ndarray, ts: int, seq: int) -> None:
        t_begin = time.perf_counter()
        h, w = frame.shape[:2]
        aspect = w / float(h)

        small = cv2.resize(frame, self.ai_size, interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        t_mp = time.perf_counter()
        faces = self.mp.detect_face(rgb, ts)               # ALL faces; no selection here
        mp_ms = (time.perf_counter() - t_mp) * 1000.0

        with self.lock:
            # CandidateTracker is the single authority: selection, lock, identity (on demand
            # in its own thread), liveness, loss/recovery, multi-face blocking.
            state = self.tracker.update(frame, faces, ts)

            running = self.session.is_running
            now = time.monotonic()
            analysis = bool(state.analysis_allowed and state.candidate_landmarks is not None)

            if analysis:
                lm = state.candidate_landmarks
                if self._head_gate.due(now):
                    self._head = self.head_est.estimate(lm, aspect)
                if self._eye_gate.due(now):
                    self._eye = self.eye.update(
                        lm, ts, aspect, head_pose=self._head, accumulate=running
                    )
                self._analyzing = True
            elif self._analyzing:
                # candidate lost / unverified / multiple faces: drop all continuity
                self.eye.suspend()
                self.head_est.reset()
                self._head, self._eye = HeadPoseResult(), self.eye.snapshot()
                self._eye_gate.reset()
                self._head_gate.reset()
                self._analyzing = False

            if running and self._last_ts is not None:
                dt = min(max((ts - self._last_ts) / 1000.0, 0.0), 0.5)
                self.metrics.add(state.status.value, dt, analysis, self._head if analysis else None)
            self._last_ts = ts

            head_out, eye_out = self._head, self._eye

        self.fps.tick()
        self.results.set(
            FrameResult(
                seq=seq,
                timestamp_ms=ts,
                candidate=state,
                eye=eye_out,
                head=head_out,
                analysis_active=analysis,
                mediapipe_ms=mp_ms,
                ai_ms=(time.perf_counter() - t_begin) * 1000.0,
            )
        )

    def stop(self) -> None:
        self.stop_event.set()
        self.buffer.close()


# ========================================================================== HUD
FONT = cv2.FONT_HERSHEY_SIMPLEX
WHITE, GREY = (240, 240, 240), (170, 170, 170)
GREEN, AMBER, RED, BLUE, CYAN = (80, 220, 90), (0, 190, 255), (70, 70, 235), (255, 170, 60), (230, 220, 90)

STATUS_COLOR = {
    CandidateStatus.WAITING_FOR_CANDIDATE: GREY,
    CandidateStatus.CANDIDATE_SELECTED: AMBER,
    CandidateStatus.CANDIDATE_LOCKED: GREEN,
    CandidateStatus.CANDIDATE_PRESENT: GREEN,
    CandidateStatus.CANDIDATE_NOT_DETECTED: AMBER,
    CandidateStatus.DIFFERENT_PERSON_DETECTED: RED,
    CandidateStatus.MULTIPLE_FACES_DETECTED: RED,
    CandidateStatus.CANDIDATE_UNCERTAIN: AMBER,
}
SESSION_COLOR = {
    SessionState.IDLE: GREY,
    SessionState.READY: BLUE,
    SessionState.RUNNING: GREEN,
    SessionState.PAUSED: AMBER,
    SessionState.COMPLETED: CYAN,
}
BLOCKING = (
    CandidateStatus.MULTIPLE_FACES_DETECTED,
    CandidateStatus.DIFFERENT_PERSON_DETECTED,
    CandidateStatus.CANDIDATE_NOT_DETECTED,
)


@dataclass
class HudStats:
    cam_fps: float = 0.0
    ai_fps: float = 0.0
    max_faces: int = 4
    manual_lock: bool = False
    require_liveness: bool = False


def _text(img: np.ndarray, s: str, x: int, y: int, color, scale: float, thick: int = 1) -> None:
    cv2.putText(img, s, (x, y), FONT, scale, (0, 0, 0), thick + 2, cv2.LINE_AA)
    cv2.putText(img, s, (x, y), FONT, scale, color, thick, cv2.LINE_AA)


def _shade(img: np.ndarray, x0: int, y0: int, x1: int, y1: int, alpha: float = 0.55) -> None:
    h, w = img.shape[:2]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        return
    roi = img[y0:y1, x0:x1]
    cv2.addWeighted(np.zeros_like(roi), alpha, roi, 1.0 - alpha, 0, dst=roi)


def _fmt_time(sec: float) -> str:
    sec = int(max(0, sec + 0.999))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def draw_hud(
    img: np.ndarray,
    fr: FrameResult,
    snap: SessionSnapshot,
    stats: HudStats,
    toast: str,
    show_details: bool,
) -> None:
    h, w = img.shape[:2]
    s = max(0.55, h / 720.0)
    cand, eye, head, lv = fr.candidate, fr.eye, fr.head, fr.candidate.liveness
    sc = STATUS_COLOR.get(cand.status, WHITE)

    # face boxes (normalized -> pixels); green only for the verified candidate
    for (x1, y1, x2, y2) in cand.face_boxes:
        color = GREEN if cand.analysis_allowed else (RED if cand.status in BLOCKING else AMBER)
        cv2.rectangle(img, (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h)), color, 2)

    lines = [
        (f"SESSION {snap.state.value}   {_fmt_time(snap.remaining_s)} left", SESSION_COLOR.get(snap.state, WHITE)),
        (f"CANDIDATE {cand.status.value}", sc),
    ]
    if cand.message:
        lines.append((cand.message, AMBER))
    if not cand.locked and stats.manual_lock and cand.enrollment_progress >= 1.0:
        lines.append(("Press L to lock this candidate", BLUE))

    if show_details:
        n = f"{cand.face_count}{'+' if cand.face_count >= stats.max_faces else ''}"
        lines.append((f"faces {n}  locked {'Y' if cand.locked else 'N'}  verified {'Y' if cand.verified else 'N'}"
                      f"  analysis {'ON' if cand.analysis_allowed else 'BLOCKED'}",
                      GREEN if cand.analysis_allowed else AMBER))
        if not cand.locked:
            filled = int(round(cand.enrollment_progress * 10))
            lines.append((f"identity enroll [{'#' * filled}{'.' * (10 - filled)}]", WHITE))
        elif cand.similarity is not None:
            lines.append((f"identity similarity {cand.similarity:.2f}", WHITE))

        ev = lv.evidence or {}
        flags = "".join(c if ev.get(k) else "-" for c, k in (("B", "blink"), ("M", "movement"), ("D", "depth")))
        lcol = GREEN if lv.is_live else AMBER
        lines.append((f"LIVENESS {lv.status.value} [{flags}] blinks {lv.blink_count} valid {lv.valid_for_s:.0f}s"
                      + ("  (required)" if stats.require_liveness else ""), lcol))

        if fr.analysis_active:
            ecol = {EyeContactState.EYE_CONTACT: GREEN, EyeContactState.LOOKING_AWAY: RED,
                    EyeContactState.EYES_CLOSED: AMBER}.get(eye.state, GREY)
            if eye.calibrating:
                lines.append((f"EYE calibrating... look at the camera {eye.calibration_progress * 100:.0f}%", CYAN))
            else:
                lines.append((f"EYE {eye.state.value}  contact {eye.eye_contact_ratio * 100:.0f}%"
                              f"  gaze {eye.gaze_offset:.2f}" + ("" if eye.calibrated else "  (uncalibrated: K)"), ecol))
                lines.append((f"   away now {eye.current_away_s:.1f}s  events {eye.away_events}"
                              f"  longest {eye.longest_away_s:.1f}s", WHITE))
            if head.valid:
                lines.append((f"HEAD yaw {head.yaw:+.0f} pitch {head.pitch:+.0f} roll {head.roll:+.0f}  "
                              f"{'FACING' if head.facing_camera else 'OFF-AXIS'}",
                              GREEN if head.facing_camera else AMBER))
        else:
            lines.append(("EYE / HEAD: waiting for verified candidate", GREY))

        lines.append((f"cam {stats.cam_fps:.0f} fps  ai {stats.ai_fps:.0f} fps  "
                      f"mp {fr.mediapipe_ms:.0f} ms  loop {fr.ai_ms:.0f} ms", GREY))

    fs, lh = 0.5 * s, int(22 * s)
    tw = max(cv2.getTextSize(t, FONT, fs, 1)[0][0] for t, _ in lines)
    _shade(img, 6, 6, 6 + tw + 20, 12 + lh * len(lines) + 4)
    y = 8 + lh
    for t, c in lines:
        _text(img, t, 14, y, c, fs)
        y += lh

    # blocking banner
    if cand.status in BLOCKING and snap.state != SessionState.IDLE:
        msg = {
            CandidateStatus.MULTIPLE_FACES_DETECTED: "MULTIPLE FACES - ANALYSIS BLOCKED",
            CandidateStatus.DIFFERENT_PERSON_DETECTED: "DIFFERENT PERSON - ANALYSIS BLOCKED",
            CandidateStatus.CANDIDATE_NOT_DETECTED: "CANDIDATE NOT DETECTED",
        }[cand.status]
        bs = 0.8 * s
        (bw, bh), _ = cv2.getTextSize(msg, FONT, bs, 2)
        bx, by = (w - bw) // 2, int(h * 0.12) + bh
        _shade(img, bx - 14, by - bh - 12, bx + bw + 14, by + 14, 0.65)
        _text(img, msg, bx, by, STATUS_COLOR[cand.status], bs, 2)

    if snap.state == SessionState.COMPLETED:
        msg = "INTERVIEW COMPLETED  -  R: new session   Q: quit"
        bs = 0.7 * s
        (bw, bh), _ = cv2.getTextSize(msg, FONT, bs, 2)
        bx, by = (w - bw) // 2, h // 2
        _shade(img, bx - 16, by - bh - 14, bx + bw + 16, by + 16, 0.7)
        _text(img, msg, bx, by, CYAN, bs, 2)

    if toast:
        ts_ = 0.6 * s
        (tw2, th2), _ = cv2.getTextSize(toast, FONT, ts_, 2)
        tx, ty = (w - tw2) // 2, int(h * 0.82)
        _shade(img, tx - 12, ty - th2 - 10, tx + tw2 + 12, ty + 12, 0.65)
        _text(img, toast, tx, ty, WHITE, ts_, 2)

    help_s = 0.42 * s
    help_txt = "SPACE start/pause/resume  C complete  R reset  K eye-calibrate  L lock  H hud  Q quit"
    _shade(img, 0, h - int(26 * s), w, h, 0.5)
    _text(img, help_txt, 10, h - int(8 * s), GREY, help_s)


# ================================================================== the runtime
class NexHireRuntime:
    def __init__(self, cfg: Optional[RuntimeConfig] = None, tracker_cfg: Optional[TrackerConfig] = None) -> None:
        self.cfg = cfg or RuntimeConfig()
        self.tracker_cfg = tracker_cfg or TrackerConfig()

        # Each model object exists exactly once for the whole run.
        self.mp_service = MediaPipeFaceService(max_faces=self.cfg.max_faces)
        self.identity = CandidateIdentityManager()
        self.liveness = LivenessDetector()
        self.tracker = CandidateTracker(self.identity, self.liveness, self.tracker_cfg)
        self.eye = EyeContactAnalyzer()
        self.head_est = HeadPoseEstimator()
        self.session = InterviewSessionController(self.cfg.session_duration_s)

        self.metrics = SessionMetrics()
        self.results = ResultHolder()
        self.buffer = LatestFrameBuffer()
        self.worker: Optional[AIWorker] = None
        self.cam_fps = FpsMeter()
        self.timings = InitTimings()

        self._cap: Optional[cv2.VideoCapture] = None
        self._events: "queue.SimpleQueue[Tuple[SessionState, SessionState]]" = queue.SimpleQueue()
        self._report_providers: Dict[str, Callable[[], Dict[str, Any]]] = {"vision": self._vision_report}
        self._toast, self._toast_until = "", 0.0
        self._show_details = True
        self._report_printed = False
        self.session.add_listener(lambda old, new: self._events.put((old, new)))   # light: queue only

    # -------------------------------------------------- extension point (Whisper)
    def register_report_provider(self, name: str, provider: Callable[[], Dict[str, Any]]) -> None:
        """A future audio/Whisper worker adds its metrics to the final report here."""
        self._report_providers[name] = provider

    # ------------------------------------------------------------------ startup
    def _open_camera(self) -> Tuple[cv2.VideoCapture, np.ndarray]:
        cfg = self.cfg
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if platform.system() == "Windows" else [cv2.CAP_ANY]
        cap = None
        for backend in backends:
            cand = cv2.VideoCapture(cfg.camera_index, backend)
            if cand.isOpened():
                cap = cand
                break
            cand.release()
        if cap is None:
            raise RuntimeError(f"Could not open camera index {cfg.camera_index}.")
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))   # usually unlocks 30 fps at 720p
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.cam_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.cam_height)
        cap.set(cv2.CAP_PROP_FPS, cfg.cam_fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        frame = None
        for _ in range(60):                                              # cameras need a moment to deliver
            ok, f = cap.read()
            if ok and f is not None and f.size:
                frame = f
                break
            time.sleep(0.05)
        if frame is None:
            cap.release()
            raise RuntimeError("Camera opened but delivered no frames.")
        return cap, frame

    def _init_models_and_camera(self) -> Tuple[cv2.VideoCapture, np.ndarray]:
        """MediaPipe and InsightFace load concurrently while the camera opens (all timed)."""
        cfg, tm = self.cfg, self.timings
        warm_h = max(2, int(round(cfg.ai_width * cfg.cam_height / float(cfg.cam_width))))

        def init_mediapipe() -> float:
            t0 = time.perf_counter()
            self.mp_service.initialize()
            try:    # warm-up: first inference is slower; keep it out of the live loop
                self.mp_service.detect_face(np.zeros((warm_h, cfg.ai_width, 3), np.uint8), 0)
            except Exception as exc:
                log.debug("MediaPipe warm-up skipped: %s", exc)
            return time.perf_counter() - t0

        def init_insightface() -> float:
            t0 = time.perf_counter()
            self.identity.load()          # raises if insightface/onnxruntime is missing
            try:
                self.identity.generate_embedding(np.zeros((160, 160, 3), np.uint8))   # warm-up
            except Exception as exc:
                log.debug("InsightFace warm-up skipped: %s", exc)
            return time.perf_counter() - t0

        t_all = time.perf_counter()
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="init") as pool:
            f_mp, f_if = pool.submit(init_mediapipe), pool.submit(init_insightface)
            cam_err: Optional[Exception] = None
            cap = frame = None
            t_cam = time.perf_counter()
            try:
                cap, frame = self._open_camera()
            except Exception as exc:
                cam_err = exc
            tm.camera_s = time.perf_counter() - t_cam
            try:
                tm.mediapipe_s = f_mp.result()
            except MediaPipeServiceError as exc:
                raise RuntimeError(f"MediaPipe failed: {exc}") from exc
            try:
                tm.insightface_s = f_if.result()
            except Exception as exc:
                raise RuntimeError(
                    f"InsightFace failed to load ({exc}). Install with: pip install insightface onnxruntime"
                ) from exc
        tm.total_wall_s = time.perf_counter() - t_all
        if cam_err is not None:
            raise cam_err
        within = "within" if tm.total_wall_s <= cfg.init_budget_s else "OVER"
        log.info(
            "\nModel initialization:\n"
            "  MediaPipe  : %.2f sec\n"
            "  InsightFace: %.2f sec\n"
            "  Camera open: %.2f sec\n"
            "  Total      : %.2f sec (wall clock, loaded in parallel) - %s the %.0f s target on this machine\n"
            "  (first run also downloads model files; later runs are the representative number)",
            tm.mediapipe_s, tm.insightface_s, tm.camera_s, tm.total_wall_s, within, cfg.init_budget_s,
        )
        return cap, frame

    # --------------------------------------------------------------- run / loop
    def run(self) -> int:
        cv2.setNumThreads(max(1, self.cfg.opencv_threads))
        try:
            self._cap, first = self._init_models_and_camera()
        except Exception as exc:
            log.error("Startup failed: %s", exc)
            self._shutdown()
            return 1

        h, w = first.shape[:2]
        ai_w = min(self.cfg.ai_width, w)
        ai_h = max(2, int(round(ai_w * h / float(w) / 2.0)) * 2)
        log.info("Camera %dx%d, AI frame %dx%d, target cam %d fps / AI %.0f fps",
                 w, h, ai_w, ai_h, self.cfg.cam_fps, self.cfg.ai_fps)

        self.worker = AIWorker(self.cfg, self.buffer, self.mp_service, self.tracker, self.eye,
                               self.head_est, self.session, self.metrics, self.results, (ai_w, ai_h))
        self.session.set_ready()
        self.worker.start()

        disp_w = min(self.cfg.display_width, w)
        disp_h = int(round(h * disp_w / float(w)))
        hud_stats = HudStats(max_faces=self.cfg.max_faces, manual_lock=not self.tracker_cfg.auto_lock,
                             require_liveness=self.tracker_cfg.require_liveness)
        cv2.namedWindow(self.cfg.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.cfg.window_name, disp_w, disp_h)

        t0 = time.monotonic()
        failures, shown = 0, False
        try:
            while True:
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    failures += 1
                    if failures > 60:
                        log.error("Camera stopped delivering frames.")
                        break
                    time.sleep(0.01)
                    continue
                failures = 0
                if self.cfg.mirror:
                    frame = cv2.flip(frame, 1)
                self.cam_fps.tick()
                # `frame` is published and never modified afterwards; HUD draws on a copy.
                self.buffer.put(frame, int((time.monotonic() - t0) * 1000))

                self._drain_session_events()
                fr = self.results.get()
                hud_stats.cam_fps, hud_stats.ai_fps = self.cam_fps.fps, self.worker.fps.fps
                display = (cv2.resize(frame, (disp_w, disp_h), interpolation=cv2.INTER_AREA)
                           if disp_w != w else frame.copy())
                toast = self._toast if time.monotonic() < self._toast_until else ""
                draw_hud(display, fr, self.session.snapshot(), hud_stats, toast, self._show_details)
                cv2.imshow(self.cfg.window_name, display)

                key = cv2.waitKey(1) & 0xFF
                if key != 255 and not self._handle_key(key, fr):
                    break
                if shown and cv2.getWindowProperty(self.cfg.window_name, cv2.WND_PROP_VISIBLE) < 1:
                    break
                shown = True
        except KeyboardInterrupt:
            log.info("Interrupted.")
        finally:
            self._finish()
            self._shutdown()
        return 0

    # ------------------------------------------------------------------- keys
    def _flash(self, msg: str, secs: float = 2.5) -> None:
        self._toast, self._toast_until = msg, time.monotonic() + secs

    def _handle_key(self, key: int, fr: FrameResult) -> bool:
        if key in (ord("q"), ord("Q"), 27):
            return False
        if key == ord(" "):
            st = self.session.state
            if st == SessionState.READY:
                self._start_session(fr)
            elif st == SessionState.RUNNING:
                self.session.pause()
            elif st == SessionState.PAUSED:
                self.session.resume()
            else:
                self._flash("Press R to start a new session.")
        elif key in (ord("c"), ord("C")):
            if not self.session.complete():
                self._flash("Nothing to complete (session not running).")
        elif key in (ord("r"), ord("R")):
            self._reset_all()
        elif key in (ord("k"), ord("K")):
            if fr.analysis_active:
                with self.worker.lock:
                    self.eye.start_calibration()
                self._flash("Calibrating: look straight at the camera and hold still...", 3.5)
            else:
                self._flash("Calibration needs a locked, verified candidate.")
        elif key in (ord("l"), ord("L")):
            self.tracker.request_lock()
            self._flash("Lock requested (needs exactly one face and finished enrollment).")
        elif key in (ord("h"), ord("H")):
            self._show_details = not self._show_details
        return True

    def _start_session(self, fr: FrameResult) -> None:
        if not fr.candidate.analysis_allowed:
            self._flash("Cannot start: candidate must be locked and verified.")
            return
        with self.worker.lock:              # statistics cover the interview only
            self.eye.reset_session_stats()
            self.metrics.reset()
        if not self.session.start():
            self._flash("Session could not be started.")

    def _reset_all(self) -> None:
        with self.worker.lock:
            self.worker.reset_analysis()
            self.tracker.reset()            # explicit user action: forget the locked identity
            self.metrics.reset()
        self.session.reset()
        self.session.set_ready()
        self.results.clear()
        self._report_printed = False
        self._flash("Reset. Waiting for a candidate.")

    # ----------------------------------------------------------------- reports
    def _drain_session_events(self) -> None:
        while True:
            try:
                old, new = self._events.get_nowait()
            except queue.Empty:
                return
            log.info("Session %s -> %s", old.value, new.value)
            if new == SessionState.COMPLETED:
                self._emit_report("Session completed")

    def _vision_report(self) -> Dict[str, Any]:
        fr = self.results.get()
        cand = fr.candidate
        return {
            "analysis": self.metrics.to_dict(),
            "eye_contact": {k: (round(v, 3) if isinstance(v, float) else v)
                            for k, v in asdict(self.eye.summary()).items()},
            "candidate": {
                "locked": cand.locked,
                "last_status": cand.status.value,
                "last_similarity": None if cand.similarity is None else round(cand.similarity, 3),
            },
            "liveness": {
                "last_status": cand.liveness.status.value,
                "blink_count": cand.liveness.blink_count,
                "note": "heuristic only, not production anti-spoofing",
            },
        }

    def build_report(self) -> Dict[str, Any]:
        snap = self.session.snapshot()
        report: Dict[str, Any] = {
            "session": {"state": snap.state.value, "duration_s": snap.duration_s,
                        "elapsed_s": round(snap.elapsed_s, 1)},
            "startup": {k: round(v, 2) for k, v in asdict(self.timings).items()},
            "runtime": {"camera_fps": round(self.cam_fps.fps, 1),
                        "ai_fps": round(self.worker.fps.fps, 1) if self.worker else 0.0},
        }
        for name, provider in self._report_providers.items():
            try:
                if self.worker is not None:
                    with self.worker.lock:
                        report[name] = provider()
                else:
                    report[name] = provider()
            except Exception as exc:
                log.error("Report provider '%s' failed: %s", name, exc)
        return report

    def _emit_report(self, why: str) -> None:
        if self._report_printed:
            return
        self._report_printed = True
        report = self.build_report()
        text = json.dumps(report, indent=2, default=str)
        log.info("%s - report:\n%s", why, text)
        if self.cfg.report_path:
            try:
                Path(self.cfg.report_path).write_text(text, encoding="utf-8")
                log.info("Report written to %s", self.cfg.report_path)
            except OSError as exc:
                log.error("Could not write report: %s", exc)

    def _finish(self) -> None:
        self._drain_session_events()
        try:
            if self.session.snapshot().elapsed_s > 0:
                self._emit_report("Exit")
        except Exception as exc:
            log.debug("Final report skipped: %s", exc)

    # ---------------------------------------------------------------- shutdown
    def _shutdown(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker.join(timeout=2.0)
        for closer in (self.tracker.close, self.mp_service.close):
            try:
                closer()
            except Exception as exc:
                log.debug("Shutdown error: %s", exc)
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        cv2.destroyAllWindows()
        log.info("NexHire stopped.")


# ====================================================================== CLI
def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NexHire - mock interview vision runtime")
    p.add_argument("--camera", type=int, default=0, help="camera index")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--cam-fps", type=int, default=30)
    p.add_argument("--ai-width", type=int, default=480)
    p.add_argument("--ai-fps", type=float, default=20.0)
    p.add_argument("--duration", type=float, default=600.0, help="interview length in seconds")
    p.add_argument("--no-mirror", action="store_true", help="disable selfie mirroring")
    p.add_argument("--manual-lock", action="store_true", help="lock only when L is pressed")
    p.add_argument("--require-liveness", action="store_true", help="block analysis unless liveness is LIVE")
    p.add_argument("--report", default=None, help="write the final JSON report to this path")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = RuntimeConfig(
        camera_index=args.camera, cam_width=args.width, cam_height=args.height, cam_fps=args.cam_fps,
        ai_width=args.ai_width, ai_fps=args.ai_fps, mirror=not args.no_mirror,
        session_duration_s=args.duration, report_path=args.report,
    )
    tracker_cfg = TrackerConfig(auto_lock=not args.manual_lock, require_liveness=args.require_liveness)
    return NexHireRuntime(cfg, tracker_cfg).run()


if __name__ == "__main__":
    sys.exit(main())