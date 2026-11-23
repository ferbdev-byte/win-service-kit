"""Tạo và cài tác vụ Task Scheduler để winservice tự chạy khi máy khởi động.

Dùng Task Scheduler thay vì Windows Service thật: không cần quyền viết service, không cần pywin32,
và chạy được dưới tài khoản người dùng (giữ được ổ mạng, rclone.conf, đăng nhập Google...).
"""

from __future__ import annotations

import os
import subprocess
import sys
from xml.sax.saxutils import escape

TEMPLATE = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{description}</Description>
    <URI>\\{name}</URI>
  </RegistrationInfo>
  <Triggers>
    <{trigger}>
      <Enabled>true</Enabled>{user_trigger}
      <Delay>PT30S</Delay>
    </{trigger}>
  </Triggers>
  <Principals>
    <Principal id="Author">
      {principal}
      <RunLevel>{run_level}</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>5</Priority>
    <RestartOnFailure><Interval>PT1M</Interval><Count>999</Count></RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{command}</Command>
      <Arguments>{arguments}</Arguments>{workdir}
    </Exec>
  </Actions>
</Task>
"""


def _quote(arg: str) -> str:
    return f'"{arg}"' if (" " in arg or not arg) else arg


def task_xml(
    name: str,
    command: list[str],
    workdir: str | None = None,
    user: str | None = None,
    at_logon: bool = False,
    highest: bool = False,
    log_file: str | None = None,
    python: str | None = None,
) -> str:
    """XML cho schtasks: chạy `winservice run -- <command>` khi khởi động (hoặc khi đăng nhập)."""
    python = python or sys.executable.replace("python.exe", "pythonw.exe")
    sup_args = ["-m", "winservice", "run"]
    if log_file:
        sup_args += ["--log", log_file]
    if workdir:
        sup_args += ["--cwd", workdir]
    sup_args += ["--", *command]
    if user:
        logon = "InteractiveToken" if at_logon else "S4U"  # S4U: chạy cả khi chưa đăng nhập, không lưu mật khẩu
        principal = f"<UserId>{escape(user)}</UserId>\n      <LogonType>{logon}</LogonType>"
    else:
        principal = "<UserId>S-1-5-18</UserId>"  # SYSTEM
    return TEMPLATE.format(
        name=escape(name),
        description=escape(f"winservice: {' '.join(command)}"),
        trigger="LogonTrigger" if at_logon else "BootTrigger",
        user_trigger=f"\n      <UserId>{escape(user)}</UserId>" if (at_logon and user) else "",
        principal=principal,
        run_level="HighestAvailable" if highest else "LeastPrivilege",
        command=escape(python),
        arguments=escape(" ".join(_quote(a) for a in sup_args)),
        workdir=f"\n      <WorkingDirectory>{escape(workdir)}</WorkingDirectory>" if workdir else "",
    )


def _schtasks(*args: str) -> int:
    if os.name != "nt":
        raise OSError("schtasks chỉ có trên Windows")
    return subprocess.run(["schtasks", *args], check=False).returncode


def install(name: str, xml: str, path: str) -> int:
    with open(path, "w", encoding="utf-16") as f:
        f.write(xml)
    return _schtasks("/Create", "/TN", name, "/XML", path, "/F")


def uninstall(name: str) -> int:
    return _schtasks("/Delete", "/TN", name, "/F")


def status(name: str) -> int:
    return _schtasks("/Query", "/TN", name, "/V", "/FO", "LIST")
