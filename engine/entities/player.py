"""``Player`` - the character the person actually plays.

Bible section 9: unlimited levels, +5 stat points and +1 skill point per level.
Section 10: promotion keeps learned skills and swaps the core skill.
Section 14: mastery grows through use.
Section 15: affinity with NPCs, marriage regardless of gender.

The Player owns state; it does not own *rules about content* - class data,
skill data and formulas are all injected, so this file never needs editing when
new content is added.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from engine.classes import ClassDefinition
from engine.codex import Codex
from engine.entities.entity import Entity
from engine.items.item import EQUIPMENT_SLOTS, Inventory, Item, SLOT_LABELS
from engine.mastery import MasteryBook
from engine.races import RaceDefinition
from engine.skills.skill import Skill, SkillCategory
from engine.stats import PRIMARY_STATS, Formulas, ModifierSet, StatBlock

__all__ = ["Player", "LevelUpReport"]


class LevelUpReport:
    """Summary of one or more level-ups, for the post-combat log."""

    def __init__(self) -> None:
        self.levels_gained: int = 0
        self.stat_points_gained: int = 0
        self.skill_points_gained: int = 0
        self.new_level: int = 1
        self.messages: list[str] = []

    @property
    def leveled(self) -> bool:
        return self.levels_gained > 0


class Player(Entity):
    """The player character."""

    def __init__(
        self,
        name: str,
        gender: str,
        class_def: ClassDefinition,
        race_def: RaceDefinition,
        formulas: Formulas,
        level: int = 1,
        progression: Mapping[str, Any] | None = None,
        equipment_config: Mapping[str, Any] | None = None,
        enchantments: Mapping[str, Any] | None = None,
        sub_race_id: str | None = None,
    ) -> None:
        progression = progression or {}
        self.equipment_config = dict(equipment_config or {})
        self.enchantment_definitions = dict(enchantments or {})
        self.gender = (gender or "any").lower()
        self.class_def = class_def
        self.race_def = race_def
        self.sub_race_id = sub_race_id or ""
        self.class_history: list[str] = [class_def.id]

        # Progression tuning (bible section 9) - JSON-driven, never hardcoded.
        self._stat_points_per_level = int(progression.get("stat_points_per_level", 5))
        self._skill_points_per_level = int(progression.get("skill_points_per_level", 1))
        self._exp_base = float(progression.get("exp_base", 100.0))
        self._exp_growth = float(progression.get("exp_growth", 1.15))
        self._exp_linear = float(progression.get("exp_linear", 20.0))

        self.exp: float = 0.0
        self.unspent_stat_points: int = 0
        self.unspent_skill_points: int = 0
        #: Points the player allocated by hand, kept separate from class growth
        #: so respec/promotion recalculation stays exact.
        self.allocated_stats = StatBlock()

        self.known_skills: dict[str, Skill] = {}
        self.equipment_granted_skills: set[str] = set()
        self.cooldowns: dict[str, int] = {}
        self.equipment: dict[str, Item | None] = {slot: None for slot in EQUIPMENT_SLOTS}
        self.inventory = Inventory()
        self.mastery = MasteryBook()

        # Bible section 15.
        self.affinity: dict[str, int] = {}
        self.spouse_id: str | None = None
        self.completed_quests: list[str] = []
        self.active_quests: list[str] = []
        self.quest_progress: dict[str, dict[str, int]] = {}
        self.faction_reputation: dict[str, int] = {}
        self.companion_loyalty: dict[str, int] = {}
        self.companion_unavailable_until: dict[str, int] = {}
        #: Mapping item_id -> list[enchantment_id]; migration handles old str form
        self.item_enchantments: dict[str, list[str]] = {}
        self.item_upgrades: dict[str, int] = {}
        self.flags: dict[str, Any] = {}
        self.party_races: list[str] = []
        self.codex = Codex(total_achievements=len(self._codex_achievements()))

        super().__init__(name=name, level=level, base_stats=StatBlock(), formulas=formulas)
        self._recalculate_base_stats()
        self.current_hp = float(self.max_hp)
        self.current_mp = float(self.max_mp)
        self.current_sp = float(self.max_sp)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    @property
    def race_id(self) -> str:
        return self.race_def.id

    @staticmethod
    def _codex_achievements() -> list:
        from engine.codex import ACHIEVEMENTS
        return ACHIEVEMENTS

    def record_achievement(self, track: str, key: str = "", amount: int = 1) -> list[str]:
        """Record an event for achievement tracking. Returns newly unlocked achievement ids."""
        return self.codex.record(track, key, amount)

    def _recalculate_base_stats(self) -> None:
        """Class growth + racial primaries (including sub-race) + hand-allocated points."""
        self.base_stats = (
            self.class_def.stats_at_level(self.level)
            .add(self.race_def.combined_stats(self.sub_race_id))
            .add(self.allocated_stats)
        )
        self.invalidate_stats()

    def special_effects(self) -> list[dict[str, Any]]:
        """Return data-defined combat specials from class, race and sub-race."""
        effects = [dict(effect) for effect in getattr(self.race_def, "special_effects", ())]
        sub = self.race_def.get_sub_race(self.sub_race_id) if self.sub_race_id else None
        if sub:
            effects.extend(dict(effect) for effect in sub.special_effects)
        for perk in self.class_def.perks:
            special = str(perk.get("special", "")).strip()
            if special:
                effects.append({"type": special, "value": float(perk.get("special_value", 0.0)), "perk_id": perk.get("id", ""), "perk_name": perk.get("name", special)})
        return effects

    def active_perks(self) -> list[dict[str, Any]]:
        """Return perks with their active state and reason, for UI feedback."""
        active = []
        for perk in self.class_def.perks:
            trigger = perk.get("trigger", "always")
            is_active = False
            reason = ""
            if trigger == "always":
                is_active = True
                reason = "Always active"
            elif trigger == "low_hp" and hasattr(self, "current_hp"):
                threshold = float(perk.get("threshold", 0.3))
                max_hp = self.formulas.derive(self.base_stats, self.level).max_hp
                frac = self.current_hp / max_hp if max_hp else 1.0
                is_active = frac < threshold
                reason = f"HP {frac*100:.0f}% < {threshold*100:.0f}%"
            elif trigger == "low_mp" and hasattr(self, "current_mp"):
                threshold = float(perk.get("threshold", 0.3))
                max_mp = self.formulas.derive(self.base_stats, self.level).max_mp
                frac = self.current_mp / max_mp if max_mp else 1.0
                is_active = frac < threshold
                reason = f"MP {frac*100:.0f}% < {threshold*100:.0f}%"
            elif trigger == "low_sp" and hasattr(self, "current_sp"):
                threshold = float(perk.get("threshold", 0.3))
                max_sp = self.formulas.derive(self.base_stats, self.level).max_sp
                frac = self.current_sp / max_sp if max_sp else 1.0
                is_active = frac < threshold
                reason = f"SP {frac*100:.0f}% < {threshold*100:.0f}%"
            active.append({"perk": perk, "active": is_active, "reason": reason})
        return active

    def _equipment_modifiers(self) -> ModifierSet:
        """Gear + class passives + learned passive skills + mastery ranks.

        All four are "always on" sources, so they are merged in one place and
        cached together by :meth:`Entity.derived_stats`.
        """
        combined = ModifierSet()
        equipped = [item for item in self.equipment.values() if item is not None]
        for item in equipped:
            rate = float(self.equipment_config.get("equipment_upgrade", {}).get("modifier_rate", 0.0))
            level = self.item_upgrades.get(item.id, 0)
            rarity_cfg = self.equipment_config.get("rarities", {}).get(item.rarity.lower(), {})
            rarity_scale = float(rarity_cfg.get("modifier_rate", 1.0))
            scale = (1.0 + rate * level) * rarity_scale
            upgraded = ModifierSet(
                flat={key: value * scale for key, value in item.modifiers.flat.items()},
                pct={key: value * scale for key, value in item.modifiers.pct.items()},
            )
            combined.merge(upgraded)
            racial_bonus = item.race_modifiers.get(self.race_id)
            if racial_bonus is not None:
                combined.merge(racial_bonus)
            # Multiple enchantments per item, up to enchant_slots
            for ench_id in self.item_enchantments.get(item.id, []):
                enchantment = self.enchantment_definitions.get(ench_id)
                if enchantment is not None:
                    combined.merge(enchantment.modifiers)
            for condition in item.conditional_modifiers:
                threshold = float(condition.get("below_hp_fraction", -1))
                base_max = self.formulas.derive(self.base_stats, self.level).max_hp
                if threshold >= 0 and hasattr(self, "current_hp") and self.current_hp < base_max * threshold:
                    combined.merge(ModifierSet.from_dict(condition.get("modifiers")))
        counts: dict[str, int] = {}
        for item in equipped:
            if item.set_id:
                counts[item.set_id] = counts.get(item.set_id, 0) + 1
        for set_id, count in counts.items():
            definition = (self.equipment_config.get("equipment_sets") or {}).get(set_id, {})
            for threshold, modifiers in (definition.get("bonuses") or {}).items():
                if count >= int(threshold):
                    combined.merge(ModifierSet.from_dict(modifiers))
        combined.merge(self.race_def.combined_modifiers(self.sub_race_id))
        # Party composition bonuses from race/sub-race passives
        for eff in self.special_effects():
            if eff.get("type") == "party_bonus":
                needed = str(eff.get("race_id","")).lower()
                if needed and needed in [r.lower() for r in self.party_races]:
                    stat = str(eff.get("stat","")).lower()
                    val = float(eff.get("value",0))
                    # Interpret as pct if value <1, else flat? Use heuristics: if stat is evasion/accuracy etc treat as flat
                    if stat in ("evasion","accuracy","crit_chance","crit_damage","status_resist"):
                        combined.add_flat(stat, val)
                    elif stat in ("physical_power","magic_power","armor","max_hp","max_mp","speed"):
                        combined.add_pct(stat, val) if val < 1 else combined.add_flat(stat, val)
                    else:
                        combined.add_pct(stat, val)
            elif eff.get("type") in ("accuracy_bonus","evasion_bonus","status_resist_bonus"):
                # Map to flat stats
                t = eff.get("type")
                v = float(eff.get("value",0))
                if t == "accuracy_bonus":
                    combined.add_flat("accuracy", v)
                elif t == "evasion_bonus":
                    combined.add_flat("evasion", v)
                elif t == "status_resist_bonus":
                    combined.add_flat("status_resist", v)
        combined.merge(self.class_def.passive_modifiers)
        # Apply class perks (always-on and conditional)
        for perk in self.class_def.perks:
            trigger = perk.get("trigger", "always")
            if trigger == "always":
                combined.merge(ModifierSet.from_dict(perk.get("modifiers", {})))
            elif trigger == "low_hp" and hasattr(self, "current_hp"):
                threshold = float(perk.get("threshold", 0.3))
                max_hp = self.formulas.derive(self.base_stats, self.level).max_hp
                if max_hp > 0 and self.current_hp / max_hp < threshold:
                    combined.merge(ModifierSet.from_dict(perk.get("modifiers", {})))
            elif trigger == "low_mp" and hasattr(self, "current_mp"):
                threshold = float(perk.get("threshold", 0.3))
                max_mp = self.formulas.derive(self.base_stats, self.level).max_mp
                if max_mp > 0 and self.current_mp / max_mp < threshold:
                    combined.merge(ModifierSet.from_dict(perk.get("modifiers", {})))
            elif trigger == "low_sp" and hasattr(self, "current_sp"):
                threshold = float(perk.get("threshold", 0.3))
                max_sp = self.formulas.derive(self.base_stats, self.level).max_sp
                if max_sp > 0 and self.current_sp / max_sp < threshold:
                    combined.merge(ModifierSet.from_dict(perk.get("modifiers", {})))
        for skill in self.known_skills.values():
            if skill.is_passive:
                combined.merge(skill.passive_modifiers)
        combined.merge(self.mastery.modifiers())
        return combined

    def allocate_stat(self, stat: str, amount: int = 1) -> bool:
        """Spend unspent stat points.  Returns ``False`` if unaffordable."""
        stat = stat.upper()
        if stat not in PRIMARY_STATS or amount <= 0 or self.unspent_stat_points < amount:
            return False
        self.allocated_stats[stat] = self.allocated_stats[stat] + amount
        self.unspent_stat_points -= amount
        self._recalculate_base_stats()
        return True

    # ------------------------------------------------------------------
    # Experience and levelling
    # ------------------------------------------------------------------
    def exp_to_next_level(self) -> float:
        """Geometric + linear curve - unlimited levels (bible section 9)."""
        return self._exp_base * (self._exp_growth ** (self.level - 1)) + self._exp_linear * (self.level - 1)

    def gain_exp(self, amount: float) -> LevelUpReport:
        """Award EXP and process any number of resulting level-ups."""
        report = LevelUpReport()
        if amount <= 0:
            report.new_level = self.level
            return report

        self.exp += float(amount)
        # A loop, not an if - a big boss kill can grant several levels at once.
        while self.exp >= self.exp_to_next_level():
            self.exp -= self.exp_to_next_level()
            self.level += 1
            self.unspent_stat_points += self._stat_points_per_level
            self.unspent_skill_points += self._skill_points_per_level
            report.levels_gained += 1
            report.stat_points_gained += self._stat_points_per_level
            report.skill_points_gained += self._skill_points_per_level
            report.messages.append(f"{self.name} reached level {self.level}!")

        if report.levels_gained:
            self._recalculate_base_stats()
            # Levelling raises max HP/MP/SP; grant the difference so a level-up
            # mid-fight feels like a reward rather than nothing.
            self.current_hp = min(float(self.max_hp), self.current_hp + report.levels_gained * 5)
            self.current_mp = min(float(self.max_mp), self.current_mp + report.levels_gained * 3)
            self.current_sp = min(float(self.max_sp), self.current_sp + report.levels_gained * 4)
            # Codex: track level achievements
            unlocked = self.record_achievement("level", str(self.level), self.level)
            for ach_id in unlocked:
                report.messages.append(f"🏆 Achievement unlocked: {ach_id}")

        report.new_level = self.level
        return report

    def exp_progress(self) -> tuple[float, float]:
        return (self.exp, self.exp_to_next_level())

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------
    def learn_skill(self, skill: Skill, spend_points: bool = True) -> tuple[bool, str]:
        """Learn a skill, validating every gate before charging points."""
        if skill.id in self.known_skills:
            return False, f"{skill.name} is already known."
        if self.level < skill.required_level:
            return False, f"{skill.name} requires level {skill.required_level}."
        missing = [p for p in skill.prerequisites if p not in self.known_skills]
        if missing:
            return False, f"{skill.name} requires: {', '.join(missing)}."
        if not self.mastery.meets(skill.required_mastery):
            need = ", ".join(f"{t.title()} {r}" for t, r in skill.required_mastery.items())
            return False, f"{skill.name} requires mastery: {need}."
        if skill.required_class_ids and self.class_def.id not in skill.required_class_ids:
            return False, f"{skill.name} is not available to {self.class_def.name}."
        if spend_points and self.unspent_skill_points < skill.skill_point_cost:
            return False, f"Not enough skill points ({skill.skill_point_cost} needed)."

        if spend_points:
            self.unspent_skill_points -= skill.skill_point_cost
        self.known_skills[skill.id] = skill
        if skill.is_passive:
            self.invalidate_stats()
        return True, f"{self.name} learned {skill.name}!"

    def forget_skill(self, skill_id: str) -> bool:
        if skill_id not in self.known_skills:
            return False
        was_passive = self.known_skills[skill_id].is_passive
        del self.known_skills[skill_id]
        if was_passive:
            self.invalidate_stats()
        return True

    def usable_skills(self) -> list[Skill]:
        """Skills selectable in combat right now, weapon gating applied."""
        weapon = self.equipment.get("weapon")
        weapon_type = weapon.weapon_type if weapon else ""
        usable = []
        for skill in self.known_skills.values():
            if not skill.is_usable_in_combat:
                continue
            if skill.required_weapon_types and weapon_type not in skill.required_weapon_types:
                continue
            usable.append(skill)
        return sorted(usable, key=lambda s: (SkillCategory.ALL.index(s.category), s.name))

    def passive_skills(self) -> list[Skill]:
        return sorted((s for s in self.known_skills.values() if s.is_passive), key=lambda s: s.name)

    def tick_cooldowns(self) -> None:
        """Advance all cooldowns one turn; drop the finished ones."""
        for skill_id in list(self.cooldowns):
            self.cooldowns[skill_id] -= 1
            if self.cooldowns[skill_id] <= 0:
                del self.cooldowns[skill_id]

    # ------------------------------------------------------------------
    # Equipment
    # ------------------------------------------------------------------
    def can_equip(self, item: Item) -> tuple[bool, str]:
        if not item.is_equipment:
            return False, f"{item.name} cannot be equipped."
        if self.level < item.required_level:
            return False, f"{item.name} requires level {item.required_level}."
        for stat, needed in item.required_stats.items():
            if self.base_stats[stat] < needed:
                return False, f"{item.name} requires {stat} {needed}."
        if item.slot == "weapon" and not self.class_def.allows_weapon(item.weapon_type):
            return False, f"{self.class_def.name} cannot wield {item.weapon_type or 'that'}."
        return True, ""

    def equip(self, item: Item) -> tuple[bool, str]:
        """Move an item from bag to slot, returning any displaced item.

        The bag entry is removed *before* the old item is added back so a full
        inventory can still swap gear - net slot usage is unchanged.
        """
        ok, reason = self.can_equip(item)
        if not ok:
            return False, reason
        if not self.inventory.has(item.id):
            return False, f"{item.name} is not in your inventory."

        self.inventory.remove(item.id, 1)
        previous = self.equipment.get(item.slot)
        self.equipment[item.slot] = item
        if previous is not None:
            self.inventory.add(previous, 1)
        self.invalidate_stats()

        note = f" ({previous.name} returned to inventory)" if previous else ""
        return True, f"Equipped {item.name}{note}."

    def unequip(self, slot: str) -> tuple[bool, str]:
        item = self.equipment.get(slot)
        if item is None:
            return False, f"Nothing equipped in {SLOT_LABELS.get(slot, slot)}."
        if self.inventory.is_full:
            return False, "Inventory is full."
        self.equipment[slot] = None
        self.inventory.add(item, 1)
        self.invalidate_stats()
        return True, f"Unequipped {item.name}."

    def equipped_weapon_type(self) -> str:
        weapon = self.equipment.get("weapon")
        return weapon.weapon_type if weapon else "unarmed"

    def active_set_bonuses(self) -> list[str]:
        counts: dict[str, int] = {}
        for item in self.equipment.values():
            if item and item.set_id:
                counts[item.set_id] = counts.get(item.set_id, 0) + 1
        lines: list[str] = []
        for set_id, count in counts.items():
            definition = (self.equipment_config.get("equipment_sets") or {}).get(set_id, {})
            for threshold in sorted((definition.get("bonuses") or {}), key=int):
                if count >= int(threshold):
                    lines.append(f"{definition.get('name', set_id)} ({threshold})")
        return lines

    def equipment_lines(self) -> list[str]:
        """``Weapon: Iron Sword`` lines for the Equipment screen."""
        return [
            f"{SLOT_LABELS[slot]}: {item.name if item else '(empty)'}"
            for slot, item in ((s, self.equipment[s]) for s in EQUIPMENT_SLOTS)
        ]

    # ------------------------------------------------------------------
    # Mastery
    # ------------------------------------------------------------------
    def train_mastery(self, track_id: str, amount: float) -> str | None:
        """Grant mastery EXP; returns the new rank name if it went up."""
        if not track_id:
            return None
        _, promoted = self.mastery.gain(track_id, amount)
        if promoted:
            self.invalidate_stats()
        return promoted

    # ------------------------------------------------------------------
    # Promotion (bible section 10)
    # ------------------------------------------------------------------
    def apply_promotion(self, new_class: ClassDefinition, new_skills: Iterable[Skill]) -> list[str]:
        """Switch class, keeping learned skills and swapping the core skill.

        The *old* core skill is deliberately dropped while every other learned
        skill is kept - that is exactly what the bible specifies.
        """
        messages: list[str] = []
        old_core = self.class_def.core_skill_id

        self.class_def = new_class
        self.class_history.append(new_class.id)

        if old_core and old_core in self.known_skills and old_core != new_class.core_skill_id:
            removed = self.known_skills.pop(old_core)
            messages.append(f"{removed.name} was replaced by your new core skill.")

        for skill in new_skills:
            if skill.id not in self.known_skills:
                self.known_skills[skill.id] = skill
                messages.append(f"Learned {skill.name}.")

        self._recalculate_base_stats()
        self.current_hp = float(self.max_hp)
        self.current_mp = float(self.max_mp)
        self.current_sp = float(self.max_sp)
        messages.insert(0, f"{self.name} promoted to {new_class.name}!")
        return messages

    # ------------------------------------------------------------------
    # Affinity and marriage (bible section 15)
    # ------------------------------------------------------------------
    def change_affinity(self, npc_id: str, amount: int) -> int:
        self.affinity[npc_id] = max(-100, min(100, self.affinity.get(npc_id, 0) + int(amount)))
        return self.affinity[npc_id]

    def affinity_with(self, npc_id: str) -> int:
        return self.affinity.get(npc_id, 0)

    def marry(self, npc_id: str) -> tuple[bool, str]:
        """Marriage is gender-agnostic by design (bible section 15)."""
        if self.spouse_id:
            return False, "You are already married."
        self.spouse_id = npc_id
        return True, f"You are now married to {npc_id.replace('_', ' ').title()}."

    # ------------------------------------------------------------------
    # Quests
    # ------------------------------------------------------------------
    def accept_quest(self, quest_id: str) -> bool:
        if quest_id in self.completed_quests or quest_id in self.active_quests:
            return False
        self.active_quests.append(quest_id)
        self.quest_progress[quest_id] = {}
        return True

    def quest_progress_value(self, quest_id: str, objective_key: str) -> int:
        return int(self.quest_progress.get(quest_id, {}).get(objective_key, 0))

    def advance_quest(self, quest_id: str, objective_key: str, amount: int, *, maximum: int) -> int:
        if quest_id not in self.active_quests or amount <= 0:
            return self.quest_progress_value(quest_id, objective_key)
        progress = self.quest_progress.setdefault(quest_id, {})
        progress[objective_key] = min(maximum, int(progress.get(objective_key, 0)) + int(amount))
        return progress[objective_key]

    def complete_quest(self, quest_id: str) -> bool:
        if quest_id in self.completed_quests:
            return False
        if quest_id in self.active_quests:
            self.active_quests.remove(quest_id)
        self.quest_progress.pop(quest_id, None)
        self.completed_quests.append(quest_id)
        return True

    # ------------------------------------------------------------------
    # Presentation
    # ------------------------------------------------------------------
    def summary_lines(self) -> list[str]:
        """The stacked key:value block the style guide describes."""
        current_exp, needed_exp = self.exp_progress()
        return [
            f"Name: {self.name}",
            f"Gender: {self.gender.title()}",
            f"Race: {self.race_def.name}",
            f"Class: {self.class_def.name}",
            f"Tier: {self.class_def.tier}",
            f"Level: {self.level}",
            f"EXP: {current_exp:.0f}/{needed_exp:.0f}",
            f"HP: {self.hp_text()}",
            f"MP: {self.mp_text()}",
            f"SP: {self.sp_text()}",
            f"Gold: {self.inventory.gold}",
            f"Mastery: {self.mastery.highest_rank()}",
        ]

    def stat_lines(self) -> list[str]:
        """Primary stats with the modifier delta shown when non-zero."""
        effective = self.effective_primaries()
        lines = []
        for key in PRIMARY_STATS:
            base = self.base_stats[key]
            total = effective.get(key, base)
            delta = total - base
            suffix = f" ({delta:+.0f})" if abs(delta) >= 0.5 else ""
            lines.append(f"{key}: {base:.0f}{suffix}")
        return lines

    def perk_lines(self) -> list[str]:
        """Class perk feedback for Status screen."""
        lines = []
        if not self.class_def.perks:
            return lines
        lines.append("Perks:")
        for entry in self.active_perks():
            perk = entry["perk"]
            active = entry["active"]
            reason = entry["reason"]
            status = "[Active]" if active else "[Inactive]"
            name = perk.get("name", perk.get("id", "Perk"))
            desc = perk.get("description", "")
            special = perk.get("special", "")
            special_val = perk.get("special_value", 0)
            line = f"  {status} {name}: {desc}"
            if special:
                line += f" ({special}:{special_val})"
            if reason:
                line += f" - {reason}"
            lines.append(line)
            mods = ModifierSet.from_dict(perk.get("modifiers", {}))
            for ml in mods.describe():
                lines.append(f"    {ml}")
        return lines

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        data = self._serialise_common()
        data.update(
            {
                "gender": self.gender,
                "race_id": self.race_id,
                "sub_race_id": self.sub_race_id,
                "class_id": self.class_def.id,
                "class_history": list(self.class_history),
                "exp": self.exp,
                "unspent_stat_points": self.unspent_stat_points,
                "unspent_skill_points": self.unspent_skill_points,
                "allocated_stats": self.allocated_stats.to_dict(),
                "known_skill_ids": list(self.known_skills),
                "cooldowns": dict(self.cooldowns),
                "equipment": {slot: (item.id if item else None) for slot, item in self.equipment.items()},
                "inventory": self.inventory.to_dict(),
                "mastery": self.mastery.to_dict(),
                "affinity": dict(self.affinity),
                "spouse_id": self.spouse_id,
                "completed_quests": list(self.completed_quests),
                "active_quests": list(self.active_quests),
                "quest_progress": {
                    quest_id: dict(progress) for quest_id, progress in self.quest_progress.items()
                },
                "faction_reputation": dict(self.faction_reputation),
                "companion_loyalty": dict(self.companion_loyalty),
                "companion_unavailable_until": dict(self.companion_unavailable_until),
                "item_enchantments": {k: list(v) for k, v in self.item_enchantments.items()},
                "item_upgrades": dict(self.item_upgrades),
                "flags": dict(self.flags),
                "codex": self.codex.to_dict(),
            }
        )
        return data
