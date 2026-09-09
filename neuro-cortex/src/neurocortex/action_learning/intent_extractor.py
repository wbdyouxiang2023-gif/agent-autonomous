"""IntentExtractor — deterministic, rule-based task-intent extraction.

Level 5.0-R1: upgrades Situation intent from "tool name" to "task intent".

Principles
----------
1. intent describes WHAT the user/agent wants to accomplish, never WHICH
   tool was used.
2. tool_name is NEVER used as intent (explicitly forbidden).
3. When intent cannot be inferred reliably → return None / "unknown".
   No guessing.
4. No use of execution outcome / success / failure / action_type to infer
   intent (no data leakage).
5. Deterministic, explainable, unit-testable, no network, no model.

Layers
------
L1 — task verbs/patterns   (check disk → disk_check)
L2 — object recognition    (config/disk/file/code/test/service)
L3 — compose canonical intent (verb + object)
L4 — fallback → unknown/None
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

# ── Layer 1: task verb patterns (regex → canonical verb) ───────────────
VERB_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(check|inspect|look|examine|查看|检查|看)\w*\b", re.I), "inspect"),
    (re.compile(r"\b(read|open|cat|view|show|print|读取|打开|查看内容)\w*\b", re.I), "read"),
    (re.compile(r"\b(search|find|grep|locate|搜索|查找|找)\w*\b", re.I), "search"),
    (re.compile(r"\b(run|execute|launch|执行|运行|跑)\w*\b", re.I), "run"),
    (re.compile(r"\b(restart|reboot|重启)\w*\b", re.I), "restart"),
    (re.compile(r"\b(stop|停止)\w*\b", re.I), "stop"),
    (re.compile(r"\b(start|启动)\w*\b", re.I), "start"),
    (re.compile(r"\b(list|ls|dir|列出|列举)\w*\b", re.I), "list"),
    (re.compile(r"\b(create|make|新建|创建|建立)\w*\b", re.I), "create"),
    (re.compile(r"\b(delete|remove|rm|删除|移除)\w*\b", re.I), "delete"),
    (re.compile(r"\b(install|装|安装)\w*\b", re.I), "install"),
    (re.compile(r"\b(update|upgrade|更新|升级)\w*\b", re.I), "update"),
    (re.compile(r"\b(copy|cp|复制)\w*\b", re.I), "copy"),
    (re.compile(r"\b(move|mv|移动)\w*\b", re.I), "move"),
    (re.compile(r"\b(set|configure|配置|设置)\w*\b", re.I), "configure"),
]

# ── Layer 2: object patterns (regex → canonical object) ────────────────
OBJECT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(config|configuration|配置|settings)\w*\b", re.I), "config"),
    (re.compile(r"\b(disk|storage|磁盘|存储|空间)\w*\b", re.I), "disk"),
    (re.compile(r"\b(file|document|文件|文档|档案)\w*\b", re.I), "file"),
    (re.compile(r"\b(code|source|源码|代码|工程)\w*\b", re.I), "code"),
    (re.compile(r"\b(test|tests|测试|用例)\w*\b", re.I), "test"),
    (re.compile(r"\b(service|daemon|服务|进程)\w*\b", re.I), "service"),
    (re.compile(r"\b(memory|ram|内存)\w*\b", re.I), "memory"),
    (re.compile(r"\b(network|net|网络)\w*\b", re.I), "network"),
    (re.compile(r"\b(process|proc|进程)\w*\b", re.I), "process"),
    (re.compile(r"\b(user|用户)\w*\b", re.I), "user"),
    (re.compile(r"\b(host|主机|hostname)\w*\b", re.I), "host"),
    (re.compile(r"\b(package|pkg|包)\w*\b", re.I), "package"),
    (re.compile(r"\b(system|系统|os|kernel)\w*\b", re.I), "system"),
    (re.compile(r"\b(uptime|负载)\w*\b", re.I), "uptime"),
    (re.compile(r"\b(time|date|时间|日期)\w*\b", re.I), "time"),
    (re.compile(r"\b(log|日志|syslog)\w*\b", re.I), "log"),
    (re.compile(r"\b(path|路径|pwd|cwd)\w*\b", re.I), "path"),
    (re.compile(r"\b(echo|输出)\w*\b", re.I), "echo"),
    (re.compile(r"\b(src|source|目录)\w*\b", re.I), "code"),
    (re.compile(r"\b(README|readme|md|txt)\b", re.I), "file"),
]

# ── Layer 3: canonical intent composition ──────────────────────────────
# (verb, object) → canonical intent
_CANONICAL: dict[tuple[str, str], str] = {
    ("inspect", "disk"): "disk_check",
    ("check", "disk"): "disk_check",
    ("read", "disk"): "disk_check",
    ("inspect", "file"): "file_inspect",
    ("read", "file"): "file_read",
    ("check", "file"): "file_inspect",
    ("search", "file"): "file_search",
    ("find", "file"): "file_search",
    ("list", "file"): "file_list",
    ("search", "code"): "code_search",
    ("find", "code"): "code_search",
    ("inspect", "code"): "code_inspect",
    ("read", "config"): "config_read",
    ("inspect", "config"): "config_read",
    ("check", "config"): "config_check",
    ("read", "test"): "test_read",
    ("run", "test"): "test_run",
    ("execute", "test"): "test_run",
    ("restart", "service"): "service_restart",
    ("stop", "service"): "service_stop",
    ("start", "service"): "service_start",
    ("read", "memory"): "memory_check",
    ("inspect", "memory"): "memory_check",
    ("check", "memory"): "memory_check",
    ("read", "network"): "network_check",
    ("check", "network"): "network_check",
    ("check", "process"): "process_check",
    ("list", "process"): "process_list",
    ("list", "user"): "user_list",
    ("install", "package"): "package_install",
    ("update", "package"): "package_update",
    ("configure", "config"): "config_edit",
    ("create", "file"): "file_create",
    ("delete", "file"): "file_delete",
    ("list", "file"): "file_list",
    ("read", "file"): "file_read",
    ("read", "host"): "host_check",
    ("read", "system"): "system_check",
    ("list", "host"): "host_list",
    ("check", "host"): "host_check",
    ("check", "system"): "system_check",
    ("search", "file"): "file_search",
    ("list", "disk"): "disk_list",
    ("check", "uptime"): "uptime_check",
    ("read", "uptime"): "uptime_check",
    ("read", "time"): "time_check",
    ("check", "memory"): "memory_check",
    ("list", "memory"): "memory_list",
    ("count", "file"): "file_count",
    ("search", "package"): "package_search",
    ("read", "user"): "user_query",
    ("check", "user"): "user_query",
    ("inspect", "host"): "host_check",
    ("check", "host"): "host_check",
    ("read", "host"): "host_check",
    ("inspect", "user"): "user_query",
    ("check", "file"): "file_inspect",
    ("read", "log"): "log_read",
    ("check", "log"): "log_check",
    ("read", "path"): "path_query",
    ("list", "path"): "path_list",
    ("inspect", "system"): "system_check",
    ("check", "system"): "system_check",
    ("read", "system"): "system_check",
    ("inspect", "uptime"): "uptime_check",
    ("check", "uptime"): "uptime_check",
    ("inspect", "time"): "time_check",
    ("check", "time"): "time_check",
    ("read", "time"): "time_check",
    ("inspect", "log"): "log_check",
    ("check", "log"): "log_check",
    ("inspect", "echo"): "echo_task",
    ("check", "echo"): "echo_task",
    ("inspect", "path"): "path_query",
    ("check", "path"): "path_query",
    ("inspect", "code"): "code_inspect",
    ("check", "code"): "code_check",
}

# Reverse lookup for (canonical → (verb, object)) used in explainability
_CANONICAL_REV: dict[str, tuple[str, str]] = {v: k for k, v in _CANONICAL.items()}


@dataclass(frozen=True)
class IntentResult:
    intent: str | None
    confidence: float
    source: str = "rule"
    matched_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "matched_patterns": list(self.matched_patterns),
        }


class IntentExtractor:
    """Deterministic rule-based task intent extraction (no model, no network)."""

    def __init__(self) -> None:
        pass

    def extract(self, raw_input: str) -> IntentResult:
        """Extract canonical intent from raw task text.

        Returns IntentResult with intent=None when uncertain.
        NEVER returns tool names as intent.
        """
        if not raw_input or not raw_input.strip():
            return IntentResult(intent=None, confidence=0.0, matched_patterns=["empty"])

        # Hard exclusions: patterns where we must NOT guess intent
        if re.search(r"\b(ssh|rsync|scp|git|curl|wget)\b", raw_input, re.I):
            return IntentResult(intent=None, confidence=0.0, matched_patterns=["excluded:remote/network-cmd"])

        text = self._normalize_input(raw_input)

        # ── Layer 1: find verb(s) ──────────────────────────────────
        verbs: list[str] = []
        matched_v: list[str] = []
        # Chinese verbs are substring matches (no word boundary in CJK)
        zh_verbs = [
            ("搜索", "search"), ("查找", "search"), ("找", "search"),
            ("检查", "inspect"), ("查看", "inspect"), ("看", "inspect"),
            ("读取", "read"), ("打开", "read"), ("读", "read"),
            ("运行", "run"), ("执行", "run"), ("重启", "restart"), ("停止", "stop"),
            ("列出", "list"), ("创建", "create"), ("删除", "delete"),
        ]
        for zh, verb in zh_verbs:
            if zh in text:
                verbs.append(verb)
                matched_v.append(f"verb:{verb}")
        for pat, verb in VERB_PATTERNS:
            if pat.search(text):
                verbs.append(verb)
                matched_v.append(f"verb:{verb}")

        # ── Layer 2: find object(s) ────────────────────────────────
        objects: list[str] = []
        matched_o: list[str] = []
        zh_objs = [
            ("配置", "config"), ("配置文件", "config"),
            ("磁盘", "disk"), ("存储", "disk"), ("空间", "disk"),
            ("文件", "file"), ("文档", "file"),
            ("代码", "code"), ("源码", "code"), ("工程", "code"),
            ("测试", "test"), ("服务", "service"), ("进程", "process"),
            ("内存", "memory"), ("网络", "network"), ("用户", "user"),
        ]
        for zh, obj in zh_objs:
            if zh in text:
                objects.append(obj)
                matched_o.append(f"obj:{obj}")
        for pat, obj in OBJECT_PATTERNS:
            if pat.search(text):
                objects.append(obj)
                matched_o.append(f"obj:{obj}")

        # ── Layer 3: compose canonical intent ──────────────────────
        # Priority: code-related combos first (code > file for source search)
        for verb in verbs:
            if verb == "search" and "code" in objects:
                return IntentResult(
                    intent="code_search", confidence=0.9,
                    matched_patterns=matched_v + matched_o,
                )
        for verb in verbs:
            for obj in objects:
                key = (verb, obj)
                if key in _CANONICAL:
                    return IntentResult(
                        intent=_CANONICAL[key],
                        confidence=0.9,
                        matched_patterns=matched_v + matched_o,
                    )
                # Try reversed (object before verb is unusual but possible)
                key_r = (obj, verb)
                if key_r in _CANONICAL:
                    return IntentResult(
                        intent=_CANONICAL[key_r],
                        confidence=0.85,
                        matched_patterns=matched_v + matched_o,
                    )

        # Single-object fallbacks (no verb)
        single_obj = {
            "echo": "echo_task",
            "code": "code_search",
            "file": "file_search",
        }
        if not verbs and objects:
            for obj in objects:
                if obj in single_obj:
                    return IntentResult(
                        intent=single_obj[obj], confidence=0.5,
                        matched_patterns=matched_o,
                    )

        # ── Layer 4: verb only (no object) → generic intent ────────
        if verbs:
            return IntentResult(
                intent=f"{verbs[0]}_task",
                confidence=0.4,
                matched_patterns=matched_v,
            )

        # Object only → inspection-ish generic
        if objects:
            return IntentResult(
                intent=f"{objects[0]}_query",
                confidence=0.4,
                matched_patterns=matched_o,
            )

        return IntentResult(intent=None, confidence=0.0, matched_patterns=[])

    @staticmethod
    def _normalize_input(raw: str) -> str:
        """Normalize raw_input: extract from JSON wrapper, add command-name
        hints (ls→list, df→disk, cat→read, whoami→user, ...) so that
        JSON-style tool args still produce meaningful intent."""
        text = raw.strip()

        # Try JSON unwrap first
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                parts = []
                has_pattern = False
                for key in ("command", "cmd", "path", "pattern", "query", "input"):
                    v = obj.get(key)
                    if v and isinstance(v, str) and v.strip():
                        # Strip home-dir prefixes to avoid path 'user' false match
                        cleaned = re.sub(r"^/home/[^/]+/", "", v)
                        parts.append(cleaned)
                        if key in ("pattern", "query"):
                            has_pattern = True
                if not parts:
                    # Empty JSON payload (all fields empty) → no signal
                    return ""
                text = " ".join(parts)
                # pattern/query fields imply a search task
                if has_pattern:
                    text += " search"
                # target: content/files implies searching code/files
                tgt = obj.get("target")
                if tgt == "content":
                    text += " code"
                if obj.get("output_mode") == "files_only":
                    text += " file"
        except (ValueError, TypeError):
            pass  # not JSON, use as-is

        # Command-name hints (works on both plain and JSON-extracted text)
        cmd_hints = [
            (r"\bcat\b", "read"),
            (r"\bls\b", "list file"),
            (r"\bdf\b", "check disk"),
            (r"\bdu\b", "check disk"),
            (r"\blsblk\b", "check disk"),
            (r"\bwhoami\b", "check user"),
            (r"\bid\b", "check user"),
            (r"\bhostname\b", "check host"),
            (r"\bfree\b", "check memory"),
            (r"\buptime\b", "check uptime"),
            (r"\bdate\b", "check time"),
            (r"\buname\b", "check system"),
            (r"\bfind\b", "search file"),
            (r"\bgrep\b", "search file"),
            (r"\bhead\b", "read"),
            (r"\btail\b", "read"),
            (r"\bwc\b", "count file"),
            (r"\bhosts\b", "check host"),
            (r"\bpasswd\b", "check user"),
            (r"\bconfig\b", "config"),
            (r"\bos-release\b", "check system"),
            (r"\bsystemctl\b", "service"),
            (r"\bpytest\b", "run test"),
            (r"\bnpm test\b", "run test"),
            (r"\bproc\b", "check system"),
            (r"\bsyslog\b", "log"),
            (r"\bapp\.log\b", "log"),
        ]
        for pat_str, hint in cmd_hints:
            if re.search(pat_str, text, re.I):
                text += f" {hint}"

        return text


# Convenience singleton
_extractor = IntentExtractor()


def extract_intent(raw_input: str) -> IntentResult:
    """Module-level convenience."""
    return _extractor.extract(raw_input)
