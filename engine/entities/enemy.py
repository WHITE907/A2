"""``Enemy`` - ONE class for every monster in the game.

Every enemy is an instance spawned by
:meth:`~engine.managers.enemy_manager.EnemyManager.spawn`; nothing here is
subclassed per monster (docs/ENGINE_DESIGN.md).

Bible section 13: JSON-driven stats, growth, AI, skills, loot, EXP, gold and
level scaling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from engine.entities.entity import Entity
from engine.skills.skill import Skill
from engine.stats import Formulas, ModifierSet, StatBlock

__all__ = ["Enemy", "LootEntry", "EnemyTemplate"]


@dataclass
class LootEntry:
    """One possible drop."""

    item_id: str
    chance: float = 1.0
    min_quantity: int = 1
    max_quantity: int = 1
    guaranteed: bool = False
    rarity: str = ""
    min_rarity: str = ""
    rarity_weights: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LootEntry":
        quantity = payload.get("quantity")
        low = int(payload.get("min_quantity", quantity if quantity is not None else 1))
        high = int(payload.get("max_quantity", quantity if quantity is not None else low))
        rw = payload.get("rarity_weights") or {}
        return cls(
            item_id=str(payload.get("item_id", payload.get("id", ""))),
            chance=float(payload.get("chance", 1.0)),
            min_quantity=low,
            max_quantity=max(low, high),
            guaranteed=bool(payload.get("guaranteed", False)),
            rarity=str(payload.get("rarity", "")).lower(),
            min_rarity=str(payload.get("min_rarity", "")).lower(),
            rarity_weights={str(k).lower(): float(v) for k, v in rw.items()},
        )


@dataclass
class EnemyTemplate:
    """Immutable blueprint shared by every spawn of one monster type."""

    id: str
    name: str
    base_level: int = 1
    base_stats: StatBlock = field(default_factory=StatBlock)
    growth: StatBlock = field(default_factory=StatBlock)
    skill_ids: list[str] = field(default_factory=list)
    ai_behavior_id: str = "aggressive"
    loot: list[LootEntry] = field(default_factory=list)
    exp_reward: float = 10.0
    gold_reward: int = 5
    reward_scaling: float = 0.1
    modifiers: ModifierSet = field(default_factory=ModifierSet)
    description: str = ""
    family: str = "beast"
    is_boss: bool = False
    mastery_reward: float = 0.0
    boss_phases: list[dict[str, Any]] = field(default_factory=list)
    boss_rules: dict[str, Any] = field(default_factory=dict)
    guaranteed_rarity_min: str = ""
    resistance: dict[str, float] = field(default_factory=dict)

    def stats_at_level(self, level: int) -> StatBlock:
        result = self.base_stats.copy()
        steps = max(0, level - self.base_level)
        for key in ("STR", "END", "INT", "AGI"):
            result[key] = result[key] + self.growth[key] * steps
        return result

    def rewards_at_level(self, level: int) -> tuple[float, int]:
        steps = max(0, level - self.base_level)
        multiplier = 1.0 + self.reward_scaling * steps
        return (self.exp_reward * multiplier, int(self.gold_reward * multiplier))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EnemyTemplate":
        enemy_id = str(payload.get("id", "")).strip()
        if not enemy_id:
            raise ValueError("enemy entry is missing an 'id'")
        return cls(
            id=enemy_id,
            name=str(payload.get("name", enemy_id)),
            base_level=int(payload.get("base_level", 1)),
            base_stats=StatBlock.from_dict(payload.get("base_stats")),
            growth=StatBlock.from_dict(payload.get("growth")),
            skill_ids=[str(s) for s in payload.get("skill_ids", [])],
            ai_behavior_id=str(payload.get("ai_behavior_id", "aggressive")),
            loot=[LootEntry.from_dict(item) for item in payload.get("loot", [])],
            exp_reward=float(payload.get("exp_reward", 10.0)),
            gold_reward=int(payload.get("gold_reward", 5)),
            reward_scaling=float(payload.get("reward_scaling", 0.1)),
            modifiers=ModifierSet.from_dict(payload.get("modifiers")),
            description=str(payload.get("description", "")),
            family=str(payload.get("family", "beast")),
            is_boss=bool(payload.get("is_boss", False)),
            mastery_reward=float(payload.get("mastery_reward", 0.0)),
            boss_phases=[dict(value) for value in payload.get("boss_phases", [])],
            boss_rules=dict(payload.get("boss_rules") or {}),
            guaranteed_rarity_min=str(payload.get("guaranteed_rarity_min", "")).lower(),
            resistance={str(k).lower(): float(v) for k, v in (payload.get("resistance") or {}).items()},
        )


class Enemy(Entity):
    """A live monster in a battle."""

    def __init__(
        self,
        template: EnemyTemplate,
        level: int,
        formulas: Formulas,
        skills: Sequence[Skill] = (),
        name_suffix: str = "",
    ) -> None:
        self.template = template
        self.skills: list[Skill] = list(skills)
        self.cooldowns: dict[str, int] = {}
        self.ai_behavior_id = template.ai_behavior_id
        self.name_suffix = name_suffix
        self.boss_phase: int = 0
        self._phase_modifiers = ModifierSet()

        display_name = f"{template.name} {name_suffix}".strip()
        super().__init__(
            name=display_name,
            level=level,
            base_stats=template.stats_at_level(level),
            formulas=formulas,
        )

    @property
    def resistance(self) -> dict[str, float]:
        return self.template.resistance

    def _equipment_modifiers(self) -> ModifierSet:
        combined = ModifierSet()
        combined.merge(self.template.modifiers)
        combined.merge(self._phase_modifiers)
        return combined

    def enter_boss_phase(self, index: int, modifiers: Mapping[str, Any] | None = None) -> None:
        self.boss_phase = index
        self._phase_modifiers = ModifierSet.from_dict(modifiers)
        self.invalidate_stats()

    @property
    def is_boss(self) -> bool:
        return self.template.is_boss

    def rewards(self) -> tuple[float, int]:
        return self.template.rewards_at_level(self.level)

    def usable_skills(self) -> list[Skill]:
        return [s for s in self.skills if s.is_usable_in_combat and s.can_use(self)[0]]

    def tick_cooldowns(self) -> None:
        for skill_id in list(self.cooldowns):
            self.cooldowns[skill_id] -= 1
            if self.cooldowns[skill_id] <= 0:
                del self.cooldowns[skill_id]

    def roll_loot(self, rng: Any, item_manager: Any | None = None, rarity_config: Mapping[str, Any] | None = None) -> list[tuple[str, int]]:
        drops: list[tuple[str, int]] = []
        guaranteed_dropped = False

        def resolve_variant(base_id: str, desired_rarity: str) -> str:
            if not desired_rarity or item_manager is None:
                return base_id
            base_item = item_manager.get(base_id) if item_manager else None
            if base_item is None:
                return base_id
            if base_item.rarity.lower() == desired_rarity.lower():
                return base_id
            try:
                variant = item_manager.get_or_create_variant(base_id, desired_rarity)
                return variant.id
            except Exception:
                return base_id

        for entry in self.template.loot:
            if not entry.item_id:
                continue
            is_guaranteed_entry = entry.guaranteed
            if self.template.is_boss and not guaranteed_dropped and not any(e.guaranteed for e in self.template.loot):
                if entry is self.template.loot[0]:
                    is_guaranteed_entry = True

            should_drop = is_guaranteed_entry or rng.chance(entry.chance)
            if not should_drop:
                continue

            quantity = rng.randint(entry.min_quantity, entry.max_quantity)
            if quantity <= 0:
                continue

            final_id = entry.item_id
            if entry.rarity:
                final_id = resolve_variant(final_id, entry.rarity)
            elif entry.rarity_weights and rng is not None and item_manager is not None:
                choices = list(entry.rarity_weights.items())
                total = sum(w for _, w in choices)
                if total > 0:
                    roll = rng.uniform(0, total)
                    cum = 0.0
                    for rarity, weight in choices:
                        cum += weight
                        if roll <= cum:
                            final_id = resolve_variant(final_id, rarity)
                            break
            elif entry.min_rarity and item_manager is not None:
                base_item = item_manager.get(final_id)
                if base_item and base_item.is_equipment:
                    final_id = resolve_variant(final_id, entry.min_rarity)

            drops.append((final_id, quantity))
            if is_guaranteed_entry:
                guaranteed_dropped = True

        if self.template.is_boss and not guaranteed_dropped:
            for entry in self.template.loot:
                if entry.guaranteed or entry.chance >= 1.0:
                    final_id = entry.item_id
                    if entry.rarity:
                        final_id = resolve_variant(final_id, entry.rarity)
                    elif entry.min_rarity:
                        final_id = resolve_variant(final_id, entry.min_rarity)
                    quantity = rng.randint(entry.min_quantity, entry.max_quantity) if rng else entry.min_quantity
                    if quantity > 0:
                        drops.append((final_id, quantity))
                        guaranteed_dropped = True
                        break
            if not guaranteed_dropped and self.template.loot:
                entry = self.template.loot[0]
                final_id = entry.item_id
                if entry.rarity:
                    final_id = resolve_variant(final_id, entry.rarity)
                quantity = rng.randint(entry.min_quantity, entry.max_quantity) if rng else entry.min_quantity
                drops.append((final_id, max(1, quantity)))

        if self.template.is_boss and item_manager is not None and rarity_config:
            min_rarity = (self.template.guaranteed_rarity_min or "rare").lower()
            order = ["common", "uncommon", "rare", "epic", "legendary"]
            min_idx = order.index(min_rarity) if min_rarity in order else 2
            has_high = False
            for item_id, _ in drops:
                it = item_manager.get(item_id)
                if it and it.rarity.lower() in order:
                    if order.index(it.rarity.lower()) >= min_idx:
                        has_high = True
                        break
            if not has_high and drops:
                for idx, (item_id, qty) in enumerate(drops):
                    it = item_manager.get(item_id)
                    if it and it.is_equipment:
                        upgraded_id = resolve_variant(item_id.split("@")[0], min_rarity)
                        drops[idx] = (upgraded_id, qty)
                        has_high = True
                        break

        return drops

    def summary_lines(self) -> list[str]:
        lines = [
            f"Name: {self.name}",
            f"Level: {self.level}",
            f"HP: {self.hp_text()}",
            f"MP: {self.mp_text()}",
            f"Family: {self.template.family.title()}",
        ]
        if self.statuses:
            lines.append("Status: " + ", ".join(self.status_summaries()))
        return lines

    def to_dict(self) -> dict[str, Any]:
        data = self._serialise_common()
        data.update(
            {
                "template_id": self.template.id,
                "name_suffix": self.name_suffix,
                "cooldowns": dict(self.cooldowns),
            }
        )
        return data
