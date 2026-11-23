import sys

import pytest

from winservice import Supervisor, task_xml
from winservice.cli import main, parse_env


def test_parse_env():
    assert parse_env(["PORT=8765", "URL=a=b"]) == {"PORT": "8765", "URL": "a=b"}
    with pytest.raises(SystemExit):
        parse_env(["THIEU_DAU_BANG"])


def test_env_reaches_child(tmp_path):
    log = tmp_path / "a.log"
    from winservice import Backoff

    sup = Supervisor([sys.executable, "-c", "import os; print('PORT=' + os.environ['PORT']); raise SystemExit(0)"],
                     log_file=log, backoff=Backoff(max_restarts=0), env={"PORT": "8765"})
    sup.run()
    assert "PORT=8765" in log.read_text(encoding="utf-8")


def test_env_in_task_xml(capsys):
    xml = task_xml("X", ["python", "app.py"], env={"PORT": "8765"}, python="C:/Py/pythonw.exe")
    assert "--env PORT=8765 -- python app.py" in xml
    assert main(["xml", "--name", "X", "--env", "MODE=prod", "--", "app.exe"]) == 0
    assert "--env MODE=prod" in capsys.readouterr().out
