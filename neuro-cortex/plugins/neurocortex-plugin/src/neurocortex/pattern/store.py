"""Pattern Store — JSONL persistence for Phase 12 patterns."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from .pattern import Pattern

if TYPE_CHECKING:
    pass


class PatternStore:
    """
    Append-only JSONL pattern store.

    Each line is a JSON-serialized Pattern object.
    Supports:
    - Saving patterns
    - Loading all patterns
    - Loading by pattern_id
    - Graceful handling of malformed lines
    """

    def __init__(self, store_path: str | None = None):
        self._path = Path(store_path) if store_path else None
        self._patterns: dict[str, Pattern] = {}
        if self._path:
            self._load_from_file()

    def _load_from_file(self) -> None:
        """Load all patterns from JSONL file."""
        if not self._path or not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    pat = Pattern.from_dict(data)
                    self._patterns[pat.pattern_id] = pat
                except (json.JSONDecodeError, TypeError):
                    continue

    def save(self, pattern: Pattern) -> None:
        """Save a pattern (append-only)."""
        self._patterns[pattern.pattern_id] = pattern
        if self._path:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(pattern.to_dict(), ensure_ascii=False) + "\n")

    def save_all(self, patterns: list[Pattern]) -> None:
        """
        Save all patterns, replacing the file content.

        Use this after full consolidation to ensure a clean state.
        """
        self._patterns.clear()
        for pat in patterns:
            self._patterns[pat.pattern_id] = pat
        if self._path:
            with open(self._path, "w", encoding="utf-8") as f:
                for pat in patterns:
                    f.write(json.dumps(pat.to_dict(), ensure_ascii=False) + "\n")

    def get(self, pattern_id: str) -> Pattern | None:
        """Get a pattern by ID."""
        return self._patterns.get(pattern_id)

    def list_all(self) -> list[Pattern]:
        """List all stored patterns."""
        return list(self._patterns.values())

    def list_active(self) -> list[Pattern]:
        """List only active (non-retired, non-weakening) patterns."""
        return [p for p in self._patterns.values() if p.is_active()]

    def count(self) -> int:
        """Return number of stored patterns."""
        return len(self._patterns)

    def count_active(self) -> int:
        """Return number of active patterns."""
        return sum(1 for p in self._patterns.values() if p.is_active())

    def clear(self) -> None:
        """Remove all patterns."""
        self._patterns.clear()
        if self._path and self._path.exists():
            self._path.unlink()

    @property
    def path(self) -> Path | None:
        return self._path
