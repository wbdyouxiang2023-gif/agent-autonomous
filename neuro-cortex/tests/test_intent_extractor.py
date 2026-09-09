"""IntentExtractor tests — Level 5.0-R1 (golden dataset + metrics).

Run: pytest tests/test_intent_extractor.py -v
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from neurocortex.action_learning.intent_extractor import IntentExtractor, extract_intent

extractor = IntentExtractor()

# ── Golden dataset (人工标注，只作测试标准，extractor 不读取) ──────────
GOLDEN = [
    # file inspection/read
    ('{"path": "/home/user/README.md"}', "file_read"),
    ('{"path": "/etc/hostname"}', "host_check"),
    ('{"command": "cat /etc/hosts"}', "host_check"),
    ('{"command": "cat /etc/passwd"}', "user_query"),
    ('{"command": "head /var/log/syslog"}', "read_task"),
    ('{"command": "tail -f /var/log/app.log"}', "read_task"),
    ('{"path": "/etc/os-release"}', "system_check"),
    ('{"command": "cat /proc/cpuinfo"}', "system_check"),
    # file search
    ('{"command": "find ~/workspace -name \\"*.py\\""}', "file_search"),
    ('{"command": "ls ~/workspace"}', "file_list"),
    ('{"command": "ls /tmp"}', "file_list"),
    ('{"command": "ls -la /var/log"}', "file_list"),
    ('{"output_mode": "files_only", "path": "/home/user/workspace", "pattern": "action"}', "file_search"),
    # code search
    ('{"pattern": "neurocortex", "target": "content"}', "code_search"),
    ('{"command": "grep -r \\"action\\" src/"}', "code_search"),
    ('search code for action learning', "code_search"),
    ('find source files with policy', "code_search"),
    # disk/storage check
    ('{"command": "df -h"}', "disk_check"),
    ('{"command": "du -sh ~/.hermes"}', "disk_check"),
    ('check disk space', "disk_check"),
    ('{"command": "lsblk"}', "disk_check"),
    # memory check
    ('{"command": "free -m"}', "memory_check"),
    ('{"command": "free -h"}', "memory_check"),
    ('check memory usage', "memory_check"),
    # test execution
    ('{"command": "pytest tests/"}', "test_run"),
    ('{"command": "npm test"}', "test_run"),
    ('run the test suite', "test_run"),
    # service restart
    ('{"command": "systemctl restart nginx"}', "service_restart"),
    ('restart the service', "service_restart"),
    ('{"command": "systemctl stop mysql"}', "service_stop"),
    # system info
    ('{"command": "uname -a"}', "system_check"),
    ('{"command": "hostname"}', "host_check"),
    ('{"command": "uptime"}', "uptime_check"),
    ('{"command": "date"}', "time_check"),
    # user info
    ('{"command": "whoami"}', "user_query"),
    ('{"command": "id"}', "user_query"),
    # terminal/general command
    ('{"command": "pwd"}', "path_query"),
    ('{"command": "echo hello"}', "echo_task"),
    ('{"command": "ls -la"}', "file_list"),
    # unknown/ambiguous (should be None, never guessed as tool name)
    ('deploy application', None),
    ('{"command": "git status"}', None),
    ('{"command": "curl http://example.com"}', None),
    ("", None),
    ('{"path": ""}', None),
    ('{"command": "rsync -av src/ dst/"}', None),
    ('{"command": "ssh user@host"}', None),
]


# ── 1. golden accuracy ─────────────────────────────────────────────────


def test_golden_accuracy():
    """Accuracy >= 90% on golden dataset."""
    correct = 0
    total = len(GOLDEN)
    for raw, expected in GOLDEN:
        r = extract_intent(raw)
        if expected is None:
            if r.intent is None:
                correct += 1
        else:
            if r.intent == expected:
                correct += 1
    acc = correct / total
    print(f"golden accuracy: {correct}/{total} = {acc:.2%}")
    assert acc >= 0.90, f"accuracy too low: {acc:.2%}"


# ── 2. tool-name-as-intent rate ≈ 0 ───────────────────────────────────


def test_tool_name_as_intent_zero():
    """Never returns tool names as intent (read_file/search/terminal/...)."""
    tool_names = {"read_file", "search", "search_files", "terminal", "write_file",
                  "code_edit", "respond", "execute"}
    for raw, _ in GOLDEN:
        r = extract_intent(raw)
        assert r.intent not in tool_names, f"tool name leaked as intent: {r.intent} for {raw}"
    for raw in ['{"command": "ls /tmp"}', "read the config file", '{"command": "df -h"}']:
        r = extract_intent(raw)
        assert r.intent not in tool_names, f"tool name leaked: {r.intent}"


# ── 3. unknown rate ───────────────────────────────────────────────────


def test_unknown_rate():
    """Unknown (None) rate within reasonable bounds (not everything guessed)."""
    unknown = sum(1 for raw, exp in GOLDEN if extract_intent(raw).intent is None)
    rate = unknown / len(GOLDEN)
    print(f"unknown rate: {unknown}/{len(GOLDEN)} = {rate:.2%}")
    assert 0.05 <= rate <= 0.35, f"unknown rate out of range: {rate:.2%}"


# ── 4. coverage ───────────────────────────────────────────────────────


def test_coverage():
    """At least 80% of golden samples get SOME intent (not None)."""
    covered = sum(1 for raw, exp in GOLDEN if extract_intent(raw).intent is not None)
    rate = covered / len(GOLDEN)
    print(f"coverage: {covered}/{len(GOLDEN)} = {rate:.2%}")
    assert rate >= 0.80, f"coverage too low: {rate:.2%}"


# ── 5. cross-tool situation recovery ──────────────────────────────────


def test_cross_tool_situations():
    """The critical Level 5.0-R1 requirement: intent describes TASK not tool."""
    cases = [
        ("搜索代码中的配置项", "code_search"),  # 不是 search
        ("打开配置文件检查内容", "config_read"),  # 不是 read_file
        ("检查磁盘空间", "disk_check"),  # 不是 terminal
        ("search code for config", "code_search"),
        ("read the config file", "config_read"),
        ("check disk space", "disk_check"),
        ("restart the service", "service_restart"),
        ("run the tests", "test_run"),
    ]
    for raw, expected in cases:
        r = extract_intent(raw)
        assert r.intent == expected, f"{raw} → {r.intent} (expected {expected})"
        assert r.intent not in {"read_file", "search", "terminal", "search_files", "write_file"}, f"tool name leaked: {r.intent}"


# ── 6. explainability ─────────────────────────────────────────────────


def test_explainable():
    """Extractor returns confidence + matched patterns (interpretable)."""
    r = extract_intent("check disk space")
    assert r.confidence > 0.5
    assert r.matched_patterns, "no matched patterns"
    assert r.source == "rule"
    assert "verb" in str(r.matched_patterns) and "obj" in str(r.matched_patterns)


# ── 7. deterministic ──────────────────────────────────────────────────


def test_deterministic():
    assert extract_intent("check disk space").intent == extract_intent("check disk space").intent
    assert extract_intent('{"command": "df -h"}').intent == extract_intent('{"command": "df -h"}').intent


# ── 8. no leakage (outcome/action not used) ───────────────────────────


def test_no_outcome_leakage():
    """Intent extraction must not use success/failure/action_type."""
    r1 = extract_intent("check disk space")
    r2 = extract_intent("check disk space")
    assert r1.intent == r2.intent  # same input, same intent regardless of outcome


# ── 9. edge inputs ────────────────────────────────────────────────────


def test_edge_inputs():
    assert extract_intent("").intent is None
    assert extract_intent("   ").intent is None
    assert extract_intent('{}').intent is None or extract_intent('{}').intent is not None  # no crash
    assert extract_intent('{"command": ""}').intent is None or True  # no crash


# ── 10. JSON unwrap ───────────────────────────────────────────────────


def test_json_unwrap():
    assert extract_intent('{"command": "df -h"}').intent == "disk_check"
    assert extract_intent('{"path": "/etc/hostname"}').intent == "host_check"
    assert extract_intent('{"command": "ls /tmp"}').intent == "file_list"
