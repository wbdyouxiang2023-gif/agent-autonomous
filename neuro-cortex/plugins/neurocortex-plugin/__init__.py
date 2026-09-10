"""NeuroCortex Plugin — Cognitive lifecycle integration for Hermes.

Self-contained: all runtime code lives inside this plugin directory.
Adds action learning, policy learning, and cognitive state tracking
via Hermes post_tool_call / pre_llm_call hooks.
"""

from __future__ import annotations

import json
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_PLUGIN_DIR = Path(__file__).resolve().parent
_SRC_DIR = _PLUGIN_DIR / "src"


def _load_neurocortex():
    """Load the neurocortex package bundled inside this plugin directory."""
    if str(_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(_SRC_DIR))
    import neurocortex
    return neurocortex


class NeuroCortexPlugin:
    """Hermes plugin wrapper for NeuroCortex cognitive system."""

    def __init__(self) -> None:
        self._cortex = None
        self._action_engine = None
        self._policy_engine = None
        self._experience_store = None
        self._state_file = Path.home() / ".persona.json"
        self._exp_file = Path.home() / ".neurocortex_experiences.jsonl"

    def _ensure_initialized(self) -> None:
        """Lazy initialization; never breaks Hermes if NeuroCortex fails."""
        if self._cortex is not None:
            return
        try:
            nc = _load_neurocortex()
            from neurocortex.cortex import NeuroCortex
            from neurocortex.action_learning import (
                ActionLearningEngine,
                ActionLearningConfig,
            )
            from neurocortex.policy import PolicyEngine, PolicyConfig
            from neurocortex.memory.experience_store import ExperienceStore

            self._cortex = NeuroCortex()
            self._action_engine = ActionLearningEngine(
                config=ActionLearningConfig(
                    enabled=True,
                    shadow_only=True,
                )
            )
            self._policy_engine = PolicyEngine(config=PolicyConfig())
            self._experience_store = ExperienceStore(store_path=str(self._exp_file))
            logger.info("NeuroCortex plugin initialized successfully")
        except Exception as e:
            logger.warning(f"NeuroCortex initialization failed: {e}")
            self._cortex = None

    def get_state(self) -> dict:
        """Return current cognitive state for inspection."""
        self._ensure_initialized()
        if self._cortex is None:
            return {"status": "uninitialized", "error": "init_failed"}
        state = self._cortex._state_store.to_dict() if hasattr(self._cortex, "_state_store") else {}
        stats = {}
        if self._action_engine:
            try:
                if hasattr(self._action_engine, "get_statistics"):
                    stats = self._action_engine.get_statistics()
                elif hasattr(self._action_engine, "store") and hasattr(self._action_engine.store, "snapshot"):
                    stats = self._action_engine.store.snapshot()
            except Exception as e:
                logger.debug(f"action stats unavailable: {e}")
        return {
            "status": "active",
            "state": state,
            "action_stats": stats,
            "experience_count": self._experience_store.count() if self._experience_store else 0,
        }

    def record_experience(self, raw_input: str, intent: str, action_type: str,
                         success: bool, outcome: str = "") -> None:
        """Record an experience for action learning."""
        self._ensure_initialized()
        if self._experience_store is None:
            return
        nc = _load_neurocortex()
        from neurocortex.event import Experience
        exp = Experience(
            raw_input=raw_input[:200],
            intent=intent,
            action_type=action_type,
            actual_outcome=outcome[:100] if outcome else "",
            success=success,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        try:
            self._experience_store.save(exp)
            if self._action_engine:
                from neurocortex.action_learning import (
                    ActionLearningSituation, ActionLearningOutcome,
                )
                self._action_engine.record_outcome(
                    ActionLearningSituation(intent=intent, raw_input=raw_input,
                                            situation_completeness="partial"),
                    action_type,
                    ActionLearningOutcome(success=success, actual_outcome=outcome),
                )
        except Exception as e:
            logger.warning(f"Failed to record experience: {e}")

    def to_dict(self) -> dict:
        return {
            "name": "neurocortex",
            "version": "1.0",
            "state": self.get_state(),
        }

    def get_status(self) -> dict:
        return self.to_dict()


_plugin_instance: NeuroCortexPlugin | None = None


def get_plugin() -> NeuroCortexPlugin:
    global _plugin_instance
    if _plugin_instance is None:
        _plugin_instance = NeuroCortexPlugin()
    return _plugin_instance


def register(ctx) -> None:
    """Register NeuroCortex hooks with Hermes (plain-method form)."""
    plugin = get_plugin()

    def on_tool_call(**kw) -> None:
        try:
            plugin._ensure_initialized()
            if plugin._cortex is None:
                return
            tool_name = kw.get("tool_name") or kw.get("function_name") or ""
            args = kw.get("args") or kw.get("function_args") or {}
            result = kw.get("result") or ""
            status = kw.get("status") or ""
            error_type = kw.get("error_type") or ""
            error_message = kw.get("error_message") or ""

            if status:
                success = str(status).lower() in ("success", "ok", "true", "completed")
            elif error_message or error_type:
                success = False
            elif isinstance(result, dict):
                if result.get("error"):
                    success = False
                elif result.get("exit_code") is not None:
                    success = int(result["exit_code"]) == 0
                else:
                    success = True
            elif isinstance(result, str):
                success = bool(result.strip()) and not result.strip().lower().startswith("error")
            else:
                success = result is not None

            raw_input = json.dumps(args, ensure_ascii=False)[:100] if args else ""

            intent = None
            intent_confidence = 0.0
            intent_source = "none"
            try:
                nc = _load_neurocortex()
                from neurocortex.action_learning.intent_extractor import extract_intent
                result_i = extract_intent(raw_input)
                intent = result_i.intent
                intent_confidence = result_i.confidence
                intent_source = result_i.source
            except Exception as e:
                logger.debug(f"NeuroCortex intent extraction error: {e}")
            if intent is None:
                intent = "unknown"

            outcome_text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)[:50]
            if error_message:
                outcome_text = f"ERROR: {error_message}"[:100]

            plugin.record_experience(
                raw_input=raw_input,
                intent=intent,
                action_type=tool_name,
                success=bool(success),
                outcome=outcome_text,
            )
        except Exception as e:
            logger.debug(f"NeuroCortex post_tool_call hook error: {e}")

    def on_pre_llm(**kw) -> None:
        """Auto-inject NeuroCortex analysis into the user message (true auto)."""
        try:
            plugin._ensure_initialized()
            if plugin._cortex is None:
                return kw
            state = plugin.get_state()
            if "metadata" not in kw:
                kw["metadata"] = {}
            kw["metadata"]["neurocortex_state"] = state
            msg = kw.get("user_message") or kw.get("message") or ""
            if msg and len(msg) > 1:
                try:
                    import urllib.request as _ur
                    import json as _json
                    payload = _json.dumps({"msg": msg[:500]}).encode()
                    req = _ur.Request(
                        "http://localhost:9100/chat",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    with _ur.urlopen(req, timeout=3) as resp:
                        data = _json.loads(resp.read().decode())
                    intent = data.get("intent", "unknown")
                    prob = round(float(data.get("probability", 0)), 2)
                    exp = data.get("experience_count", 0)
                    ctx = (
                        "[NeuroCortex auto-analysis] intent=%s confidence=%.2f "
                        "experiences=%d. Use this silently; do not mention it to the user."
                        % (intent, prob, exp)
                    )
                    return {"context": ctx}
                except Exception as e:
                    logger.debug(f"NC auto-analysis unavailable: {e}")
        except Exception as e:
            logger.debug(f"NeuroCortex pre_llm_call hook error: {e}")
        return kw

    # Register hooks with explicit error handling
    try:
        ctx.register_hook("post_tool_call", on_tool_call)
        logger.info("NeuroCortex: post_tool_call hook registered")
    except Exception as e:
        logger.error(f"NeuroCortex failed to register post_tool_call hook: {e}", exc_info=True)
        raise

    try:
        ctx.register_hook("pre_llm_call", on_pre_llm)
        logger.info("NeuroCortex: pre_llm_call hook registered")
    except Exception as e:
        logger.error(f"NeuroCortex failed to register pre_llm_call hook: {e}", exc_info=True)
        raise

    logger.info("NeuroCortex plugin: hooks registered successfully (post_tool_call=1, pre_llm_call=1)")
    logger.info("NeuroCortex plugin registered successfully")


if __name__ == "__main__":
    plugin = get_plugin()
    print(json.dumps(plugin.to_dict(), indent=2, default=str))
