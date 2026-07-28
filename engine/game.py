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
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine.classes import ClassDefinition
from engine.combat.ai import default_registry
from engine.combat.combat import Battle, CombatState
from engine.entities.companion import Companion
from engine.entities.player import Player
from engine.items.item import EQUIPMENT_SLOTS, Item
from engine.managers.class_manager import ClassManager
from engine.managers.companion_manager import CompanionManager
from engine.managers.data_loader import ContentError, DataLoader
from engine.managers.enemy_manager import EnemyManager
from engine.managers.item_manager import ItemManager
from engine.managers.save_manager import SaveManager, SaveSlotInfo
from engine.managers.skill_manager import SkillManager
from engine.managers.world_manager import WorldManager
from engine.mastery import MasteryBook
from engine.party import Party
from engine.relationships import MarriageCheck, RelationshipRules
from engine.rng import GameRandom
from engine.stats import Formulas, ModifierSet, StatBlock
from engine.world.world import WorldState

#: Re-exported so GUI screens can type-annotate what :meth:`Game.save_slots`
#: returns without importing from ``engine.managers`` - the facade stays the
#: single seam between the UI and the engine (bible section 5/18).
__all__ = ["Game", "GAME_VERSION", "SaveSlotInfo"]

#: Shown on the main menu under the title (per the GUI style reference).
GAME_VERSION = "0.2.0"


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
        self.enemies = EnemyManager(self.loader, self.skills, self.formulas)
        self.companions = CompanionManager(self.loader, self.skills, self.formulas)
        self.world_manager = WorldManager(self.loader)
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
        self.enemies.load()
        self.companions.load()
        self.world_manager.load()
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

        for companion in self.companions.all_definitions():
            for skill_id in companion.skill_ids:
                if self.skills.get(skill_id) is None:
                    problems.append(f"companion {companion.id!r} references unknown skill {skill_id!r}")
            for item_id in companion.recruit.items:
                if self.items.get(item_id) is None:
                    problems.append(f"companion {companion.id!r} needs unknown item {item_id!r}")
            for item_id in companion.gift_item_ids:
                if self.items.get(item_id) is None:
                    problems.append(f"companion {companion.id!r} likes unknown gift {item_id!r}")
            if companion.location_id and self.world_manager.get_area(companion.location_id) is None:
                problems.append(
                    f"companion {companion.id!r} is in unknown area {companion.location_id!r}"
                )

        for area in self.world_manager.all_areas():
            for encounter in area.encounters:
                for enemy_id in encounter.enemy_ids:
                    if self.enemies.get_template(enemy_id) is None:
                        problems.append(f"area {area.id!r} spawns unknown enemy {enemy_id!r}")

        for shop_id in {s for a in self.world_manager.all_areas() for s in a.shop_ids}:
            shop = self.world_manager.get_shop(shop_id)
            if shop is None:
                continue
            for item_id in shop.item_ids:
                if self.items.get(item_id) is None:
                    problems.append(f"shop {shop_id!r} sells unknown item {item_id!r}")

        if problems:
            raise ContentError("content validation failed:\n  - " + "\n  - ".join(problems))

    def content_summary(self) -> list[str]:
        """Counts for the launcher's diagnostics panel."""
        return [
            f"Classes: {self.classes.count()}",
            f"Skills: {self.skills.count()}",
            f"Items: {self.items.count()}",
            f"Enemies: {self.enemies.count()}",
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

    def create_character(self, name: str, gender: str, class_id: str) -> tuple[bool, str]:
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

        progression = self.config.get("progression", {})
        player = Player(
            name=name,
            gender=gender,
            class_def=definition,
            formulas=self.formulas,
            level=int(progression.get("starting_level", 1)),
            progression=progression,
        )
        player.mastery = self._new_mastery_book()

        for skill in self.classes.create_starting_kit(definition, player.level):
            player.learn_skill(skill, spend_points=False)

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
        return True, f"{name} the {definition.name} begins their ascension."

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
        return self.player.equip(item)

    def unequip_slot(self, slot: str) -> tuple[bool, str]:
        if not self.player:
            return False, "No character loaded."
        return self.player.unequip(slot)

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
        return self.player.learn_skill(skill)

    # ==================================================================
    # Promotion
    # ==================================================================
    def promotion_options(self) -> list[Any]:
        return self.classes.available_promotions(self.player) if self.player else []

    def promote(self, target_class_id: str) -> tuple[bool, list[str]]:
        if not self.player:
            return False, ["No character loaded."]
        return self.classes.promote(self.player, target_class_id)

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
        return self.world.travel_to(area_id, self.player.level)

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
        elif battle.state is CombatState.DEFEAT:
            lines.extend(self.handle_death())

        self.battle = None
        # Companions earn affinity for fighting beside you.
        if battle.state is CombatState.VICTORY and self.player:
            for companion in self.party.active:
                self.player.change_affinity(companion.id, self.relationships.per_battle)
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
        return True, lines

    def shop_stock(self, shop_id: str) -> list[Item]:
        shop = self.world_manager.get_shop(shop_id)
        if shop is None:
            return []
        return [item for item in (self.items.get(i) for i in shop.item_ids) if item is not None]

    def buy_item(self, shop_id: str, item_id: str) -> tuple[bool, str]:
        if not self.player:
            return False, "No character loaded."
        shop = self.world_manager.get_shop(shop_id)
        item = self.items.get(item_id)
        if shop is None or item is None or item_id not in shop.item_ids:
            return False, "That item is not for sale here."
        price = max(1, int(item.value * shop.buy_rate))
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
        return ok, message

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
        player = Player(
            name=str(player_data.get("name", "Hero")),
            gender=str(player_data.get("gender", "male")),
            class_def=definition,
            formulas=self.formulas,
            level=int(player_data.get("level", 1)),
            progression=progression,
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

        player.affinity = {str(k): int(v) for k, v in (player_data.get("affinity") or {}).items()}
        player.spouse_id = player_data.get("spouse_id")
        player.completed_quests = [str(q) for q in player_data.get("completed_quests", [])]
        player.flags = dict(player_data.get("flags") or {})

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
