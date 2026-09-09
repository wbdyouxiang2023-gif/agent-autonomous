"""NC-08C.8 — Situation Classification V4 (Improved).

Builds on V3 with better context awareness and pattern prioritization.
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
    ambiguity_reason: str = ""


# ── Context-Aware Patterns ──────────────────────────────────────────
# Priority order: most specific first
_PATTERNS = [
    # Code locator (highest priority for code tasks)
    (re.compile(r"定位.*函数|定位.*符号|查找.*函数定义|函数.*定义.*位置|类.*定义.*位置", re.I),
     "code_locator", "search_files", "locate function/class definition"),
    (re.compile(r"查找.*符号.*位置|符号.*在.*代码", re.I),
     "code_locator", "search_files", "locate symbol in code"),
    (re.compile(r"找.*函数.*哪里|找.*类.*哪里|找.*定义", re.I),
     "code_locator", "search_files", "find function/class location"),
    
    # Code inspect (understand structure/organization)
    (re.compile(r"查看.*代码结构|分析.*代码结构|代码.*结构|项目.*结构|看看.*结构", re.I),
     "code_inspect", "search_files", "inspect code structure"),
    (re.compile(r"分析.*组织|代码.*组织|项目.*组织", re.I),
     "code_inspect", "search_files", "analyze organization"),
    (re.compile(r"查看.*架构|项目.*架构|代码.*架构", re.I),
     "code_inspect", "search_files", "inspect architecture"),
    (re.compile(r"理解.*项目|项目.*怎么组织", re.I),
     "code_inspect", "search_files", "understand project"),
    (re.compile(r"依赖.*关系|代码.*依赖", re.I),
     "code_inspect", "search_files", "check dependencies"),
    
    # Code check (quality/issues)
    (re.compile(r"检查.*代码质量|代码.*质量|审查.*代码|代码.*review", re.I),
     "code_check", "terminal", "check code quality"),
    (re.compile(r"分析.*问题|代码.*问题|检查.*bug", re.I),
     "code_check", "terminal", "analyze problems"),
    (re.compile(r"代码.*规范|代码.*检查", re.I),
     "code_check", "terminal", "check code standards"),
    (re.compile(r"复杂度|代码.*复杂度", re.I),
     "code_check", "terminal", "check complexity"),
    
    # Code search
    (re.compile(r"搜索.*代码|代码.*搜索|源码.*查找|grep.*code", re.I),
     "code_search", "search_files", "search in code"),
    (re.compile(r"搜索.*函数|搜索.*符号", re.I),
     "code_locator", "search_files", "search function/symbol"),
    
    # File read
    (re.compile(r"读取.*内容|文件.*内容|打开.*文件|查看.*内容|cat.*", re.I),
     "file_read", "read_file", "read file content"),
    (re.compile(r"看.*文件|文件.*第一行|文本.*文件|日志.*文件|README|文档.*内容", re.I),
     "file_read", "read_file", "view file"),
    
    # File search
    (re.compile(r"搜索.*文件|查找.*文件|找.*文件|grep.*file|find.*file", re.I),
     "file_search", "search_files", "search files"),
    (re.compile(r"找到.*文件|文件.*位置", re.I),
     "file_search", "search_files", "find file location"),
    
    # Terminal
    (re.compile(r"执行.*命令|运行.*命令|获取.*版本|系统.*信息|运行.*测试", re.I),
     "terminal", "terminal", "execute command"),
    (re.compile(r"获取.*版本|系统.*信息|主机名|时间.*获取", re.I),
     "terminal", "terminal", "get system info"),
    (re.compile(r"检查.*磁盘|检查.*内存|检查.*进程|检查.*网络|检查.*负载", re.I),
     "terminal", "terminal", "check system"),
    (re.compile(r"运行.*test|pytest|npm.*test|测试.*套件", re.I),
     "terminal", "terminal", "run tests"),
    (re.compile(r"进程.*列表|查看.*进程|服务.*状态|健康.*检查", re.I),
     "terminal", "terminal", "check processes"),
    (re.compile(r"查看.*日志|运行.*诊断|状态.*检查", re.I),
     "terminal", "terminal", "check logs/status"),
    
    # Fix
    (re.compile(r"修复.*bug|debug|解决.*错误|修.*故障", re.I),
     "fix", "read_file", "fix bug"),
    
    # Create
    (re.compile(r"创建.*文件|新建.*文件|生成.*文件|写入.*文件", re.I),
     "file_write", "write_file", "create file"),
]

# Fallback patterns (lower priority, only match if no higher pattern matches)
_FALLBACKS = [
    (re.compile(r"搜索|查找|找\b", re.I), "file_search", "search_files", "search general"),
    (re.compile(r"读取|打开|查看|看\b", re.I), "file_read", "read_file", "read general"),
]


def _is_ambiguous(text: str) -> tuple[bool, str]:
    """Check if input is ambiguous."""
    if len(text.strip()) < 4:
        return True, "too short"
    
    # Very generic without context
    if text.strip() in ["看看", "检查一下", "分析一下", "搜索一下", "读取一下"]:
        return True, "only generic verb"
    
    # Check for conflicting signals
    has_code = any(k in text for k in ["代码", "函数", "符号", "类", "定义"])
    has_file = any(k in text for k in ["文件", "文档", "配置"])
    has_verb = any(k in text for k in ["查看", "检查", "分析", "搜索", "读取"])
    
    # If has both code and file keywords but no clear operation
    if has_code and has_file and not any(k in text for k in ["结构", "内容", "位置", "定义"]):
        return True, "conflicting code+file"
    
    return False, ""


def classify_v4(situation: str) -> ClassificationResult:
    """Context-aware classification."""
    if not situation or not situation.strip():
        return ClassificationResult(None, None, 0.0, "empty input")
    
    text = situation.strip()
    
    # Check ambiguity
    is_ambig, ambig_reason = _is_ambiguous(text)
    if is_ambig:
        return ClassificationResult(None, None, 0.3, "ambiguous", 
                                   is_ambiguous=True, ambiguity_reason=ambig_reason)
    
    # Try patterns in priority order
    for pat, tt, act, desc in _PATTERNS:
        if pat.search(text):
            confidence = _compute_confidence(text, tt, act)
            return ClassificationResult(tt, act, confidence, f"matched: {desc}")
    
    # Try fallbacks
    for pat, tt, act, desc in _FALLBACKS:
        if pat.search(text):
            confidence = _compute_confidence(text, tt, act)
            return ClassificationResult(tt, act, confidence, f"fallback: {desc}")
    
    return ClassificationResult(None, None, 0.0, "no match")


def _compute_confidence(text: str, task_type: str, action: str) -> float:
    """Compute confidence based on context clues."""
    confidence = 0.5
    
    # Boost for strong indicators
    strong_indicators = {
        "code_locator": ["定位", "函数定义", "类定义", "符号位置"],
        "code_inspect": ["代码结构", "项目结构", "组织架构"],
        "code_check": ["代码质量", "审查", "问题"],
        "file_read": ["读取内容", "打开文件", "查看内容"],
        "file_search": ["搜索文件", "查找文件"],
        "terminal": ["执行命令", "运行命令", "获取版本"],
    }
    
    for indicator in strong_indicators.get(task_type, []):
        if indicator in text:
            confidence = max(confidence, 0.8)
            break
    
    # Penalize politeness prefixes
    if any(p in text for p in ["帮我", "请帮我", "麻烦"]):
        confidence = min(confidence, 0.7)
    
    return confidence


def classify_to_tuple(situation: str) -> tuple[str, str] | None:
    """Return (task_type, action) or None."""
    result = classify_v4(situation)
    if result.task_type and result.confidence >= 0.5:
        return (result.task_type, result.action)
    return None


# ── Canonical Situation Family Mapping ───────────────────────────────
# Maps fine-grained task_types to coarser learning families.
# Enables cross-type generalization in action learning.
TASK_TYPE_TO_FAMILY: dict[str, str] = {
    # Code location tasks → share learning
    "code_locator": "CODE_LOCATION",
    "code_search": "CODE_LOCATION",
    # Code inspection tasks → separate family
    "code_inspect": "CODE_INSPECTION",
    "code_check": "CODE_QUALITY",
    # File operations → separate families
    "file_search": "FILE_SEARCH",
    "file_read": "FILE_READ",
    "file_write": "FILE_WRITE",
    # System tasks
    "terminal": "GENERIC_COMMAND",
    "info_extract": "GENERIC_COMMAND",
    "test_run": "GENERIC_COMMAND",
}


def get_canonical_family(task_type: str | None) -> str:
    """Get canonical situation family for learning key normalization."""
    if not task_type:
        return "UNKNOWN"
    return TASK_TYPE_TO_FAMILY.get(task_type, task_type.upper())
