"""Data-driven playable and world races.

Race count scales through ``data/races.json`` rather than Python subclasses.
Each definition composes primary-stat adjustments, derived modifiers, and
presentation-only trait descriptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from engine.stats import ModifierSet, StatBlock

__all__ = ["RaceDefinition"]


@dataclass(frozen=True)
class RaceDefinition:
    """One playable/world ancestry definition."""

    id: str
    name: str
    description: str = ""
    base_stats: StatBlock = field(default_factory=StatBlock)
    modifiers: ModifierSet = field(default_factory=ModifierSet)
    traits: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RaceDefinition":
        race_id = str(payload.get("id", "")).strip()
        if not race_id:
            raise ValueError("race entry is missing an 'id'")
        return cls(
            id=race_id,
            name=str(payload.get("name", race_id.replace("_", " ").title())),
            description=str(payload.get("description", "")),
            base_stats=StatBlock.from_dict(payload.get("base_stats")),
            modifiers=ModifierSet.from_dict(payload.get("modifiers")),
            traits=tuple(str(trait) for trait in payload.get("traits", [])),
        )

    def detail_lines(self) -> list[str]:
        lines = [self.name]
        if self.description:
            lines.append(self.description)
        for stat, value in self.base_stats.to_dict().items():
            if value:
                lines.append(f"{value:+d} {stat}")
        lines.extend(self.modifiers.describe())
        lines.extend(f"Trait: {trait}" for trait in self.traits)
        return lines
