"""Pattern Consolidator — groups experiences into patterns by condition."""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from .pattern import Pattern

if TYPE_CHECKING:
    from ..memory.experience_store import ExperienceStore


class PatternConsolidator:
    """
    Examines an ExperienceStore and produces/updates Pattern records.

    Consolidation Algorithm (v1):
      1. Group all experiences by (intent, action_type)
      2. For each group with >= 1 experience:
         a. Compute success_rate = success_count / total
         b. Compute contradiction_count (minority outcome count)
         c. Compute confidence from evidence model
         d. Determine lifecycle status
      3. Return list of Pattern objects

    Deterministic: same experience set → same pattern set.
    No ML, no clustering, no embeddings.
    """

    def consolidate(self, store: "ExperienceStore") -> list[Pattern]:
        """
        Scan all experiences and produce patterns.

        Args:
            store: ExperienceStore containing experiences to consolidate

        Returns:
            List of Pattern objects, one per unique (intent, action_type) group
            that has at least 1 experience.
        """
        experiences = store.list_all()
        if not experiences:
            return []

        # Group by (intent, action_type)
        groups: dict[tuple[str, str], list] = defaultdict(list)
        for exp in experiences:
            key = (exp.intent, exp.action_type)
            groups[key].append(exp)

        # Create one pattern per group
        patterns = []
        for (intent, action_type), exps in sorted(groups.items()):
            predicted_outcome = ""
            # Derive predicted_outcome from the majority outcome
            success_count = sum(1 for e in exps if e.success)
            if success_count > len(exps) / 2:
                predicted_outcome = f"{intent}完成" if intent else "general完成"
            else:
                predicted_outcome = f"{intent}失败" if intent else "general失败"

            pattern = Pattern.create(
                condition_intent=intent,
                condition_action_type=action_type,
                experiences=exps,
                predicted_outcome=predicted_outcome,
            )
            patterns.append(pattern)

        return patterns

    def consolidate_incremental(
        self,
        store: "ExperienceStore",
        existing_patterns: list[Pattern],
        new_experience_ids: set[str],
    ) -> list[Pattern]:
        """
        Incremental consolidation: only re-process groups containing new experiences.

        More efficient than full consolidation when only a few new experiences arrived.

        Args:
            store: Full experience store
            existing_patterns: Previously computed patterns (for retention)
            new_experience_ids: Set of experience IDs added since last consolidation

        Returns:
            Updated pattern list (retained old patterns + recomputed new ones)
        """
        if not new_experience_ids:
            return existing_patterns

        # Find which groups have new experiences
        all_exps = store.list_all()
        new_exp_map = {e.experience_id: e for e in all_exps if e.experience_id in new_experience_ids}

        if not new_exp_map:
            return existing_patterns

        # Group new experiences by (intent, action_type)
        new_groups: dict[tuple[str, str], list] = defaultdict(list)
        for exp in new_exp_map.values():
            key = (exp.intent, exp.action_type)
            new_groups[key].append(exp)

        # Build lookup: existing pattern → (intent, action_type)
        existing_map: dict[tuple[str, str], Pattern] = {}
        for p in existing_patterns:
            if p.is_active():
                existing_map[(p.condition_intent, p.condition_action_type)] = p

        # Re-consolidate only affected groups, merge with unaffected
        updated_patterns = []
        processed_groups = set()

        for (intent, action_type), new_exps in new_groups.items():
            key = (intent, action_type)
            processed_groups.add(key)

            # Gather ALL experiences for this group (existing + new)
            all_group_exps = [e for e in all_exps if e.intent == intent and e.action_type == action_type]

            # If we had an existing pattern for this group, merge source IDs
            existing = existing_map.get(key)
            if existing:
                # Keep existing source IDs, add new ones
                new_source_ids = {e.experience_id for e in all_group_exps}
                existing.source_experience_ids = list(
                    set(existing.source_experience_ids) | new_source_ids
                )
                # Rebuild from all experiences
                pattern = Pattern.create(
                    condition_intent=intent,
                    condition_action_type=action_type,
                    experiences=all_group_exps,
                    predicted_outcome=existing.predicted_outcome,
                )
                # Preserve retirement status if already retired
                if existing.status == "RETIRED":
                    pattern.retire()
                updated_patterns.append(pattern)
            else:
                # New group — create from scratch
                pattern = Pattern.create(
                    condition_intent=intent,
                    condition_action_type=action_type,
                    experiences=all_group_exps,
                )
                updated_patterns.append(pattern)

        # Retain unaffected existing patterns
        for p in existing_patterns:
            key = (p.condition_intent, p.condition_action_type)
            if key not in processed_groups:
                updated_patterns.append(p)

        return updated_patterns

    @staticmethod
    def should_consolidate(store_count: int, pattern_count: int, last_consolidation_count: int) -> bool:
        """
        Determine if consolidation should run (lazy trigger).

        Trigger when:
          - No patterns exist yet and store has >= 1 experience
          - Store has grown by >= 10 experiences since last consolidation

        Args:
            store_count: Current number of experiences in store
            pattern_count: Current number of patterns
            last_consolidation_count: Store count at last consolidation

        Returns:
            True if consolidation should run now
        """
        if pattern_count == 0 and store_count >= 1:
            return True
        if store_count - last_consolidation_count >= 10:
            return True
        return False
