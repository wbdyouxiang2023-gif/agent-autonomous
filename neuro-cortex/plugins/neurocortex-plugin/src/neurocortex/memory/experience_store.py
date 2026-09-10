"""Experience Store — JSONL persistence for Phase 11."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from ..event import Experience

if TYPE_CHECKING:
    from ..event import CortexEvent


class ExperienceStore:
    """
    Append-only JSONL experience store.

    Each line is a JSON-serialized Experience object.
    Supports:
    - Saving experiences
    - Loading all experiences
    - Loading by experience_id
    - Graceful handling of malformed lines
    """

    def __init__(self, store_path: str | None = None):
        self._path = Path(store_path) if store_path else None
        self._experiences: dict[str, Experience] = {}
        if self._path:
            self._load_from_file()

    def _load_from_file(self) -> None:
        """Load all experiences from JSONL file."""
        if not self._path or not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    exp = Experience.from_dict(data)
                    self._experiences[exp.experience_id] = exp
                except (json.JSONDecodeError, TypeError):
                    # Skip malformed lines
                    continue

    def save(self, experience: Experience) -> None:
        """Save an experience (append-only)."""
        self._experiences[experience.experience_id] = experience
        if self._path:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(experience.to_dict(), ensure_ascii=False) + "\n")

    def get(self, experience_id: str) -> Experience | None:
        """Get an experience by ID."""
        return self._experiences.get(experience_id)

    def list_all(self) -> list[Experience]:
        """List all stored experiences."""
        return list(self._experiences.values())

    def count(self) -> int:
        """Return number of stored experiences."""
        return len(self._experiences)

    def clear(self) -> None:
        """Remove all experiences."""
        self._experiences.clear()
        if self._path and self._path.exists():
            self._path.unlink()

    @property
    def path(self) -> Path | None:
        return self._path
