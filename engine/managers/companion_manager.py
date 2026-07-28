"""``CompanionManager`` - factory for :class:`Companion` objects.

Bible section 6 lists Companion as a planned core entity; this is the manager
behind it, matching the shape of every other manager: it is the only code that
reads ``companions.json``, and it hands out live objects.
"""

from __future__ import annotations

from typing import Any, Sequence

from engine.entities.companion import Companion, CompanionDefinition
from engine.managers.data_loader import ContentError, DataLoader
from engine.managers.race_manager import RaceManager
from engine.managers.skill_manager import SkillManager
from engine.stats import Formulas

__all__ = ["CompanionManager"]


class CompanionManager:
    """Loads companion definitions and recruits them at the right level."""

    COMPANION_FILE = "companions.json"

    def __init__(
        self,
        loader: DataLoader,
        skill_manager: SkillManager,
        race_manager: RaceManager,
        formulas: Formulas,
    ) -> None:
        self._loader = loader
        self._skills = skill_manager
        self._races = race_manager
        self._formulas = formulas
        self._definitions: dict[str, CompanionDefinition] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    def load(self) -> None:
        if self._loaded:
            return
        # Optional: a build with no companion content should still run.
        for entry in self._loader.load_entries(self.COMPANION_FILE, "companions", required=False):
            try:
                definition = CompanionDefinition.from_dict(entry)
            except ValueError as exc:
                raise ContentError(f"{self.COMPANION_FILE}: {exc}") from exc
            if definition.id in self._definitions:
                raise ContentError(f"duplicate companion id {definition.id!r} in {self.COMPANION_FILE}")
            self._definitions[definition.id] = definition
        self._loaded = True

    # ------------------------------------------------------------------
    def get(self, companion_id: str) -> CompanionDefinition | None:
        self.load()
        return self._definitions.get(companion_id)

    def require(self, companion_id: str) -> CompanionDefinition:
        definition = self.get(companion_id)
        if definition is None:
            raise ContentError(f"unknown companion id {companion_id!r}")
        return definition

    def all_definitions(self) -> list[CompanionDefinition]:
        self.load()
        return sorted(self._definitions.values(), key=lambda c: c.name)

    def at_location(self, area_id: str) -> list[CompanionDefinition]:
        """Recruitable companions found in one area."""
        self.load()
        return [c for c in self.all_definitions() if c.location_id == area_id]

    # ------------------------------------------------------------------
    def create(self, companion_id: str, player_level: int) -> Companion:
        """Instantiate a companion scaled to the player."""
        definition = self.require(companion_id)
        return Companion(
            definition=definition,
            level=definition.level_for(player_level),
            race_def=self._races.require(definition.race_id),
            formulas=self._formulas,
            skills=self._skills.get_many(definition.skill_ids),
        )

    def count(self) -> int:
        self.load()
        return len(self._definitions)
