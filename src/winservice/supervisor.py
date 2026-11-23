"""Giám sát tiến trình: chạy, ghi log xoay vòng, bật lại khi chết, kiểm tra sức khoẻ qua HTTP."""

from __future__ import annotations

import logging
import subprocess
import threading
import time
import urllib.request
from collections.abc import Callable, Sequence
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import IO

from .backoff import Backoff


def _pipe_to_log(stream: IO[bytes], logger: logging.Logger, level: int) -> None:
    for raw in iter(stream.readline, b""):
        logger.log(level, raw.decode("utf-8", errors="replace").rstrip())
    stream.close()


def http_ok(url: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 - URL do người cấu hình đưa vào
            return bool(200 <= r.status < 400)
    except Exception:
        return False


class Supervisor:
    def __init__(
        self,
        command: Sequence[str],
        log_file: str | Path | None = None,
        cwd: str | Path | None = None,
        backoff: Backoff | None = None,
        health_url: str | None = None,
        health_interval: float = 30.0,
        health_failures: int = 3,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.command = list(command)
        self.cwd = cwd
        self.backoff = backoff or Backoff()
        self.health_url = health_url
        self.health_interval = health_interval
        self.health_failures = health_failures
        self.clock, self.sleep = clock, sleep
        self.restarts = 0
        self._stop = threading.Event()
        self._proc: subprocess.Popen[bytes] | None = None

        self.log = logging.getLogger(f"winservice.{id(self)}")
        self.log.setLevel(logging.INFO)
        self.log.propagate = False
        handler: logging.Handler
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(log_file, maxBytes=5 * 2**20, backupCount=5, encoding="utf-8")
        else:
            handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.log.addHandler(handler)

    def stop(self) -> None:
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def _run_once(self) -> int:
        self._proc = subprocess.Popen(
            self.command, cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL
        )
        threads = [
            threading.Thread(target=_pipe_to_log, args=(self._proc.stdout, self.log, logging.INFO), daemon=True),
            threading.Thread(target=_pipe_to_log, args=(self._proc.stderr, self.log, logging.WARNING), daemon=True),
        ]
        for t in threads:
            t.start()
        fails, last_check = 0, self.clock()
        while self._proc.poll() is None:
            if self._stop.wait(0.2):
                break
            if self.health_url and self.clock() - last_check >= self.health_interval:
                last_check = self.clock()
                fails = 0 if http_ok(self.health_url) else fails + 1
                if fails >= self.health_failures:
                    self.log.error("kiểm tra sức khoẻ thất bại %d lần liên tiếp, khởi động lại", fails)
                    self._proc.kill()
        code = self._proc.wait()
        for t in threads:
            t.join(timeout=2)
        return code

    def run(self) -> int:
        """Chạy cho tới khi `stop()` hoặc tiến trình chết quá nhiều lần. Trả về mã thoát cuối."""
        code = 0
        while not self._stop.is_set():
            started = self.clock()
            self.log.info("khởi chạy: %s", " ".join(self.command))
            try:
                code = self._run_once()
            except FileNotFoundError as exc:
                self.log.error("không chạy được lệnh: %s", exc)
                return 127
            if self._stop.is_set():
                self.log.info("đã dừng theo yêu cầu")
                break
            delay = self.backoff.next_delay(self.clock() - started, self.clock())
            if delay is None:
                self.log.critical("tiến trình chết quá nhiều lần trong %.0fs, bỏ cuộc", self.backoff.window)
                return code or 1
            self.restarts += 1
            self.log.warning("tiến trình thoát với mã %s, bật lại sau %.0fs", code, delay)
            self.sleep(delay)
        return code
