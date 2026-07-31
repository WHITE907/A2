"""``ClassManager`` - factory for :class:`ClassDefinition` objects.

Owns promotion logic end to end: eligibility checks, the promotion itself, and
the "what can I become next" queries the GUI needs.

Per docs/ENGINE_DESIGN.md this manager *flags* item/quest promotion
requirements it cannot enforce rather than silently ignoring them - now that
the item system exists it enforces items for real, and still flags quests when
no quest log is supplied.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from engine.classes import MAX_TIER, ClassDefinition, PromotionCheck
from engine.managers.data_loader import ContentError, DataLoader
from engine.managers.skill_manager import SkillManager
from engine.skills.skill import SkillCategory

__all__ = ["ClassManager"]


class ClassManager:
    """Loads class definitions and drives promotion."""

    CLASS_FILE = "classes.json"

    def __init__(self, loader: DataLoader, skill_manager: SkillManager) -> None:
        self._loader = loader
        self._skills = skill_manager
        self._classes: dict[str, ClassDefinition] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    def load(self) -> None:
        if self._loaded:
            return
        for entry in self._loader.load_entries(self.CLASS_FILE, "classes"):
            try:
                definition = ClassDefinition.from_dict(entry)
            except ValueError as exc:
                raise ContentError(f"{self.CLASS_FILE}: {exc}") from exc
            if definition.id in self._classes:
                raise ContentError(f"duplicate class id {definition.id!r} in {self.CLASS_FILE}")
            self._classes[definition.id] = definition
        self._loaded = True
        self._validate_references()

    def _validate_references(self) -> None:
        """Check promotion targets and skill ids resolve.

        Skill problems are raised as content errors because a class granting a
        nonexistent skill silently gives the player nothing, which is very hard
        to notice in play.
        """
        for definition in self._classes.values():
            for target in definition.promotions:
                if target not in self._classes:
                    raise ContentError(
                        f"class {definition.id!r} promotes to unknown class {target!r}"
                    )
                target_def = self._classes[target]
                if target_def.tier <= definition.tier:
                    raise ContentError(
                        f"class {definition.id!r} (tier {definition.tier}) promotes to "
                        f"{target!r} (tier {target_def.tier}) - target tier must be higher"
                    )
            for skill_id in definition.available_skill_ids(level=9999):
                if self._skills.get(skill_id) is None:
                    raise ContentError(f"class {definition.id!r} references unknown skill {skill_id!r}")

    # ------------------------------------------------------------------
    def get(self, class_id: str) -> ClassDefinition | None:
        self.load()
        return self._classes.get(class_id)

    def require(self, class_id: str) -> ClassDefinition:
        definition = self.get(class_id)
        if definition is None:
            raise ContentError(f"unknown class id {class_id!r}")
        return definition

    def all_classes(self) -> list[ClassDefinition]:
        self.load()
        return sorted(self._classes.values(), key=lambda c: (c.tier, c.name))

    def starting_classes(self, gender: str | None = None) -> list[ClassDefinition]:
        """Tier-1 classes, filtered by gender restriction (bible section 10)."""
        self.load()
        return sorted(
            (
                c
                for c in self._classes.values()
                if c.is_starting_class and (gender is None or c.allows_gender(gender))
            ),
            key=lambda c: c.name,
        )

    def classes_at_tier(self, tier: int) -> list[ClassDefinition]:
        self.load()
        return sorted((c for c in self._classes.values() if c.tier == tier), key=lambda c: c.name)

    def promotion_targets(self, class_id: str) -> list[ClassDefinition]:
        definition = self.get(class_id)
        if definition is None:
            return []
        return [self._classes[t] for t in definition.promotions if t in self._classes]

    # ------------------------------------------------------------------
    def check_promotion(self, player: Any, target_class_id: str) -> PromotionCheck:
        """Full eligibility check for one target class."""
        self.load()
        current = player.class_def
        target = self._classes.get(target_class_id)
        if target is None:
            return PromotionCheck(
                eligible=False,
                target_class_id=target_class_id,
                reason=f"Unknown class {target_class_id!r}.",
            )
        if not target.allows_gender(player.gender):
            return PromotionCheck(
                eligible=False,
                target_class_id=target_class_id,
                target_class_name=target.name,
                reason=f"{target.name} is not available to {player.gender} characters.",
            )
        return current.check_promotion(
            target_class_id,
            level=player.level,
            stats=player.base_stats,
            mastery=player.mastery,
            inventory=player.inventory,
            completed_quests=player.completed_quests,
            target_name=target.name,
        )

    def available_promotions(self, player: Any) -> list[PromotionCheck]:
        """Every promotion path from the player's class, eligible or not.

        Ineligible paths are included on purpose: the checklist of what is
        still missing is the useful part of the promotion screen.
        """
        self.load()
        return [
            self.check_promotion(player, target_id)
            for target_id in player.class_def.promotions
        ]

    def promote(self, player: Any, target_class_id: str) -> tuple[bool, list[str]]:
        """Promote the player if eligible.

        Consumes required items and gold, then hands off to
        :meth:`Player.apply_promotion` for the state change.
        """
        check = self.check_promotion(player, target_class_id)
        if not check.eligible:
            reason = check.reason or "Requirements not met."
            return False, [reason] + [f"Needs: {item}" for item in check.unmet]

        target = self.require(target_class_id)
        requirement = player.class_def.promotions.get(target_class_id)

        if requirement is not None:
            for item_id, quantity in requirement.items.items():
                player.inventory.remove(item_id, quantity)
            if requirement.gold:
                player.inventory.spend_gold(requirement.gold)

        new_skills = self._skills.get_many(self._granted_ids(target, player.level))
        messages = player.apply_promotion(target, new_skills)
        return True, messages

    @staticmethod
    def _granted_ids(definition: ClassDefinition, level: int) -> list[str]:
        """Skills automatically gained on promotion: core + granted only.

        Skill-tree entries stay purchasable with skill points; handing them all
        over free would make the skill-point economy meaningless.
        """
        ids = list(definition.granted_skill_ids)
        if definition.core_skill_id:
            ids.insert(0, definition.core_skill_id)
        ids.extend(definition.unlocked_ultimates(level))
        seen: set[str] = set()
        unique: list[str] = []
        for skill_id in ids:
            if skill_id not in seen:
                seen.add(skill_id)
                unique.append(skill_id)
        return unique

    # ------------------------------------------------------------------
    def learnable_skills(self, player: Any) -> list[Any]:
        """Skill-tree entries the player could still buy, in tree order."""
        self.load()
        definition = player.class_def
        candidates = list(definition.skill_tree_ids) + definition.unlocked_ultimates(player.level)
        weapon_type = player.equipped_weapon_type()
        for skill in self._skills.weapon_skills(weapon_type):
            if skill.id not in candidates:
                candidates.append(skill.id)
        for skill in self._skills.all_skills():
            race_matches = not skill.required_race_ids or player.race_id.lower() in [r.lower() for r in skill.required_race_ids]
            lineage_matches = not skill.required_sub_race_ids or player.sub_race_id.lower() in [
                sub_race.lower() for sub_race in skill.required_sub_race_ids
            ]
            if skill.required_race_ids and race_matches and lineage_matches:
                if skill.id not in candidates:
                    candidates.append(skill.id)
            elif not skill.required_race_ids and not skill.required_class_ids:
                if skill.id not in candidates and skill.category in (SkillCategory.ACTIVE, SkillCategory.PASSIVE, SkillCategory.SHARED):
                    candidates.append(skill.id)

        results = []
        for skill in self._skills.get_many(candidates):
            if skill.id in player.known_skills:
                continue
            if skill.required_race_ids and player.race_id.lower() not in [r.lower() for r in skill.required_race_ids]:
                continue
            if skill.required_sub_race_ids and player.sub_race_id.lower() not in [
                sub_race.lower() for sub_race in skill.required_sub_race_ids
            ]:
                continue
            if skill.required_class_ids and player.class_def.id not in skill.required_class_ids:
                continue
            results.append(skill)
        return results

    def create_starting_kit(self, definition: ClassDefinition, level: int = 1) -> list[Any]:
        """Skills a brand-new character of this class starts with."""
        return self._skills.get_many(self._granted_ids(definition, level))

    def count(self) -> int:
        self.load()
        return len(self._classes)

    def max_tier(self) -> int:
        return MAX_TIER
