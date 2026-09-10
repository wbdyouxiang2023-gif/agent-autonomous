"""Perception module — transforms raw input into structured perceptual data."""

from __future__ import annotations

import re
from typing import Any, Optional

from ..event import CortexEvent, PerceptionData
from ..interfaces import PerceptionModule


# ── Intent heuristics (English + Chinese) ──────────────────────
# Keywords are stored as plain substrings. Matching strategy:
#   - ASCII keywords → word-boundary regex (avoids substring false positives)
#   - CJK keywords → plain substring (CJK has no word boundaries)

def _kw_matches(kw: str, text: str) -> bool:
    """Check if keyword matches text, using appropriate strategy per language."""
    if any('\u4e00' <= c <= '\u9fff' for c in kw):
        return kw in text
    return bool(re.search(rf'\b{re.escape(kw)}\b', text))


def _has_cjk(text: str) -> bool:
    return any('\u4e00' <= c <= '\u9fff' for c in text)


_INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("create",  ["create", "build", "make", "write", "design", "develop", "implement", "produce",
                 "实现", "构建", "开发", "创建", "编写", "设计", "做", "写", "造", "搭建", "新建"]),
    ("fix",     ["fix", "debug", "repair", "solve", "patch", "correct", "resolve",
                 "修复", "解决", "修补", "改正", "处理", "调试", "修", "搞定", "弄好"]),
    ("learn",   ["learn", "understand", "explain", "teach", "study", "explore", "discover",
                 "学习", "理解", "解释", "说明", "研究", "探索", "了解", "教", "讲讲", "是什么", "为什么"]),
    ("optimize",["optimize", "improve", "refactor", "enhance", "upgrade", "speed up",
                 "优化", "改进", "重构", "提升", "升级", "加速", "改善", "增强"]),
    ("deploy",  ["deploy", "run", "start", "launch", "ship", "publish",
                 "部署", "运行", "启动", "发布", "上线", "提交", "推送", "发布"]),
    ("analyze", ["analyze", "evaluate", "assess", "review", "inspect", "audit",
                 "分析", "评估", "审查", "检查", "审计", "调研", "评价", "审视"]),
    ("delete",  ["delete", "remove", "discard", "destroy", "clean", "clear",
                 "删除", "移除", "清除", "销毁", "清理", "丢掉", "删掉"]),
    ("security",["security", "vulnerability", "exploit", "attack", "protect", "secure", "risk", "danger",
                 "安全", "漏洞", "风险", "危险", "攻击", "防护", "威胁", "隐患", "泄露"]),
    ("debug",   ["trace", "log", "investigate", "diagnose", "check",
                 "排查", "诊断", "调查", "检查", "追踪", "定位", "找问题"]),
    ("test",    ["test", "verify", "validate", "prove",
                 "测试", "验证", "确认", "证明", "检验", "试运行"]),
    ("migrate", ["migrate", "transfer", "move", "convert", "port",
                 "迁移", "转换", "搬运", "移植", "重构数据"]),
]

_EMOTION_PATTERNS: list[tuple[str, list[str]]] = [
    ("positive",  ["good", "great", "excellent", "amazing", "love", "happy", "awesome", "perfect",
                   "好", "棒", "优秀", "完美", "喜欢", "高兴", "满意", "不错", "厉害", "太好了", "赞"]),
    ("negative",  ["bad", "terrible", "awful", "hate", "sad", "angry", "horrible", "worst",
                   "坏", "糟糕", "讨厌", "难过", "生气", "差", "垃圾", "坑", "烂", "无语"]),
    ("uncertain", ["maybe", "perhaps", "somewhat", "kind of", "a bit", "seems", "might", "possibly", "guess",
                   "可能", "也许", "大概", "好像", "不确定", "试试", "看情况", "不确定"]),
    ("urgent",    ["urgent", " ASAP", " immediately", "now", "quickly", "fast", "critical", "emergency",
                   "紧急", "立刻", "马上", "赶紧", "快点", "急", "严重", "非常重要", "必须"]),
    ("curious",   ["wonder", "好奇", "explore", "out of curiosity"]),
]

_RISK_PATTERNS: list[tuple[str, list[str]]] = [
    ("high",    ["danger", "risk", "vulnerability", "exploit", "attack", "breach", "critical", "fatal",
                 "危险", "风险", "漏洞", "严重", "致命", "崩溃", "事故", "攻击", "入侵", "泄露", "高危"]),
    ("medium",  ["caution", "careful", "warning", "potential", "possible", "maybe", "risky",
                 "注意", "小心", "警告", "潜在", "可能", "有点风险", "谨慎"]),
    ("low",     ["safe", "secure", "stable", "reliable", "trustworthy", "verified",
                 "安全", "稳定", "可靠", "信任", "已验证", "没问题"]),
]

_LANG_DETECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("zh", re.compile(r"[\u4e00-\u9fff]")),
    ("ja", re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")),
    ("ko", re.compile(r"[\uac00-\ud7af]")),
    ("ar", re.compile(r"[\u0600-\u06ff]")),
    ("cyrillic", re.compile(r"[\u0400-\u04ff]")),
    ("latin", re.compile(r"[a-zA-Z]{3,}")),
]


class BasicPerception(PerceptionModule):
    """
    Deterministic, rule-based perception module.

    No ML models. No external APIs. Pure heuristic analysis.
    Fields that cannot be confidently determined are set to safe defaults:
    - intent = "unknown"
    - emotion = "neutral"
    - risk = 0.0
    - confidence reflects the certainty of detection
    """

    def process(self, event: CortexEvent) -> CortexEvent:
        text = event.raw_input
        intent, intent_conf = self._detect_intent(text)
        emotion, emotion_conf = self._detect_emotion(text)
        risk, risk_conf = self._detect_risk(text)
        entities = self._extract_entities(text)
        language = self._detect_language(text)
        overall_confidence = self._compute_confidence(
            intent_conf, emotion_conf, risk_conf, len(entities), text
        )

        event.perceive(PerceptionData(
            raw_input=text,
            intent=intent,
            emotion=emotion,
            risk=risk,
            entities=entities,
            confidence=overall_confidence,
            metadata={
                "input_type": self._classify_input_type(text),
                "language": language,
                "intent_confidence": round(intent_conf, 2),
                "emotion_confidence": round(emotion_conf, 2),
                "risk_confidence": round(risk_conf, 2),
                "entity_count": len(entities),
                "token_count": len(text.split()),
            },
        ))
        return event

    # ── Intent detection ─────────────────────────────────────────

    def _detect_intent(self, text: str) -> tuple[str, float]:
        text_lower = text.lower()
        matches = 0
        best_intent = "unknown"
        best_conf = 0.0

        for intent, keywords in _INTENT_PATTERNS:
            hits = sum(1 for kw in keywords if _kw_matches(kw, text_lower))
            if hits > 0:
                matches += hits
                conf = min(hits / max(len(keywords), 1), 1.0) * 0.7 + 0.15
                if conf >= best_conf:
                    best_conf = conf
                    best_intent = intent

        if matches == 0:
            q_patterns = ["?", "how to", "what is", "why", "can i", "should i",
                          "如何", "怎么", "什么", "为什么", "能不能", "可以吗", "怎么办"]
            if any(q in text_lower for q in q_patterns):
                return "inquire", 0.5
            if text.strip().startswith(("/", "!", "#")):
                return "command", 0.3
            return "unknown", 0.15
        return best_intent, best_conf

    # ── Emotion detection ────────────────────────────────────────

    def _detect_emotion(self, text: str) -> tuple[str, float]:
        text_lower = text.lower()
        matches = 0
        best_emotion = "neutral"
        best_conf = 0.0

        for emotion, keywords in _EMOTION_PATTERNS:
            hits = sum(1 for kw in keywords if _kw_matches(kw, text_lower))
            if hits > 0:
                conf = min(hits / max(len(keywords), 1), 1.0) * 0.7 + 0.15
                if conf >= best_conf:
                    best_conf = conf
                    best_emotion = emotion
                    matches += hits

        if matches == 0:
            # Check for question words implying uncertainty
            if any(w in text_lower for w in ("?", "不确定", "不知道", "how", "what", "why")):
                return "uncertain", 0.4
        return best_emotion, best_conf

    # ── Risk detection ───────────────────────────────────────────

    def _detect_risk(self, text: str) -> tuple[float, float]:
        text_lower = text.lower()
        score = 0.0
        confidence = 0.0
        total_hits = 0

        for risk_label, keywords in _RISK_PATTERNS:
            hits = sum(1 for kw in keywords if _kw_matches(kw, text_lower))
            total_hits += hits
            if risk_label == "high":
                score += hits * 0.3
            elif risk_label == "medium":
                score += hits * 0.15
            elif risk_label == "low":
                score -= hits * 0.1

        confidence = min(total_hits / 5.0, 1.0) * 0.8 if total_hits > 0 else 0.1
        return round(max(0.0, min(1.0, score)), 2), round(confidence, 2)

    # ── Entity extraction ────────────────────────────────────────

    def _extract_entities(self, text: str) -> list[str]:
        """Extract noun-like entities: CamelCase words, quoted strings, slug-like tokens."""
        entities: list[str] = []
        # camelCase segments: any uppercase-starting word followed by lowercase
        entities.extend(re.findall(r"[A-Z][a-zA-Z]*", text))
        # quoted strings
        entities.extend(re.findall(r'"([^"]+)"', text))
        entities.extend(re.findall(r"'([^']+)'", text))
        # slug-like (hyphenated compound words)
        entities.extend(re.findall(r"[a-z]+-[a-z]+", text))
        return list(dict.fromkeys(entities))  # preserve order, deduplicate

    # ── Language detection ───────────────────────────────────────

    def _detect_language(self, text: str) -> str:
        for lang, pattern in _LANG_DETECTION_PATTERNS:
            if pattern.search(text):
                return lang
        return "unknown"

    # ── Input type classification ────────────────────────────────

    def _classify_input_type(self, text: str) -> str:
        if not text or not text.strip():
            return "empty"
        if any(text.startswith(p) for p in ("/", "!", "#", "$", "`")):
            return "command"
        if "?" in text and text.count("?") <= 2:
            return "question"
        if any(kw in text.lower() for kw in ("帮我", "请", "麻烦", "能否")):
            return "request"
        if len(text.split()) <= 3:
            return "short"
        return "statement"

    # ── Confidence computation ───────────────────────────────────

    @staticmethod
    def _compute_confidence(
        intent_conf: float,
        emotion_conf: float,
        risk_conf: float,
        entity_count: int,
        text: str,
    ) -> float:
        """
        Overall perception confidence is a weighted average.
        If text is empty, confidence is 0.
        More entities and clearer signals increase confidence.
        """
        if not text or not text.strip():
            return 0.0
        weights = {"intent": 0.4, "emotion": 0.15, "risk": 0.15, "entities": 0.3}
        entity_score = min(entity_count / 3.0, 1.0)
        components = [
            intent_conf * weights["intent"],
            emotion_conf * weights["emotion"],
            risk_conf * weights["risk"],
            entity_score * weights["entities"],
        ]
        return round(sum(components), 2)
