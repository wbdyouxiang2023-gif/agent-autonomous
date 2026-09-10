"""Task Verifier — execution_success is never sufficient for task_completed.

task_completed ∈ {True, False, None}
  True  — verifier confirmed the task goal
  False — verifier confirmed the goal was missed
  None  — unknown (no rule / insufficient evidence)

Never infers task_completed from ExecutionResult.success.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema import ExecutionResult


@dataclass(frozen=True)
class VerifyResult:
    task_completed: bool | None
    completion_source: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_completed": self.task_completed,
            "completion_source": self.completion_source,
            "reason": self.reason,
        }


class TaskVerifier:
    """Rule-based verifier against sandbox state + execution output."""

    def __init__(self, sandbox_root: str | Path):
        self.root = Path(sandbox_root).resolve()

    def verify(self, spec: dict[str, Any], result: ExecutionResult) -> VerifyResult:
        kind = spec.get("verify")
        args = spec.get("verify_args") or {}
        if not kind:
            return VerifyResult(None, "unknown", "no verifier rule")

        try:
            ok = self._run(kind, args, result)
        except Exception as exc:
            return VerifyResult(None, "task_verifier", f"verifier error: {exc}")

        if ok is None:
            return VerifyResult(None, "task_verifier", f"unknown rule={kind}")
        return VerifyResult(bool(ok), "task_verifier", kind)

    def _run(self, kind: str, args: dict[str, Any], result: ExecutionResult) -> bool | None:
        if kind == "file_exists":
            return self._path(args["path"]).is_file()
        if kind == "file_content_contains":
            path = self._path(args["path"])
            if not path.is_file():
                return False
            return str(args["needle"]) in path.read_text(encoding="utf-8")
        if kind == "first_line_equals":
            path = self._path(args["path"])
            if not path.is_file():
                return False
            text = path.read_text(encoding="utf-8")
            first = text.splitlines()[0] if text.splitlines() else ""
            expected = str(args["expected"])
            in_output = expected in (result.output or "")
            return first == expected and in_output
        if kind == "output_contains":
            needle = str(args["needle"])
            return needle in (result.output or "")
        if kind == "search_hit":
            needle = str(args.get("needle") or args.get("pattern") or "")
            out = result.output or ""
            return bool(out.strip()) and (needle in out if needle else True)
        if kind == "python_version":
            out = (result.output or "") + (result.error or "")
            return "Python" in out and any(ch.isdigit() for ch in out)
        return None

    def _path(self, rel: str) -> Path:
        p = Path(rel)
        if not p.is_absolute():
            p = self.root / p
        return p.resolve()
