"""Chờ tăng dần giữa các lần bật lại, và phát hiện vòng chết liên tục."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class Backoff:
    base: float = 1.0
    factor: float = 2.0
    cap: float = 300.0
    stable_after: float = 60.0      # chạy được lâu hơn chừng này thì coi là ổn, đặt lại độ chờ
    max_restarts: int = 10          # quá số lần này trong `window` giây thì bỏ cuộc
    window: float = 600.0
    _attempt: int = 0
    _history: deque = field(default_factory=deque)

    def next_delay(self, ran_for: float, now: float) -> float | None:
        """Gọi sau mỗi lần tiến trình thoát. Trả về số giây cần chờ, hoặc None nếu nên dừng hẳn."""
        if ran_for >= self.stable_after:
            self._attempt = 0
        self._history.append(now)
        while self._history and now - self._history[0] > self.window:
            self._history.popleft()
        if len(self._history) > self.max_restarts:
            return None
        delay = min(self.cap, self.base * self.factor**self._attempt)
        self._attempt += 1
        return delay
