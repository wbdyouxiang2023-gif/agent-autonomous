"""NC-08C.7 — Context-Aware Situation Classifier V3.

Fixes the bug where "查看代码结构" was incorrectly classified as file_read.
Uses context-aware pattern matching with priority rules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass



@dataclass
class ClassificationResult:
    task_type: str | None
    action: str | None
    confidence: float
    reason: str
    is_ambiguous: bool = False


# ── Pattern Priority Rules ───────────────────────────────────────────
# Order matters: more specific patterns first.
# Each pattern: (regex, task_type, action, description)
_ZH_PATTERNS: list[tuple[re.Pattern, tuple[str, str], str]] = [
    # Code-related patterns (high priority) - must come before file patterns
    (re.compile(r"定位.*函数|定位.*符号|查找.*函数定义|搜索.*代码中的.*符号", re.I),
     ("code_locator", "search_files"), "locate function/symbol in code"),
    (re.compile(r"查看.*代码结构|分析.*代码结构|看看.*项目结构|检查.*代码组织|代码结构|代码目录结构", re.I),
     ("code_inspect", "search_files"), "inspect code structure"),
    (re.compile(r"查看.*项目架构|项目架构|代码架构", re.I),
     ("code_inspect", "search_files"), "inspect project architecture"),
    (re.compile(r"检查.*代码质量|审查.*代码|分析.*代码.*问题|code.*quality|代码质量", re.I),
     ("code_check", "terminal"), "check code quality"),
    (re.compile(r"搜索.*代码|查找.*源码|grep.*code|search.*source|源码.*查找", re.I),
     ("code_search", "search_files"), "search in code"),
    (re.compile(r"看看.*函数|分析.*代码|代码.*分析|代码.*检查", re.I),
     ("code_inspect", "search_files"), "inspect code"),
    
    # File operation patterns
    (re.compile(r"读取.*文件内容|打开.*文件|cat.*文件|看.*文件内容|文件.*内容", re.I),
     ("file_read", "read_file"), "read file content"),
    (re.compile(r"创建.*文件|新建.*文件|生成.*文件|写入.*文件", re.I),
     ("file_create", "write_file"), "create file"),
    (re.compile(r"搜索.*文件|查找.*文件|找.*文件|grep.*file|文件.*搜索", re.I),
     ("file_search", "search_files"), "search files"),
    
    # System info patterns
    (re.compile(r"获取.*版本|查看.*系统信息|运行.*命令|执行.*命令|系统.*信息", re.I),
     ("info_extract", "terminal"), "get system info"),
    (re.compile(r"检查.*磁盘|查看.*存储|df|du|磁盘.*检查", re.I),
     ("disk_check", "terminal"), "check disk"),
    (re.compile(r"检查.*内存|查看.*内存|内存.*检查", re.I),
     ("memory_check", "terminal"), "check memory"),
    (re.compile(r"进程.*列表|查看.*进程|进程.*检查", re.I),
     ("process_check", "terminal"), "check processes"),
    (re.compile(r"网络.*连接|检查.*网络|网络.*检查", re.I),
     ("network_check", "terminal"), "check network"),
    (re.compile(r"系统.*状态|系统.*检查|状态.*检查|系统负载", re.I),
     ("info_extract", "terminal"), "check system status"),
    (re.compile(r"获取.*时间|当前时间|时间.*获取", re.I),
     ("info_extract", "terminal"), "get time"),
    (re.compile(r"运行.*测试|测试.*套件|pytest", re.I),
     ("test_run", "terminal"), "run tests"),
    (re.compile(r"诊断.*命令|诊断.*测试|诊断", re.I),
     ("info_extract", "terminal"), "run diagnostics"),
    
    # Fix patterns
    (re.compile(r"修复.*bug|debug|解决.*错误|修.*故障|bug.*修复", re.I),
     ("fix", "read_file"), "fix bug"),
    
    # Create patterns
    (re.compile(r"写一个.*函数|创建一个.*程序|build.*app|开发.*应用", re.I),
     ("create", "write_file"), "create program"),
]

# Fallback patterns (lower priority)
_FALLBACK_PATTERNS: list[tuple[re.Pattern, tuple[str, str], str]] = [
    (re.compile(r"搜索|查找|找\b", re.I), ("file_search", "search_files"), "search general"),
    (re.compile(r"读取|打开|查看|看\b", re.I), ("file_read", "read_file"), "read general"),
]


def _is_short_ambiguous(text: str) -> bool:
    """Check if input is too short/vague to classify reliably."""
    # Short inputs without specific keywords are ambiguous
    if len(text) < 6:
        return True
    # Inputs ending with 一下/看看 but with specific context are OK
    if text.rstrip().endswith("一下") or text.rstrip().endswith("看看"):
        # But if there's a specific object, don't mark as ambiguous
        specific = ["代码", "文件", "函数", "项目", "符号", "配置", "日志"]
        if any(s in text for s in specific):
            return False
        return True
    # Very generic patterns without specific objects
    generic = ["检查", "查看", "搜索", "读取", "分析"]
    match_count = sum(1 for g in generic if g in text)
    # If only generic verbs and no specific objects, might be ambiguous
    if match_count > 0 and len(text) < 10:
        specific = ["代码", "文件", "函数", "项目", "符号", "配置", "日志", "结构", "质量"]
        if not any(s in text for s in specific):
            return True
    return False


def _classify_context_aware(situation: str) -> ClassificationResult:
    """Context-aware classification with priority rules."""
    if not situation or not situation.strip():
        return ClassificationResult(None, None, 0.0, "empty input")
    
    text = situation.strip()
    
    # Check if input is ambiguous
    if _is_short_ambiguous(text):
        return ClassificationResult(None, None, 0.3, "ambiguous input", is_ambiguous=True)
    
    # Check high-priority patterns first
    for pat, (tt, act), desc in _ZH_PATTERNS:
        if pat.search(text):
            # Additional context validation
            confidence = _compute_confidence(text, tt, act)
            return ClassificationResult(tt, act, confidence, f"matched: {desc}")
    
    # Check fallback patterns
    for pat, (tt, act), desc in _FALLBACK_PATTERNS:
        if pat.search(text):
            confidence = _compute_confidence(text, tt, act)
            # Mark as ambiguous if confidence is low
            is_ambiguous = confidence < 0.5
            return ClassificationResult(tt, act, confidence, f"fallback: {desc}", is_ambiguous)
    
    return ClassificationResult(None, None, 0.0, "no match")


def _compute_confidence(text: str, task_type: str, action: str) -> float:
    """Compute confidence based on context clues."""
    confidence = 0.5  # Base confidence
    
    # Boost for specific keywords
    if task_type == "code_locator":
        if any(kw in text for kw in ["函数", "符号", "定位", "定义"]):
            confidence = max(confidence, 0.9)
    elif task_type == "code_inspect":
        if any(kw in text for kw in ["结构", "组织", "查看", "分析"]):
            confidence = max(confidence, 0.85)
    elif task_type == "file_read":
        if any(kw in text for kw in ["读取", "打开", "内容"]):
            confidence = max(confidence, 0.85)
    elif task_type == "file_search":
        if any(kw in text for kw in ["搜索", "查找", "找"]):
            confidence = max(confidence, 0.8)
    
    # Penalize ambiguous cases
    if "帮我" in text or "请" in text:
        confidence = min(confidence, 0.7)
    
    return confidence


def classify_to_task_type(situation: str) -> tuple[str, str] | None:
    """Main entry point: returns (task_type, action) or None."""
    result = _classify_context_aware(situation)
    if result.task_type and result.confidence >= 0.5:
        return (result.task_type, result.action)
    return None


def classify_with_details(situation: str) -> ClassificationResult:
    """Return full classification result with confidence and reason."""
    return _classify_context_aware(situation)
