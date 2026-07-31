"""Race selection, racial traits/items, and companion questline coverage."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.game import Game

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def new_game(save_dir=None) -> Game:
    game = Game(data_dir=PROJECT_ROOT / "data", save_dir=save_dir, seed=6060)
    game.load_content()
    return game


class TestRaceEngine(unittest.TestCase):
    def test_eight_data_driven_races_load(self):
        game = new_game()
        ids = {race.id for race in game.race_options()}
        self.assertEqual(
            ids,
            {"human", "elf", "half_elf", "dwarf", "dragonkin", "demon", "tiefling", "beastkin",
             "orc", "gnome", "halfling", "genasi", "goliath", "lamia", "arachne"},
        )

    def test_character_creation_applies_racial_stats_and_traits(self):
        human = new_game()
        elf = new_game()
        human.create_character("Human", "female", "maiden", "human")
        elf.create_character("Elf", "female", "maiden", "elf")
        self.assertEqual(elf.player.race_id, "elf")
        self.assertGreater(elf.player.base_stats["AGI"], human.player.base_stats["AGI"])
        self.assertGreater(elf.player.max_mp, human.player.max_mp)
        self.assertIn("Race: Elf", elf.player.summary_lines())

    def test_unknown_race_is_rejected(self):
        game = new_game()
        ok, message = game.create_character("Unknown", "male", "squire", "not_a_race")
        self.assertFalse(ok)
        self.assertIn("race", message.lower())

    def test_every_race_works_with_every_eligible_starting_class(self):
        game = new_game()
        for race in game.race_options():
            for gender in game.genders():
                for definition in game.starting_classes(gender):
                    ok, message = game.create_character("Combination", gender, definition.id, race.id)
                    self.assertTrue(ok, (race.id, gender, definition.id, message))
                    self.assertGreater(game.player.max_hp, 0)
                    self.assertGreaterEqual(game.player.max_mp, 0)

    def test_race_specific_item_bonus_only_applies_to_matching_race(self):
        elf = new_game()
        dwarf = new_game()
        elf.create_character("Elf", "female", "maiden", "elf")
        dwarf.create_character("Dwarf", "female", "maiden", "dwarf")
        item = elf.items.require("moonleaf_brooch")
        elf.player.inventory.add(item)
        dwarf.player.inventory.add(item)
        elf.player.equip(item)
        dwarf.player.equip(item)
        self.assertGreater(elf.player.derived_stats().magic_power, dwarf.player.derived_stats().magic_power)

    def test_race_survives_save_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = new_game(tmp)
            game.create_character("Scale", "male", "squire", "dragonkin")
            game.save_game("race")
            restored = new_game(tmp)
            self.assertTrue(restored.load_game("race")[0])
            self.assertEqual(restored.player.race_id, "dragonkin")


class TestRacialWorldContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = new_game()

    def test_companions_mix_races_and_have_more_dialogue(self):
        companions = self.game.companions.all_definitions()
        self.assertEqual(len(companions), 21)
        self.assertGreaterEqual(len({companion.race_id for companion in companions}), 7)
        self.assertTrue(all(len(companion.dialogue) >= 6 for companion in companions))

    def test_companion_racial_traits_apply_in_combat_stats(self):
        definition = self.game.companions.require("brokk_embervein")
        companion = self.game.companions.create(definition.id, 30)
        bare = self.game.formulas.derive(
            definition.stats_at_level(companion.level), companion.level, definition.modifiers
        )
        self.assertGreater(companion.derived_stats().armor, bare.armor)
        self.assertGreater(companion.max_hp, bare.max_hp)

    def test_npcs_mix_races(self):
        world = self.game.world_manager.create_world()
        self.assertGreaterEqual(len(world.npcs), 18)
        self.assertGreaterEqual(len({npc.race_id for npc in world.npcs.values()}), 7)

    def test_racial_items_cross_validate_and_describe_bonuses(self):
        racial_items = [item for item in self.game.items.all_items() if item.race_modifiers]
        self.assertGreaterEqual(len(racial_items), 8)
        for item in racial_items:
            lines = item.detail_lines()
            self.assertTrue(any("racial bonus" in line.lower() for line in lines), item.id)
        world = self.game.world_manager.create_world()
        sold = {item_id for shop in world.shops.values() for item_id in shop.item_ids}
        rewarded = {
            item_id
            for quest in self.game.quests.all_definitions()
            for item_id in quest.rewards.items
        }
        self.assertEqual({item.id for item in racial_items} - sold - rewarded, set())


class TestCompanionQuestlines(unittest.TestCase):
    def setUp(self):
        self.game = new_game()
        self.game.create_character("Story", "female", "maiden", "half_elf")
        self.game.player.level = 25
        self.game.player._recalculate_base_stats()

    def test_four_two_part_companion_questlines_exist(self):
        expected = {
            "lethira_roots", "lethira_remembers", "brokk_resonance", "brokk_deep_song",
            "veyra_debt", "veyra_unbound", "rhazek_oath", "rhazek_first_light",
        }
        self.assertTrue(expected <= {quest.id for quest in self.game.quests.all_definitions()})
        for prefix in ("lethira", "brokk", "veyra", "rhazek"):
            self.assertEqual(len([quest for quest in expected if quest.startswith(prefix)]), 2)

    def test_intro_quest_is_offered_by_unrecruited_companion_at_home(self):
        quest = self.game.quests.require("lethira_roots")
        self.game.world.current_area_id = quest.start_area_id
        offered = {entry.id for entry in self.game.quests_from("lethira_vale")}
        self.assertIn(quest.id, offered)

    def test_intro_quest_unlocks_recruitment(self):
        quest = self.game.quests.require("lethira_roots")
        self.game.world.current_area_id = quest.start_area_id
        self.game.player.level = max(self.game.player.level, quest.min_level)
        self.assertTrue(self.game.accept_quest(quest.id)[0])
        target = quest.objectives[0].target_id
        self.game.quests.record_defeats(self.game.player, [target] * quest.objectives[0].quantity)
        self.assertTrue(self.game.complete_quest(quest.id)[0])
        self.game.player.affinity["lethira_vale"] = 100
        self.game.player.inventory.add_gold(99999)
        self.assertTrue(self.game.check_recruit("lethira_vale")[0])

    def test_second_quest_requires_companion_to_be_recruited(self):
        first = self.game.quests.require("lethira_roots")
        second = self.game.quests.require("lethira_remembers")
        self.game.player.complete_quest(first.id)
        self.game.player.level = max(self.game.player.level, second.min_level)
        self.game.world.current_area_id = second.start_area_id or "town_emberwatch"
        self.assertNotIn(second.id, {quest.id for quest in self.game.available_quests()})
        companion = self.game.companions.create("lethira_vale", self.game.player.level)
        self.game.party.recruit(companion)
        self.assertIn(second.id, {quest.id for quest in self.game.available_quests()})


if __name__ == "__main__":
    unittest.main(verbosity=2)
