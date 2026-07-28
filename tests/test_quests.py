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
        self.assertIn("Quests: 10", game.content_summary())

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

    def test_level_and_class_gate_availability(self):
        ids = {quest.id for quest in self.game.available_quests()}
        self.assertEqual(ids, {"trial_of_the_dawn"})

    def test_accept_quest_once(self):
        ok, _ = self.game.accept_quest("trial_of_the_dawn")
        self.assertTrue(ok)
        self.assertFalse(self.game.accept_quest("trial_of_the_dawn")[0])
        self.assertEqual(self.player.active_quests, ["trial_of_the_dawn"])

    def test_defeat_event_advances_and_clamps_progress(self):
        self.game.accept_quest("trial_of_the_dawn")
        self.game.quests.record_defeats(self.player, ["shadow_warden", "shadow_warden"])
        definition = self.game.quests.require("trial_of_the_dawn")
        self.assertEqual(self.player.quest_progress_value(definition.id, definition.objectives[0].key), 1)

    def test_unrelated_defeat_does_not_advance(self):
        self.game.accept_quest("trial_of_the_dawn")
        self.assertEqual(self.game.quests.record_defeats(self.player, ["bandit_chief"]), [])

    def test_finished_victory_records_defeated_enemies(self):
        self.game.accept_quest("trial_of_the_dawn")
        battle = self.game.start_battle([("shadow_warden", 15)])
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

    def test_cannot_complete_before_objective(self):
        self.game.accept_quest("trial_of_the_dawn")
        ok, lines = self.game.complete_quest("trial_of_the_dawn")
        self.assertFalse(ok)
        self.assertIn("0/1", lines[0])

    def test_complete_quest_grants_rewards_and_calls_player_flow(self):
        definition = self.game.quests.require("trial_of_the_dawn")
        self.game.accept_quest(definition.id)
        self.game.quests.record_defeats(self.player, ["shadow_warden"])
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
            game.accept_quest("trial_of_the_dawn")
            game.quests.record_defeats(game.player, ["shadow_warden"])
            game.save_game("quest-test")

            restored = new_game(tmp)
            ok, _ = restored.load_game("quest-test")
            self.assertTrue(ok)
            self.assertEqual(restored.player.active_quests, ["trial_of_the_dawn"])
            self.assertEqual(
                restored.player.quest_progress["trial_of_the_dawn"]["defeat_enemy:shadow_warden"],
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

    def test_shadow_warden_drops_all_upper_promotion_items(self):
        game = new_game()
        enemy = game.enemies.spawn("shadow_warden")
        drops = dict(enemy.roll_loot(game.rng))
        item_ids = {"sacred_relic", "void_shard", "codex_infinite"}
        self.assertTrue(item_ids <= drops.keys())
        self.assertTrue(all(game.items.require(item_id).stackable for item_id in item_ids))


if __name__ == "__main__":
    unittest.main(verbosity=2)
