"""``Skill`` - ONE class for every skill in the game.

Fireball, Power Strike, a future Ultimate: all instances of this class,
differing only in the list of :class:`~engine.skills.effects.Effect` objects
composed into them.  Adding the 200th skill is a JSON diff (docs/ENGINE_DESIGN.md).

Skill categories come from bible section 11: core, active, passive, weapon,
shared, ultimate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from engine.skills.effects import Effect, EffectContext, EffectResult, build_effects
from engine.stats import ModifierSet

__all__ = ["Skill", "SkillCategory", "SkillTargeting", "SkillUseResult"]


class SkillCategory:
    """Bible section 11 categories."""

    CORE = "core"
    ACTIVE = "active"
    PASSIVE = "passive"
    WEAPON = "weapon"
    SHARED = "shared"
    ULTIMATE = "ultimate"

    ALL = (CORE, ACTIVE, PASSIVE, WEAPON, SHARED, ULTIMATE)
    #: Categories that appear as a choosable action in combat.
    USABLE = (CORE, ACTIVE, WEAPON, SHARED, ULTIMATE)


class SkillTargeting:
    """Who a skill can be aimed at."""

    ENEMY = "enemy"
    ALL_ENEMIES = "all_enemies"
    SELF = "self"
    ALLY = "ally"
    ALL_ALLIES = "all_allies"

    ALL = (ENEMY, ALL_ENEMIES, SELF, ALLY, ALL_ALLIES)
    #: Targeting modes that need the player to pick a specific target.
    NEEDS_PICK = (ENEMY, ALLY)


@dataclass
class SkillUseResult:
    """Everything that happened from one activation - the combat log entry."""

    skill_name: str
    caster_name: str
    success: bool = True
    failure_reason: str = ""
    mp_spent: float = 0.0
    results: list[EffectResult] = field(default_factory=list)

    @property
    def messages(self) -> list[str]:
        return [r.message for r in self.results if r.message]

    @property
    def total_damage(self) -> float:
        return sum(r.amount for r in self.results if r.kind == "damage")

    @property
    def total_healing(self) -> float:
        return sum(r.amount for r in self.results if r.kind == "heal")

    @property
    def any_crit(self) -> bool:
        return any(r.crit for r in self.results)

    @property
    def killed_targets(self) -> list[str]:
        return [r.target_name for r in self.results if r.lethal]

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill_name,
            "caster": self.caster_name,
            "success": self.success,
            "failure_reason": self.failure_reason,
            "mp_spent": self.mp_spent,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class Skill:
    """A single skill definition + its runtime behaviour."""

    id: str
    name: str
    category: str = SkillCategory.ACTIVE
    description: str = ""
    mp_cost: float = 0.0
    sp_cost: float = 0.0
    hp_cost: float = 0.0
    cooldown: int = 0
    targeting: str = SkillTargeting.ENEMY
    effects: list[Effect] = field(default_factory=list)
    #: Always-on stat bonuses; only meaningful for passives.
    passive_modifiers: ModifierSet = field(default_factory=ModifierSet)
    #: Skill-point cost to learn, and gating requirements.
    skill_point_cost: int = 1
    required_level: int = 1
    required_class_ids: list[str] = field(default_factory=list)
    required_weapon_types: list[str] = field(default_factory=list)
    required_mastery: dict[str, str] = field(default_factory=dict)
    prerequisites: list[str] = field(default_factory=list)
    required_race_ids: list[str] = field(default_factory=list)
    #: Optional lineage gate, used by sub-race techniques.
    required_sub_race_ids: list[str] = field(default_factory=list)
    #: Mastery track this skill trains when used (e.g. ``"sword"``).
    mastery_track: str = ""
    icon: str = ""
    #: Skill tags for categorization and resource determination (e.g. "physical", "magical", "fire")
    tags: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    @property
    def is_passive(self) -> bool:
        return self.category == SkillCategory.PASSIVE

    @property
    def is_usable_in_combat(self) -> bool:
        return self.category in SkillCategory.USABLE and bool(self.effects)

    @property
    def needs_target_pick(self) -> bool:
        return self.targeting in SkillTargeting.NEEDS_PICK

    @property
    def hits_all_enemies(self) -> bool:
        return self.targeting == SkillTargeting.ALL_ENEMIES

    @property
    def is_physical(self) -> bool:
        """True if tagged as physical (uses stamina)."""
        return "physical" in self.tags

    @property
    def is_magical(self) -> bool:
        """True if tagged as magical (uses mana)."""
        return "magical" in self.tags

    @property
    def is_hybrid(self) -> bool:
        """True if tagged as both physical and magical."""
        return self.is_physical and self.is_magical

    # ------------------------------------------------------------------
    # Targeting
    # ------------------------------------------------------------------
    def resolve_targets(
        self,
        caster: Any,
        chosen: Sequence[Any],
        allies: Sequence[Any],
        enemies: Sequence[Any],
        effect: Effect | None = None,
    ) -> list[Any]:
        """Work out which entities an effect actually lands on.

        An individual effect may override the skill-level targeting - that is
        what lets a single JSON entry describe "damage the enemy *and* shield
        yourself" without needing two skills.
        """
        mode = (effect.target_override if effect and effect.target_override else self.targeting) or self.targeting
        if mode == SkillTargeting.SELF:
            return [caster]
        if mode == SkillTargeting.ALL_ENEMIES:
            return [e for e in enemies if e.is_alive]
        if mode == SkillTargeting.ALL_ALLIES:
            return [a for a in allies if a.is_alive]
        if mode == SkillTargeting.ALLY:
            picked = [t for t in chosen if t in allies and t.is_alive]
            return picked or [caster]
        picked = [t for t in chosen if t.is_alive]
        if picked:
            return picked
        living = [e for e in enemies if e.is_alive]
        return living[:1]

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------
    def can_use(self, caster: Any) -> tuple[bool, str]:
        """Check costs and cooldown.  Returns ``(ok, reason_if_not)``."""
        if self.is_passive:
            return False, f"{self.name} is a passive skill."
        if not caster.is_alive:
            return False, f"{caster.name} cannot act."
        if not caster.can_afford(self.mp_cost):
            return False, f"Not enough MP for {self.name}."
        if self.sp_cost and not caster.can_afford_sp(self.sp_cost):
            return False, f"Not enough SP for {self.name}."
        if self.hp_cost and caster.current_hp <= self.hp_cost:
            return False, f"Not enough HP for {self.name}."
        remaining = getattr(caster, "cooldowns", {}).get(self.id, 0)
        if remaining > 0:
            return False, f"{self.name} is on cooldown ({remaining} turns)."
        return True, ""

    def use(
        self,
        caster: Any,
        targets: Sequence[Any],
        ctx: EffectContext,
        allies: Sequence[Any] | None = None,
        enemies: Sequence[Any] | None = None,
    ) -> SkillUseResult:
        """Pay costs, run every effect, and report what happened.

        The combat loop calls this without knowing what any specific skill
        does - that is the whole point of the composition pattern.
        """
        allies = list(allies) if allies is not None else [caster]
        enemies = list(enemies) if enemies is not None else list(targets)

        ok, reason = self.can_use(caster)
        if not ok:
            return SkillUseResult(self.name, caster.name, success=False, failure_reason=reason)

        caster.spend_mp(self.mp_cost)
        if self.sp_cost:
            caster.spend_sp(self.sp_cost)
        if self.hp_cost:
            caster.take_raw_damage(self.hp_cost, damage_type="true", ignore_shield=True)

        outcome = SkillUseResult(self.name, caster.name, mp_spent=self.mp_cost)

        for effect in self.effects:
            for target in self.resolve_targets(caster, targets, allies, enemies, effect):
                result = effect.apply(caster, target, ctx)
                if result is not None:
                    outcome.results.append(result)

        if self.cooldown > 0 and hasattr(caster, "cooldowns"):
            # +1 because the caster's own end-of-turn tick decrements it in
            # the same round; without this a "2 turn" cooldown lasts only 1.
            caster.cooldowns[self.id] = self.cooldown + 1

        return outcome

    # ------------------------------------------------------------------
    # Presentation
    # ------------------------------------------------------------------
    def cost_text(self) -> str:
        bits = []
        if self.mp_cost:
            bits.append(f"{self.mp_cost:.0f} MP")
        if self.sp_cost:
            bits.append(f"{self.sp_cost:.0f} SP")
        if self.hp_cost:
            bits.append(f"{self.hp_cost:.0f} HP")
        if self.cooldown:
            bits.append(f"CD {self.cooldown}")
        return " | ".join(bits) or "No cost"

    def effect_lines(self) -> list[str]:
        if self.is_passive:
            return self.passive_modifiers.describe() or ["No effect"]
        return [effect.describe() for effect in self.effects] or ["No effect"]

    def detail_lines(self) -> list[str]:
        """Full tooltip block for the Skills screen."""
        lines = [f"{self.name}  [{self.category.title()}]"]
        if self.tags:
            lines.append(f"Tags: {', '.join(t.title() for t in self.tags)}")
        if self.description:
            lines.append(self.description)
        lines.append(self.cost_text())
        lines.extend(f"- {line}" for line in self.effect_lines())
        if self.required_weapon_types:
            lines.append(f"Requires weapon: {', '.join(self.required_weapon_types)}")
        return lines

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Skill":
        skill_id = str(payload.get("id", "")).strip()
        if not skill_id:
            raise ValueError("skill entry is missing an 'id'")

        category = str(payload.get("category", SkillCategory.ACTIVE)).lower()
        if category not in SkillCategory.ALL:
            raise ValueError(f"skill {skill_id!r} has unknown category {category!r}")

        targeting = str(payload.get("targeting", SkillTargeting.ENEMY)).lower()
        if targeting not in SkillTargeting.ALL:
            raise ValueError(f"skill {skill_id!r} has unknown targeting {targeting!r}")

        return cls(
            id=skill_id,
            name=str(payload.get("name", skill_id)),
            category=category,
            description=str(payload.get("description", "")),
            mp_cost=float(payload.get("mp_cost", 0.0)),
            sp_cost=float(payload.get("sp_cost", 0.0)),
            hp_cost=float(payload.get("hp_cost", 0.0)),
            cooldown=int(payload.get("cooldown", 0)),
            targeting=targeting,
            effects=build_effects(payload.get("effects")),
            passive_modifiers=ModifierSet.from_dict(payload.get("passive_modifiers")),
            skill_point_cost=int(payload.get("skill_point_cost", 1)),
            required_level=int(payload.get("required_level", 1)),
            required_class_ids=[str(v) for v in payload.get("required_class_ids", [])],
            required_weapon_types=[str(v) for v in payload.get("required_weapon_types", [])],
            required_mastery={str(k): str(v) for k, v in (payload.get("required_mastery") or {}).items()},
            prerequisites=[str(v) for v in payload.get("prerequisites", [])],
            required_race_ids=[str(v).lower() for v in payload.get("required_race_ids", [])],
            required_sub_race_ids=[str(v).lower() for v in payload.get("required_sub_race_ids", [])],
            mastery_track=str(payload.get("mastery_track", "")),
            icon=str(payload.get("icon", "")),
            tags=[str(t).lower() for t in payload.get("tags", [])],
        )
