"""NC-08C.7 — Classifier V3 Tests.

Tests the context-aware situation classifier.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from neurocortex.perception.classifier_v3 import classify_with_details


# ── C.5 Failure Cases (must all be fixed) ────────────────────────────
C5_FAILURE_CASES = [
    ("查看 project_4 的代码结构", "code_inspect", "search_files"),
    ("查看 project_2 的代码结构", "code_inspect", "search_files"),
    ("查看 project_9 的代码结构", "code_inspect", "search_files"),
    ("查看 project_6 的代码结构", "code_inspect", "search_files"),
    ("查看 project_7 的代码结构", "code_inspect", "search_files"),
]


@pytest.mark.parametrize("situation,expected_tt,expected_act", C5_FAILURE_CASES)
def test_c5_failures_fixed(situation, expected_tt, expected_act):
    """C.5 LEVEL_3 failures must be fixed by V3."""
    result = classify_with_details(situation)
    assert result.task_type == expected_tt, f"{situation}: got {result.task_type}"
    assert result.action == expected_act, f"{situation}: got {result.action}"
    assert result.confidence >= 0.5, f"{situation}: confidence too low"


# ── Full Dataset Tests ──────────────────────────────────────────────
DATASET = [
    # Code-related (20 cases)
    ("查看 project_4 的代码结构", "code_inspect", "search_files"),
    ("查看 project_2 的代码结构", "code_inspect", "search_files"),
    ("查看 project_9 的代码结构", "code_inspect", "search_files"),
    ("查看 project_6 的代码结构", "code_inspect", "search_files"),
    ("查看 project_7 的代码结构", "code_inspect", "search_files"),
    ("帮我看看这个项目的代码结构", "code_inspect", "search_files"),
    ("分析一下代码的组织方式", "code_inspect", "search_files"),
    ("检查代码质量并找出问题", "code_check", "terminal"),
    ("审查这段代码的实现", "code_check", "terminal"),
    ("定位函数 find_x 在源码中的位置", "code_locator", "search_files"),
    ("搜索代码中 find_func_1 的定义", "code_search", "search_files"),
    ("查找符号 symbol_y 在代码中的位置", "file_search", "search_files"),
    ("搜索包含 keyword_1 的代码文件", "code_search", "search_files"),
    ("在源码中查找 func_z", "code_search", "search_files"),
    ("查看代码目录结构", "code_inspect", "search_files"),
    ("分析代码依赖关系", "code_inspect", "search_files"),
    ("检查代码规范", None, None),
    ("看看这个函数的实现", "code_inspect", "search_files"),
    ("查看项目架构", "code_inspect", "search_files"),
    ("分析代码复杂度", "code_inspect", "search_files"),
    
    # File read (15 cases)
    ("读取文件 readme_1.md 的内容", "file_read", "read_file"),
    ("打开配置文件 config.json", "file_read", "read_file"),
    ("查看文件内容 data.txt", "file_read", "read_file"),
    ("读取这个文件的第一行", "file_read", "read_file"),
    ("cat /etc/hostname", None, None),
    ("查看日志文件内容", "file_read", "read_file"),
    ("读取项目说明文档", "file_read", "read_file"),
    ("打开并查看代码文件", "file_read", "read_file"),
    ("查看 README 文件", "file_read", "read_file"),
    ("读取配置文件的内容", "file_read", "read_file"),
    ("查看这个文本文件", "file_read", "read_file"),
    ("读取 JSON 文件", "file_read", "read_file"),
    ("查看 YAML 配置", "file_read", "read_file"),
    ("打开日志文件", "file_read", "read_file"),
    ("读取第一个文件", "file_read", "read_file"),
    
    # File search (15 cases)
    ("搜索包含 pattern_1 的配置文件", "file_search", "search_files"),
    ("查找包含 keyword_1 的文件", "file_search", "search_files"),
    ("搜索代码中的符号", "code_locator", "search_files"),
    ("找到包含特定内容的文件", "file_search", "search_files"),
    ("grep 搜索某个关键字", "file_search", "search_files"),
    ("查找所有 Python 文件", "file_search", "search_files"),
    ("搜索包含 class 的文件", "file_search", "search_files"),
    ("找一下这个函数在哪个文件", "file_search", "search_files"),
    ("搜索配置文件", "file_search", "search_files"),
    ("查找日志文件位置", "file_search", "search_files"),
    ("搜索项目中的测试文件", "file_search", "search_files"),
    ("找到包含特定字符串的文件", "file_search", "search_files"),
    ("搜索代码目录", "code_search", "search_files"),
    ("查找项目结构文件", "file_search", "search_files"),
    ("搜索文档目录", None, None),
    
    # Terminal (15 cases)
    ("执行命令获取系统信息", "info_extract", "terminal"),
    ("获取 Python 版本", "info_extract", "terminal"),
    ("运行测试套件", "test_run", "terminal"),
    ("检查磁盘空间", None, None),
    ("查看内存使用情况", None, None),
    ("执行 python 命令", "info_extract", "terminal"),
    ("运行 ls 命令", "info_extract", "terminal"),
    ("检查系统负载", None, None),
    ("获取当前时间", "info_extract", "terminal"),
    ("查看进程列表", None, None),
    ("运行测试", None, None),
    ("检查网络连接", None, None),
    ("执行状态检查", None, None),
    ("运行诊断命令", "info_extract", "terminal"),
    ("获取系统状态", "info_extract", "terminal"),
    
    # Ambiguous cases (15 cases) - some may still be classified
    ("看看这个文件", None, None),
    ("检查一下", None, None),
    ("分析一下", None, None),
    ("帮我看看", None, None),
    ("查看一下", None, None),
    ("搜索一下", None, None),
    ("检查代码", None, None),
    ("看看代码", None, None),
    ("分析一下代码", "code_inspect", "search_files"),
    ("搜索文件", None, None),
    ("读取内容", None, None),
    ("查看项目", None, None),
    ("检查项目", None, None),
    ("看看项目", None, None),
    ("分析一下项目", None, None),
]


@pytest.mark.parametrize("situation,expected_tt,expected_act", DATASET)
def test_classification_accuracy(situation, expected_tt, expected_act):
    """Test classification accuracy on full dataset."""
    result = classify_with_details(situation)
    
    if expected_tt is None:
        # Ambiguous case: should return None or be marked ambiguous
        assert result.is_ambiguous or result.task_type is None, \
            f"Ambiguous case {situation} should not be classified"
    else:
        assert result.task_type == expected_tt, \
            f"{situation}: expected {expected_tt}, got {result.task_type}"
        assert result.action == expected_act, \
            f"{situation}: expected {expected_act}, got {result.action}"


def test_confidence_threshold():
    """Test that confident classifications have confidence >= 0.5."""
    result = classify_with_details("查看 project_4 的代码结构")
    assert result.confidence >= 0.5


def test_empty_input():
    """Test empty input handling."""
    result = classify_with_details("")
    assert result.task_type is None
    assert result.confidence == 0.0


def test_whitespace_input():
    """Test whitespace-only input."""
    result = classify_with_details("   ")
    assert result.task_type is None
