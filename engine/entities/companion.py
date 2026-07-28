"""``Companion`` - ONE class for every recruitable ally (roadmap v0.0.9).

Bible section 6 lists Companion as a planned core entity.  It follows the same
rule as Skill/Enemy/Item (docs/ENGINE_DESIGN.md): one Python class, many JSON
entries.  Rook the mercenary and Iven the scholar are *instances*, not
subclasses.

Two deliberate design choices, both to avoid systems that add grind without
adding depth:

**Companions level with the player**, offset by ``level_offset``, rather than
earning separate EXP.  A companion that falls behind becomes dead weight and
forces the player to bench them - which is exactly the opposite of what a
companion system is for.  The offset still lets content authors ship a
deliberately fragile healer or an over-levelled bodyguard.

**Companions fight themselves**, through the existing AI registry
(``engine/combat/ai.py``).  They are allies, so :class:`Battle` already routes
their turns; nothing in the combat loop needed a companion-shaped special case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from engine.entities.entity import Entity
from engine.skills.skill import Skill
from engine.stats import Formulas, ModifierSet, StatBlock

__all__ = ["Companion", "CompanionDefinition", "RecruitRequirement"]


@dataclass
class RecruitRequirement:
    """What the player must satisfy before a companion will join."""

    level: int = 1
    affinity: int = 0
    gold: int = 0
    items: dict[str, int] = field(default_factory=dict)
    quests: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "RecruitRequirement":
        payload = payload or {}
        raw_items = payload.get("items") or {}
        if isinstance(raw_items, Mapping):
            items = {str(k): int(v) for k, v in raw_items.items()}
        elif isinstance(raw_items, (str, bytes)):
            items = {str(raw_items): 1}
        else:
            items = {str(item): 1 for item in raw_items}
        return cls(
            level=int(payload.get("level", 1)),
            affinity=int(payload.get("affinity", 0)),
            gold=int(payload.get("gold", 0)),
            items=items,
            quests=[str(q) for q in payload.get("quests", [])],
        )

    def describe(self) -> list[str]:
        lines: list[str] = []
        if self.level > 1:
            lines.append(f"Level {self.level}")
        if self.affinity:
            lines.append(f"Affinity {self.affinity}")
        if self.gold:
            lines.append(f"{self.gold} gold")
        lines.extend(f"{i.replace('_', ' ').title()} x{q}" for i, q in self.items.items())
        lines.extend(f"Quest: {q.replace('_', ' ').title()}" for q in self.quests)
        return lines


@dataclass
class CompanionDefinition:
    """Immutable blueprint for one companion.

    Satisfies the same informal "suitor" shape as
    :class:`~engine.world.world.NPC` (``id``/``name``/``marriageable``/
    ``marriage_affinity``/``gift_item_ids``), which is what lets
    :mod:`engine.relationships` drive affinity and marriage for both without
    branching on type.
    """

    id: str
    name: str
    description: str = ""
    role: str = "fighter"
    base_stats: StatBlock = field(default_factory=StatBlock)
    growth: StatBlock = field(default_factory=StatBlock)
    skill_ids: list[str] = field(default_factory=list)
    ai_behavior_id: str = "aggressive"
    #: Level relative to the player - negative is deliberately fragile.
    level_offset: int = 0
    modifiers: ModifierSet = field(default_factory=ModifierSet)
    weapon_type: str = ""
    #: Where the player can find and recruit them.
    location_id: str = ""
    recruit: RecruitRequirement = field(default_factory=RecruitRequirement)
    dialogue: list[str] = field(default_factory=list)
    #: -- relationship fields, shared shape with NPC --
    marriageable: bool = False
    marriage_affinity: int = 80
    gift_item_ids: list[str] = field(default_factory=list)

    def stats_at_level(self, level: int) -> StatBlock:
        result = self.base_stats.copy()
        steps = max(0, level - 1)
        for key in ("STR", "END", "INT", "AGI"):
            result[key] = result[key] + self.growth[key] * steps
        return result

    def level_for(self, player_level: int) -> int:
        return max(1, player_level + self.level_offset)

    def detail_lines(self) -> list[str]:
        lines = [self.name]
        if self.description:
            lines.append(self.description)
        lines.append(f"Role: {self.role.title()}")
        if self.weapon_type:
            lines.append(f"Fights with: {self.weapon_type.title()}")
        return lines

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompanionDefinition":
        companion_id = str(payload.get("id", "")).strip()
        if not companion_id:
            raise ValueError("companion entry is missing an 'id'")
        return cls(
            id=companion_id,
            name=str(payload.get("name", companion_id)),
            description=str(payload.get("description", "")),
            role=str(payload.get("role", "fighter")),
            base_stats=StatBlock.from_dict(payload.get("base_stats")),
            growth=StatBlock.from_dict(payload.get("growth")),
            skill_ids=[str(s) for s in payload.get("skill_ids", [])],
            ai_behavior_id=str(payload.get("ai_behavior_id", "aggressive")),
            level_offset=int(payload.get("level_offset", 0)),
            modifiers=ModifierSet.from_dict(payload.get("modifiers")),
            weapon_type=str(payload.get("weapon_type", "")).lower(),
            location_id=str(payload.get("location_id", "")),
            recruit=RecruitRequirement.from_dict(payload.get("recruit")),
            dialogue=[str(line) for line in payload.get("dialogue", [])],
            marriageable=bool(payload.get("marriageable", False)),
            marriage_affinity=int(payload.get("marriage_affinity", 80)),
            gift_item_ids=[str(i) for i in payload.get("gift_item_ids", [])],
        )


class Companion(Entity):
    """A live recruited ally in the party."""

    def __init__(
        self,
        definition: CompanionDefinition,
        level: int,
        formulas: Formulas,
        skills: Sequence[Skill] = (),
    ) -> None:
        self.definition = definition
        self.skills: list[Skill] = list(skills)
        self.cooldowns: dict[str, int] = {}
        self.ai_behavior_id = definition.ai_behavior_id
        #: Set by the party when a marriage bonus applies.
        self._married_bonus: ModifierSet | None = None

        super().__init__(
            name=definition.name,
            level=level,
            base_stats=definition.stats_at_level(level),
            formulas=formulas,
        )

    # ------------------------------------------------------------------
    @property
    def id(self) -> str:
        return self.definition.id

    def _equipment_modifiers(self) -> ModifierSet:
        """Companions carry no gear; template + marriage bonuses stand in."""
        combined = ModifierSet()
        combined.merge(self.definition.modifiers)
        if self._married_bonus is not None:
            combined.merge(self._married_bonus)
        return combined

    def set_married_bonus(self, bonus: ModifierSet | None) -> None:
        """Apply (or clear) the spouse bonus and refresh derived stats."""
        self._married_bonus = bonus
        self.invalidate_stats()

    def sync_level(self, player_level: int) -> bool:
        """Re-level to track the player.  Returns ``True`` if it changed.

        HP/MP are scaled proportionally rather than refilled, so levelling up
        between fights is a boost without being a free heal.
        """
        target = self.definition.level_for(player_level)
        if target == self.level:
            return False

        hp_fraction = self.hp_fraction if self.max_hp else 1.0
        mp_fraction = self.mp_fraction if self.max_mp else 1.0

        self.level = target
        self.base_stats = self.definition.stats_at_level(target)
        self.invalidate_stats()

        self.current_hp = max(1.0, float(self.max_hp) * hp_fraction)
        self.current_mp = float(self.max_mp) * mp_fraction
        return True

    # ------------------------------------------------------------------
    def usable_skills(self) -> list[Skill]:
        """What the AI may choose from this turn."""
        return [s for s in self.skills if s.is_usable_in_combat and s.can_use(self)[0]]

    def tick_cooldowns(self) -> None:
        for skill_id in list(self.cooldowns):
            self.cooldowns[skill_id] -= 1
            if self.cooldowns[skill_id] <= 0:
                del self.cooldowns[skill_id]

    # ------------------------------------------------------------------
    def summary_lines(self) -> list[str]:
        lines = [
            f"Name: {self.name}",
            f"Role: {self.definition.role.title()}",
            f"Level: {self.level}",
            f"HP: {self.hp_text()}",
            f"MP: {self.mp_text()}",
        ]
        if self.statuses:
            lines.append("Status: " + ", ".join(self.status_summaries()))
        return lines

    def to_dict(self) -> dict[str, Any]:
        data = self._serialise_common()
        data.update({"companion_id": self.definition.id, "cooldowns": dict(self.cooldowns)})
        return data
