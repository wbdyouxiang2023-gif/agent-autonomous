"""State module - thin pipeline adapter for CortexState."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neurocortex.event import CortexEvent
else:
    from neurocortex.interfaces import StateModule


class BasicStateModule(StateModule):
    """
    Thin pipeline adapter for CortexState.

    Responsibilities:
    - Ensure event.state exists
    - Call event.update_state() to advance stage
    - No state computation
    - Pure passthrough for state values

    Does NOT:
    - Call update_from_event()
    - Create temporary CortexState
    - Compute state changes
    - Store state (that's Cortex's job)
    """

    def process(self, event: CortexEvent) -> CortexEvent:
        """Ensure event.state exists, then advance stage."""
        if not event.state:
            from neurocortex.event import InternalState
            event.state = InternalState()
        # Advance stage from ATTENTION to STATE
        event.update_state()
        return event
