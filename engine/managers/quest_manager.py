"""Load quest content and apply objective events to a player's quest log."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from engine.managers.data_loader import ContentError, DataLoader
from engine.quests import QuestDefinition

__all__ = ["QuestManager"]


class QuestManager:
    """Repository and progression rules for data-driven quests."""

    QUEST_FILE = "quests.json"
    DEFEAT_OBJECTIVE = "defeat_enemy"
    SUPPORTED_OBJECTIVES = frozenset({
        DEFEAT_OBJECTIVE,
        "collect_item", "visit_area", "talk_to", "recruit_companion",
        "travel_with_companion", "equip_item_type", "affinity",
        "battle_no_downs", "battle_turn_limit", "choice",
    })

    def __init__(self, loader: DataLoader) -> None:
        self._loader = loader
        self._definitions: dict[str, QuestDefinition] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        for entry in self._loader.load_entries(self.QUEST_FILE, "quests"):
            try:
                definition = QuestDefinition.from_dict(entry)
            except (TypeError, ValueError) as exc:
                raise ContentError(f"{self.QUEST_FILE}: {exc}") from exc
            if definition.id in self._definitions:
                raise ContentError(f"duplicate quest id {definition.id!r} in {self.QUEST_FILE}")
            unsupported = {objective.kind for objective in definition.objectives} - self.SUPPORTED_OBJECTIVES
            if unsupported:
                names = ", ".join(sorted(unsupported))
                raise ContentError(f"quest {definition.id!r} uses unsupported objective type(s): {names}")
            self._definitions[definition.id] = definition
        if not self._definitions:
            raise ContentError(f"{self.QUEST_FILE} defines no quests")
        self._validate_prerequisites()
        self._loaded = True

    def _validate_prerequisites(self) -> None:
        for definition in self._definitions.values():
            for quest_id in definition.prerequisite_quest_ids:
                if quest_id not in self._definitions:
                    raise ContentError(f"quest {definition.id!r} requires unknown quest {quest_id!r}")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(quest_id: str) -> None:
            if quest_id in visiting:
                raise ContentError(f"quest prerequisite cycle includes {quest_id!r}")
            if quest_id in visited:
                return
            visiting.add(quest_id)
            for prerequisite in self._definitions[quest_id].prerequisite_quest_ids:
                visit(prerequisite)
            visiting.remove(quest_id)
            visited.add(quest_id)

        for quest_id in self._definitions:
            visit(quest_id)

    def get(self, quest_id: str) -> QuestDefinition | None:
        self.load()
        return self._definitions.get(quest_id)

    def require(self, quest_id: str) -> QuestDefinition:
        definition = self.get(quest_id)
        if definition is None:
            raise ContentError(f"unknown quest id {quest_id!r}")
        return definition

    def all_definitions(self) -> list[QuestDefinition]:
        self.load()
        return sorted(self._definitions.values(), key=lambda quest: (quest.min_level, quest.name))

    def available_for(
        self,
        player,
        area_id: str = "",
        giver_id: str | None = None,
    ) -> list[QuestDefinition]:
        """Quests this player can accept from the current place and giver."""
        available: list[QuestDefinition] = []
        for definition in self.all_definitions():
            if definition.id in player.active_quests or definition.id in player.completed_quests:
                continue
            if player.level < definition.min_level:
                continue
            if definition.required_class_ids and player.class_def.id not in definition.required_class_ids:
                continue
            if definition.start_area_id and definition.start_area_id != area_id:
                continue
            if giver_id is not None and definition.giver_id != giver_id:
                continue
            if any(quest_id not in player.completed_quests for quest_id in definition.prerequisite_quest_ids):
                continue
            available.append(definition)
        return available

    def active_for(self, player) -> list[QuestDefinition]:
        self.load()
        return [self._definitions[quest_id] for quest_id in player.active_quests if quest_id in self._definitions]

    def record_event(
        self, player, kind: str, target_id: str, amount: int = 1, *, absolute: bool = False
    ) -> list[str]:
        """Apply one generic gameplay event to every matching active objective."""
        changed: list[str] = []
        for definition in self.active_for(player):
            quest_changed = False
            for objective in definition.objectives:
                if objective.kind != kind or objective.target_id != str(target_id):
                    continue
                before = player.quest_progress_value(definition.id, objective.key)
                delta = max(0, int(amount) - before) if absolute else int(amount)
                after = player.advance_quest(
                    definition.id, objective.key, delta, maximum=objective.quantity
                )
                quest_changed = quest_changed or after != before
            if quest_changed:
                changed.append(definition.id)
        return changed

    def record_defeats(self, player, enemy_ids: Iterable[str]) -> list[str]:
        """Advance defeat objectives, preserving group kill counts."""
        changed: list[str] = []
        for enemy_id, count in Counter(str(value) for value in enemy_ids).items():
            for quest_id in self.record_event(player, self.DEFEAT_OBJECTIVE, enemy_id, count):
                if quest_id not in changed:
                    changed.append(quest_id)
        return changed

    def can_complete(self, player, quest_id: str) -> tuple[bool, list[str]]:
        definition = self.get(quest_id)
        if definition is None:
            return False, ["Unknown quest."]
        if quest_id in player.completed_quests:
            return False, ["Quest already completed."]
        if quest_id not in player.active_quests:
            return False, ["Quest is not active."]

        progress = player.quest_progress.get(quest_id, {})
        unmet = [
            line
            for objective, line in zip(definition.objectives, definition.progress_lines(progress))
            if int(progress.get(objective.key, 0)) < objective.quantity
        ]
        return (not unmet), unmet

    def count(self) -> int:
        self.load()
        return len(self._definitions)
