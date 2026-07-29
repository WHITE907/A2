"""``Game`` - the facade the GUI talks to.

Bible section 5: *"UI only displays information. Engine performs all
calculations."*  This class is the boundary.  Every Tkinter screen holds a
reference to one :class:`Game` and calls methods on it; no screen imports a
manager, touches JSON, or does arithmetic on a stat.

It owns:

- the manager instances (created once, shared)
- the active :class:`~engine.entities.player.Player` and
  :class:`~engine.world.world.WorldState`
- the active :class:`~engine.combat.combat.Battle`, if any
- save/load, including the morning autosave and inn respawn
"""

from __future__ import annotations

import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine.classes import ClassDefinition
from engine.codex import Codex
from engine.combat.ai import default_registry
from engine.combat.combat import Battle, CombatState
from engine.entities.companion import Companion
from engine.entities.player import Player
from engine.items.item import EQUIPMENT_SLOTS, Item
from engine.managers.class_manager import ClassManager
from engine.managers.companion_manager import CompanionManager
from engine.managers.data_loader import ContentError, DataLoader
from engine.managers.enemy_manager import EnemyManager
from engine.managers.enchantment_manager import EnchantmentManager
from engine.managers.item_manager import ItemManager
from engine.managers.quest_manager import QuestManager
from engine.managers.race_manager import RaceManager
from engine.managers.save_manager import SaveManager, SaveSlotInfo
from engine.managers.skill_manager import SkillManager
from engine.managers.story_manager import StoryManager
from engine.managers.world_manager import WorldManager
from engine.mastery import MasteryBook
from engine.party import Party
from engine.quests import QuestDefinition
from engine.races import RaceDefinition
from engine.relationships import MarriageCheck, RelationshipRules
from engine.rng import GameRandom
from engine.stats import Formulas, ModifierSet, StatBlock
from engine.world.world import WorldState

#: Re-exported so GUI screens can type-annotate what :meth:`Game.save_slots`
#: returns without importing from ``engine.managers`` - the facade stays the
#: single seam between the UI and the engine (bible section 5/18).
__all__ = ["Game", "GAME_VERSION", "QuestDefinition", "RaceDefinition", "SaveSlotInfo"]

#: Shown on the main menu under the title (per the GUI style reference).
GAME_VERSION = "0.7.0"


class Game:
    """Application-level engine state and the GUI's only entry point."""

    def __init__(
        self,
        data_dir: Path | str | None = None,
        save_dir: Path | str | None = None,
        seed: int | None = None,
    ) -> None:
        self.loader = DataLoader(data_dir)
        self.config: dict[str, Any] = self.loader.load_mapping("config.json", required=True)
        self.formulas = Formulas.from_dict(self.config.get("formulas"))
        self.rng = GameRandom(seed)

        self.skills = SkillManager(self.loader)
        self.classes = ClassManager(self.loader, self.skills)
        self.items = ItemManager(self.loader)
        self.enchantments = EnchantmentManager(self.loader)
        self.races = RaceManager(self.loader)
        self.enemies = EnemyManager(self.loader, self.skills, self.formulas)
        self.quests = QuestManager(self.loader)
        self.companions = CompanionManager(self.loader, self.skills, self.races, self.formulas)
        self.world_manager = WorldManager(self.loader)
        self.story = StoryManager(self.loader)
        self.saves = SaveManager(save_dir)
        self.ai_registry = default_registry()
        self.relationships = RelationshipRules(self.config)

        self.player: Player | None = None
        self.party = Party(int((self.config.get("party") or {}).get("max_active", 2)))
        self.world: WorldState | None = None
        self.battle: Battle | None = None
        self.current_slot: str | None = None
        #: Transient one-line notices for the GUI status bar.
        self.notices: list[str] = []

    # ==================================================================
    # Content
    # ==================================================================
    def load_content(self) -> None:
        """Force-load and cross-validate every content file.

        Called by the launcher so a content error surfaces immediately at
        startup rather than halfway through a battle.
        """
        self.skills.load()
        self.classes.load()
        self.items.load()
        self.enchantments.load()
        self.races.load()
        self.enemies.load()
        self.quests.load()
        self.companions.load()
        self.world_manager.load()
        self.story.load()
        self._validate_cross_references()

    def _validate_cross_references(self) -> None:
        """Check ids that span two content files."""
        problems: list[str] = []

        for template in self.enemies.all_templates():
            for skill_id in template.skill_ids:
                if self.skills.get(skill_id) is None:
                    problems.append(f"enemy {template.id!r} references unknown skill {skill_id!r}")
            for entry in template.loot:
                if entry.item_id and self.items.get(entry.item_id) is None:
                    problems.append(f"enemy {template.id!r} drops unknown item {entry.item_id!r}")
            for phase in template.boss_phases:
                for summon in phase.get("summons", []):
                    if self.enemies.get_template(str(summon.get("enemy_id", ""))) is None:
                        problems.append(f"enemy {template.id!r} phase summons unknown enemy {summon.get('enemy_id')!r}")

        for skill in self.skills.all_skills():
            for class_id in skill.required_class_ids:
                if self.classes.get(class_id) is None:
                    problems.append(f"skill {skill.id!r} requires unknown class {class_id!r}")

        for item in self.items.all_items():
            for race_id in item.race_modifiers:
                if self.races.get(race_id) is None:
                    problems.append(f"item {item.id!r} has a bonus for unknown race {race_id!r}")
            if item.bound_skill_id and self.skills.get(item.bound_skill_id) is None:
                problems.append(f"item {item.id!r} grants unknown skill {item.bound_skill_id!r}")
            if item.set_id and item.set_id not in (self.config.get("equipment_sets") or {}):
                problems.append(f"item {item.id!r} uses unknown equipment set {item.set_id!r}")

        for definition in self.classes.all_classes():
            for item_id in definition.starting_items:
                if self.items.get(item_id) is None:
                    problems.append(f"class {definition.id!r} grants unknown item {item_id!r}")
            for target, requirement in definition.promotions.items():
                for item_id in requirement.items:
                    if self.items.get(item_id) is None:
                        problems.append(
                            f"class {definition.id!r} promotion to {target!r} needs unknown item {item_id!r}"
                        )
                for quest_id in requirement.quests:
                    if self.quests.get(quest_id) is None:
                        problems.append(
                            f"class {definition.id!r} promotion to {target!r} needs unknown quest {quest_id!r}"
                        )

        for companion in self.companions.all_definitions():
            if self.races.get(companion.race_id) is None:
                problems.append(f"companion {companion.id!r} has unknown race {companion.race_id!r}")
            for skill_id in companion.skill_ids:
                if self.skills.get(skill_id) is None:
                    problems.append(f"companion {companion.id!r} references unknown skill {skill_id!r}")
            for item_id in companion.recruit.items:
                if self.items.get(item_id) is None:
                    problems.append(f"companion {companion.id!r} needs unknown item {item_id!r}")
            for item_id in companion.gift_item_ids:
                if self.items.get(item_id) is None:
                    problems.append(f"companion {companion.id!r} likes unknown gift {item_id!r}")
            for quest_id in companion.recruit.quests:
                if self.quests.get(quest_id) is None:
                    problems.append(f"companion {companion.id!r} needs unknown quest {quest_id!r}")
            if companion.location_id and self.world_manager.get_area(companion.location_id) is None:
                problems.append(
                    f"companion {companion.id!r} is in unknown area {companion.location_id!r}"
                )

        for npc in self.world_manager.create_world().npcs.values():
            if self.races.get(npc.race_id) is None:
                problems.append(f"npc {npc.id!r} has unknown race {npc.race_id!r}")

        for quest in self.quests.all_definitions():
            giver = self.world_manager.get_npc(quest.giver_id) or self.companions.get(quest.giver_id)
            if giver is None:
                problems.append(f"quest {quest.id!r} has unknown giver {quest.giver_id!r}")
            for field_name, area_id in (
                ("start_area_id", quest.start_area_id),
                ("turn_in_area_id", quest.turn_in_area_id),
            ):
                if area_id and self.world_manager.get_area(area_id) is None:
                    problems.append(f"quest {quest.id!r} has unknown {field_name} {area_id!r}")
            if giver is not None and quest.start_area_id and giver.location_id != quest.start_area_id:
                problems.append(
                    f"quest {quest.id!r} giver {giver.id!r} is not in start area {quest.start_area_id!r}"
                )
            if quest.required_companion_id and self.companions.get(quest.required_companion_id) is None:
                problems.append(
                    f"quest {quest.id!r} requires unknown companion {quest.required_companion_id!r}"
                )
            for class_id in quest.required_class_ids:
                if self.classes.get(class_id) is None:
                    problems.append(f"quest {quest.id!r} requires unknown class {class_id!r}")
            for objective in quest.objectives:
                if (
                    objective.kind == self.quests.DEFEAT_OBJECTIVE
                    and self.enemies.get_template(objective.target_id) is None
                ):
                    problems.append(f"quest {quest.id!r} targets unknown enemy {objective.target_id!r}")
            for item_id in quest.rewards.items:
                if self.items.get(item_id) is None:
                    problems.append(f"quest {quest.id!r} rewards unknown item {item_id!r}")

        for area in self.world_manager.all_areas():
            for encounter in area.encounters:
                for enemy_id in encounter.enemy_ids:
                    if self.enemies.get_template(enemy_id) is None:
                        problems.append(f"area {area.id!r} spawns unknown enemy {enemy_id!r}")
                if encounter.is_boss:
                    boss = self.enemies.get_template(encounter.boss_id)
                    if encounter.boss_id not in encounter.enemy_ids:
                        problems.append(
                            f"area {area.id!r} boss encounter names {encounter.boss_id!r} outside enemy_ids"
                        )
                    elif boss is None or not boss.is_boss:
                        problems.append(
                            f"area {area.id!r} marks non-boss enemy {encounter.boss_id!r} as a boss encounter"
                        )

        for shop_id in {s for a in self.world_manager.all_areas() for s in a.shop_ids}:
            shop = self.world_manager.get_shop(shop_id)
            if shop is None:
                continue
            for item_id in [*shop.item_ids, *[i for values in shop.race_item_ids.values() for i in values]]:
                if self.items.get(item_id) is None:
                    problems.append(f"shop {shop_id!r} sells unknown item {item_id!r}")
            for race_id in [*shop.race_item_ids, *shop.race_buy_rates]:
                if self.races.get(race_id) is None:
                    problems.append(f"shop {shop_id!r} has rules for unknown race {race_id!r}")
            if shop.faction_id and self.story.faction(shop.faction_id) is None:
                problems.append(f"shop {shop_id!r} serves unknown faction {shop.faction_id!r}")

        for faction in self.story.factions.values():
            for rival in faction.rivals:
                if self.story.faction(rival) is None:
                    problems.append(f"faction {faction.id!r} names unknown rival {rival!r}")
        for tree in self.story.dialogues.values():
            if self._find_suitor(tree.speaker_id) is None:
                problems.append(f"dialogue {tree.id!r} has unknown speaker {tree.speaker_id!r}")
            if tree.start_node_id not in tree.nodes:
                problems.append(f"dialogue {tree.id!r} has unknown start node {tree.start_node_id!r}")
            for node in tree.nodes.values():
                for option in node.options:
                    if option.next_node_id and option.next_node_id not in tree.nodes:
                        problems.append(f"dialogue {tree.id!r} option {option.id!r} has unknown next node")
        if problems:
            raise ContentError("content validation failed:\n  - " + "\n  - ".join(problems))

    def content_summary(self) -> list[str]:
        """Counts for the launcher's diagnostics panel."""
        return [
            f"Classes: {self.classes.count()}",
            f"Skills: {self.skills.count()}",
            f"Items: {self.items.count()}",
            f"Races: {self.races.count()}",
            f"Enemies: {self.enemies.count()}",
            f"Quests: {self.quests.count()}",
            f"Dialogues: {self.story.count_dialogues()}",
            f"Factions: {len(self.story.factions)}",
            f"Companions: {self.companions.count()}",
            f"Areas: {self.world_manager.count()}",
        ]

    # ==================================================================
    # Character creation
    # ==================================================================
    def starting_classes(self, gender: str) -> list[ClassDefinition]:
        return self.classes.starting_classes(gender)

    def genders(self) -> list[str]:
        return list(self.config.get("genders", ["male", "female"]))

    def race_options(self) -> list[RaceDefinition]:
        return self.races.all_definitions()

    def default_race_id(self) -> str:
        return str(self.config.get("default_race_id", ""))

    def race_detail_lines(self, race_id: str) -> list[str]:
        race = self.races.get(race_id)
        return race.detail_lines() if race else ["Unknown race."]

    def race_name(self, race_id: str) -> str:
        race = self.races.get(race_id)
        return race.name if race else race_id.replace("_", " ").title()

    def create_character(
        self,
        name: str,
        gender: str,
        class_id: str,
        race_id: str | None = None,
        sub_race_id: str | None = None,
    ) -> tuple[bool, str]:
        """Build a fresh player and place them in the starting area."""
        name = (name or "").strip()
        if not name:
            return False, "Please enter a name."
        if len(name) > 24:
            return False, "Name must be 24 characters or fewer."

        definition = self.classes.get(class_id)
        if definition is None:
            return False, "Please choose a class."
        if not definition.allows_gender(gender):
            return False, f"{definition.name} is not available to {gender} characters."

        selected_race_id = race_id or str(self.config.get("default_race_id", ""))
        race = self.races.get(selected_race_id)
        if race is None:
            return False, "Please choose a race."

        # Validate sub-race if provided
        if sub_race_id:
            selected_sub_race = race.get_sub_race(sub_race_id)
            if selected_sub_race is None:
                return False, "Invalid sub-race selection."
            gender_rules = {"succubus": "female", "incubus": "male"}
            required_gender = gender_rules.get(sub_race_id)
            if required_gender and gender.lower() != required_gender:
                return False, f"{selected_sub_race.name} is only available to {required_gender} characters."

        progression = self.config.get("progression", {})
        player = Player(
            name=name,
            gender=gender,
            class_def=definition,
            race_def=race,
            formulas=self.formulas,
            level=int(progression.get("starting_level", 1)),
            progression=progression,
            equipment_config=self.config,
            enchantments=self.enchantments.definitions,
            sub_race_id=sub_race_id,
        )
        player.mastery = self._new_mastery_book()

        for skill in self.classes.create_starting_kit(definition, player.level):
            player.learn_skill(skill, spend_points=False)

        # Every sub-race begins with its own racial gift; it is free and does
        # not consume the character's level-one skill point.
        if sub_race_id:
            racial_skill = self.skills.get(f"racial_{sub_race_id}")
            if racial_skill is not None:
                player.learn_skill(racial_skill, spend_points=False)

        player.inventory.add_gold(definition.starting_gold or int(self.config.get("starting_gold", 0)))
        for item_id, quantity in definition.starting_items.items():
            self.items.grant(player.inventory, item_id, quantity)
        self._auto_equip_starting_gear(player)

        player.restore_fully()

        self.player = player
        self.party = Party(int((self.config.get("party") or {}).get("max_active", 2)))
        self.world = self.world_manager.create_world()
        self.battle = None
        self.current_slot = None
        return True, f"{name}, {race.name} {definition.name}, begins their ascension."

    def _new_mastery_book(self) -> MasteryBook:
        mastery_config = self.config.get("mastery", {})
        return MasteryBook(
            thresholds=mastery_config.get("thresholds"),
            rank_bonuses=mastery_config.get("rank_bonuses"),
            catalog=mastery_config.get("tracks"),
        )

    def _auto_equip_starting_gear(self, player: Player) -> None:
        """Equip one item per empty slot from the starting kit.

        Saves the player a trip to the Equipment screen before their first
        fight, which otherwise reads as the class handing out useless items.
        """
        for entry in list(player.inventory.equipment_entries()):
            item = entry.item
            if player.equipment.get(item.slot) is None:
                player.equip(item)

    # ==================================================================
    # Player queries (GUI reads these; it computes nothing itself)
    # ==================================================================
    @property
    def has_character(self) -> bool:
        return self.player is not None

    def player_summary(self) -> list[str]:
        return self.player.summary_lines() if self.player else ["No character loaded."]

    def player_stats(self) -> list[str]:
        if not self.player:
            return []
        lines = list(self.player.stat_lines())
        derived = self.player.derived_stats()
        lines.extend(
            [
                f"Attack: {derived.physical_power:.0f}",
                f"Magic: {derived.magic_power:.0f}",
                f"Armor: {derived.armor:.0f}",
                f"Resist: {derived.magic_resist:.0f}",
                f"Crit: {derived.crit_chance * 100:.0f}%",
                f"Accuracy: {derived.accuracy * 100:.0f}%",
                f"Evasion: {derived.evasion * 100:.0f}%",
                f"Speed: {derived.speed:.0f}",
            ]
        )
        return lines

    def status_lines(self) -> list[str]:
        """Everything the Status screen shows, in one stacked block."""
        if not self.player:
            return ["No character loaded."]
        lines = list(self.player.summary_lines())
        lines.append("")
        lines.extend(self.player_stats())
        lines.append("")
        lines.append(f"Stat points: {self.player.unspent_stat_points}")
        lines.append(f"Skill points: {self.player.unspent_skill_points}")
        mastery_lines = self.player.mastery.display_lines()
        if mastery_lines:
            lines.append("")
            lines.extend(mastery_lines)
        if self.player.statuses:
            lines.append("")
            lines.extend(self.player.status_summaries())
        if self.player.spouse_id:
            lines.append("")
            lines.append(f"Spouse: {self.player.spouse_id.replace('_', ' ').title()}")
        return lines

    def allocate_stat(self, stat: str, amount: int = 1) -> tuple[bool, str]:
        if not self.player:
            return False, "No character loaded."
        if self.player.allocate_stat(stat, amount):
            return True, f"{stat} increased by {amount}."
        return False, "No stat points available."

    # ==================================================================
    # Inventory / equipment
    # ==================================================================
    def inventory_lines(self, kind: str | None = None) -> list[str]:
        if not self.player:
            return []
        return [entry.label() for entry in self.player.inventory.sorted_entries(kind)]

    def inventory_entries(self, kind: str | None = None) -> list[Any]:
        return self.player.inventory.sorted_entries(kind) if self.player else []

    def equipment_lines(self) -> list[str]:
        return self.player.equipment_lines() if self.player else []

    def equippable_for_slot(self, slot: str) -> list[Item]:
        if not self.player:
            return []
        return [e.item for e in self.player.inventory.equipment_entries(slot)]

    def equip_item(self, item_id: str) -> tuple[bool, str]:
        if not self.player:
            return False, "No character loaded."
        item = self.items.get(item_id)
        if item is None:
            return False, "Unknown item."
        ok, message = self.player.equip(item)
        if ok:
            if item.bound_skill_id:
                skill = self.skills.get(item.bound_skill_id)
                if skill and skill.id not in self.player.known_skills:
                    self.player.known_skills[skill.id] = skill
                    self.player.equipment_granted_skills.add(skill.id)
            for target in (item.id, item.slot, item.weapon_type, item.kind):
                if target:
                    self.quests.record_event(self.player, "equip_item_type", target)
        return ok, message

    def unequip_slot(self, slot: str) -> tuple[bool, str]:
        if not self.player:
            return False, "No character loaded."
        item = self.player.equipment.get(slot)
        ok, message = self.player.unequip(slot)
        if ok and item and item.bound_skill_id in self.player.equipment_granted_skills:
            still_granted = any(
                equipped and equipped.bound_skill_id == item.bound_skill_id
                for equipped in self.player.equipment.values()
            )
            if not still_granted:
                self.player.known_skills.pop(item.bound_skill_id, None)
                self.player.equipment_granted_skills.discard(item.bound_skill_id)
        return ok, message

    def enchant_item(self, item_id: str, enchantment_id: str) -> tuple[bool, str]:
        if not self.player:
            return False, "No character loaded."
        item = self.items.get(item_id)
        enchantment = self.enchantments.get(enchantment_id)
        if item is None or enchantment is None or not item.is_equipment:
            return False, "Invalid item or enchantment."
        if item.enchant_slots < 1:
            return False, f"{item.name} cannot be enchanted."
        if not (self.player.inventory.has(item_id) or item in self.player.equipment.values()):
            return False, f"You do not own {item.name}."
        if not self.player.inventory.spend_gold(enchantment.gold_cost):
            return False, f"You need {enchantment.gold_cost} gold."
        self.player.item_enchantments[item_id] = enchantment_id
        self.player.invalidate_stats()
        return True, f"Applied {enchantment.name} to {item.name}."

    def upgrade_item(self, item_id: str) -> tuple[bool, str]:
        if not self.player:
            return False, "No character loaded."
        item = self.items.get(item_id)
        if item is None or not item.is_equipment:
            return False, "Invalid equipment."
        current = self.player.item_upgrades.get(item_id, 0)
        cfg = self.config.get("equipment_upgrade") or {}
        if current >= int(cfg.get("max_level", 0)):
            return False, "That item is fully upgraded."
        cost = int(cfg.get("base_gold", 0)) * (current + 1)
        if not self.player.inventory.spend_gold(cost):
            return False, f"You need {cost} gold."
        self.player.item_upgrades[item_id] = current + 1
        self.player.invalidate_stats()
        return True, f"Upgraded {item.name} to +{current + 1}."

    def use_item(self, item_id: str) -> tuple[bool, list[str]]:
        """Use a consumable outside combat."""
        if not self.player:
            return False, ["No character loaded."]
        ctx = self.skills.make_context(self.rng, self.formulas)
        return self.items.use_consumable(self.player, item_id, ctx, [self.player])

    # ==================================================================
    # Skills
    # ==================================================================
    def known_skill_lines(self) -> list[str]:
        if not self.player:
            return []
        lines = [f"{s.name} [{s.category}] - {s.cost_text()}" for s in self.player.usable_skills()]
        lines.extend(f"{s.name} [passive]" for s in self.player.passive_skills())
        return lines

    def learnable_skills(self) -> list[Any]:
        return self.classes.learnable_skills(self.player) if self.player else []

    def learn_skill(self, skill_id: str) -> tuple[bool, str]:
        if not self.player:
            return False, "No character loaded."
        skill = self.skills.get(skill_id)
        if skill is None:
            return False, "Unknown skill."
        ok, message = self.player.learn_skill(skill)
        if ok:
            # Codex: track skills learned
            unlocked = self.player.record_achievement("skills_learned", skill_id)
            for ach_id in unlocked:
                message += f"\n🏆 Achievement unlocked: {self._achievement_name(ach_id)}"
        return ok, message

    # ==================================================================
    # Promotion
    # ==================================================================
    def promotion_options(self) -> list[Any]:
        return self.classes.available_promotions(self.player) if self.player else []

    def promote(self, target_class_id: str) -> tuple[bool, list[str]]:
        if not self.player:
            return False, ["No character loaded."]
        ok, messages = self.classes.promote(self.player, target_class_id)
        if ok:
            # Codex: track promotions
            unlocked = self.player.record_achievement("promotions", target_class_id)
            for ach_id in unlocked:
                messages.append(f"🏆 Achievement unlocked: {self._achievement_name(ach_id)}")
        return ok, messages

    # ==================================================================
    # Quests
    # ==================================================================
    def available_quests(self) -> list[QuestDefinition]:
        if not self.player or not self.world:
            return []
        return [
            quest
            for quest in self.quests.available_for(self.player, self.world.current_area_id)
            if not quest.required_companion_id or self.party.has(quest.required_companion_id)
        ]

    def quests_from(self, giver_id: str) -> list[QuestDefinition]:
        if not self.player or not self.world:
            return []
        return [
            quest
            for quest in self.quests.available_for(
                self.player,
                self.world.current_area_id,
                giver_id=giver_id,
            )
            if not quest.required_companion_id or self.party.has(quest.required_companion_id)
        ]

    def active_quests(self) -> list[QuestDefinition]:
        return self.quests.active_for(self.player) if self.player else []

    def completed_quests(self) -> list[QuestDefinition]:
        if not self.player:
            return []
        return [
            definition
            for quest_id in self.player.completed_quests
            if (definition := self.quests.get(quest_id)) is not None
        ]

    def accept_quest(self, quest_id: str) -> tuple[bool, str]:
        if not self.player:
            return False, "No character loaded."
        definition = self.quests.get(quest_id)
        if definition is None:
            return False, "Unknown quest."
        if not self.world or definition not in self.available_quests():
            return False, "That quest is not available from anyone here."
        if not self.player.accept_quest(quest_id):
            return False, "That quest is already active or completed."
        # A save must not dead-end if the player defeated a one-time boss before
        # speaking to its quest giver. The giver recognises the existing deed.
        if self.world.defeated_bosses:
            self.quests.record_defeats(self.player, self.world.defeated_bosses)
        return True, f"Accepted quest from {self._quest_giver_name(definition)}: {definition.name}."

    def _quest_giver_name(self, definition: QuestDefinition) -> str:
        giver = self._find_suitor(definition.giver_id)
        return giver.name if giver else definition.giver_id.replace("_", " ").title()

    def quest_giver_lines(self, giver_id: str) -> list[str]:
        """Quest summary shown while speaking to one NPC."""
        available = self.quests_from(giver_id)
        active = [quest for quest in self.active_quests() if quest.giver_id == giver_id]
        lines: list[str] = []
        lines.extend(f"Available quest: {quest.name}" for quest in available)
        for quest in active:
            ready, _ = self.quest_completion_check(quest.id)
            state = "Ready to turn in" if ready else "In progress"
            lines.append(f"{state}: {quest.name}")
        return lines

    def quest_detail_lines(self, quest_id: str) -> list[str]:
        definition = self.quests.get(quest_id)
        if definition is None:
            return ["Unknown quest."]
        lines = [definition.name]
        if definition.description:
            lines.append(definition.description)
        lines.append(f"Minimum level: {definition.min_level}")
        if definition.giver_id:
            lines.append(f"Quest giver: {self._quest_giver_name(definition)}")
        if definition.start_area_id:
            area = self.world_manager.get_area(definition.start_area_id)
            lines.append(f"Accept in: {area.name if area else definition.start_area_id}")
        if definition.turn_in_area_id:
            area = self.world_manager.get_area(definition.turn_in_area_id)
            lines.append(f"Return to: {area.name if area else definition.turn_in_area_id}")
        progress = self.player.quest_progress.get(quest_id, {}) if self.player else {}
        lines.append("Objectives:")
        lines.extend(definition.progress_lines(progress))
        reward_parts: list[str] = []
        if definition.rewards.exp:
            reward_parts.append(f"{definition.rewards.exp:.0f} EXP")
        if definition.rewards.gold:
            reward_parts.append(f"{definition.rewards.gold} gold")
        for item_id, quantity in definition.rewards.items.items():
            item = self.items.get(item_id)
            name = item.name if item else item_id.replace("_", " ").title()
            reward_parts.append(f"{name} x{quantity}")
        lines.append("Rewards: " + (", ".join(reward_parts) if reward_parts else "None"))
        return lines

    def refresh_quest_objectives(self) -> None:
        """Refresh objectives sourced from current character state."""
        if not self.player:
            return
        collected: dict[str, int] = {}
        for entry in self.player.inventory.entries:
            collected[entry.item.id] = collected.get(entry.item.id, 0) + entry.quantity
        for item_id, quantity in collected.items():
            self.quests.record_event(
                self.player, "collect_item", item_id, quantity, absolute=True
            )
        for target_id, affinity in self.player.affinity.items():
            self.quests.record_event(
                self.player, "affinity", target_id, affinity, absolute=True
            )
        for item in self.player.equipment.values():
            if item is None:
                continue
            for target in (item.id, item.slot, item.weapon_type, item.kind):
                if target:
                    self.quests.record_event(self.player, "equip_item_type", target, 1, absolute=True)

    def quest_completion_check(self, quest_id: str) -> tuple[bool, list[str]]:
        if not self.player or not self.world:
            return False, ["No character loaded."]
        self.refresh_quest_objectives()
        ready, unmet = self.quests.can_complete(self.player, quest_id)
        definition = self.quests.get(quest_id)
        if (
            ready
            and definition is not None
            and definition.turn_in_area_id
            and self.world.current_area_id != definition.turn_in_area_id
        ):
            area = self.world_manager.get_area(definition.turn_in_area_id)
            return False, [f"Return to {area.name if area else definition.turn_in_area_id}."]
        return ready, unmet

    def complete_quest(self, quest_id: str) -> tuple[bool, list[str]]:
        if not self.player:
            return False, ["No character loaded."]
        ready, unmet = self.quest_completion_check(quest_id)
        if not ready:
            return False, unmet

        definition = self.quests.require(quest_id)
        # Turning in is atomic: a full bag must not consume the quest and lose
        # an item reward that can never be claimed again.
        trial_inventory = deepcopy(self.player.inventory)
        for item_id, quantity in definition.rewards.items.items():
            item = self.items.require(item_id)
            if trial_inventory.add(item, quantity) != quantity:
                return False, ["Make room in your inventory before completing this quest."]

        if not self.player.complete_quest(quest_id):
            return False, ["Quest already completed."]

        lines = [f"Quest completed: {definition.name}."]
        if definition.rewards.gold:
            self.player.inventory.add_gold(definition.rewards.gold)
            lines.append(f"Received {definition.rewards.gold} gold.")
        if definition.rewards.exp:
            report = self.player.gain_exp(definition.rewards.exp)
            lines.append(f"Gained {definition.rewards.exp:.0f} EXP.")
            lines.extend(report.messages)
        for item_line in self.items.grant_many(self.player.inventory, definition.rewards.items):
            lines.append(f"Received {item_line}.")
        # Codex: track quests completed
        unlocked = self.player.record_achievement("quests_completed", quest_id)
        for ach_id in unlocked:
            lines.append(f"🏆 Achievement unlocked: {self._achievement_name(ach_id)}")
        return True, lines

    # ==================================================================
    # World
    # ==================================================================
    def world_lines(self) -> list[str]:
        if not self.world or not self.player:
            return []
        area = self.world.current_area
        lines = [
            f"Day: {self.world.day}",
            f"Location: {self.world.area_name()}",
        ]
        if area and area.description:
            lines.append(area.description)
        return lines

    def travel_options(self) -> list[Any]:
        if not self.world or not self.player:
            return []
        return self.world.connected_areas(self.player.level)

    def travel_to(self, area_id: str) -> tuple[bool, str]:
        if not self.world or not self.player:
            return False, "No character loaded."
        ok, message = self.world.travel_to(area_id, self.player.level)
        if ok:
            self.quests.record_event(self.player, "visit_area", area_id)
            # Codex: track area visited
            unlocked = self.player.record_achievement("areas_visited", area_id)
            for ach_id in unlocked:
                message += f"\n🏆 Achievement unlocked: {self._achievement_name(ach_id)}"
            # Random travel event (20% chance)
            event = self._random_travel_event(area_id)
            if event:
                message += "\n\n" + event
            for companion in self.party.active:
                self.quests.record_event(self.player, "travel_with_companion", companion.id)
            banter = self.trigger_banter("travel", area_id=area_id)
            if banter:
                message += "\n" + "\n".join(banter)
        return ok, message

    def _random_travel_event(self, area_id: str) -> str | None:
        """Generate a random event during travel. 20% chance per journey."""
        if not self.player or not self.rng:
            return None
        if not self.rng.chance(0.2):
            return None

        events = [
            # Positive events
            ("merchant", "You encounter a travelling merchant who offers you a fair price for your wares.", lambda: self._event_merchant()),
            ("shrine", "You find a roadside shrine that fills you with renewed vigour.", lambda: self._event_shrine()),
            ("traveller", "A fellow traveller shares news of the road ahead.", lambda: self._event_traveller()),
            ("herbs", "You spot rare healing herbs growing by the roadside.", lambda: self._event_herbs()),
            ("treasure", "You discover a hidden cache left by a previous adventurer.", lambda: self._event_treasure()),
            # Negative events
            ("ambush", "Bandits leap from the undergrowth!", lambda: self._event_ambush()),
            ("storm", "A sudden storm forces you to take shelter, costing time.", lambda: self._event_storm()),
            ("trap", "You stumble into a hunter's trap!", lambda: self._event_trap()),
            # Neutral events
            ("ruins", "You pass ancient ruins. Something stirs within, but does not emerge.", lambda: self._event_ruins()),
            ("omen", "A raven circles overhead three times before flying south. An omen?", lambda: self._event_omen()),
        ]

        event_type, text, handler = self.rng.choice(events)
        result = handler()
        if result:
            return f"📍 {text}\n{result}"
        return f"📍 {text}"

    def _event_merchant(self) -> str:
        if self.player and self.player.inventory.gold >= 50:
            self.player.inventory.spend_gold(50)
            return "You trade 50 gold for useful supplies."
        return "You have nothing to trade."

    def _event_shrine(self) -> str:
        if self.player:
            heal = int(self.player.max_hp * 0.2)
            self.player.heal(heal)
            mana = int(self.player.max_mp * 0.2)
            self.player.change_mp(mana)
            sp = int(self.player.max_sp * 0.2)
            self.player.change_sp(sp)
            return f"The shrine's blessing restores {heal} HP, {mana} MP, and {sp} SP."
        return ""

    def _event_traveller(self) -> str:
        if self.player:
            self.player.gain_exp(50)
            return "You gain 50 EXP from the shared knowledge."
        return ""

    def _event_herbs(self) -> str:
        if self.player:
            item = self.items.get("minor_potion")
            if item:
                self.player.inventory.add(item, 1)
                return "You gather enough herbs to brew a Minor Potion."
        return ""

    def _event_treasure(self) -> str:
        if self.player:
            gold = self.rng.randint(30, 120) if self.rng else 50
            self.player.inventory.add_gold(gold)
            return f"You find {gold} gold in the cache!"
        return ""

    def _event_ambush(self) -> str:
        if self.player:
            damage = int(self.player.max_hp * 0.1)
            self.player.take_raw_damage(damage, damage_type="physical")
            return f"The bandits wound you for {damage} damage before fleeing."
        return ""

    def _event_storm(self) -> str:
        return "You lose an hour waiting for the storm to pass."

    def _event_trap(self) -> str:
        if self.player:
            damage = int(self.player.max_hp * 0.08)
            self.player.take_raw_damage(damage, damage_type="physical")
            return f"You take {damage} damage from the trap."
        return ""

    def _event_ruins(self) -> str:
        if self.player:
            self.player.gain_exp(30)
            return "You gain 30 EXP from exploring the ruins."
        return ""

    def _event_omen(self) -> str:
        if self.player:
            self.player.gain_exp(20)
            return "You ponder the omen and gain 20 EXP."
        return ""

    def _achievement_name(self, achievement_id: str) -> str:
        from engine.codex import ACHIEVEMENTS
        for ach in ACHIEVEMENTS:
            if ach.id == achievement_id:
                return ach.name
        return achievement_id

    def explore(self) -> tuple[str, Battle | None]:
        """Take one exploration step; starts a battle on an encounter.

        Returns ``(message, battle_or_None)`` so the GUI can decide whether to
        switch to the Combat screen without inspecting engine internals.
        """
        if not self.world or not self.player:
            return ("No character loaded.", None)
        if self.battle and not self.battle.is_over:
            return ("You are already in battle.", self.battle)

        result = self.world.explore(self.rng, self.player.level)
        if not result.is_encounter:
            return (result.message, None)

        battle = self.start_battle(result.spawns)
        return (result.message, battle)

    def start_battle(self, spawns: Sequence[tuple[str, int]]) -> Battle:
        """Spawn a group and open a battle against it."""
        if not self.player:
            raise RuntimeError("cannot start a battle without a player")
        enemies = self.enemies.spawn_group(list(spawns))
        ctx = self.skills.make_context(self.rng, self.formulas)
        combat_config = self.config.get("combat", {})
        # Companions track the player's level so they never become dead weight.
        self.party.sync_levels(self.player.level)
        self.battle = Battle(
            player=self.player,
            enemies=enemies,
            ctx=ctx,
            rng=self.rng,
            allies=self.party.battle_allies(),
            ai_registry=self.ai_registry,
            flee_base_chance=float(combat_config.get("flee_base_chance", 0.45)),
            mastery_per_action=float(combat_config.get("mastery_per_action", 6.0)),
            summon_factory=lambda enemy_id, level: self.enemies.spawn(enemy_id, level),
        )
        # Fast enemies may act before the player's first turn.
        self.battle.run_until_player_turn()
        return self.battle

    # ==================================================================
    # Combat resolution
    # ==================================================================
    def finish_battle(self) -> list[str]:
        """Wrap up a finished battle: loot, then death handling.

        Safe to call more than once; the battle is cleared on the first call.
        """
        battle = self.battle
        if battle is None or not battle.is_over:
            return []

        lines: list[str] = []
        if battle.state is CombatState.VICTORY:
            lines.extend(battle.grant_loot(self.items))
            lines.extend(battle.rewards.summary_lines())
            defeated_ids = [enemy.template.id for enemy in battle.enemies]
            boss_victory = False
            if self.world:
                for enemy in battle.enemies:
                    if enemy.is_boss and enemy.template.id not in self.world.defeated_bosses:
                        boss_victory = True
                        self.world.defeated_bosses.add(enemy.template.id)
                        lines.append(f"World updated: {enemy.template.name} has been defeated.")
            if self.player:
                # Codex: track enemy defeats
                for eid in defeated_ids:
                    unlocked = self.player.record_achievement("enemies_defeated", eid)
                    for ach_id in unlocked:
                        lines.append(f"🏆 Achievement unlocked: {self._achievement_name(ach_id)}")
                # Codex: track unique enemy types
                unique = self.player.codex.count_for("enemies_defeated")
                if len(set(defeated_ids)) > 0:
                    unlocked = self.player.record_achievement("unique_enemies", "total", len(set(defeated_ids)))
                    for ach_id in unlocked:
                        lines.append(f"🏆 Achievement unlocked: {self._achievement_name(ach_id)}")
                changed = self.quests.record_defeats(self.player, defeated_ids)
                for quest_id in changed:
                    definition = self.quests.require(quest_id)
                    progress = self.player.quest_progress.get(quest_id, {})
                    lines.append(f"Quest progress — {definition.name}:")
                    lines.extend(definition.progress_lines(progress))
                if not any(not companion.is_alive for companion in self.party.active):
                    self.quests.record_event(self.player, "battle_no_downs", "any")
                if battle.round <= 5:
                    self.quests.record_event(self.player, "battle_turn_limit", "5")
                if boss_victory:
                    # Codex: track boss kills
                    for enemy in battle.enemies:
                        if enemy.is_boss:
                            unlocked = self.player.record_achievement("bosses_slain", enemy.template.id)
                            for ach_id in unlocked:
                                lines.append(f"🏆 Achievement unlocked: {self._achievement_name(ach_id)}")
                    lines.extend(self.trigger_banter("boss_victory"))
                for family in {enemy.template.family for enemy in battle.enemies}:
                    lines.extend(self.trigger_banter("enemy_family", enemy_family=family))
                for companion in self.party.active:
                    if not companion.is_alive:
                        lines.extend(self.trigger_banter("companion_downed", companion_id=companion.id))
        elif battle.state is CombatState.DEFEAT:
            lines.extend(self.handle_death())

        self.battle = None
        # Companions earn affinity for fighting beside you.
        if battle.state is CombatState.VICTORY and self.player:
            for companion in self.party.active:
                self.player.change_affinity(companion.id, self.relationships.per_battle)
                self.change_loyalty(companion.id, 3 if any(enemy.is_boss for enemy in battle.enemies) else 1)
        lines.extend(self.party.revive_fallen())
        self.party.clear_battle_state()
        if self.player:
            self.player.cooldowns.clear()
            for status in list(self.player.statuses):
                # Battle-only statuses should not persist into the world map.
                self.player.remove_status(status.id)
        return lines

    def handle_death(self) -> list[str]:
        """Respawn at the Inn (bible section 16), with a gold penalty."""
        if not self.player or not self.world:
            return []
        penalty_rate = float(self.config.get("death_gold_penalty", 0.1))
        lost = int(self.player.inventory.gold * penalty_rate)
        self.player.inventory.gold -= lost

        inn_area = str(self.config.get("respawn_area_id", ""))
        if inn_area and inn_area in self.world.areas:
            self.world.current_area_id = inn_area
            self.world.visited.add(inn_area)

        self.player.restore_fully()
        self.party.restore_all()
        return [
            f"{self.player.name} awakens at the Inn.",
            f"Lost {lost} gold." if lost else "No gold was lost.",
        ]

    # ==================================================================
    # Town actions
    # ==================================================================
    def rest_at_inn(self) -> tuple[bool, list[str]]:
        """Sleep -> next day -> morning autosave (bible section 8)."""
        if not self.player or not self.world:
            return False, ["No character loaded."]
        if not self.world.is_in_town():
            return False, ["You can only rest in town."]

        cost = int(self.config.get("inn_cost", 0))
        if cost and not self.player.inventory.spend_gold(cost):
            return False, [f"You need {cost} gold to rest."]

        self.player.restore_fully()
        self.party.restore_all()
        self.party.sync_levels(self.player.level)
        day = self.world.advance_day()
        lines = [f"You rest until morning. Day {day} begins.", "Fully restored."]
        if cost:
            lines.append(f"Paid {cost} gold.")

        slot, saved = self.autosave()
        lines.append(f"Autosaved to '{slot}'." if saved else "Autosave failed.")
        lines.extend(self.trigger_banter("rest", area_id=self.world.current_area_id))
        return True, lines

    def shop_stock(self, shop_id: str) -> list[Item]:
        shop = self.world_manager.get_shop(shop_id)
        if shop is None:
            return []
        ids = list(shop.item_ids)
        if self.player:
            ids.extend(shop.race_item_ids.get(self.player.race_id, []))
        return [item for item in (self.items.get(i) for i in ids) if item is not None]

    def buy_item(self, shop_id: str, item_id: str) -> tuple[bool, str]:
        if not self.player:
            return False, "No character loaded."
        shop = self.world_manager.get_shop(shop_id)
        item = self.items.get(item_id)
        available_ids = {item.id for item in self.shop_stock(shop_id)}
        if shop is None or item is None or item_id not in available_ids:
            return False, "That item is not for sale here."
        price = self.shop_price(shop_id, item_id)
        if not self.player.inventory.spend_gold(price):
            return False, f"You need {price} gold."
        if self.player.inventory.add(item, 1) <= 0:
            self.player.inventory.add_gold(price)
            return False, "Your inventory is full."
        return True, f"Bought {item.name} for {price} gold."

    def sell_item(self, shop_id: str, item_id: str) -> tuple[bool, str]:
        if not self.player:
            return False, "No character loaded."
        shop = self.world_manager.get_shop(shop_id)
        item = self.items.get(item_id)
        if item is None:
            return False, "Unknown item."
        if not self.player.inventory.has(item_id):
            return False, f"You have no {item.name}."
        rate = shop.sell_rate if shop else 0.4
        price = item.sell_price(rate)
        self.player.inventory.remove(item_id, 1)
        self.player.inventory.add_gold(price)
        return True, f"Sold {item.name} for {price} gold."

    # ==================================================================
    # Companions and party (bible section 6, roadmap v0.0.9)
    # ==================================================================
    def recruitable_here(self) -> list[Any]:
        """Companion definitions in this area the player has not recruited."""
        if not self.world or not self.player:
            return []
        return [
            definition
            for definition in self.companions.at_location(self.world.current_area_id)
            if not self.party.has(definition.id)
        ]

    def check_recruit(self, companion_id: str) -> tuple[bool, list[str]]:
        """Requirement checklist for recruiting, in the promotion-check style."""
        if not self.player:
            return False, ["No character loaded."]
        definition = self.companions.get(companion_id)
        if definition is None:
            return False, ["Nobody by that name."]
        if self.party.has(companion_id):
            return False, [f"{definition.name} already travels with you."]

        requirement = definition.recruit
        unmet: list[str] = []
        unavailable_until = self.player.companion_unavailable_until.get(companion_id, 0)
        if self.world and self.world.day < unavailable_until:
            unmet.append(f"Needs time alone until day {unavailable_until}")
        if self.player.level < requirement.level:
            unmet.append(f"Level {requirement.level} (have {self.player.level})")
        affinity = self.player.affinity_with(companion_id)
        if affinity < requirement.affinity:
            unmet.append(f"Affinity {requirement.affinity} (have {affinity})")
        if requirement.gold and self.player.inventory.gold < requirement.gold:
            unmet.append(f"{requirement.gold} gold (have {self.player.inventory.gold})")
        for item_id, quantity in requirement.items.items():
            if not self.player.inventory.has(item_id, quantity):
                item = self.items.get(item_id)
                label = item.name if item else item_id.replace("_", " ").title()
                unmet.append(f"{label} x{quantity} (have {self.player.inventory.count(item_id)})")
        for quest_id in requirement.quests:
            if quest_id not in self.player.completed_quests:
                unmet.append(f"Quest: {quest_id.replace('_', ' ').title()}")

        return (not unmet), unmet

    def recruit(self, companion_id: str) -> tuple[bool, list[str]]:
        """Recruit a companion, consuming the required gold and items."""
        ok, unmet = self.check_recruit(companion_id)
        if not ok or self.player is None:
            return False, unmet or ["They will not join you."]

        definition = self.companions.require(companion_id)
        requirement = definition.recruit
        if requirement.gold:
            self.player.inventory.spend_gold(requirement.gold)
        for item_id, quantity in requirement.items.items():
            self.player.inventory.remove(item_id, quantity)

        companion = self.companions.create(companion_id, self.player.level)
        self._apply_spouse_bonus(companion)
        joined, message = self.party.recruit(companion)
        if joined:
            self.quests.record_event(self.player, "recruit_companion", companion_id)
            self.player.companion_loyalty.setdefault(companion_id, 0)
            # Codex: track companions recruited
            unlocked = self.player.record_achievement("companions_recruited", companion_id)
            for ach_id in unlocked:
                message += f"\n🏆 Achievement unlocked: {self._achievement_name(ach_id)}"
        return joined, [message]

    def dismiss_companion(self, companion_id: str) -> tuple[bool, str]:
        """Dismiss a companion.  Affinity is kept, so they can rejoin."""
        if not self.player:
            return False, "No character loaded."
        if self.player.spouse_id == companion_id:
            return False, "You will not send your spouse away."
        return self.party.dismiss(companion_id)

    def set_companion_active(self, companion_id: str, active: bool) -> tuple[bool, str]:
        return self.party.set_active(companion_id, active)

    def set_companion_tactics(self, companion_id: str, tactics: Mapping[str, Any]) -> tuple[bool, str]:
        companion = self.party.get(companion_id)
        if companion is None:
            return False, "They are not in your party."
        allowed = {"stance", "preferred_target", "preserve_mp", "healing_threshold", "ultimate_policy", "protect_target"}
        companion.set_tactics({key: value for key, value in tactics.items() if key in allowed})
        return True, f"Updated tactics for {companion.name}."

    def party_lines(self) -> list[str]:
        return self.party.summary_lines()

    def companion_detail_lines(self, companion_id: str) -> list[str]:
        """Full readout for one companion, recruited or not."""
        if not self.player:
            return []
        definition = self.companions.get(companion_id)
        if definition is None:
            return ["Nobody by that name."]

        member = self.party.get(companion_id)
        lines = list(definition.detail_lines())
        lines.append("")
        if member is not None:
            lines.extend(member.summary_lines()[2:])
            lines.append("Status: " + ("Active" if self.party.is_active(companion_id) else "Reserve"))
        else:
            lines.append(f"Level: {definition.level_for(self.player.level)} (joins at your level)")

        affinity = self.player.affinity_with(companion_id)
        lines.append("")
        lines.append(f"Affinity: {affinity} ({self.relationships.tier_label(affinity)})")
        lines.append(f"Loyalty: {self.player.companion_loyalty.get(companion_id, 0)} ({self.loyalty_rank(companion_id)})")
        if member and member.loyalty_title:
            lines.append(f"Title: {member.loyalty_title}")
        if member and member.outfit_id != "default":
            lines.append(f"Outfit: {member.outfit_id.replace('_', ' ').title()}")
        if self.player.spouse_id == companion_id:
            lines.append("Married to you")
        elif definition.marriageable:
            lines.append(f"Marriage at: {definition.marriage_affinity}")

        if member is None:
            requirements = definition.recruit.describe()
            if requirements:
                lines.append("")
                lines.append("To recruit:")
                lines.extend(f"  {line}" for line in requirements)
        return lines

    def _apply_spouse_bonus(self, companion: Any) -> None:
        """Give a married companion their spouse bonus, and only them."""
        if not self.player:
            return
        if self.player.spouse_id == companion.id:
            bonus = ModifierSet.from_dict({"flat": self.relationships.spouse_modifiers()})
            companion.set_married_bonus(bonus)
        else:
            companion.set_married_bonus(None)

    # ==================================================================
    # NPCs, affinity, marriage (bible section 15)
    #
    # Companions and townspeople share these methods: both satisfy the
    # `Suitor` shape, so `engine.relationships` drives them identically and
    # a companion is marriageable on exactly the same terms as an NPC.
    # ==================================================================
    def npcs_here(self) -> list[Any]:
        return self.world.npcs_here() if self.world else []

    def _find_suitor(self, target_id: str) -> Any | None:
        """Resolve an id to an NPC or a companion definition."""
        npc = self.world_manager.get_npc(target_id)
        if npc is not None:
            return npc
        return self.companions.get(target_id)

    def social_targets_here(self) -> list[Any]:
        """Everyone the player can talk to right now - NPCs and companions.

        Recruited companions travel with the player, so they are always
        available; unrecruited ones only appear in their home area.
        """
        targets: list[Any] = list(self.npcs_here())
        targets.extend(self.party.all_members)
        targets.extend(self.recruitable_here())
        return targets

    def talk_to(self, target_id: str) -> tuple[bool, list[str]]:
        """Talk to an NPC or companion: dialogue plus a small affinity gain."""
        if not self.player or not self.world:
            return False, ["No character loaded."]
        suitor = self._find_suitor(target_id)
        if suitor is None:
            return False, ["There is nobody by that name here."]

        # Repeat chatter in one day is worth less, so the optimal play is not
        # clicking Talk a hundred times.
        talked = self.player.flags.setdefault("talked_today", {})
        key = f"{self.world.day}:{target_id}"
        times = int(talked.get(key, 0))
        talked[key] = times + 1

        value = self.player.change_affinity(target_id, self.relationships.talk_gain(times))
        self.quests.record_event(self.player, "talk_to", target_id)
        self.quests.record_event(self.player, "affinity", target_id, value, absolute=True)
        line = self.rng.choice(suitor.dialogue) if suitor.dialogue else f"{suitor.name} nods at you."
        lines = [
            f'{suitor.name}: "{line}"',
            f"Affinity with {suitor.name}: {value} ({self.relationships.tier_label(value)})",
        ]
        if (
            getattr(suitor, "marriageable", False)
            and value >= suitor.marriage_affinity
            and not self.player.spouse_id
        ):
            lines.append(f"{suitor.name} seems ready for a deeper commitment.")
        return True, lines

    def give_gift(self, target_id: str, item_id: str) -> tuple[bool, list[str]]:
        """Gift an item; favourites are worth far more affinity."""
        if not self.player:
            return False, ["No character loaded."]
        suitor = self._find_suitor(target_id)
        item = self.items.get(item_id)
        if suitor is None or item is None:
            return False, ["That gift cannot be given."]
        if not self.player.inventory.has(item_id):
            return False, [f"You have no {item.name}."]

        gain, liked = self.relationships.gift_gain(suitor, item_id)
        self.player.inventory.remove(item_id, 1)
        value = self.player.change_affinity(target_id, gain)
        reaction = "loves" if liked else "accepts"
        return True, [
            f"{suitor.name} {reaction} the {item.name}.",
            f"Affinity with {suitor.name}: {value} ({self.relationships.tier_label(value)})",
        ]

    def marriage_check(self, target_id: str) -> Any:
        """Full marriage checklist for an NPC or companion."""
        suitor = self._find_suitor(target_id)
        if suitor is None or not self.player:
            return MarriageCheck(eligible=False, target_id=target_id, reason="Unknown person.")

        ring_id = self.relationships.marriage_item_id
        ring = self.items.get(ring_id) if ring_id else None
        # A companion must be travelling with you; an NPC has no such notion.
        recruited = self.party.has(target_id) if self.companions.get(target_id) else True

        return self.relationships.check_marriage(
            suitor,
            affinity=self.player.affinity_with(target_id),
            has_ring=(not ring_id) or self.player.inventory.has(ring_id),
            current_spouse_id=self.player.spouse_id,
            ring_name=ring.name if ring else "",
            recruited=recruited,
        )

    def can_marry(self, target_id: str) -> tuple[bool, str]:
        """Backwards-compatible boolean form of :meth:`marriage_check`.

        The unmet items are preferred over the generic ``reason`` so the caller
        is told *what* is missing ("Affinity 70 (have 0); Eternal Band") rather
        than just that something is.
        """
        if not self.player:
            return False, "No character loaded."
        check = self.marriage_check(target_id)
        if check.eligible:
            return True, "You may propose."
        return False, "; ".join(check.unmet) or check.reason or "Requirements not met."

    def marry(self, target_id: str) -> tuple[bool, str]:
        """Marry an NPC or companion.  Gender is never considered."""
        check = self.marriage_check(target_id)
        if not check.eligible or self.player is None:
            return False, "; ".join(check.unmet) or check.reason or "Requirements not met."

        ring_id = self.relationships.marriage_item_id
        if ring_id:
            self.player.inventory.remove(ring_id, 1)

        ok, message = self.player.marry(target_id)
        if ok:
            # A married companion fights harder from here on.
            member = self.party.get(target_id)
            if member is not None:
                self._apply_spouse_bonus(member)
            self.notices.extend(self.trigger_banter("marriage", companion_id=target_id))
            # Codex: track marriage
            unlocked = self.player.record_achievement("marriages", target_id)
            for ach_id in unlocked:
                message += f"\n🏆 Achievement unlocked: {self._achievement_name(ach_id)}"
        return ok, message

    # ==================================================================
    # Story, factions, loyalty, and banter
    # ==================================================================
    def change_reputation(self, faction_id: str, amount: int) -> int:
        if not self.player or self.story.faction(faction_id) is None:
            return 0
        value = max(-100, min(100, self.player.faction_reputation.get(faction_id, 0) + int(amount)))
        self.player.faction_reputation[faction_id] = value
        if amount > 0:
            for rival in self.story.faction(faction_id).rivals:
                self.player.faction_reputation[rival] = max(
                    -100, self.player.faction_reputation.get(rival, 0) - max(1, amount // 2)
                )
        return value

    def shop_price(self, shop_id: str, item_id: str) -> int:
        shop = self.world_manager.get_shop(shop_id)
        item = self.items.get(item_id)
        if shop is None or item is None:
            return 0
        discount = 0.0
        faction = self.story.faction(shop.faction_id)
        if faction and self.player:
            reputation = max(0, self.player.faction_reputation.get(faction.id, 0))
            discount = min(faction.max_discount, reputation * faction.shop_discount_per_point)
        race_rate = shop.race_buy_rates.get(self.player.race_id, 1.0) if self.player else 1.0
        return max(1, int(item.value * shop.buy_rate * race_rate * (1.0 - discount)))

    def _story_conditions_met(self, conditions: Mapping[str, Any]) -> bool:
        if not self.player:
            return False
        checks = (
            ("race_ids", self.player.race_id),
            ("class_ids", self.player.class_def.id),
            ("sub_race_ids", self.player.sub_race_id),
        )
        for key, value in checks:
            allowed = conditions.get(key)
            if allowed and value not in allowed:
                return False
        for key, expected in (conditions.get("flags") or {}).items():
            if self.player.flags.get(key) != expected:
                return False
        for faction_id, minimum in (conditions.get("reputation_min") or {}).items():
            if self.player.faction_reputation.get(faction_id, 0) < int(minimum):
                return False
        for target_id, minimum in (conditions.get("affinity_min") or {}).items():
            if self.player.affinity_with(target_id) < int(minimum):
                return False
        if conditions.get("requires_spouse") and not self.player.spouse_id:
            return False
        if conditions.get("spouse_ids") and self.player.spouse_id not in conditions["spouse_ids"]:
            return False
        if conditions.get("companions") and not all(self.party.has(x) for x in conditions["companions"]):
            return False
        return True

    def _dialogue_view(self, tree_id: str, node_id: str) -> dict[str, Any]:
        tree = self.story.dialogue(tree_id)
        node = tree.nodes.get(node_id) if tree else None
        if node is None:
            return {"tree_id": tree_id, "node_id": "", "text": "", "options": []}
        options = [
            {"id": option.id, "text": option.text}
            for option in node.options if self._story_conditions_met(option.conditions)
        ]
        return {"tree_id": tree_id, "node_id": node.id, "text": node.text, "options": options}

    def dialogues_for_speaker(self, speaker_id: str) -> list[dict[str, str]]:
        self.story.load()
        return [
            {"id": tree.id, "title": tree.id.replace("_", " ").title()}
            for tree in self.story.dialogues.values() if tree.speaker_id == speaker_id
        ]

    def start_dialogue(self, tree_id: str) -> dict[str, Any]:
        tree = self.story.dialogue(tree_id)
        return self._dialogue_view(tree_id, tree.start_node_id if tree else "")

    def choose_dialogue(self, tree_id: str, option_id: str) -> dict[str, Any]:
        tree = self.story.dialogue(tree_id)
        if tree is None:
            return self._dialogue_view(tree_id, "")
        option = next(
            (o for node in tree.nodes.values() for o in node.options if o.id == option_id), None
        )
        if option is None or not self._story_conditions_met(option.conditions):
            return self._dialogue_view(tree_id, tree.start_node_id)
        for action in option.actions:
            kind = action.get("type")
            if kind == "flag":
                self.player.flags[str(action.get("key"))] = action.get("value", True)
            elif kind == "affinity":
                self.player.change_affinity(str(action.get("target_id")), int(action.get("amount", 0)))
            elif kind == "reputation":
                self.change_reputation(str(action.get("faction_id")), int(action.get("amount", 0)))
            elif kind == "loyalty":
                self.change_loyalty(str(action.get("companion_id")), int(action.get("amount", 0)))
            elif kind == "quest_accept":
                self.accept_quest(str(action.get("quest_id")))
            elif kind == "choice":
                self.quests.record_event(self.player, "choice", str(action.get("choice_id")))
            elif kind == "item":
                self.items.grant(self.player.inventory, str(action.get("item_id")), int(action.get("quantity", 1)))
        return self._dialogue_view(tree_id, option.next_node_id)

    def loyalty_rank(self, companion_id: str) -> str:
        value = self.player.companion_loyalty.get(companion_id, 0) if self.player else 0
        thresholds = (self.config.get("loyalty") or {}).get("thresholds", {})
        rank = "Wary"
        for label, minimum in sorted(thresholds.items(), key=lambda pair: int(pair[1])):
            if value >= int(minimum):
                rank = label
        return rank

    def change_loyalty(self, companion_id: str, amount: int) -> int:
        if not self.player:
            return 0
        value = max(-100, min(100, self.player.companion_loyalty.get(companion_id, 0) + int(amount)))
        self.player.companion_loyalty[companion_id] = value
        member = self.party.get(companion_id)
        if member:
            bonuses = (self.config.get("loyalty") or {}).get("bonuses", {})
            rank = self.loyalty_rank(companion_id)
            member.set_loyalty_bonus(ModifierSet.from_dict(bonuses.get(rank)))
            member.loyalty_title = member.definition.loyalty_titles.get(rank, member.loyalty_title)
            member.outfit_id = member.definition.loyalty_outfits.get(rank, member.outfit_id)
            for skill_id in member.definition.loyalty_skill_ids.get(rank, []):
                skill = self.skills.get(skill_id)
                if skill and all(existing.id != skill.id for existing in member.skills):
                    member.skills.append(skill)
        return value

    def companion_disagrees(self, companion_id: str, severity: int = 25) -> tuple[bool, str]:
        if not self.player or not self.world:
            return False, "No character loaded."
        self.change_loyalty(companion_id, -abs(severity))
        member = self.party.get(companion_id)
        if member is None:
            return False, "They are not travelling with you."
        if severity >= int((self.config.get("loyalty") or {}).get("leave_severity", 75)):
            self.party.dismiss(companion_id)
            days = int((self.config.get("loyalty") or {}).get("leave_days", 3))
            self.player.companion_unavailable_until[companion_id] = self.world.day + days
            return True, f"{member.name} leaves to cool off."
        return True, f"{member.name} strongly disagrees."

    def can_rejoin_companion(self, companion_id: str) -> bool:
        return bool(self.world and self.player and self.world.day >= self.player.companion_unavailable_until.get(companion_id, 0))

    def trigger_banter(self, trigger: str, **context: Any) -> list[str]:
        if not self.player:
            return []
        seen = self.player.flags.setdefault("banter_seen", {})
        for entry in self.story.banter:
            if entry.trigger != trigger or (entry.once and seen.get(entry.id)):
                continue
            cond = entry.conditions
            if cond.get("area_ids") and context.get("area_id") not in cond["area_ids"]:
                continue
            if cond.get("player_race_ids") and self.player.race_id not in cond["player_race_ids"]:
                continue
            if cond.get("player_class_ids") and self.player.class_def.id not in cond["player_class_ids"]:
                continue
            if cond.get("enemy_families") and context.get("enemy_family") not in cond["enemy_families"]:
                continue
            if cond.get("companion_ids") and context.get("companion_id") not in cond["companion_ids"]:
                continue
            if cond.get("companions") and not all(self.party.has(cid) for cid in cond["companions"]):
                continue
            if cond.get("spouse_in_party") and not (self.player.spouse_id and self.party.has(self.player.spouse_id)):
                continue
            seen[entry.id] = True
            # Codex: track banter heard
            self.player.record_achievement("banter_heard", entry.id)
            return list(entry.lines)
        return []

    # ==================================================================
    # Save / load
    # ==================================================================
    def save_slots(self) -> list[SaveSlotInfo]:
        return self.saves.list_slots()

    def to_save_payload(self) -> dict[str, Any]:
        """Serialise the whole session.

        The ``meta`` block duplicates a few player fields on purpose so the
        Save Browser can show a preview without constructing a Player.
        """
        if not self.player or not self.world:
            raise RuntimeError("nothing to save")
        area = self.world.current_area
        return {
            "game_version": GAME_VERSION,
            "meta": {
                "character_name": self.player.name,
                "class_name": self.player.class_def.name,
                "level": self.player.level,
                "day": self.world.day,
                "gold": self.player.inventory.gold,
                "mastery": self.player.mastery.highest_rank(),
                "area_name": area.name if area else "",
                "companions": len(self.party),
            },
            "player": self.player.to_dict(),
            "party": self.party.to_dict(),
            "world": self.world.to_dict(),
            "rng": self.rng.to_dict(),
        }

    def save_game(self, slot: str | None = None) -> tuple[bool, str]:
        if not self.player:
            return False, "No character to save."
        target = slot or self.current_slot or self.saves.suggest_slot(self.player.name)
        try:
            self.saves.write(target, self.to_save_payload())
        except (OSError, RuntimeError) as exc:
            return False, f"Save failed: {exc}"
        self.current_slot = target
        return True, f"Game saved to '{target}'."

    def autosave(self) -> tuple[str, bool]:
        """Morning autosave (bible section 16)."""
        if not self.player:
            return ("", False)
        slot = self.saves.next_autosave_slot(self.player.name)
        ok, _ = self.save_game(slot)
        # An autosave should not hijack the player's chosen manual slot.
        self.current_slot = slot if ok else self.current_slot
        return (slot, ok)

    def load_game(self, slot: str) -> tuple[bool, str]:
        """Restore a session from a slot, rebuilding every live object."""
        payload = self.saves.read(slot)
        if payload is None:
            return False, "That save could not be read."

        player_data = payload.get("player")
        if not isinstance(player_data, Mapping):
            return False, "That save is missing character data."

        class_id = str(player_data.get("class_id", ""))
        definition = self.classes.get(class_id)
        if definition is None:
            return False, f"This save uses class '{class_id}', which no longer exists."

        progression = self.config.get("progression", {})
        default_race_id = str(self.config.get("default_race_id", ""))
        race_id = str(player_data.get("race_id", default_race_id))
        race = self.races.get(race_id) or self.races.get(default_race_id)
        if race is None:
            return False, f"This save uses race '{race_id}', which no longer exists."
        sub_race_id = str(player_data.get("sub_race_id", "") or "")
        player = Player(
            name=str(player_data.get("name", "Hero")),
            gender=str(player_data.get("gender", "male")),
            class_def=definition,
            race_def=race,
            formulas=self.formulas,
            level=int(player_data.get("level", 1)),
            progression=progression,
            equipment_config=self.config,
            enchantments=self.enchantments.definitions,
            sub_race_id=sub_race_id,
        )

        player.class_history = [str(c) for c in player_data.get("class_history", [class_id])]
        player.exp = float(player_data.get("exp", 0.0))
        player.unspent_stat_points = int(player_data.get("unspent_stat_points", 0))
        player.unspent_skill_points = int(player_data.get("unspent_skill_points", 0))
        player.allocated_stats = StatBlock.from_dict(player_data.get("allocated_stats"))

        player.mastery = self._new_mastery_book()
        player.mastery.load_dict(player_data.get("mastery"))

        for skill_id in player_data.get("known_skill_ids", []):
            skill = self.skills.get(skill_id)
            # Skills deleted from content are dropped rather than blocking the
            # load - backwards compatibility over strictness (bible section 5).
            if skill is not None:
                player.known_skills[skill.id] = skill
        player.cooldowns = {str(k): int(v) for k, v in (player_data.get("cooldowns") or {}).items()}

        inventory_data = player_data.get("inventory") or {}
        player.inventory.capacity = int(inventory_data.get("capacity", player.inventory.capacity))
        player.inventory.gold = int(inventory_data.get("gold", 0))
        for entry in inventory_data.get("entries", []):
            item = self.items.get(str(entry.get("id", "")))
            if item is not None:
                player.inventory.add(item, int(entry.get("quantity", 1)))

        for slot_name, item_id in (player_data.get("equipment") or {}).items():
            if slot_name in EQUIPMENT_SLOTS and item_id:
                item = self.items.get(str(item_id))
                if item is not None:
                    player.equipment[slot_name] = item
                    if item.bound_skill_id:
                        skill = self.skills.get(item.bound_skill_id)
                        if skill and skill.id not in player.known_skills:
                            player.known_skills[skill.id] = skill
                            player.equipment_granted_skills.add(skill.id)

        player.affinity = {str(k): int(v) for k, v in (player_data.get("affinity") or {}).items()}
        player.spouse_id = player_data.get("spouse_id")
        player.completed_quests = [str(q) for q in player_data.get("completed_quests", [])]
        player.active_quests = [
            str(q) for q in player_data.get("active_quests", []) if self.quests.get(str(q)) is not None
        ]
        raw_progress = player_data.get("quest_progress") or {}
        player.quest_progress = {
            quest_id: {str(key): int(value) for key, value in (raw_progress.get(quest_id) or {}).items()}
            for quest_id in player.active_quests
        }
        player.faction_reputation = {str(k): int(v) for k, v in (player_data.get("faction_reputation") or {}).items()}
        player.companion_loyalty = {str(k): int(v) for k, v in (player_data.get("companion_loyalty") or {}).items()}
        player.companion_unavailable_until = {str(k): int(v) for k, v in (player_data.get("companion_unavailable_until") or {}).items()}
        player.item_enchantments = {str(k): str(v) for k, v in (player_data.get("item_enchantments") or {}).items()}
        player.item_upgrades = {str(k): int(v) for k, v in (player_data.get("item_upgrades") or {}).items()}
        player.flags = dict(player_data.get("flags") or {})
        player.codex = Codex.from_dict(player_data.get("codex"))

        player._recalculate_base_stats()
        player._restore_common(player_data)

        world = self.world_manager.create_world()
        world.load_dict(payload.get("world"))
        self.rng.load_state(payload.get("rng"))

        self.player = player
        self.party = self._load_party(payload.get("party"), player)
        self.world = world
        self.battle = None
        self.current_slot = slot
        return True, f"Loaded {player.name} (Level {player.level})."

    def _load_party(self, payload: Mapping[str, Any] | None, player: Player) -> Party:
        """Rebuild the party from a save.

        Companions whose definitions no longer exist are dropped rather than
        blocking the load - the same backwards-compatibility stance the rest of
        the loader takes (bible section 5).
        """
        default_max = int((self.config.get("party") or {}).get("max_active", 2))
        if not payload:
            return Party(default_max)

        party = Party(int(payload.get("max_active", default_max)))
        for key, target in (("active", party.active), ("reserve", party.reserve)):
            for entry in payload.get(key, []):
                companion_id = str(entry.get("companion_id", ""))
                if self.companions.get(companion_id) is None:
                    continue
                companion = self.companions.create(companion_id, player.level)
                companion.cooldowns = {str(k): int(v) for k, v in (entry.get("cooldowns") or {}).items()}
                companion.set_tactics(entry.get("tactics") or {})
                loyalty = player.companion_loyalty.get(companion_id, 0)
                thresholds = (self.config.get("loyalty") or {}).get("thresholds", {})
                rank = "Wary"
                for label, minimum in sorted(thresholds.items(), key=lambda pair: int(pair[1])):
                    if loyalty >= int(minimum):
                        rank = label
                companion.set_loyalty_bonus(
                    ModifierSet.from_dict((self.config.get("loyalty") or {}).get("bonuses", {}).get(rank))
                )
                companion.loyalty_title = companion.definition.loyalty_titles.get(rank, "")
                companion.outfit_id = companion.definition.loyalty_outfits.get(rank, "default")
                for skill_id in companion.definition.loyalty_skill_ids.get(rank, []):
                    skill = self.skills.get(skill_id)
                    if skill and all(existing.id != skill.id for existing in companion.skills):
                        companion.skills.append(skill)
                if player.spouse_id == companion_id:
                    companion.set_married_bonus(
                        ModifierSet.from_dict({"flat": self.relationships.spouse_modifiers()})
                    )
                companion._restore_common(entry)
                target.append(companion)
        return party

    def delete_save(self, slot: str) -> tuple[bool, str]:
        if self.saves.delete(slot):
            if self.current_slot == slot:
                self.current_slot = None
            return True, f"Deleted save '{slot}'."
        return False, "That save could not be deleted."
