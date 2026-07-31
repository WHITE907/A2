"""Data-driven quest definitions and per-character quest progress.

Quest content is represented by :class:`QuestDefinition` instances rather than
one Python class per story.  New quests are JSON entries; code changes are only
needed when a genuinely new objective behaviour is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

__all__ = ["QuestDefinition", "QuestObjective", "QuestReward"]


@dataclass(frozen=True)
class QuestObjective:
    """One measurable requirement in a quest."""

    kind: str
    target_id: str
    quantity: int = 1

    @property
    def key(self) -> str:
        """Stable save key, independent of objective order in the JSON file."""
        return f"{self.kind}:{self.target_id}"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "QuestObjective":
        kind = str(payload.get("kind", "")).strip()
        target_id = str(payload.get("target_id", "")).strip()
        quantity = int(payload.get("quantity", 1))
        if not kind:
            raise ValueError("quest objective is missing a 'kind'")
        if not target_id:
            raise ValueError("quest objective is missing a 'target_id'")
        if quantity < 1:
            raise ValueError("quest objective quantity must be at least 1")
        return cls(kind=kind, target_id=target_id, quantity=quantity)


@dataclass(frozen=True)
class QuestReward:
    """Rewards granted once when a quest is turned in."""

    exp: float = 0.0
    gold: int = 0
    items: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "QuestReward":
        data = payload or {}
        items = {str(item_id): int(quantity) for item_id, quantity in (data.get("items") or {}).items()}
        if float(data.get("exp", 0.0)) < 0 or int(data.get("gold", 0)) < 0:
            raise ValueError("quest rewards cannot be negative")
        if any(quantity < 1 for quantity in items.values()):
            raise ValueError("quest item reward quantities must be at least 1")
        return cls(exp=float(data.get("exp", 0.0)), gold=int(data.get("gold", 0)), items=items)


@dataclass(frozen=True)
class QuestDefinition:
    """The single content class used by every quest."""

    id: str
    name: str
    description: str
    min_level: int = 1
    giver_id: str = ""
    start_area_id: str = ""
    turn_in_area_id: str = ""
    required_companion_id: str = ""
    required_class_ids: tuple[str, ...] = ()
    #: Heritage quests can be offered only to a race or a specific lineage.
    required_race_ids: tuple[str, ...] = ()
    required_sub_race_ids: tuple[str, ...] = ()
    prerequisite_quest_ids: tuple[str, ...] = ()
    objectives: tuple[QuestObjective, ...] = ()
    rewards: QuestReward = field(default_factory=QuestReward)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "QuestDefinition":
        quest_id = str(payload.get("id", "")).strip()
        if not quest_id:
            raise ValueError("quest entry is missing an 'id'")
        name = str(payload.get("name", quest_id.replace("_", " ").title())).strip()
        objectives = tuple(QuestObjective.from_dict(entry) for entry in payload.get("objectives", []))
        if not objectives:
            raise ValueError(f"quest {quest_id!r} defines no objectives")
        keys = [objective.key for objective in objectives]
        if len(keys) != len(set(keys)):
            raise ValueError(f"quest {quest_id!r} contains duplicate objectives")
        min_level = int(payload.get("min_level", 1))
        if min_level < 1:
            raise ValueError(f"quest {quest_id!r} min_level must be at least 1")
        return cls(
            id=quest_id,
            name=name,
            description=str(payload.get("description", "")),
            min_level=min_level,
            giver_id=str(payload.get("giver_id", "")),
            start_area_id=str(payload.get("start_area_id", "")),
            turn_in_area_id=str(payload.get("turn_in_area_id", payload.get("start_area_id", ""))),
            required_companion_id=str(payload.get("required_companion_id", "")),
            required_class_ids=tuple(str(value) for value in payload.get("required_class_ids", [])),
            required_race_ids=tuple(str(value).lower() for value in payload.get("required_race_ids", [])),
            required_sub_race_ids=tuple(str(value).lower() for value in payload.get("required_sub_race_ids", [])),
            prerequisite_quest_ids=tuple(str(value) for value in payload.get("prerequisite_quest_ids", [])),
            objectives=objectives,
            rewards=QuestReward.from_dict(payload.get("rewards")),
        )

    def progress_lines(self, progress: Mapping[str, int]) -> list[str]:
        """Human-readable objective checklist for engine and GUI callers."""
        lines: list[str] = []
        for objective in self.objectives:
            current = min(objective.quantity, int(progress.get(objective.key, 0)))
            target = objective.target_id.replace("_", " ").title()
            verb = objective.kind.replace("_", " ").title()
            lines.append(f"{verb}: {target} ({current}/{objective.quantity})")
        return lines
