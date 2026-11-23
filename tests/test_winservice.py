import sys
import threading
import time
import xml.etree.ElementTree as ET

from winservice import Backoff, Supervisor, task_xml
from winservice.cli import main

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def test_backoff_grows_and_caps():
    b = Backoff(base=1, factor=2, cap=5, max_restarts=100)
    delays = [b.next_delay(ran_for=0.1, now=i) for i in range(5)]
    assert delays == [1, 2, 4, 5, 5]


def test_backoff_resets_after_stable_run():
    b = Backoff(base=1, factor=2, stable_after=60, max_restarts=100)
    b.next_delay(0.1, 0)
    b.next_delay(0.1, 1)
    assert b.next_delay(ran_for=120, now=200) == 1


def test_backoff_gives_up_on_crash_loop():
    b = Backoff(max_restarts=3, window=60)
    results = [b.next_delay(0.1, now=i) for i in range(5)]
    assert results[:3] != [None] * 3 and results[-1] is None


def test_backoff_window_forgets_old_crashes():
    b = Backoff(max_restarts=2, window=10)
    b.next_delay(0.1, 0)
    b.next_delay(0.1, 1)
    assert b.next_delay(0.1, 100) is not None


def test_supervisor_restarts_then_gives_up(tmp_path):
    log = tmp_path / "svc.log"
    sleeps = []
    sup = Supervisor(
        [sys.executable, "-c", "import sys; print('xin chào'); sys.exit(3)"],
        log_file=log,
        backoff=Backoff(max_restarts=2, window=600),
        sleep=sleeps.append,
    )
    code = sup.run()
    assert code == 3
    assert sup.restarts == 2
    assert sleeps == [1.0, 2.0]
    text = log.read_text(encoding="utf-8")
    assert "xin chào" in text and "bỏ cuộc" in text


def test_supervisor_stop(tmp_path):
    sup = Supervisor([sys.executable, "-c", "import time; time.sleep(30)"], log_file=tmp_path / "a.log")
    t = threading.Thread(target=sup.run)
    t.start()
    time.sleep(1)
    sup.stop()
    t.join(timeout=10)
    assert not t.is_alive()
    assert sup.restarts == 0


def test_supervisor_bad_command(tmp_path):
    sup = Supervisor(["khong-co-lenh-nay-xyz"], log_file=tmp_path / "a.log")
    assert sup.run() == 127


def test_task_xml_boot_system():
    xml = task_xml("MayChu\\DongBo", ["winsync", "watch", "-c", "C:/cfg file.json"], python="C:/Py/pythonw.exe")
    root = ET.fromstring(xml.split("?>", 1)[1])
    assert root.find("t:Triggers/t:BootTrigger", NS) is not None
    assert root.find("t:Principals/t:Principal/t:UserId", NS).text == "S-1-5-18"
    args = root.find("t:Actions/t:Exec/t:Arguments", NS).text
    assert args.startswith("-m winservice run -- winsync watch")
    assert '"C:/cfg file.json"' in args
    assert root.find("t:Settings/t:ExecutionTimeLimit", NS).text == "PT0S"


def test_task_xml_logon_user():
    xml = task_xml("X", ["app.exe"], user="MAYCHU\\cuong", at_logon=True, highest=True, workdir="C:/App")
    root = ET.fromstring(xml.split("?>", 1)[1])
    assert root.find("t:Triggers/t:LogonTrigger/t:UserId", NS).text == "MAYCHU\\cuong"
    assert root.find("t:Principals/t:Principal/t:RunLevel", NS).text == "HighestAvailable"
    assert root.find("t:Actions/t:Exec/t:WorkingDirectory", NS).text == "C:/App"


def test_cli_xml(capsys):
    assert main(["xml", "--name", "Demo", "--", "python", "app.py"]) == 0
    assert "<BootTrigger>" in capsys.readouterr().out
