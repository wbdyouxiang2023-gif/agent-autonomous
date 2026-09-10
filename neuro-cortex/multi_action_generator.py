#!/usr/bin/env python3
"""
NC-05B: Multi-Action Candidate Generation

This module generates multiple REAL candidate actions for a given situation.
It does NOT modify the production decision pipeline.

Design:
  - Situation-aware: different situations get different candidate sets
  - Action-realistic: all candidates must be real system actions
  - Zero behavioral change: only used in shadow observation
  - Deterministic: same situation → same candidates (for reproducibility)

Usage:
  generator = MultiActionCandidateGenerator()
  candidates = generator.generate(situation, original_action)
  
  # Returns list of candidate dicts with 'id' and 'score'
  # Example: [{"id": "respond", "score": 0.5}, {"id": "tool_call", "score": 0.3}]
"""
import re
from typing import Any, Optional


# ── Situation Keywords → Candidate Patterns ──────────────────────────────
# Each pattern maps keyword triggers to a list of REAL action candidates.
# All candidates must be from: noop, respond, tool_call, code_edit, code_review

SITUATION_PATTERNS = [
    # Pattern 1: Search + Read operations
    {
        "keywords": ["搜索", "查找", "查询", "find", "search", "look up", 
                     "读取", "阅读", "read", "检查文件", "查看文件"],
        "candidates": [
            {"id": "tool_call", "score": 0.7},   # search via tool
            {"id": "respond", "score": 0.3},     # direct response
        ],
        "situation_type": "search_read",
        "description": "Information retrieval tasks"
    },
    
    # Pattern 2: Code analysis + Review
    {
        "keywords": ["审查", "分析", "review", "analyze", "检查代码", 
                     "code review", "代码质量", "代码审查", "诊断"],
        "candidates": [
            {"id": "code_review", "score": 0.8},  # dedicated review
            {"id": "respond", "score": 0.2},      # text explanation
        ],
        "situation_type": "code_review",
        "description": "Code quality analysis"
    },
    
    # Pattern 3: Create + Implement
    {
        "keywords": ["创建", "实现", "build", "create", "make", "开发",
                     "编写代码", "写一个", "帮我写", "生成代码"],
        "candidates": [
            {"id": "code_edit", "score": 0.7},    # code modification
            {"id": "tool_call", "score": 0.3},    # tool-based creation
        ],
        "situation_type": "code_create",
        "description": "Code creation tasks"
    },
    
    # Pattern 4: Fix + Debug
    {
        "keywords": ["修复", "调试", "debug", "fix", "错误", "bug",
                     "问题解决", "代码出错", "报错", "异常处理"],
        "candidates": [
            {"id": "code_review", "score": 0.6},  # analyze the bug
            {"id": "code_edit", "score": 0.4},    # fix the code
        ],
        "situation_type": "bug_fix",
        "description": "Bug fixing and debugging"
    },
    
    # Pattern 5: Optimize + Improve
    {
        "keywords": ["优化", "加速", "性能", "fast", "optimize", "improve",
                     "提升性能", "代码优化", "效率提升"],
        "candidates": [
            {"id": "tool_call", "score": 0.6},    # use tools for optimization
            {"id": "code_edit", "score": 0.4},    # direct code changes
        ],
        "situation_type": "optimization",
        "description": "Performance optimization"
    },
    
    # Pattern 6: Test + Verify
    {
        "keywords": ["测试", "验证", "test", "verify", "用例", "validate"],
        "candidates": [
            {"id": "tool_call", "score": 0.7},    # run tests via tools
            {"id": "respond", "score": 0.3},      # explain testing approach
        ],
        "situation_type": "testing",
        "description": "Testing and verification"
    },
    
    # Pattern 7: Deploy + Run
    {
        "keywords": ["部署", "运行", "启动", "deploy", "run", "start",
                     "上线", "发布", "执行"],
        "candidates": [
            {"id": "tool_call", "score": 0.8},    # deployment via tools
            {"id": "respond", "score": 0.2},      # instructions
        ],
        "situation_type": "deployment",
        "description": "Deployment and execution"
    },
]


class MultiActionCandidateGenerator:
    """
    Generates multiple REAL candidate actions for a given situation.
    
    This is a SHADOW-only module. It does NOT modify the production
    decision pipeline. It's used to observe how PolicyEngine would
    behave with true multi-action competition.
    """
    
    def __init__(self, patterns: Optional[list] = None):
        self._patterns = patterns or SITUATION_PATTERNS
        self._match_log: list[dict] = []
    
    @property
    def match_log(self) -> list[dict]:
        return self._match_log.copy()
    
    def generate(
        self,
        raw_input: str,
        intent: str,
        original_action: str,
    ) -> list[dict[str, Any]]:
        """
        Generate candidate actions for a situation.
        
        Args:
            raw_input: The original user input
            intent: The detected intent (e.g., "fix", "create")
            original_action: The action BasicDecision would choose
            
        Returns:
            List of candidate dicts: [{"id": str, "score": float}, ...]
            
        Guarantees:
            - At least 2 candidates if multi-action is possible
            - All candidates are REAL system actions
            - original_action is always included
            - noop is never a competitive candidate (only as fallback)
        """
        # Try to match situation patterns
        matched_pattern = None
        for pattern in self._patterns:
            keywords = pattern.get("keywords", [])
            if any(kw in raw_input.lower() for kw in keywords):
                matched_pattern = pattern
                break
        
        # If no pattern matched, use intent-based fallback
        if matched_pattern is None:
            candidates = self._intent_based_candidates(intent, original_action)
        else:
            candidates = matched_pattern["candidates"].copy()
        
        # Ensure original_action is in candidates
        original_in_candidates = any(c["id"] == original_action for c in candidates)
        if not original_in_candidates and original_action != "noop":
            candidates.append({"id": original_action, "score": 0.3})
        
        # Re-score to ensure valid probabilities
        candidates = self._rescore_candidates(candidates)
        
        # Log the generation
        self._match_log.append({
            "raw_input": raw_input[:100],
            "intent": intent,
            "original_action": original_action,
            "matched_pattern": matched_pattern["situation_type"] if matched_pattern else "intent_fallback",
            "candidate_count": len(candidates),
            "candidates": candidates,
        })
        
        return candidates
    
    def _intent_based_candidates(self, intent: str, original: str) -> list[dict]:
        """Generate candidates based on intent when no pattern matches."""
        intent_map = {
            "explain": [{"id": "respond", "score": 0.8}],
            "create": [{"id": "code_edit", "score": 0.7}],
            "fix": [{"id": "code_review", "score": 0.7}],
            "review": [{"id": "code_review", "score": 0.7}],
            "optimize": [{"id": "tool_call", "score": 0.7}],
            "deploy": [{"id": "tool_call", "score": 0.7}],
            "test": [{"id": "tool_call", "score": 0.7}],
        }
        
        candidates = intent_map.get(intent, [{"id": "respond", "score": 0.5}])
        
        # Ensure original is included
        if not any(c["id"] == original for c in candidates) and original != "noop":
            candidates.append({"id": original, "score": 0.3})
        
        return candidates
    
    def _rescore_candidates(self, candidates: list[dict]) -> list[dict]:
        """Rescore candidates to ensure valid probabilities."""
        if not candidates:
            return [{"id": "noop", "score": 0.0}]
        
        # Normalize scores to sum to 1.0
        total = sum(c.get("score", 0.1) for c in candidates)
        if total > 0:
            for c in candidates:
                c["score"] = round(c["score"] / total, 3)
        else:
            # Equal distribution if all scores are 0
            n = len(candidates)
            for c in candidates:
                c["score"] = round(1.0 / n, 3)
        
        return candidates
    
    def get_stats(self) -> dict:
        """Get generation statistics."""
        if not self._match_log:
            return {"total": 0}
        
        pattern_counts = {}
        multi_action_count = 0
        
        for log in self._match_log:
            pattern = log["matched_pattern"]
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
            if log["candidate_count"] >= 2:
                multi_action_count += 1
        
        return {
            "total": len(self._match_log),
            "multi_action_count": multi_action_count,
            "multi_action_rate": multi_action_count / len(self._match_log) if self._match_log else 0,
            "pattern_distribution": pattern_counts,
        }


# Global instance
_generator = None


def get_candidate_generator() -> MultiActionCandidateGenerator:
    """Get or create the global candidate generator."""
    global _generator
    if _generator is None:
        _generator = MultiActionCandidateGenerator()
    return _generator


def generate_multi_action_candidates(
    raw_input: str,
    intent: str,
    original_action: str,
) -> list[dict[str, Any]]:
    """Convenience function to generate multi-action candidates."""
    generator = get_candidate_generator()
    return generator.generate(raw_input, intent, original_action)
