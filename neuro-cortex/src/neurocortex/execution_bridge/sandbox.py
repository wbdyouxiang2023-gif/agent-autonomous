"""NC-08C.0.1 Sandbox Executor — real actions inside a TEST SANDBOX only.

Actions:
  read_file / write_file / search_files / terminal

Safety:
  - all filesystem writes stay under sandbox_root
  - path traversal rejected
  - terminal is allow-listed
  - never fakes a successful run
"""
from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import ActionRequest, ExecutionResult

ALLOWED_ACTIONS = ("read_file", "write_file", "search_files", "terminal")

_SAFE_PYTHON_C = re.compile(
    r"^python3\s+-c\s+(['\"])(print\([^)]*\)|import sys; print\(sys\.version\)|print\(\d+\)|import sys; print\(sys\.version\.split\(\)\[0\]\))\1$",
    re.I
)
_SAFE_CMDS = (
    re.compile(r"^python3\s+--version$"),
    re.compile(r"^python3\s+-V$"),
    re.compile(r"^echo\s+.+$"),
    re.compile(r"^ls(\s+[a-zA-Z0-9_./-]+)?$"),
    re.compile(r"^cat\s+[a-zA-Z0-9_./-]+$"),
    re.compile(r"^pwd$"),
    _SAFE_PYTHON_C,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SandboxExecutor:
    """Real executor constrained to a sandbox directory."""

    def __init__(self, sandbox_root: str | Path):
        self.root = Path(sandbox_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str | None) -> Path:
        raw = (path or "").strip() or "."
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise PermissionError(f"path outside sandbox: {path}") from exc
        return resolved

    def execute(self, request: ActionRequest) -> ExecutionResult:
        started = _now()
        eid = f"exec-{request.request_id}"
        action = request.action_type
        if action not in ALLOWED_ACTIONS:
            return ExecutionResult(
                execution_id=eid, request_id=request.request_id,
                action_type=action, tool_name=action,
                status="unsupported", success=None,
                error=f"unsupported action_type={action!r}",
                started_at=started, finished_at=_now(),
            )
        try:
            if action == "read_file":
                return self._read(request, eid, started)
            if action == "write_file":
                return self._write(request, eid, started)
            if action == "search_files":
                return self._search(request, eid, started)
            return self._terminal(request, eid, started)
        except PermissionError as exc:
            return ExecutionResult(
                execution_id=eid, request_id=request.request_id,
                action_type=action, tool_name=action,
                status="failure", success=False, error=str(exc),
                started_at=started, finished_at=_now(),
            )
        except Exception as exc:
            return ExecutionResult(
                execution_id=eid, request_id=request.request_id,
                action_type=action, tool_name=action,
                status="unknown", success=None, error=f"execution raised: {exc}",
                started_at=started, finished_at=_now(),
            )

    def _read(self, request: ActionRequest, eid: str, started: str) -> ExecutionResult:
        path = self.resolve(str(request.arguments.get("path", "")))
        if not path.exists() or not path.is_file():
            return ExecutionResult(
                execution_id=eid, request_id=request.request_id,
                action_type="read_file", tool_name="read_file",
                status="failure", success=False,
                error=f"File not found: {path}",
                started_at=started, finished_at=_now(),
            )
        text = path.read_text(encoding="utf-8")
        return ExecutionResult(
            execution_id=eid, request_id=request.request_id,
            action_type="read_file", tool_name="read_file",
            status="success", success=True, output=text[:8000],
            started_at=started, finished_at=_now(),
        )

    def _write(self, request: ActionRequest, eid: str, started: str) -> ExecutionResult:
        path = self.resolve(str(request.arguments.get("path", "")))
        content = request.arguments.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ExecutionResult(
            execution_id=eid, request_id=request.request_id,
            action_type="write_file", tool_name="write_file",
            status="success", success=True,
            output=f"wrote {len(content)} bytes to {path.name}",
            started_at=started, finished_at=_now(),
        )

    def _search(self, request: ActionRequest, eid: str, started: str) -> ExecutionResult:
        pattern = str(request.arguments.get("pattern", "")).strip()
        if not pattern:
            return ExecutionResult(
                execution_id=eid, request_id=request.request_id,
                action_type="search_files", tool_name="search_files",
                status="failure", success=False, error="empty pattern",
                started_at=started, finished_at=_now(),
            )
        hits: list[str] = []
        for dirpath, _, files in os.walk(self.root):
            for name in files:
                fpath = Path(dirpath) / name
                rel = str(fpath.relative_to(self.root))
                if pattern in name:
                    hits.append(rel)
                    continue
                try:
                    text = fpath.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if pattern in text:
                    hits.append(rel)
        output = "\n".join(hits)
        return ExecutionResult(
            execution_id=eid, request_id=request.request_id,
            action_type="search_files", tool_name="search_files",
            status="success", success=True, output=output,
            started_at=started, finished_at=_now(),
        )

    def _terminal(self, request: ActionRequest, eid: str, started: str) -> ExecutionResult:
        cmd = str(request.arguments.get("command", "")).strip()
        if not cmd or not any(p.match(cmd) for p in _SAFE_CMDS):
            return ExecutionResult(
                execution_id=eid, request_id=request.request_id,
                action_type="terminal", tool_name="terminal",
                status="failure", success=False,
                error=f"command not allow-listed: {cmd!r}",
                started_at=started, finished_at=_now(),
            )
        try:
            proc = subprocess.run(
                cmd, shell=True, cwd=str(self.root),
                capture_output=True, text=True, timeout=8, check=False,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                execution_id=eid, request_id=request.request_id,
                action_type="terminal", tool_name="terminal",
                status="unknown", success=None, error="timeout",
                started_at=started, finished_at=_now(),
            )
        ok = proc.returncode == 0
        return ExecutionResult(
            execution_id=eid, request_id=request.request_id,
            action_type="terminal", tool_name="terminal",
            status="success" if ok else "failure",
            success=ok,
            output=(proc.stdout or "")[:4000],
            error=(proc.stderr or "")[:1000],
            started_at=started, finished_at=_now(),
        )


def request_for_action(action_type: str, arguments: dict[str, Any],
                       request_id: str = "sandbox") -> ActionRequest:
    return ActionRequest(
        request_id=request_id,
        action_type=action_type,
        situation={"intent": action_type, "raw_input": action_type},
        tool_name=action_type,
        arguments=arguments or {},
    )
