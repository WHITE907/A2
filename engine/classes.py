"""``ClassDefinition`` - ONE class covering every character class in the game.

Warrior, Mage, and every future promotion are *instances* built from JSON, not
subclasses (docs/ENGINE_DESIGN.md).

Bible section 10:

- Gender-restricted starting classes
- Seven promotion tiers
- Promotion requires level, stats, mastery, items and quests
- Promotion expands the skill tree, changes the core skill, keeps learned
  skills, and unlocks ultimates later
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from engine.mastery import rank_at_least
from engine.stats import PRIMARY_STATS, ModifierSet, StatBlock

__all__ = ["MAX_TIER", "PromotionRequirement", "PromotionCheck", "ClassDefinition"]

#: Bible section 10 - seven promotion tiers.  Tier 1 is the starting class,
#: so tiers run 1..7 and tier 7 is the apex.
MAX_TIER: int = 7


def _deduplicate(ids: Sequence[str]) -> list[str]:
    """Order-preserving de-duplication of skill ids."""
    seen: set[str] = set()
    unique: list[str] = []
    for skill_id in ids:
        if skill_id not in seen:
            seen.add(skill_id)
            unique.append(skill_id)
    return unique


def _id_quantity_map(raw: Any) -> dict[str, int]:
    """Normalise an item requirement written as either a list or a mapping.

    Content authors naturally write ``["orb"]`` for "one of these" and
    ``{"orb": 2}`` when a quantity matters.  Both are accepted so neither form
    is a silent mistake; anything else resolves to "no requirement".
    """
    if not raw:
        return {}
    if isinstance(raw, Mapping):
        return {str(key): int(value) for key, value in raw.items()}
    if isinstance(raw, (str, bytes)):
        return {str(raw): 1}
    if isinstance(raw, Iterable):
        return {str(item): 1 for item in raw}
    return {}


@dataclass
class PromotionRequirement:
    """Everything that must be true before a class can promote."""

    level: int = 1
    stats: dict[str, int] = field(default_factory=dict)
    mastery: dict[str, str] = field(default_factory=dict)
    items: dict[str, int] = field(default_factory=dict)
    quests: list[str] = field(default_factory=list)
    gold: int = 0

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "PromotionRequirement":
        payload = payload or {}
        items = _id_quantity_map(payload.get("items"))
        return cls(
            level=int(payload.get("level", 1)),
            stats={str(k).upper(): int(v) for k, v in (payload.get("stats") or {}).items()},
            mastery={str(k).lower(): str(v) for k, v in (payload.get("mastery") or {}).items()},
            items=items,
            quests=[str(q) for q in payload.get("quests", [])],
            gold=int(payload.get("gold", 0)),
        )

    def describe(self) -> list[str]:
        """Requirement checklist text for the promotion screen."""
        lines = [f"Level {self.level}"]
        lines.extend(f"{stat} {value}" for stat, value in self.stats.items())
        lines.extend(f"{track.title()} mastery {rank}" for track, rank in self.mastery.items())
        lines.extend(f"{item_id.replace('_', ' ').title()} x{qty}" for item_id, qty in self.items.items())
        lines.extend(f"Quest: {quest.replace('_', ' ').title()}" for quest in self.quests)
        if self.gold:
            lines.append(f"{self.gold} gold")
        return lines


@dataclass
class PromotionCheck:
    """Per-requirement pass/fail, so the GUI can show a real checklist.

    ENGINE_DESIGN.md notes ClassManager should *flag* unenforced item/quest
    requirements rather than silently ignore them; ``unenforced`` carries that.
    """

    eligible: bool
    target_class_id: str = ""
    target_class_name: str = ""
    met: list[str] = field(default_factory=list)
    unmet: list[str] = field(default_factory=list)
    unenforced: list[str] = field(default_factory=list)
    reason: str = ""

    def summary_lines(self) -> list[str]:
        lines = [f"{'[ok]' if self.eligible else '[--]'} {self.target_class_name or self.target_class_id}"]
        lines.extend(f"  met   : {item}" for item in self.met)
        lines.extend(f"  needs : {item}" for item in self.unmet)
        lines.extend(f"  note  : {item}" for item in self.unenforced)
        return lines


@dataclass
class ClassDefinition:
    """One character class at one promotion tier."""

    id: str
    name: str
    tier: int = 1
    description: str = ""
    #: ``"male"``, ``"female"``, or ``"any"`` (bible section 10).
    gender_restriction: str = "any"
    base_stats: StatBlock = field(default_factory=StatBlock)
    #: Auto-applied stats per level, on top of the player's 5 free points.
    growth: StatBlock = field(default_factory=StatBlock)
    #: The signature skill; replaced (not lost) on promotion.
    core_skill_id: str = ""
    #: Skills automatically known at this tier.
    granted_skill_ids: list[str] = field(default_factory=list)
    #: Skills purchasable with skill points at this tier.
    skill_tree_ids: list[str] = field(default_factory=list)
    #: Ultimates, gated behind ``ultimate_unlock_level``.
    ultimate_skill_ids: list[str] = field(default_factory=list)
    ultimate_unlock_level: int = 1
    #: Weapon types this class may equip; empty = no restriction.
    weapon_types: list[str] = field(default_factory=list)
    #: ``{target_class_id: PromotionRequirement}``.
    promotions: dict[str, PromotionRequirement] = field(default_factory=dict)
    passive_modifiers: ModifierSet = field(default_factory=ModifierSet)
    starting_items: dict[str, int] = field(default_factory=dict)
    starting_gold: int = 0

    # ------------------------------------------------------------------
    @property
    def is_starting_class(self) -> bool:
        return self.tier == 1

    @property
    def is_max_tier(self) -> bool:
        return self.tier >= MAX_TIER or not self.promotions

    def allows_gender(self, gender: str) -> bool:
        restriction = (self.gender_restriction or "any").lower()
        return restriction in ("any", "") or restriction == (gender or "").lower()

    def allows_weapon(self, weapon_type: str) -> bool:
        """Empty ``weapon_types`` means the class can use anything."""
        if not self.weapon_types:
            return True
        return (weapon_type or "").lower() in self.weapon_types

    def unlocked_ultimates(self, level: int) -> list[str]:
        return list(self.ultimate_skill_ids) if level >= self.ultimate_unlock_level else []

    def available_skill_ids(self, level: int) -> list[str]:
        """Everything learnable/known at this tier, ultimates included."""
        ids = list(self.granted_skill_ids) + list(self.skill_tree_ids) + self.unlocked_ultimates(level)
        if self.core_skill_id:
            ids.insert(0, self.core_skill_id)
        return _deduplicate(ids)

    def stats_at_level(self, level: int) -> StatBlock:
        """Base stats plus automatic growth from level 1 to ``level``."""
        result = self.base_stats.copy()
        gained = max(0, level - 1)
        for key in PRIMARY_STATS:
            result[key] = result[key] + self.growth[key] * gained
        return result

    def detail_lines(self) -> list[str]:
        """Stacked ``key: value`` block for Character Creation."""
        lines = [self.name, f"Tier: {self.tier}"]
        if self.description:
            lines.append(self.description)
        lines.append("Base stats: " + ", ".join(f"{k} {self.base_stats[k]}" for k in PRIMARY_STATS))
        lines.append("Growth: " + ", ".join(f"{k} +{self.growth[k]}" for k in PRIMARY_STATS))
        if self.weapon_types:
            lines.append("Weapons: " + ", ".join(w.title() for w in self.weapon_types))
        return lines

    # ------------------------------------------------------------------
    def check_promotion(
        self,
        target_class_id: str,
        *,
        level: int,
        stats: StatBlock,
        mastery: Any,
        inventory: Any = None,
        completed_quests: Sequence[str] = (),
        target_name: str = "",
    ) -> PromotionCheck:
        """Evaluate one promotion path in full.

        Item and quest requirements are checked when an inventory/quest log is
        supplied and *flagged as unenforced* when not, per ENGINE_DESIGN.md -
        never silently dropped.
        """
        requirement = self.promotions.get(target_class_id)
        if requirement is None:
            return PromotionCheck(
                eligible=False,
                target_class_id=target_class_id,
                target_class_name=target_name,
                reason=f"{self.name} cannot promote to {target_class_id}.",
            )

        check = PromotionCheck(
            eligible=True, target_class_id=target_class_id, target_class_name=target_name or target_class_id
        )

        bucket = check.met if level >= requirement.level else check.unmet
        bucket.append(f"Level {requirement.level} (have {level})")

        for stat, needed in requirement.stats.items():
            have = stats[stat] if stat in PRIMARY_STATS else 0
            (check.met if have >= needed else check.unmet).append(f"{stat} {needed} (have {have})")

        for track, rank in requirement.mastery.items():
            have_rank = mastery.rank_of(track) if mastery is not None else "F"
            (check.met if rank_at_least(have_rank, rank) else check.unmet).append(
                f"{track.title()} mastery {rank} (have {have_rank})"
            )

        for item_id, qty in requirement.items.items():
            label = f"{item_id.replace('_', ' ').title()} x{qty}"
            if inventory is None:
                check.unenforced.append(f"{label} (item system unavailable - not enforced)")
            else:
                (check.met if inventory.has(item_id, qty) else check.unmet).append(
                    f"{label} (have {inventory.count(item_id)})"
                )

        for quest_id in requirement.quests:
            label = f"Quest: {quest_id.replace('_', ' ').title()}"
            if completed_quests is None:
                check.unenforced.append(f"{label} (quest system unavailable - not enforced)")
            else:
                (check.met if quest_id in completed_quests else check.unmet).append(label)

        if requirement.gold:
            have_gold = getattr(inventory, "gold", 0) if inventory is not None else 0
            (check.met if have_gold >= requirement.gold else check.unmet).append(
                f"{requirement.gold} gold (have {have_gold})"
            )

        check.eligible = not check.unmet
        if not check.eligible:
            check.reason = "Requirements not met."
        return check

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ClassDefinition":
        class_id = str(payload.get("id", "")).strip()
        if not class_id:
            raise ValueError("class entry is missing an 'id'")

        tier = int(payload.get("tier", 1))
        if not 1 <= tier <= MAX_TIER:
            raise ValueError(f"class {class_id!r} has tier {tier}, must be 1..{MAX_TIER}")

        gender = str(payload.get("gender_restriction", "any")).lower()
        if gender not in ("any", "male", "female"):
            raise ValueError(f"class {class_id!r} has invalid gender_restriction {gender!r}")

        promotions = {
            str(target): PromotionRequirement.from_dict(req)
            for target, req in (payload.get("promotions") or {}).items()
        }

        starting_items = _id_quantity_map(payload.get("starting_items"))

        return cls(
            id=class_id,
            name=str(payload.get("name", class_id)),
            tier=tier,
            description=str(payload.get("description", "")),
            gender_restriction=gender,
            base_stats=StatBlock.from_dict(payload.get("base_stats")),
            growth=StatBlock.from_dict(payload.get("growth")),
            core_skill_id=str(payload.get("core_skill_id", "")),
            granted_skill_ids=[str(s) for s in payload.get("granted_skill_ids", [])],
            skill_tree_ids=[str(s) for s in payload.get("skill_tree_ids", [])],
            ultimate_skill_ids=[str(s) for s in payload.get("ultimate_skill_ids", [])],
            ultimate_unlock_level=int(payload.get("ultimate_unlock_level", 1)),
            weapon_types=[str(w).lower() for w in payload.get("weapon_types", [])],
            promotions=promotions,
            passive_modifiers=ModifierSet.from_dict(payload.get("passive_modifiers")),
            starting_items=starting_items,
            starting_gold=int(payload.get("starting_gold", 0)),
        )
