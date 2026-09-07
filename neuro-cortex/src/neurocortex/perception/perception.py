"""Perception module — transforms raw input into structured perceptual data."""

from __future__ import annotations

import re
from typing import Any, Optional

from ..event import CortexEvent, PerceptionData
from ..interfaces import PerceptionModule


# ── Intent heuristics ──────────────────────────────────────────

_INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("create", ["create", "build", "make", "write", "design", "develop", "implement", "produce"]),
    ("fix",   ["fix", "debug", "repair", "solve", "patch", "correct", "resolve"]),
    ("learn", ["learn", "understand", "explain", "teach", "study", "explore", "discover"]),
    ("optimize", ["optimize", "improve", "refactor", "enhance", "upgrade", "speed up"]),
    ("deploy",  ["deploy", "run", "start", "launch", "ship", "publish"]),
    ("analyze", ["analyze", "evaluate", "assess", "review", "inspect", "audit"]),
    ("delete",  ["delete", "remove", "discard", "destroy", "clean", "clear"]),
    ("security", ["security", "vulnerability", "exploit", "attack", "protect", "secure", "risk", "danger"]),
    ("debug",   ["trace", "log", "investigate", "diagnose", "check"]),
]

_EMOTION_PATTERNS: list[tuple[str, list[str]]] = [
    ("positive",  ["good", "great", "excellent", "amazing", "love", "happy", "awesome", "perfect"]),
    ("negative",  ["bad", "terrible", "awful", "hate", "sad", "angry", "horrible", "worst"]),
    ("uncertain", ["maybe", "perhaps", "somewhat", "kind of", "a bit", "seems", "might", "possibly", "guess"]),
    ("urgent",    ["urgent", " ASAP", " immediately", "now", "quickly", "fast", "critical", "emergency"]),
    ("curious",   ["wonder", "好奇", "explore", "explore", "out of curiosity"]),
]

_RISK_PATTERNS: list[tuple[str, float]] = [
    ("high",    ["danger", "risk", "vulnerability", "exploit", "attack", "breach", "critical", "fatal"]),
    ("medium",  ["caution", "careful", "warning", "potential", "possible", "maybe", "risky"]),
    ("low",     ["safe", "secure", "stable", "reliable", "trustworthy", "verified"]),
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
        total_patterns = 0
        best_intent = "unknown"
        best_conf = 0.2  # default low confidence

        for intent, keywords in _INTENT_PATTERNS:
            total_patterns += 1
            # Use word-boundary matching to avoid substring false positives
            hits = sum(1 for kw in keywords if re.search(rf'\b{re.escape(kw)}\b', text_lower))
            if hits > 0:
                matches += hits
                conf = min(hits / max(len(keywords), 1), 1.0) * 0.8 + 0.1
                if conf >= best_conf:
                    best_conf = conf
                    best_intent = intent

        if matches == 0:
            # Check for question patterns
            if "?" in text or any(q in text_lower for q in ("how to", "what is", "why", "can i", "should i")):
                return "inquire", 0.5
            if text.strip().startswith(("/", "!", "#")):
                return "command", 0.3
        return best_intent, best_conf

    # ── Emotion detection ────────────────────────────────────────

    def _detect_emotion(self, text: str) -> tuple[str, float]:
        text_lower = text.lower()
        matches = 0
        best_emotion = "neutral"
        best_conf = 0.2

        for emotion, keywords in _EMOTION_PATTERNS:
            hits = sum(1 for kw in keywords if re.search(rf'\b{re.escape(kw)}\b', text_lower))
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
            hits = sum(1 for kw in keywords if re.search(rf'\b{re.escape(kw)}\b', text_lower))
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
