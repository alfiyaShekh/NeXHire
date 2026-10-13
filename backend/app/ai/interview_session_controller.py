"""
interview_session_controller.py

Interview session STATE and TIMER only.

States: IDLE -> READY -> RUNNING <-> PAUSED -> COMPLETED

It knows nothing about faces, identity, liveness, MediaPipe, InsightFace, audio or
Whisper. Other components observe it through snapshot() or add_listener().
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    IDLE = "IDLE"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class SessionSnapshot:
    state: SessionState
    duration_s: float
    elapsed_s: float
    remaining_s: float


class InterviewSessionController:
    def __init__(self, duration_s: float = 600.0) -> None:
        if duration_s <= 0:
            raise ValueError("duration_s must be positive")
        self.duration_s = float(duration_s)
        self._lock = threading.RLock()
        self._listeners: List[Callable[[SessionState, SessionState], None]] = []
        self._state = SessionState.IDLE
        self._elapsed_before_s = 0.0
        self._run_started_at = 0.0

    # --------------------------------------------------------------- observers
    def add_listener(self, callback: Callable[[SessionState, SessionState], None]) -> None:
        """callback(old_state, new_state) - invoked after every state change."""
        with self._lock:
            self._listeners.append(callback)

    def _set_state(self, new_state: SessionState) -> None:
        old = self._state
        self._state = new_state
        for cb in list(self._listeners):
            try:
                cb(old, new_state)
            except Exception as exc:
                logger.error("Session listener error: %s", exc)

    # ------------------------------------------------------------------- state
    @property
    def state(self) -> SessionState:
        self._auto_complete()
        return self._state

    def _elapsed_unlocked(self) -> float:
        elapsed = self._elapsed_before_s
        if self._state == SessionState.RUNNING:
            elapsed += time.monotonic() - self._run_started_at
        return min(elapsed, self.duration_s)

    def _auto_complete(self) -> None:
        with self._lock:
            if self._state == SessionState.RUNNING and self._elapsed_unlocked() >= self.duration_s:
                self._elapsed_before_s = self.duration_s
                self._set_state(SessionState.COMPLETED)

    # ----------------------------------------------------------------- actions
    def set_ready(self) -> bool:
        with self._lock:
            if self._state != SessionState.IDLE:
                return False
            self._set_state(SessionState.READY)
            return True

    def start(self) -> bool:
        with self._lock:
            if self._state != SessionState.READY:
                return False
            self._elapsed_before_s = 0.0
            self._run_started_at = time.monotonic()
            self._set_state(SessionState.RUNNING)
            return True

    def pause(self) -> bool:
        self._auto_complete()
        with self._lock:
            if self._state != SessionState.RUNNING:
                return False
            self._elapsed_before_s = self._elapsed_unlocked()
            self._set_state(SessionState.PAUSED)
            return True

    def resume(self) -> bool:
        with self._lock:
            if self._state != SessionState.PAUSED:
                return False
            self._run_started_at = time.monotonic()
            self._set_state(SessionState.RUNNING)
            return True

    def complete(self) -> bool:
        self._auto_complete()
        with self._lock:
            if self._state not in (SessionState.RUNNING, SessionState.PAUSED):
                return False
            self._elapsed_before_s = self._elapsed_unlocked()
            self._set_state(SessionState.COMPLETED)
            return True

    def reset(self) -> None:
        with self._lock:
            self._elapsed_before_s = 0.0
            self._run_started_at = 0.0
            if self._state != SessionState.IDLE:
                self._set_state(SessionState.IDLE)

    # ------------------------------------------------------------------ timing
    def elapsed_seconds(self) -> float:
        self._auto_complete()
        with self._lock:
            return self._elapsed_unlocked()

    def remaining_seconds(self) -> float:
        return max(0.0, self.duration_s - self.elapsed_seconds())

    def snapshot(self) -> SessionSnapshot:
        self._auto_complete()
        with self._lock:
            elapsed = self._elapsed_unlocked()
            return SessionSnapshot(
                state=self._state,
                duration_s=self.duration_s,
                elapsed_s=elapsed,
                remaining_s=max(0.0, self.duration_s - elapsed),
            )

    @property
    def is_running(self) -> bool:
        return self.state == SessionState.RUNNING
