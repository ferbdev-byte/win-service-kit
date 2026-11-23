"""Dòng lệnh: run / install / uninstall / status / xml."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import tempfile

from . import __version__
from .backoff import Backoff
from .supervisor import Supervisor
from .task import install, status, task_xml, uninstall


def _split(argv: list[str]) -> tuple[list[str], list[str]]:
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1 :]
    return argv, []


def main(argv: list[str] | None = None) -> int:
    own, command = _split(list(sys.argv[1:] if argv is None else argv))
    p = argparse.ArgumentParser(prog="winservice", description="Giữ một lệnh chạy 24/24 trên Windows.")
    p.add_argument("--version", action="version", version=f"winservice {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="chạy và giám sát lệnh sau dấu --")
    r.add_argument("--log", help="file log (xoay vòng 5 MB × 5)")
    r.add_argument("--cwd")
    r.add_argument("--health-url", help="URL trả 2xx khi ứng dụng khoẻ")
    r.add_argument("--max-restarts", type=int, default=10)

    for name in ("install", "xml"):
        i = sub.add_parser(name, help="cài tác vụ khởi động" if name == "install" else "in XML tác vụ")
        i.add_argument("--name", required=True, help="tên tác vụ, vd. MayChu\\DongBo")
        i.add_argument("--user", help="chạy dưới tài khoản này thay vì SYSTEM")
        i.add_argument("--at-logon", action="store_true", help="chạy khi người dùng đăng nhập")
        i.add_argument("--highest", action="store_true", help="chạy với quyền cao nhất")
        i.add_argument("--log")
        i.add_argument("--cwd")

    for name in ("uninstall", "status"):
        sub.add_parser(name).add_argument("--name", required=True)

    args = p.parse_args(own)

    if args.cmd == "run":
        if not command:
            p.error("cần lệnh sau dấu --, vd. winservice run -- python app.py")
        sup = Supervisor(command, args.log, args.cwd, Backoff(max_restarts=args.max_restarts), args.health_url)
        signal.signal(signal.SIGINT, lambda *_: sup.stop())
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, lambda *_: sup.stop())
        return sup.run()

    if args.cmd in ("install", "xml"):
        if not command:
            p.error("cần lệnh sau dấu --")
        xml = task_xml(args.name, command, args.cwd, args.user, args.at_logon, args.highest, args.log)
        if args.cmd == "xml":
            print(xml)
            return 0
        path = os.path.join(tempfile.gettempdir(), "winservice-task.xml")
        return install(args.name, xml, path)

    return uninstall(args.name) if args.cmd == "uninstall" else status(args.name)


if __name__ == "__main__":
    sys.exit(main())
