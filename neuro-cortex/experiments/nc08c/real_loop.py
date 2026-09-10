"""NC-08C.0.1 real closed-loop runner.

Situation → action → SandboxExecutor → Verifier → OutcomeData
Never infers task_completed from execution_success.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neurocortex.event import OutcomeData
from neurocortex.execution_bridge.sandbox import SandboxExecutor, request_for_action
from neurocortex.execution_bridge.verifier import TaskVerifier
from neurocortex.perception.intent_router import detect_coarse_intent

INTENT_ACTION = {
    "create": "write_file",
    "read": "read_file",
    "review": "search_files",
    "fix": "read_file",
    "explain": "read_file",
    "deploy": "terminal",
    "test": "terminal",
    "optimize": "read_file",
    "general": "read_file",
}


@dataclass
class LoopRecord:
    task_id: str
    raw_input: str
    intent: str
    action_type: str
    execution_success: bool | None
    task_completed: bool | None
    completion_source: str
    actual_outcome: str
    error_message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_task(spec: dict[str, Any], sandbox: Path, log_path: Path | None = None) -> LoopRecord:
    ex = SandboxExecutor(sandbox)
    vf = TaskVerifier(sandbox)
    raw = spec["raw_input"]
    intent = spec.get("intent") or detect_coarse_intent(raw)
    action = spec.get("action") or INTENT_ACTION.get(intent, "read_file")
    args = spec.get("arguments") or {}
    result = ex.execute(request_for_action(action, args, spec.get("task_id", "t")))
    verified = vf.verify(spec, result)
    outcome = OutcomeData(
        actual_outcome=result.output or result.error or result.status,
        success=bool(result.success) if result.success is not None else False,
        error_message=result.error,
        task_completed=verified.task_completed,
        completion_source=verified.completion_source,
    )
    rec = LoopRecord(
        task_id=spec.get("task_id") or uuid.uuid4().hex[:8],
        raw_input=raw,
        intent=intent,
        action_type=action,
        execution_success=result.success,
        task_completed=outcome.task_completed,
        completion_source=outcome.completion_source,
        actual_outcome=outcome.actual_outcome[:300],
        error_message=outcome.error_message,
    )
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            row = rec.to_dict()
            row["written_at"] = datetime.now(timezone.utc).isoformat()
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rec


def default_tasks() -> list[dict[str, Any]]:
    return [
        {
            "task_id": "TASK-01",
            "raw_input": "创建一个测试文件",
            "action": "write_file",
            "arguments": {"path": "hello.txt", "content": "alpha-line\nsecond\n"},
            "verify": "file_content_contains",
            "verify_args": {"path": "hello.txt", "needle": "alpha-line"},
        },
        {
            "task_id": "TASK-02",
            "raw_input": "读取 test.txt 并告诉我第一行内容",
            "action": "read_file",
            "arguments": {"path": "hello.txt"},
            "verify": "first_line_equals",
            "verify_args": {"path": "hello.txt", "expected": "alpha-line"},
        },
        {
            "task_id": "TASK-03",
            "raw_input": "搜索指定文件",
            "action": "search_files",
            "arguments": {"pattern": "alpha-line"},
            "verify": "search_hit",
            "verify_args": {"needle": "hello.txt"},
        },
        {
            "task_id": "TASK-04",
            "raw_input": "获取 Python 版本",
            "action": "terminal",
            "arguments": {"command": "python3 --version"},
            "verify": "python_version",
            "verify_args": {},
        },
        {
            "task_id": "TASK-05",
            "raw_input": "检查代码质量",
            "action": "search_files",
            "arguments": {"pattern": "def "},
            "verify": "search_hit",
            "verify_args": {"needle": "sample.py"},
        },
        {
            "task_id": "TASK-06",
            "raw_input": "执行一个安全 Python 测试",
            "action": "terminal",
            "arguments": {"command": "python3 -c 'print(1)'"},
            "verify": "output_contains",
            "verify_args": {"needle": "1"},
        },
    ]
