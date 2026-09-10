#!/usr/bin/env python3
"""NeuroCortex Interactive Demo — Phase 0-11"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from neurocortex.cortex import NeuroCortex
from neurocortex.modules import MockPerception, MockRepresentation, MockAttention, MockState, MockMemory, MockDecision, MockAction, MockFeedback
from neurocortex.state import BasicStateModule
from neurocortex.prediction import BasicPrediction
from neurocortex.learning.experience_learner import ExperienceLearningModule
from neurocortex.memory.experience_store import ExperienceStore
from neurocortex.memory.experience_retriever import ExperienceRetriever
from neurocortex.prediction.experience_prediction import ExperiencePredictionModule
from neurocortex.interfaces import OutcomeProvider
from neurocortex.event import OutcomeData
import json


class FixedOutcomeProvider(OutcomeProvider):
    def __init__(self, success):
        self._success = success
    def provide(self, event):
        event.record_outcome(OutcomeData(actual_outcome="done", success=self._success))
        return event


STORE_PATH = os.path.expanduser("~/.neurocortex_experiences.jsonl")


def main():
    store = ExperienceStore(STORE_PATH)
    learner = ExperienceLearningModule(store)
    retriever = ExperienceRetriever(store, top_k=3)
    exp_pred = ExperiencePredictionModule(retriever, base_prediction=BasicPrediction())

    cortex = NeuroCortex(
        perception=MockPerception(), representation=MockRepresentation(),
        attention=MockAttention(), state=BasicStateModule(), memory=MockMemory(),
        prediction=exp_pred, decision=MockDecision(), action=MockAction(),
        outcome_provider=FixedOutcomeProvider(success=True),
        feedback=MockFeedback(),
        learning=learner,
    )

    print("=" * 60)
    print("  NeuroCortex v0.1 — Interactive Demo")
    print("  Commands: process <text>, status, retrieve <text>,")
    print("            list, clear, stats, help, exit")
    print("=" * 60)

    while True:
        try:
            cmd = input("\n>>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not cmd:
            continue

        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()

        if action in ("exit", "quit", "q"):
            print("Bye!")
            break

        elif action == "help":
            print("""
Commands:
  process <text>       Run the full cognitive pipeline on input
  status               Show current cortex state
  retrieve <text>      Query experience store
  list                 List all stored experiences
  clear                Clear experience store
  stats                Show store statistics
  exit                 Quit
""")

        elif action == "process" and len(parts) > 1:
            raw = parts[1]
            e = cortex.process(raw)
            s = e.state
            print(f"  stage     : {e.stage}")
            print(f"  intent    : {e.perception.intent}")
            print(f"  state     : curiosity={s.curiosity:.2f} motivation={s.motivation:.2f} uncertainty={s.uncertainty:.2f}")
            print(f"  prediction: {e.prediction.predicted_outcome} (prob={e.prediction.success_probability:.2f})")
            print(f"  decision  : action={e.decision.selected_action}")
            print(f"  outcome   : {e.outcome.actual_outcome} (success={e.outcome.success})")
            print(f"  evaluation: {e.feedback.evaluation}")
            print(f"  experiences: {store.count()} total")

        elif action == "status":
            print(f"  Cortex ready. Experience store: {store.count()} experiences")

        elif action == "retrieve" and len(parts) > 1:
            query = parts[1]
            results = retriever.retrieve(query)
            if not results:
                print(f"  No experiences found for '{query}'")
            else:
                print(f"  Top results for '{query}':")
                for exp, score in results:
                    print(f"    [{score:.2f}] '{exp.raw_input}' success={exp.success} tags={exp.context_tags}")

        elif action == "list":
            exps = store.list_all()
            if not exps:
                print("  No experiences stored yet.")
            else:
                for i, exp in enumerate(exps, 1):
                    print(f"  {i}. '{exp.raw_input}' success={exp.success} tags={exp.context_tags}")

        elif action == "clear":
            store.clear()
            retriever = ExperienceRetriever(store, top_k=3)
            exp_pred._retriever = retriever
            print("  Store cleared.")

        elif action == "stats":
            exps = store.list_all()
            if not exps:
                print("  No experiences yet.")
            else:
                successes = sum(1 for e in exps if e.success)
                failures = len(exps) - successes
                intents = {}
                actions = {}
                for e in exps:
                    intents[e.intent] = intents.get(e.intent, 0) + 1
                    actions[e.action_type] = actions.get(e.action_type, 0) + 1
                print(f"  Total: {len(exps)}")
                print(f"  Success: {successes}  Failure: {failures}")
                print(f"  By intent: {dict(intents)}")
                print(f"  By action: {dict(actions)}")

        else:
            print(f"  Unknown command: {action}. Type 'help' for options.")


if __name__ == "__main__":
    main()
