#!/usr/bin/env python3
"""NC-08B.3 — Completion Ranking Shadow Adapter.

SHADOW-ONLY. Never influences actual Hermes action selection.

Given a situation + candidate actions + real completion evidence,
produces a completion-based ranking recommendation and logs it to an
independent shadow log. The actual action is ALWAYS the original policy's
choice — the adapter only observes and recommends.

Feature flag: NC_SHADOW_MODE (default OFF). When OFF, the adapter is a
no-op passthrough with zero side effects.

Safety invariant:
    actual_action == original_action  (asserted on every record)
"""
from __future__ import annotations

import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

MODEL_VERSION = "nc08b3-shadow-v1"
FLAG = os.environ.get("NC_SHADOW_MODE", "off").strip().lower() in ("1", "true", "yes", "on")

# Real completion evidence source (read-only)
EVIDENCE_PATH = Path(__file__).parent.parent / "real_completion_observations.jsonl"
SITUATION_PATH = Path(__file__).parent.parent / "situation_observations.jsonl"

# Shadow log output (independent, never production experience)
SHADOW_DIR = Path(__file__).parent
SHADOW_LOG = SHADOW_DIR / "shadow_log.jsonl"


# ── Chinese → task_type fallback classifier ───────────────────────────
# Order matters: more specific patterns first.
_ZH_TO_TASK: list[tuple[re.Pattern, tuple[str, str]]] = [
    (re.compile(r"读取|打开.*文件|打开.*文档|看.*文件", re.I), ("file_read", "read_file")),
    (re.compile(r"搜索.*文件|查找.*文件|搜索.*指定", re.I), ("file_search", "search_files")),
    (re.compile(r"定位.*函数|定位.*符号|查找.*函数|搜索.*代码", re.I), ("code_locator", "search_files")),
    (re.compile(r"python|版本|version|uptime|运行.*测试|执行.*命令", re.I), ("info_extract", "terminal")),
    (re.compile(r"创建.*文件|新建.*文件|生成.*文件|写入", re.I), ("file_create", "write_file")),
    (re.compile(r"检查.*代码|检查.*质量|分析.*代码|审查.*代码|code.*quality|review", re.I), ("code_check", "terminal")),
    (re.compile(r"搜索|查找|找\b", re.I), ("file_search", "search_files")),
    (re.compile(r"读取|打开|查看|看\b", re.I), ("file_read", "read_file")),
    (re.compile(r"获取.*信息|系统.*信息", re.I), ("info_extract", "terminal")),
]


def _classify_to_task_type(situation: str) -> tuple[str, str] | None:
    """Fallback classifier: Chinese situation text → (task_type, action)."""
    for pat, tt_action in _ZH_TO_TASK:
        if pat.search(situation):
            return tt_action
    return None


def _load_evidence() -> tuple[dict[tuple[str, str], dict], dict[str, tuple[str, str]]]:
    """Load real completion evidence and build situation→task_type map.

    Returns:
        agg: (task_type, action) -> {t, f, n}
        sit_map: situation_description -> (task_type, selected_action)
    """
    agg: dict[tuple[str, str], dict] = defaultdict(lambda: {"t": 0, "f": 0, "n": 0})
    sit_map: dict[str, tuple[str, str]] = {}
    for p in (EVIDENCE_PATH, SITUATION_PATH):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").strip().splitlines():
            if not line:
                continue
            o = json.loads(line)
            key = (o.get("task_type"), o.get("selected_action"))
            agg[key]["n"] += 1
            if o.get("task_completed") is True:
                agg[key]["t"] += 1
            elif o.get("task_completed") is False:
                agg[key]["f"] += 1
            td = o.get("task_description", "")
            if td and key not in sit_map:
                sit_map[td] = key
    return dict(agg), sit_map


def _completion_rate(ev: dict | None) -> float | None:
    """True / (True + False). None excluded. None if no valid evidence."""
    if ev is None or (ev["t"] + ev["f"]) == 0:
        return None
    return ev["t"] / (ev["t"] + ev["f"])


# Related task types that should be checked together for code-related queries
_CODE_RELATED_TASK_TYPES = ("code_check", "code_locator", "code_check_fail")


def _get_all_related_tts(situation: str, classifier) -> list[str]:
    """Get all relevant task types for a situation, including alternatives."""
    tts = set()
    if classifier:
        tt_match = classifier(situation)
        if tt_match:
            tts.add(tt_match[0])
            # If classifier says 'code_check', also check 'code_locator' and vice versa
            if tt_match[0] in ("code_check", "code_check_fail"):
                tts.add("code_locator")
            elif tt_match[0] == "code_locator":
                tts.add("code_check")
                tts.add("code_check_fail")
    return list(tts)


def rank_by_completion(situation: str, candidate_actions: list[str],
                        evidence: dict[tuple[str, str], dict],
                        sit_map: dict[str, tuple[str, str]] | None = None,
                        classifier=_classify_to_task_type) -> list[dict]:
    """Completion-based ranking of candidate actions for a situation.

    Scores each candidate by completion_rate from real evidence.
    Candidates with no valid evidence get score=None (ranked last, no guess).
    Deterministic tie-breaker: support count then action name.

    Lookup order:
      1. Exact (situation, action) key match
      2. sit_map lookup (exact task_description match)
      3. Chinese classifier fallback with multi-key evidence aggregation
    """
    scored = []
    for a in candidate_actions:
        ev = None
        # 1. Try direct key first
        ev = evidence.get((situation, a))
        # 2. Fall back to sit_map
        if ev is None and sit_map is not None:
            tt_key = sit_map.get(situation)
            if tt_key:
                ev = evidence.get((tt_key[0], a))
        # 3. Fall back to classifier with multi-key aggregation
        if ev is None and classifier is not None:
            related_tts = _get_all_related_tts(situation, classifier)
            best_ev = None
            best_rate = None
            for tt in related_tts:
                candidate_ev = evidence.get((tt, a))
                if candidate_ev and (candidate_ev["t"] + candidate_ev["f"]) > 0:
                    rate = _completion_rate(candidate_ev)
                    if best_rate is None or rate > best_rate:
                        best_rate = rate
                        best_ev = candidate_ev
            ev = best_ev
        rate = _completion_rate(ev)
        support = (ev["t"] + ev["f"]) if ev else 0
        scored.append({"action": a, "score": rate, "support": support})
    # None scores last; else desc by (score, support), asc name
    scored.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0), -r["support"], r["action"]))
    return scored


class ShadowAdapter:
    """Shadow completion-ranking recommender. Never executes actions."""

    def __init__(self, enabled: bool | None = None):
        self.enabled = FLAG if enabled is None else enabled
        if self.enabled:
            self._evidence, self._sit_map = _load_evidence()
        else:
            self._evidence = {}
            self._sit_map = {}

    @property
    def is_enabled(self) -> bool:
        return self.enabled

    def recommend(self, situation: str, candidate_actions: list[str],
                  original_action: str) -> dict | None:
        """Compute shadow recommendation.

        Returns None when disabled (zero side effects). When enabled,
        logs a shadow record with the safety assertion
        actual_action == original_action.
        """
        if not self.enabled:
            return None
        ranking = rank_by_completion(situation, candidate_actions, self._evidence, self._sit_map)
        nc_top = ranking[0]["action"] if ranking else None
        # completion evidence for original action (observational only)
        ev_orig = self._evidence.get((situation, original_action))
        if ev_orig is None and self._sit_map:
            tt_key = self._sit_map.get(situation)
            if tt_key:
                ev_orig = self._evidence.get((tt_key[0], original_action))
        if ev_orig is None:
            tt_match = _classify_to_task_type(situation)
            if tt_match:
                ev_orig = self._evidence.get((tt_match[0], original_action))
        orig_rate = _completion_rate(ev_orig)

        rec = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": str(uuid.uuid4())[:8],
            "situation": situation,
            "candidate_actions": candidate_actions,
            "original_action": original_action,
            "nc_recommended_action": nc_top,
            "nc_ranking": [r["action"] for r in ranking],
            "nc_scores": {r["action"]: r["score"] for r in ranking},
            "original_completion_rate": orig_rate,
            "model_version": MODEL_VERSION,
            "shadow_only": True,
        }
        # ⚠️ SAFETY: shadow must NEVER change the actual action
        assert rec["original_action"] == original_action
        self._log(rec)
        return rec

    def _log(self, rec: dict) -> None:
        SHADOW_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(SHADOW_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def make_adapter() -> ShadowAdapter:
    return ShadowAdapter()
