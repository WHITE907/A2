"""Coverage for the level-40 world/content expansion."""

from __future__ import annotations

import json
import unittest
from collections import deque
from pathlib import Path

from engine.game import Game
from engine.skills.skill import SkillCategory

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def loaded_game() -> Game:
    game = Game(data_dir=PROJECT_ROOT / "data", seed=4040)
    game.load_content()
    return game


class TestExpandedWorld(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = loaded_game()
        cls.world = cls.game.world_manager.create_world()

    def test_content_reaches_level_40(self):
        self.assertEqual(max(area.recommended_level for area in self.world.areas.values()), 40)
        self.assertEqual(max(enemy.base_level for enemy in self.game.enemies.all_templates()), 40)

    def test_world_has_four_towns_and_seventeen_areas(self):
        towns = [area for area in self.world.areas.values() if area.is_town]
        self.assertEqual(len(self.world.areas), 17)
        self.assertEqual(len(towns), 4)

    def test_every_connection_is_reciprocal(self):
        for area in self.world.areas.values():
            for target_id in area.connections:
                self.assertIn(area.id, self.world.areas[target_id].connections)

    def test_every_area_is_reachable_from_ashvale_at_level_40(self):
        seen = {self.world.current_area_id}
        pending = deque([self.world.current_area_id])
        while pending:
            area_id = pending.popleft()
            for target_id in self.world.areas[area_id].connections:
                if target_id not in seen and self.world.areas[target_id].unlock_level <= 40:
                    seen.add(target_id)
                    pending.append(target_id)
        self.assertEqual(seen, set(self.world.areas))

    def test_new_towns_are_populated(self):
        for town_id in ("town_emberwatch", "town_stonehaven", "town_skyreach"):
            area = self.world.areas[town_id]
            self.assertGreaterEqual(len(area.shop_ids), 2)
            self.assertGreaterEqual(len(area.npc_ids), 3)
            self.assertGreaterEqual(len(self.game.companions.at_location(town_id)), 2)

    def test_wilderness_areas_have_varied_encounters(self):
        for area in self.world.areas.values():
            if not area.is_town:
                self.assertGreaterEqual(len(area.encounters), 3, area.id)
        families = {enemy.family for enemy in self.game.enemies.all_templates() if enemy.base_level >= 16}
        self.assertGreaterEqual(len(families), 8)

    def test_each_upper_level_band_has_a_boss(self):
        bosses = {enemy.id: enemy.base_level for enemy in self.game.enemies.all_templates() if enemy.is_boss}
        self.assertEqual(bosses["mire_oracle"], 27)
        self.assertEqual(bosses["iron_colossus"], 34)
        self.assertEqual(bosses["dawn_tyrant"], 40)
        for area in self.world.areas.values():
            for encounter in area.encounters:
                if encounter.is_boss:
                    self.assertIn(encounter.boss_id, encounter.enemy_ids)

    def test_defeated_boss_is_removed_from_random_encounters(self):
        self.world.current_area_id = "obsidian_gate"
        area = self.world.current_area
        original_quiet = area.quiet_chance
        area.quiet_chance = 0.0
        self.world.defeated_bosses.add("dawn_tyrant")
        try:
            results = [self.world.explore(self.game.rng, 40) for _ in range(80)]
        finally:
            area.quiet_chance = original_quiet
        spawned = {enemy_id for result in results for enemy_id, _ in result.spawns}
        self.assertNotIn("dawn_tyrant", spawned)
        self.assertTrue(spawned)

    def test_defeated_bosses_round_trip_with_world_state(self):
        self.world.defeated_bosses = {"mire_oracle", "iron_colossus"}
        restored = self.game.world_manager.create_world()
        restored.load_dict(self.world.to_dict())
        self.assertEqual(restored.defeated_bosses, self.world.defeated_bosses)


class TestExpandedContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = loaded_game()

    def test_new_content_volume(self):
        self.assertEqual(self.game.enemies.count(), 30)
        self.assertEqual(self.game.skills.count(), 70)
        self.assertEqual(self.game.items.count(), 112)
        self.assertEqual(self.game.companions.count(), 21)

    def test_new_passives_are_learnable_from_class_trees(self):
        expected = {
            "paladin": "guardian_resolve",
            "assassin": "predatory_focus",
            "archmage": "ley_attunement",
        }
        for class_id, skill_id in expected.items():
            definition = self.game.classes.require(class_id)
            self.assertIn(skill_id, definition.skill_tree_ids)
            self.assertEqual(self.game.skills.require(skill_id).category, SkillCategory.PASSIVE)

    def test_equipment_covers_multiple_slots_and_level_bands(self):
        equipment = [item for item in self.game.items.all_items() if item.is_equipment and item.required_level >= 18]
        self.assertGreaterEqual(len(equipment), 25)
        self.assertTrue({18, 28, 35, 40} <= {item.required_level for item in equipment})
        self.assertGreaterEqual(len({item.slot for item in equipment}), 7)
        self.assertGreaterEqual(len({item.weapon_type for item in equipment if item.weapon_type}), 6)
        shop_items = {
            item_id
            for shop in self.game.world_manager.create_world().shops.values()
            for item_id in shop.item_ids
        }
        legendary = {"dawnblade", "sunplate", "dawn_signet"}
        self.assertFalse(legendary & shop_items)
        dawn_loot = {entry.item_id for entry in self.game.enemies.get_template("dawn_tyrant").loot}
        self.assertTrue(legendary <= dawn_loot)

    def test_all_new_materials_are_obtainable_from_enemies(self):
        dropped = {
            entry.item_id
            for enemy in self.game.enemies.all_templates()
            for entry in enemy.loot
        }
        materials = {
            item.id
            for item in self.game.items.all_items()
            if item.kind == "material" and item.value >= 120
        }
        self.assertTrue(materials)
        self.assertEqual(materials - dropped, set())

    def test_normal_encounter_exp_pacing_stays_in_measured_band(self):
        game = self.game
        game.create_character("Balance", "male", "squire")
        for area_id in (
            "emberwatch_road", "mosswood", "glassmarsh", "drowned_archive",
            "red_pass", "crystal_mines", "storm_plateau", "cloud_ruins", "obsidian_gate",
        ):
            area = game.world_manager.get_area(area_id)
            weighted: list[tuple[float, float]] = []
            for encounter in area.encounters:
                if encounter.is_boss:
                    continue
                reward = sum(game.enemies.get_template(enemy_id).exp_reward for enemy_id in encounter.enemy_ids)
                weighted.append((encounter.weight, reward))
            average = sum(weight * reward for weight, reward in weighted) / sum(
                weight for weight, _ in weighted
            )
            game.player.level = area.recommended_level
            fights = game.player.exp_to_next_level() / average
            self.assertGreaterEqual(fights, 2.5, area_id)
            self.assertLessEqual(fights, 6.0, area_id)

    def test_level_35_quests_use_regional_bosses(self):
        targets = {
            self.game.quests.require(quest_id).objectives[0].target_id
            for quest_id in ("trial_of_the_dawn", "the_silent_contract", "the_unwritten_page")
        }
        self.assertEqual(targets, {"iron_colossus", "mire_oracle", "dawn_tyrant"})

    def test_json_world_has_more_flavour_lines(self):
        payload = json.loads((PROJECT_ROOT / "data" / "world.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(payload["flavour"]), 14)


if __name__ == "__main__":
    unittest.main(verbosity=2)
