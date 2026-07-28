"""Quest manager, progression, persistence, and promotion-loot coverage."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.game import Game
from engine.managers.data_loader import ContentError, DataLoader
from engine.managers.quest_manager import QuestManager

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def new_game(save_dir: str | Path | None = None) -> Game:
    game = Game(data_dir=PROJECT_ROOT / "data", save_dir=save_dir, seed=2026)
    game.load_content()
    game.create_character("Quest Hero", "male", "squire")
    return game


class TestQuestContent(unittest.TestCase):
    def test_every_promotion_quest_resolves(self):
        game = new_game()
        referenced = {
            quest_id
            for definition in game.classes.all_classes()
            for requirement in definition.promotions.values()
            for quest_id in requirement.quests
        }
        self.assertEqual(len(referenced), 10)
        self.assertTrue(all(game.quests.get(quest_id) is not None for quest_id in referenced))

    def test_quest_count_is_reported(self):
        game = new_game()
        self.assertIn("Quests: 18", game.content_summary())

    def test_unsupported_objective_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "quests.json").write_text(
                json.dumps(
                    {
                        "quests": [
                            {
                                "id": "bad",
                                "objectives": [{"kind": "unknown", "target_id": "x"}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ContentError, "unsupported objective"):
                QuestManager(DataLoader(tmp)).load()

    def test_prerequisite_cycle_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "quests.json").write_text(
                json.dumps(
                    {
                        "quests": [
                            {
                                "id": "a",
                                "prerequisite_quest_ids": ["b"],
                                "objectives": [{"kind": "defeat_enemy", "target_id": "x"}],
                            },
                            {
                                "id": "b",
                                "prerequisite_quest_ids": ["a"],
                                "objectives": [{"kind": "defeat_enemy", "target_id": "x"}],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ContentError, "cycle"):
                QuestManager(DataLoader(tmp)).load()


class TestQuestProgression(unittest.TestCase):
    def setUp(self):
        self.game = new_game()
        self.player = self.game.player
        self.player.class_def = self.game.classes.require("paladin")
        self.player.level = 35
        self.player._recalculate_base_stats()
        definition = self.game.quests.require("trial_of_the_dawn")
        self.objective = definition.objectives[0]
        self.game.world.current_area_id = definition.start_area_id

    def test_level_and_class_gate_availability(self):
        ids = {quest.id for quest in self.game.available_quests()}
        self.assertIn("trial_of_the_dawn", ids)
        self.assertNotIn("the_silent_contract", ids)
        self.assertNotIn("the_unwritten_page", ids)

    def test_quest_requires_its_giver_location(self):
        self.game.world.current_area_id = "town_ashvale"
        self.assertNotIn("trial_of_the_dawn", {quest.id for quest in self.game.available_quests()})
        self.assertFalse(self.game.accept_quest("trial_of_the_dawn")[0])

    def test_quests_from_returns_only_that_npcs_offers(self):
        offered = {quest.id for quest in self.game.quests_from("reeve_marta")}
        self.assertEqual(offered, {"trial_of_the_dawn"})
        self.assertEqual(self.game.quests_from("miner_joss"), [])

    def test_accept_quest_once(self):
        ok, _ = self.game.accept_quest("trial_of_the_dawn")
        self.assertTrue(ok)
        self.assertFalse(self.game.accept_quest("trial_of_the_dawn")[0])
        self.assertEqual(self.player.active_quests, ["trial_of_the_dawn"])

    def test_defeat_event_advances_and_clamps_progress(self):
        self.game.accept_quest("trial_of_the_dawn")
        self.game.quests.record_defeats(self.player, [self.objective.target_id, self.objective.target_id])
        definition = self.game.quests.require("trial_of_the_dawn")
        self.assertEqual(self.player.quest_progress_value(definition.id, definition.objectives[0].key), 1)

    def test_unrelated_defeat_does_not_advance(self):
        self.game.accept_quest("trial_of_the_dawn")
        self.assertEqual(self.game.quests.record_defeats(self.player, ["bandit_chief"]), [])

    def test_finished_victory_records_defeated_enemies(self):
        self.game.accept_quest("trial_of_the_dawn")
        self.player.allocated_stats["STR"] = 1000
        self.player.allocated_stats["END"] = 1000
        self.player._recalculate_base_stats()
        self.player.restore_fully()
        battle = self.game.start_battle([(self.objective.target_id, 34)])
        for _ in range(300):
            if battle.is_over:
                break
            if battle.waiting_for_player:
                battle.player_attack(battle.living_enemies[0])
            battle.run_until_player_turn()
        self.assertTrue(battle.is_over)
        self.game.finish_battle()
        ready, _ = self.game.quest_completion_check("trial_of_the_dawn")
        self.assertTrue(ready)
        self.assertIn(self.objective.target_id, self.game.world.defeated_bosses)

    def test_cannot_complete_before_objective(self):
        self.game.accept_quest("trial_of_the_dawn")
        ok, lines = self.game.complete_quest("trial_of_the_dawn")
        self.assertFalse(ok)
        self.assertIn("0/1", lines[0])

    def test_turn_in_requires_returning_to_quest_giver_town(self):
        definition = self.game.quests.require("trial_of_the_dawn")
        self.game.accept_quest(definition.id)
        self.game.quests.record_defeats(self.player, [self.objective.target_id])
        self.game.world.current_area_id = "crystal_mines"
        ok, lines = self.game.complete_quest(definition.id)
        self.assertFalse(ok)
        self.assertIn("Stonehaven", lines[0])
        self.game.world.current_area_id = definition.turn_in_area_id
        self.assertTrue(self.game.complete_quest(definition.id)[0])

    def test_previously_defeated_boss_counts_when_quest_is_accepted(self):
        definition = self.game.quests.require("trial_of_the_dawn")
        self.game.world.defeated_bosses.add(self.objective.target_id)
        self.assertTrue(self.game.accept_quest(definition.id)[0])
        self.assertTrue(self.game.quest_completion_check(definition.id)[0])

    def test_complete_quest_grants_rewards_and_calls_player_flow(self):
        definition = self.game.quests.require("trial_of_the_dawn")
        self.game.accept_quest(definition.id)
        self.game.quests.record_defeats(self.player, [self.objective.target_id])
        gold_before = self.player.inventory.gold

        ok, lines = self.game.complete_quest(definition.id)

        self.assertTrue(ok, lines)
        self.assertIn(definition.id, self.player.completed_quests)
        self.assertNotIn(definition.id, self.player.active_quests)
        self.assertGreater(self.player.inventory.gold, gold_before)
        self.assertFalse(self.game.complete_quest(definition.id)[0])

    def test_prerequisite_and_new_class_unlock_next_quest(self):
        self.player.complete_quest("trial_of_the_dawn")
        self.player.class_def = self.game.classes.require("templar")
        self.player.level = 50
        ids = {quest.id for quest in self.game.available_quests()}
        self.assertIn("the_last_bastion", ids)

    def test_active_progress_survives_save_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = new_game(tmp)
            game.player.class_def = game.classes.require("paladin")
            game.player.level = 35
            game.player._recalculate_base_stats()
            game.world.current_area_id = game.quests.require("trial_of_the_dawn").start_area_id
            game.accept_quest("trial_of_the_dawn")
            objective = game.quests.require("trial_of_the_dawn").objectives[0]
            game.quests.record_defeats(game.player, [objective.target_id])
            game.save_game("quest-test")

            restored = new_game(tmp)
            ok, _ = restored.load_game("quest-test")
            self.assertTrue(ok)
            self.assertEqual(restored.player.active_quests, ["trial_of_the_dawn"])
            self.assertEqual(
                restored.player.quest_progress["trial_of_the_dawn"][objective.key],
                1,
            )


class TestPromotionItemLoot(unittest.TestCase):
    def test_bandit_chief_drops_all_tier_three_items(self):
        game = new_game()
        enemy = game.enemies.spawn("bandit_chief")
        drops = dict(enemy.roll_loot(game.rng))
        item_ids = {"oath_sigil", "shadow_pact", "grimoire_of_ages"}
        self.assertTrue(item_ids <= drops.keys())
        self.assertTrue(all(game.items.require(item_id).stackable for item_id in item_ids))

    def test_regional_bosses_drop_upper_promotion_items(self):
        game = new_game()
        expected = {
            "iron_colossus": "sacred_relic",
            "mire_oracle": "void_shard",
            "dawn_tyrant": "codex_infinite",
        }
        for enemy_id, item_id in expected.items():
            drops = dict(game.enemies.spawn(enemy_id).roll_loot(game.rng))
            self.assertEqual(drops.get(item_id), 3)
            self.assertTrue(game.items.require(item_id).stackable)


if __name__ == "__main__":
    unittest.main(verbosity=2)
