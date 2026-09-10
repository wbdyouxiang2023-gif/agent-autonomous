"""NC-08C.0.1 real sandbox executor + verifier tests."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from neurocortex.execution_bridge.sandbox import SandboxExecutor, request_for_action
from neurocortex.execution_bridge.verifier import TaskVerifier
from neurocortex.event import OutcomeData


def test_write_then_read_real(tmp_path):
    ex = SandboxExecutor(tmp_path)
    wr = ex.execute(request_for_action("write_file", {"path": "a.txt", "content": "hello\nworld\n"}, "w1"))
    assert wr.success is True
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "hello\nworld\n"
    rd = ex.execute(request_for_action("read_file", {"path": "a.txt"}, "r1"))
    assert rd.success is True
    assert "hello" in rd.output


def test_missing_file_is_real_failure(tmp_path):
    ex = SandboxExecutor(tmp_path)
    rd = ex.execute(request_for_action("read_file", {"path": "missing.txt"}, "r2"))
    assert rd.success is False
    assert rd.status == "failure"


def test_path_escape_rejected(tmp_path):
    ex = SandboxExecutor(tmp_path)
    rd = ex.execute(request_for_action("read_file", {"path": "../etc/passwd"}, "r3"))
    assert rd.success is False


def test_search_files_real(tmp_path):
    ex = SandboxExecutor(tmp_path)
    ex.execute(request_for_action("write_file", {"path": "n.py", "content": "def foo():\n    return 1\n"}, "w2"))
    sr = ex.execute(request_for_action("search_files", {"pattern": "def foo"}, "s1"))
    assert sr.success is True
    assert "n.py" in sr.output


def test_terminal_python_version(tmp_path):
    ex = SandboxExecutor(tmp_path)
    tr = ex.execute(request_for_action("terminal", {"command": "python3 --version"}, "t1"))
    assert tr.success is True
    assert "Python" in (tr.output + tr.error)


def test_terminal_rejects_danger(tmp_path):
    ex = SandboxExecutor(tmp_path)
    tr = ex.execute(request_for_action("terminal", {"command": "rm -rf /"}, "t2"))
    assert tr.success is False


def test_success_does_not_imply_completion(tmp_path):
    ex = SandboxExecutor(tmp_path)
    vf = TaskVerifier(tmp_path)
    wr = ex.execute(request_for_action("write_file", {"path": "x.txt", "content": "aaa\n"}, "w3"))
    assert wr.success is True
    v = vf.verify({"verify": "first_line_equals", "verify_args": {"path": "x.txt", "expected": "zzz"}}, wr)
    assert v.task_completed is False
    od = OutcomeData(
        actual_outcome=wr.output, success=bool(wr.success),
        task_completed=v.task_completed, completion_source=v.completion_source,
    )
    assert od.success is True
    assert od.task_completed is False


def test_unknown_stays_none(tmp_path):
    ex = SandboxExecutor(tmp_path)
    vf = TaskVerifier(tmp_path)
    wr = ex.execute(request_for_action("write_file", {"path": "y.txt", "content": "z\n"}, "w4"))
    v = vf.verify({}, wr)
    assert v.task_completed is None
    od = OutcomeData(actual_outcome=wr.output, success=True, task_completed=v.task_completed)
    assert od.task_completed is None
