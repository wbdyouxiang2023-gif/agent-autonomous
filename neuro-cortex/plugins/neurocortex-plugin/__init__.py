"""NeuroCortex Plugin — Cognitive lifecycle integration for Hermes.

Adds action learning, policy learning, and cognitive state tracking
to the Hermes Agent via post_tool_call hook.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _load_neurocortex():
    """Load neurocortex from source path.

    The plugin directory is now named 'neurocortex-plugin' (NOT
    'neurocortex'), so the real source package name is unambiguous.
    We still insert the source dir into sys.path to be safe.
    """
    _neuro_src = Path.home() / "workspace" / "agent-autonomous" / "neuro-cortex" / "src"
    if str(_neuro_src) not in sys.path:
        sys.path.insert(0, str(_neuro_src))
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
        """Lazy initialization to avoid breaking Hermes if neurocortex fails."""
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
            # Enable learning explicitly — the plugin's whole job is to
            # collect real outcomes. Shadow-only stays ON (never changes
            # real decisions), but recording MUST be active or nothing
            # is ever learned.
            self._action_engine = ActionLearningEngine(
                config=ActionLearningConfig(
                    enabled=True,          # record real outcomes
                    shadow_only=True,      # never alter real decisions
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

        state = self._cortex._state_store.to_dict() if hasattr(self._cortex, '_state_store') else {}

        # Add action learning stats
        stats = {}
        if self._action_engine:
            stats = self._action_engine.get_statistics()

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
                # ActionLearningEngine.record_outcome(situation, action, outcome)
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
        """Serialize plugin state."""
        return {
            "name": "neurocortex",
            "version": "1.0",
            "state": self.get_state(),
        }

    def get_status(self) -> dict:
        """Return plugin status for diagnostics."""
        return self.to_dict()


# Hermes plugin interface
_plugin_instance: NeuroCortexPlugin | None = None


def get_plugin() -> NeuroCortexPlugin:
    """Get or create the plugin singleton."""
    global _plugin_instance
    if _plugin_instance is None:
        _plugin_instance = NeuroCortexPlugin()
    return _plugin_instance


def register(ctx) -> None:
    """Register NeuroCortex hooks with Hermes.

    Hermes PluginContext.register_hook(name, callback) is a PLAIN METHOD,
    not a decorator. Calling it as a decorator (``@ctx.register_hook(...)``)
    passes the function as ``callback=`` positionally which breaks loading.
    """
    plugin = get_plugin()

    def on_tool_call(**kw) -> None:
        """Record tool call outcome for action learning.

        Real kwargs from _emit_post_tool_call_hook (tool_executor.py:274):
          function_name, function_args, result, task_id, session_id,
          tool_call_id, turn_id, duration_ms, status, error_type,
          error_message, middleware_trace
        """
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

            # success判定（从宽松到严格）:
            # 1. 显式 status 为 success / ok / true
            # 2. 有 error_message / error_type → 失败
            # 3. dict result: error 字段非空 → 失败；exit_code==0 → 成功
            # 4. 其他非空结果 → 成功
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

            # Raw input from args (the real tool arguments)
            raw_input = json.dumps(args, ensure_ascii=False)[:100] if args else ""

            # ── Level 5.0-R2: IntentExtractor replaces tool_name fallback ──
            # intent = raw_input → IntentExtractor → semantic intent
            # NEVER falls back to tool_name. None/unknown when uncertain.
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

            # Record for action learning
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
        """Inject cognitive state into LLM context."""
        try:
            plugin._ensure_initialized()
            if plugin._cortex is None:
                return kw

            state = plugin.get_state()
            if "metadata" not in kw:
                kw["metadata"] = {}
            kw["metadata"]["neurocortex_state"] = state

        except Exception as e:
            logger.debug(f"NeuroCortex pre_llm_call hook error: {e}")

        return kw

    ctx.register_hook("post_tool_call", on_tool_call)
    ctx.register_hook("pre_llm_call", on_pre_llm)
    logger.info("NeuroCortex plugin: hooks registered (post_tool_call, pre_llm_call)")

    logger.info("NeuroCortex plugin registered successfully")


# Allow direct import for testing
if __name__ == "__main__":
    plugin = get_plugin()
    print(json.dumps(plugin.to_dict(), indent=2, default=str))
