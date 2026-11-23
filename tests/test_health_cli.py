import http.server
import sys
import threading

import pytest

from winservice import Backoff, Supervisor
from winservice.cli import _split, main
from winservice.supervisor import http_ok


class _Handler(http.server.BaseHTTPRequestHandler):
    status = 200

    def do_GET(self):  # noqa: N802 - tên do http.server quy định
        self.send_response(self.status)
        self.end_headers()

    def log_message(self, *args):  # im lặng khi chạy test
        pass


@pytest.fixture
def server():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()


def test_http_ok(server):
    url = f"http://127.0.0.1:{server.server_port}/health"
    _Handler.status = 200
    assert http_ok(url)
    _Handler.status = 503
    assert not http_ok(url)
    assert not http_ok("http://127.0.0.1:9/khong-co", timeout=0.5)


def test_unhealthy_process_is_restarted(tmp_path, server):
    _Handler.status = 503
    clock = iter(float(i) for i in range(10_000))
    sup = Supervisor(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        log_file=tmp_path / "svc.log",
        backoff=Backoff(max_restarts=0, window=600),
        health_url=f"http://127.0.0.1:{server.server_port}/",
        health_interval=1,
        health_failures=2,
        clock=lambda: next(clock),
        sleep=lambda _s: None,
    )
    sup.run()
    assert "kiểm tra sức khoẻ thất bại" in (tmp_path / "svc.log").read_text(encoding="utf-8")


def test_split_args():
    assert _split(["run", "--log", "a.log", "--", "python", "app.py"]) == (["run", "--log", "a.log"], ["python", "app.py"])
    assert _split(["status", "--name", "X"]) == (["status", "--name", "X"], [])


@pytest.mark.parametrize("argv", [["run"], ["install", "--name", "X"], ["xml", "--name", "X"]])
def test_cli_requires_command(argv):
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 2


def test_cli_run_reports_exit_code(tmp_path):
    log = str(tmp_path / "a.log")
    code = main(["run", "--log", log, "--max-restarts", "0", "--", sys.executable, "-c", "raise SystemExit(4)"])
    assert code == 4
