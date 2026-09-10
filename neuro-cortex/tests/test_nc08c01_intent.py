"""NC-08C.0.1 Intent conflict tests."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from neurocortex.perception.intent_router import detect_coarse_intent

CASES = [
    ("检查代码质量", "review"),
    ("帮我检查一下代码质量，看看有没有问题", "review"),
    ("检查这个文件", "read"),
    ("检查并修复 bug", "fix"),
    ("写一个代码检查工具", "create"),
    ("分析这段代码", "review"),
    ("审查代码", "review"),
    ("修复这个 bug", "fix"),
    ("写一个 Python 函数", "create"),
]


def test_intent_conflict_table():
    for text, expected in CASES:
        got = detect_coarse_intent(text)
        assert got == expected, f"{text!r} → {got!r}, expected {expected!r}"


def test_politeness_prefix_not_create():
    assert detect_coarse_intent("帮我检查这个文件") == "read"
    assert detect_coarse_intent("请审查代码") == "review"
