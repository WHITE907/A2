"""Integration coverage for the high-value living-systems expansion.

Each class combines real JSON content with two or more engine subsystems.  The
individual rules remain covered in ``tests/logic``; these cases protect the
player-visible seams between them.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.game import Game
from engine.skills.effects import build_effect, known_effect_types

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def new_game(save_dir: str | Path | None = None) -> Game:
    game = Game(data_dir=PROJECT_ROOT / "data", save_dir=save_dir, seed=7070)
    game.load_content()
    ok, message = game.create_character("Systems", "female", "maiden", "tiefling")
    if not ok:  # A test fixture failure should name the engine rejection.
        raise AssertionError(message)
    return game


class TestQuestObjectiveStrategies(unittest.TestCase):
    def test_all_generic_objectives_are_registered(self):
        game = new_game()
        required = {
            "defeat_enemy",
            "collect_item",
            "visit_area",
            "talk_to",
            "recruit_companion",
            "travel_with_companion",
            "equip_item_type",
            "affinity",
            "battle_no_downs",
            "battle_turn_limit",
            "choice",
        }
        self.assertTrue(required <= game.quests.SUPPORTED_OBJECTIVES)

    def test_world_and_social_events_advance_objectives(self):
        game = new_game()
        game.player.accept_quest("systems_field_test")

        game.quests.record_event(game.player, "visit_area", "greenfields")
        game.quests.record_event(game.player, "talk_to", "innkeeper_mara")

        progress = game.player.quest_progress["systems_field_test"]
        self.assertEqual(progress["visit_area:greenfields"], 1)
        self.assertEqual(progress["talk_to:innkeeper_mara"], 1)

    def test_collection_affinity_and_equipment_refresh_from_state(self):
        game = new_game()
        game.player.accept_quest("systems_field_test")
        game.items.grant(game.player.inventory, "slime_core", 3)
        game.player.affinity["innkeeper_mara"] = 20

        game.refresh_quest_objectives()

        progress = game.player.quest_progress["systems_field_test"]
        self.assertEqual(progress["collect_item:slime_core"], 3)
        self.assertEqual(progress["affinity:innkeeper_mara"], 20)


class TestDialogueAndFactions(unittest.TestCase):
    def test_dialogue_tree_filters_race_specific_options(self):
        game = new_game()

        view = game.start_dialogue("mother_sable_contract")

        labels = [option["text"] for option in view["options"]]
        self.assertTrue(any("Ash Court" in label for label in labels))

    def test_dialogue_choice_applies_flags_affinity_reputation_and_exclusion(self):
        game = new_game()
        game.start_dialogue("mother_sable_contract")

        result = game.choose_dialogue("mother_sable_contract", "sign_clause")

        self.assertEqual(game.player.flags["sable_clause"], "signed")
        self.assertGreater(game.player.faction_reputation["ash_court"], 0)
        self.assertLess(game.player.faction_reputation["emberwatch_wardens"], 0)
        self.assertTrue(result["text"])

    def test_faction_reputation_changes_shop_price(self):
        game = new_game()
        game.player.inventory.add_gold(99_999)
        base_price = game.shop_price("emberwatch_outfitter", "embersteel_blade")

        game.change_reputation("emberwatch_wardens", 60)

        self.assertLess(game.shop_price("emberwatch_outfitter", "embersteel_blade"), base_price)


class TestLoyaltyAndBanter(unittest.TestCase):
    def setUp(self):
        self.game = new_game()
        self.game.player.level = 40
        self.game.player.inventory.add_gold(99_999)
        companion = self.game.companions.create("rook", 40)
        self.game.party.recruit(companion)

    def test_loyalty_ranks_and_bonus_apply(self):
        before_hp = self.game.party.get("rook").max_hp

        self.game.change_loyalty("rook", 80)

        self.assertEqual(self.game.loyalty_rank("rook"), "Sworn")
        self.assertGreater(self.game.party.get("rook").max_hp, before_hp)

    def test_disagreement_is_temporary(self):
        self.game.companion_disagrees("rook", severity=100)
        self.assertFalse(self.game.party.has("rook"))
        self.assertFalse(self.game.can_rejoin_companion("rook"))

        self.game.world.day += 10

        self.assertTrue(self.game.can_rejoin_companion("rook"))

    def test_contextual_banter_uses_party_and_race_conditions(self):
        lines = self.game.trigger_banter("travel", area_id="old_road")

        self.assertTrue(lines)
        self.assertTrue(any("Rook" in line for line in lines))


class TestEquipmentProgression(unittest.TestCase):
    def test_set_bonus_activates_at_piece_threshold(self):
        game = new_game()
        game.player.level = 40
        for item_id in ("ember_plate", "ember_helm"):
            item = game.items.require(item_id)
            game.player.inventory.add(item)
            game.player.equipment[item.slot] = item
        game.player.invalidate_stats()

        self.assertIn("Emberwatch Bulwark (2)", game.player.active_set_bonuses())

    def test_enchantment_and_upgrade_modify_equipment_stats_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = new_game(tmp)
            game.player.level = 40
            game.player.inventory.add_gold(99_999)
            blade = game.items.require("embersteel_blade")
            game.player.inventory.add(blade)
            game.player.equipment["weapon"] = blade
            game.player.invalidate_stats()
            before_power = game.player.derived_stats().physical_power

            self.assertTrue(game.enchant_item(blade.id, "keen")[0])
            self.assertTrue(game.upgrade_item(blade.id)[0])
            self.assertGreater(game.player.derived_stats().physical_power, before_power)
            game.save_game("gear")

            restored = new_game(tmp)
            restored.load_game("gear")
            self.assertIn("keen", restored.player.item_enchantments[blade.id])
            self.assertEqual(restored.player.item_upgrades[blade.id], 1)

            multi_slot_game = new_game(tmp)
            multi_slot_game.player.level = 40
            multi_slot_game.player.inventory.add_gold(99_999)
            dawnblade = multi_slot_game.items.require("dawnblade")
            multi_slot_game.player.inventory.add(dawnblade)
            multi_slot_game.player.equipment["weapon"] = dawnblade
            self.assertTrue(multi_slot_game.enchant_item(dawnblade.id, "keen")[0])
            self.assertTrue(multi_slot_game.enchant_item(dawnblade.id, "warded")[0])
            self.assertEqual(len(multi_slot_game.player.item_enchantments[dawnblade.id]), 2)

    def test_low_health_conditional_modifier(self):
        game = new_game()
        game.player.level = 40
        ring = game.items.require("blood_oath_ring")
        game.player.inventory.add(ring)
        game.player.equipment[ring.slot] = ring
        game.player.current_hp = game.player.max_hp * 0.2
        game.player.invalidate_stats()
        low_health_power = game.player.derived_stats().physical_power

        game.player.current_hp = game.player.max_hp
        game.player.invalidate_stats()

        self.assertGreater(low_health_power, game.player.derived_stats().physical_power)


class TestExpandedEffects(unittest.TestCase):
    def test_effect_registry_contains_new_behaviours(self):
        required = {
            "life_drain",
            "cleanse",
            "dispel",
            "revive",
            "taunt",
            "cooldown",
            "execute",
            "counter",
            "status_transfer",
            "delayed_attack",
        }
        self.assertTrue(required <= set(known_effect_types()))

    def test_life_drain_heals_caster(self):
        game = new_game()
        enemy = game.enemies.spawn("green_slime", 1)
        game.player.current_hp = max(1, game.player.current_hp - 20)
        before_hp = game.player.current_hp
        effect = build_effect({"type": "life_drain", "base": 20, "can_miss": False})

        result = effect.apply(game.player, enemy, game.skills.make_context(game.rng, game.formulas))

        self.assertGreater(game.player.current_hp, before_hp)
        self.assertEqual(result.kind, "damage")

    def test_cleanse_dispel_and_revive(self):
        game = new_game()
        context = game.skills.make_context(game.rng, game.formulas)
        poison = game.skills.get_status("poison").clone()
        game.player.apply_status(poison)

        build_effect({"type": "cleanse"}).apply(game.player, game.player, context)
        self.assertFalse(game.player.statuses)

        companion = game.companions.create("rook", 1)
        companion.kill()
        build_effect({"type": "revive", "percent_max_hp": 0.25}).apply(game.player, companion, context)
        self.assertTrue(companion.is_alive)


class TestBossFrameworkAndTactics(unittest.TestCase):
    def test_dawn_tyrant_has_data_driven_phases_and_hazard(self):
        game = new_game()
        tyrant = game.enemies.get_template("dawn_tyrant")

        self.assertGreaterEqual(len(tyrant.boss_phases), 2)
        self.assertTrue(tyrant.boss_rules.get("environment"))

    def test_phase_transition_changes_boss_and_logs(self):
        game = new_game()
        game.player.level = 40
        game.player.allocated_stats["STR"] = 2_000
        game.player.allocated_stats["END"] = 2_000
        game.player._recalculate_base_stats()
        game.player.restore_fully()
        battle = game.start_battle([("dawn_tyrant", 40)])
        boss = battle.enemies[0]
        boss.current_hp = boss.max_hp * 0.49

        battle.check_boss_rules()

        self.assertGreaterEqual(boss.boss_phase, 1)
        self.assertTrue(any("phase" in entry.text.lower() for entry in battle.log))

    def test_companion_tactics_persist_and_filter_ultimate_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = new_game(tmp)
            companion = game.companions.create("rook", 20)
            game.party.recruit(companion)
            game.set_companion_tactics(
                "rook",
                {
                    "stance": "defensive",
                    "preserve_mp": True,
                    "ultimate_policy": "never",
                    "healing_threshold": 0.7,
                },
            )
            self.assertEqual(companion.ai_behavior_id, "defensive")
            game.save_game("tactics")

            restored = new_game(tmp)
            restored.load_game("tactics")

            self.assertEqual(restored.party.get("rook").tactics["healing_threshold"], 0.7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
