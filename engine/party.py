"""``Party`` - the player's recruited companions.

Split into an *active* roster that fights and a *reserve* that doesn't, because
an uncapped party turns every battle into the player watching six AI turns.
The cap comes from ``data/config.json`` (``party.max_active``).

The Party owns roster membership only.  Affinity lives on the Player (so it
survives dismissal) and marriage rules live in :mod:`engine.relationships`.
"""

from __future__ import annotations

from typing import Any, Iterator, Mapping, Sequence

from engine.entities.companion import Companion

__all__ = ["Party"]


class Party:
    """Active and reserve companions."""

    def __init__(self, max_active: int = 2) -> None:
        self.max_active = max(0, int(max_active))
        self.active: list[Companion] = []
        self.reserve: list[Companion] = []

    # ------------------------------------------------------------------
    def __iter__(self) -> Iterator[Companion]:
        """Every recruited companion, active first."""
        return iter([*self.active, *self.reserve])

    def __len__(self) -> int:
        return len(self.active) + len(self.reserve)

    @property
    def all_members(self) -> list[Companion]:
        return [*self.active, *self.reserve]

    @property
    def is_active_full(self) -> bool:
        return len(self.active) >= self.max_active

    def has(self, companion_id: str) -> bool:
        return self.get(companion_id) is not None

    def get(self, companion_id: str) -> Companion | None:
        return next((c for c in self.all_members if c.id == companion_id), None)

    def is_active(self, companion_id: str) -> bool:
        return any(c.id == companion_id for c in self.active)

    # ------------------------------------------------------------------
    def recruit(self, companion: Companion) -> tuple[bool, str]:
        """Add a companion, benching them if the active roster is full."""
        if self.has(companion.id):
            return False, f"{companion.name} is already with you."
        if self.is_active_full:
            self.reserve.append(companion)
            return True, f"{companion.name} joins your party (in reserve)."
        self.active.append(companion)
        return True, f"{companion.name} joins your party!"

    def dismiss(self, companion_id: str) -> tuple[bool, str]:
        """Remove a companion entirely.

        Their affinity is untouched - it lives on the Player - so re-recruiting
        later resumes the relationship rather than resetting it.
        """
        companion = self.get(companion_id)
        if companion is None:
            return False, "They are not in your party."
        self.active = [c for c in self.active if c.id != companion_id]
        self.reserve = [c for c in self.reserve if c.id != companion_id]
        return True, f"{companion.name} leaves your party."

    def set_active(self, companion_id: str, active: bool) -> tuple[bool, str]:
        """Move a companion between the active roster and the bench."""
        companion = self.get(companion_id)
        if companion is None:
            return False, "They are not in your party."

        if active:
            if self.is_active(companion_id):
                return False, f"{companion.name} is already active."
            if self.is_active_full:
                return False, f"Your active party is full ({self.max_active})."
            self.reserve = [c for c in self.reserve if c.id != companion_id]
            self.active.append(companion)
            return True, f"{companion.name} joins the front line."

        if not self.is_active(companion_id):
            return False, f"{companion.name} is already resting."
        self.active = [c for c in self.active if c.id != companion_id]
        self.reserve.append(companion)
        return True, f"{companion.name} falls back to reserve."

    # ------------------------------------------------------------------
    def battle_allies(self) -> list[Companion]:
        """Living active companions - what :class:`Battle` receives."""
        return [c for c in self.active if c.is_alive]

    def sync_levels(self, player_level: int) -> list[str]:
        """Keep every companion tracking the player's level."""
        messages = []
        for companion in self.all_members:
            if companion.sync_level(player_level):
                messages.append(f"{companion.name} is now level {companion.level}.")
        return messages

    def restore_all(self) -> None:
        """Full heal - inn rest, respawn."""
        for companion in self.all_members:
            companion.restore_fully()

    def revive_fallen(self) -> list[str]:
        """Bring downed companions back after a battle.

        They return at a fraction of max HP rather than staying dead: a
        permanently lost companion in a game with no resurrection item would be
        a silent dead end.
        """
        messages = []
        for companion in self.all_members:
            if not companion.is_alive:
                companion.current_hp = max(1.0, companion.max_hp * 0.25)
                companion.statuses.clear()
                companion.invalidate_stats()
                messages.append(f"{companion.name} gets back on their feet.")
        return messages

    def clear_battle_state(self) -> None:
        """Drop cooldowns and lingering statuses between encounters."""
        for companion in self.all_members:
            companion.cooldowns.clear()
            companion.statuses.clear()
            companion.invalidate_stats()

    # ------------------------------------------------------------------
    def summary_lines(self) -> list[str]:
        if not self.all_members:
            return ["No companions."]
        lines = [f"Active ({len(self.active)}/{self.max_active}):"]
        if self.active:
            lines.extend(f"  {c.name} - Lv {c.level} - {c.hp_text()} HP" for c in self.active)
        else:
            lines.append("  (none)")
        if self.reserve:
            lines.append("Reserve:")
            lines.extend(f"  {c.name} - Lv {c.level}" for c in self.reserve)
        return lines

    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "max_active": self.max_active,
            "active": [c.to_dict() for c in self.active],
            "reserve": [c.to_dict() for c in self.reserve],
        }
