"""Load race definitions from ``data/races.json``."""

from __future__ import annotations

from engine.managers.data_loader import ContentError, DataLoader
from engine.races import RaceDefinition

__all__ = ["RaceManager"]


class RaceManager:
    RACE_FILE = "races.json"

    def __init__(self, loader: DataLoader) -> None:
        self._loader = loader
        self._definitions: dict[str, RaceDefinition] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        for entry in self._loader.load_entries(self.RACE_FILE, "races"):
            try:
                definition = RaceDefinition.from_dict(entry)
            except ValueError as exc:
                raise ContentError(f"{self.RACE_FILE}: {exc}") from exc
            if definition.id in self._definitions:
                raise ContentError(f"duplicate race id {definition.id!r} in {self.RACE_FILE}")
            self._definitions[definition.id] = definition
        if not self._definitions:
            raise ContentError(f"{self.RACE_FILE} defines no races")
        self._loaded = True

    def get(self, race_id: str) -> RaceDefinition | None:
        self.load()
        return self._definitions.get(race_id)

    def require(self, race_id: str) -> RaceDefinition:
        definition = self.get(race_id)
        if definition is None:
            raise ContentError(f"unknown race id {race_id!r}")
        return definition

    def all_definitions(self) -> list[RaceDefinition]:
        self.load()
        return sorted(self._definitions.values(), key=lambda race: race.name)

    def count(self) -> int:
        self.load()
        return len(self._definitions)
