"""Coarse task-intent router with explicit keyword conflict handling.

Used by BilingualPerception (server / mcp). Independent of IntentExtractor
(which produces fine-grained intents like file_read / code_search).

Conflict rules (first match among resolved scores, not raw keyword order):
  1. Strip politeness prefixes (帮我 / 请 / 麻烦) — they are NOT create signals.
  2. Fix beats review/check when a repair verb or bug is present.
  3. Strong create (写一个 / 创建 / 生成 / write a) beats nested 检查.
  4. 检查 + 文件 (no 代码质量) → read
  5. 检查/审查/分析 + 代码/质量 → review
"""
from __future__ import annotations

import re

_PREFIX_RE = re.compile(
    r"^(请你?|麻烦你?|拜托|帮忙|请帮我|帮我|请)\s*",
)

_CREATE_STRONG = (
    "写一个", "写一份", "写个", "写一篇",
    "创建一个", "创建", "新建", "生成", "实现", "开发",
    "write a", "create a", "build a", "make a",
)
_CREATE_WEAK = ("write", "create", "build", "make", "编写")

_FIX = (
    "fix", "debug", "bug", "修复", "修这个", "修好", "故障",
    "traceback", "exception",
)
_REVIEW = (
    "review", "审查", "代码质量", "分析这段", "分析代码",
    "analyze", "code quality", "质量",
)
_CHECK = ("检查", "check", "看看", "看一下")
_READ = ("读取", "read", "打开文件", "cat ", "第一行")
_FILE = ("文件", "file")
_CODE = ("代码", "code", "源码")
_EXPLAIN = (
    "what", "how", "explain", "介绍", "解释", "说明",
    "是什么", "为什么", "了解", "知道",
)
_DEPLOY = ("deploy", "部署", "上线", "发布")
_RUN = ("运行", "启动", "start", "run")
_OPTIMIZE = ("optimize", "improve", "优化", "加速", "性能", "提升")
_TEST = ("测试", "用例", "验证", "pytest", "unit test")


def _has(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _strip_prefix(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = _PREFIX_RE.sub("", text)
    return text.strip()


def detect_coarse_intent(text: str) -> str:
    """Return one of: explain/create/fix/review/read/deploy/optimize/test/general."""
    if not text or not str(text).strip():
        return "general"
    raw = text.strip()
    t = _strip_prefix(raw.lower())

    create_strong = _has(t, _CREATE_STRONG)
    create_weak = _has(t, _CREATE_WEAK)
    fix_hit = _has(t, _FIX)
    review_hit = _has(t, _REVIEW)
    check_hit = _has(t, _CHECK)
    read_hit = _has(t, _READ)
    file_hit = _has(t, _FILE)
    code_hit = _has(t, _CODE)
    explain_hit = _has(t, _EXPLAIN)
    deploy_hit = _has(t, _DEPLOY)
    run_hit = _has(t, _RUN)
    optimize_hit = _has(t, _OPTIMIZE)
    test_hit = _has(t, _TEST)

    quality_hit = "质量" in t or "quality" in t
    tool_object = any(x in t for x in ("工具", "脚本", "程序", "tool", "script"))

    if explain_hit and not (create_strong or fix_hit or review_hit or check_hit):
        return "explain"

    if fix_hit:
        return "fix"

    if create_strong:
        return "create"

    if review_hit or (check_hit and quality_hit):
        return "review"

    if check_hit and code_hit and not file_hit:
        return "review"

    if (check_hit or read_hit) and file_hit and not quality_hit:
        return "read"

    if check_hit and code_hit:
        return "review"

    if review_hit:
        return "review"

    if read_hit and not create_weak:
        return "read"

    if create_weak and not check_hit:
        return "create"

    if create_weak and tool_object:
        return "create"

    if deploy_hit or (run_hit and not test_hit and not check_hit):
        return "deploy"

    if optimize_hit:
        return "optimize"

    if test_hit:
        return "test"

    if explain_hit:
        return "explain"

    return "general"
