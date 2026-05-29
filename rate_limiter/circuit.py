"""Per-process circuit breaker for Redis failures."""

from __future__ import annotations

import time
from collections import deque
from enum import Enum
from threading import Lock


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        failure_window_sec: float = 10.0,
        open_duration_sec: float = 30.0,
        success_threshold: int = 3,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.failure_window_sec = failure_window_sec
        self.open_duration_sec = open_duration_sec
        self.success_threshold = success_threshold
        self._state = CircuitState.CLOSED
        self._failures: deque[float] = deque()
        self._success_streak = 0
        self._opened_at: float | None = None
        self._half_open_probe_in_flight = False
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_from_open()
            return self._state

    def allow_request(self) -> bool:
        with self._lock:
            self._maybe_transition_from_open()
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                return False
            # HALF_OPEN: one probe at a time
            if self._half_open_probe_in_flight:
                return False
            self._half_open_probe_in_flight = True
            return True

    def record_success(self) -> None:
        with self._lock:
            self._half_open_probe_in_flight = False
            if self._state == CircuitState.HALF_OPEN:
                self._success_streak += 1
                if self._success_streak >= self.success_threshold:
                    self._reset()
            elif self._state == CircuitState.CLOSED:
                self._failures.clear()

    def record_failure(self) -> None:
        with self._lock:
            self._half_open_probe_in_flight = False
            now = time.monotonic()
            if self._state == CircuitState.HALF_OPEN:
                self._trip(now)
                return
            self._failures.append(now)
            self._prune_failures(now)
            if len(self._failures) >= self.failure_threshold:
                self._trip(now)

    def _maybe_transition_from_open(self) -> None:
        if self._state != CircuitState.OPEN or self._opened_at is None:
            return
        if time.monotonic() - self._opened_at >= self.open_duration_sec:
            self._state = CircuitState.HALF_OPEN
            self._success_streak = 0
            self._half_open_probe_in_flight = False

    def _trip(self, now: float) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = now
        self._success_streak = 0
        self._half_open_probe_in_flight = False

    def _reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failures.clear()
        self._opened_at = None
        self._success_streak = 0
        self._half_open_probe_in_flight = False

    def _prune_failures(self, now: float) -> None:
        while self._failures and now - self._failures[0] > self.failure_window_sec:
            self._failures.popleft()
