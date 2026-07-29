"""Data-driven playable and world races.

Race count scales through ``data/races.json`` rather than Python subclasses.
Each definition composes primary-stat adjustments, derived modifiers, and
presentation-only trait descriptions. Sub-races add unique bonus traits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from engine.stats import ModifierSet, StatBlock

__all__ = ["RaceDefinition", "SubRace"]


@dataclass(frozen=True)
class SubRace:
    """A sub-race variant with unique bonus traits."""

    id: str
    name: str
    description: str = ""
    bonus_stats: StatBlock = field(default_factory=StatBlock)
    bonus_modifiers: ModifierSet = field(default_factory=ModifierSet)
    bonus_traits: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SubRace":
        sub_id = str(payload.get("id", "")).strip()
        if not sub_id:
            raise ValueError("sub-race entry is missing an 'id'")
        return cls(
            id=sub_id,
            name=str(payload.get("name", sub_id.replace("_", " ").title())),
            description=str(payload.get("description", "")),
            bonus_stats=StatBlock.from_dict(payload.get("bonus_stats")),
            bonus_modifiers=ModifierSet.from_dict(payload.get("bonus_modifiers")),
            bonus_traits=tuple(str(trait) for trait in payload.get("bonus_traits", [])),
        )

    def detail_lines(self) -> list[str]:
        lines = [self.name]
        if self.description:
            lines.append(self.description)
        for stat, value in self.bonus_stats.to_dict().items():
            if value:
                lines.append(f"{value:+d} {stat}")
        lines.extend(self.bonus_modifiers.describe())
        lines.extend(f"Bonus Trait: {trait}" for trait in self.bonus_traits)
        return lines


@dataclass(frozen=True)
class RaceDefinition:
    """One playable/world ancestry definition."""

    id: str
    name: str
    description: str = ""
    base_stats: StatBlock = field(default_factory=StatBlock)
    modifiers: ModifierSet = field(default_factory=ModifierSet)
    traits: tuple[str, ...] = ()
    sub_races: tuple[SubRace, ...] = ()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RaceDefinition":
        race_id = str(payload.get("id", "")).strip()
        if not race_id:
            raise ValueError("race entry is missing an 'id'")
        sub_races = tuple(SubRace.from_dict(sr) for sr in payload.get("sub_races", []))
        return cls(
            id=race_id,
            name=str(payload.get("name", race_id.replace("_", " ").title())),
            description=str(payload.get("description", "")),
            base_stats=StatBlock.from_dict(payload.get("base_stats")),
            modifiers=ModifierSet.from_dict(payload.get("modifiers")),
            traits=tuple(str(trait) for trait in payload.get("traits", [])),
            sub_races=sub_races,
        )

    def get_sub_race(self, sub_race_id: str) -> SubRace | None:
        """Look up a sub-race by id."""
        for sub in self.sub_races:
            if sub.id == sub_race_id:
                return sub
        return None

    def combined_stats(self, sub_race_id: str = "") -> StatBlock:
        """Base stats plus sub-race bonus stats."""
        result = self.base_stats.copy()
        if sub_race_id:
            sub = self.get_sub_race(sub_race_id)
            if sub:
                result = result.add(sub.bonus_stats)
        return result

    def combined_modifiers(self, sub_race_id: str = "") -> ModifierSet:
        """Base modifiers plus sub-race bonus modifiers."""
        combined = ModifierSet()
        combined.merge(self.modifiers)
        if sub_race_id:
            sub = self.get_sub_race(sub_race_id)
            if sub:
                combined.merge(sub.bonus_modifiers)
        return combined

    def combined_traits(self, sub_race_id: str = "") -> tuple[str, ...]:
        """Base traits plus sub-race bonus traits."""
        traits = list(self.traits)
        if sub_race_id:
            sub = self.get_sub_race(sub_race_id)
            if sub:
                traits.extend(sub.bonus_traits)
        return tuple(traits)

    def detail_lines(self) -> list[str]:
        lines = [self.name]
        if self.description:
            lines.append(self.description)
        for stat, value in self.base_stats.to_dict().items():
            if value:
                lines.append(f"{value:+d} {stat}")
        lines.extend(self.modifiers.describe())
        lines.extend(f"Trait: {trait}" for trait in self.traits)
        if self.sub_races:
            lines.append("")
            lines.append("Sub-races:")
            for sub in self.sub_races:
                lines.append(f"  • {sub.name}")
        return lines
