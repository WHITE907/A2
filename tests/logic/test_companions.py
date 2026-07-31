"""Companion, party and relationship tests (bible sections 6 and 15).

Covers the systems added in v0.2.0: recruiting, the active/reserve roster,
companions fighting through the AI registry, affinity, and marriage - which
works identically for townspeople and companions, and never consults gender.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.combat.combat import CombatState
from engine.entities.companion import Companion, CompanionDefinition, RecruitRequirement
from engine.game import Game
from engine.party import Party
from engine.relationships import AFFINITY_MAX, AFFINITY_MIN, RelationshipRules

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def new_game(seed: int = 4242, save_dir=None) -> Game:
    game = Game(data_dir=PROJECT_ROOT / "data", save_dir=save_dir, seed=seed)
    game.load_content()
    return game


def ready_player(game: Game, level: int = 10, gold: int = 3000) -> None:
    """A character able to afford most recruits."""
    game.create_character("Hero", "male", "squire")
    game.player.level = level
    game.player._recalculate_base_stats()
    game.player.inventory.add_gold(gold)


def recruit_rook(game: Game) -> None:
    ready_player(game)
    ok, messages = game.recruit("rook")
    assert ok, messages


# ======================================================================
class TestCompanionDefinition(unittest.TestCase):
    """The JSON-driven blueprint."""

    def setUp(self):
        self.game = new_game()

    def test_content_loads(self):
        self.assertGreater(self.game.companions.count(), 0)

    def test_definition_requires_id(self):
        with self.assertRaises(ValueError):
            CompanionDefinition.from_dict({"name": "Nameless"})

    def test_level_offset_applies(self):
        definition = CompanionDefinition.from_dict({"id": "x", "level_offset": -2})
        self.assertEqual(definition.level_for(10), 8)

    def test_level_never_below_one(self):
        definition = CompanionDefinition.from_dict({"id": "x", "level_offset": -50})
        self.assertEqual(definition.level_for(3), 1)

    def test_stats_grow_with_level(self):
        definition = self.game.companions.require("rook")
        low = definition.stats_at_level(1).total()
        high = definition.stats_at_level(20).total()
        self.assertGreater(high, low)

    def test_every_companion_ai_id_is_registered(self):
        from engine.combat.ai import default_registry

        registry = default_registry()
        for definition in self.game.companions.all_definitions():
            self.assertIn(definition.ai_behavior_id, registry.ids(), definition.id)

    def test_every_companion_skill_resolves(self):
        for definition in self.game.companions.all_definitions():
            for skill_id in definition.skill_ids:
                self.assertIsNotNone(self.game.skills.get(skill_id), f"{definition.id}:{skill_id}")

    def test_at_location_filters(self):
        town = {d.id for d in self.game.companions.at_location("town_ashvale")}
        self.assertIn("rook", town)
        self.assertNotIn("kess", town)

    def test_recruit_requirement_accepts_list_or_mapping(self):
        from_list = RecruitRequirement.from_dict({"items": ["orb"]})
        from_map = RecruitRequirement.from_dict({"items": {"orb": 2}})
        self.assertEqual(from_list.items, {"orb": 1})
        self.assertEqual(from_map.items, {"orb": 2})


# ======================================================================
class TestCompanionEntity(unittest.TestCase):
    def setUp(self):
        self.game = new_game()
        ready_player(self.game)
        self.companion = self.game.companions.create("rook", self.game.player.level)

    def test_is_a_full_entity(self):
        self.assertIsInstance(self.companion, Companion)
        self.assertGreater(self.companion.max_hp, 0)
        self.assertTrue(self.companion.is_alive)

    def test_template_modifiers_apply(self):
        """Rook's JSON grants +6 armor and +30 max HP."""
        bare = self.companion.formulas.derive(self.companion.base_stats, self.companion.level)
        self.assertEqual(self.companion.max_hp, bare.max_hp + 30)
        self.assertAlmostEqual(self.companion.derived_stats().armor, bare.armor + 6)

    def test_sync_level_tracks_the_player(self):
        self.assertTrue(self.companion.sync_level(30))
        self.assertEqual(self.companion.level, 30)

    def test_sync_level_is_a_noop_at_same_level(self):
        self.companion.sync_level(20)
        self.assertFalse(self.companion.sync_level(20))

    def test_sync_level_preserves_damage_proportionally(self):
        """Levelling should not be a free full heal."""
        self.companion.current_hp = self.companion.max_hp * 0.5
        self.companion.sync_level(40)
        self.assertLess(self.companion.hp_fraction, 0.75)
        self.assertGreater(self.companion.current_hp, 0)

    def test_takes_damage_and_can_fall(self):
        self.companion.take_raw_damage(999_999, damage_type="true")
        self.assertFalse(self.companion.is_alive)

    def test_status_effects_apply(self):
        self.companion.apply_status(self.game.skills.get_status("poison").clone())
        self.assertTrue(self.companion.has_status("poison"))
        self.companion.tick_status_effects()
        self.assertLess(self.companion.current_hp, self.companion.max_hp)

    def test_usable_skills_respect_mp(self):
        self.companion.current_mp = 0
        for skill in self.companion.usable_skills():
            self.assertEqual(skill.mp_cost, 0)


# ======================================================================
class TestParty(unittest.TestCase):
    """Roster mechanics in isolation."""

    def setUp(self):
        self.game = new_game()
        ready_player(self.game)
        self.party = Party(max_active=2)

    def _make(self, companion_id: str) -> Companion:
        return self.game.companions.create(companion_id, 10)

    def test_recruit_fills_active_first(self):
        self.party.recruit(self._make("rook"))
        self.assertEqual(len(self.party.active), 1)
        self.assertEqual(self.party.reserve, [])

    def test_overflow_goes_to_reserve(self):
        for companion_id in ("rook", "sister_elen", "kess"):
            self.party.recruit(self._make(companion_id))
        self.assertEqual(len(self.party.active), 2)
        self.assertEqual(len(self.party.reserve), 1)

    def test_cannot_recruit_twice(self):
        self.party.recruit(self._make("rook"))
        ok, _ = self.party.recruit(self._make("rook"))
        self.assertFalse(ok)

    def test_bench_and_activate(self):
        self.party.recruit(self._make("rook"))
        self.assertTrue(self.party.set_active("rook", False)[0])
        self.assertFalse(self.party.is_active("rook"))
        self.assertTrue(self.party.set_active("rook", True)[0])
        self.assertTrue(self.party.is_active("rook"))

    def test_cannot_activate_beyond_cap(self):
        for companion_id in ("rook", "sister_elen", "kess"):
            self.party.recruit(self._make(companion_id))
        ok, reason = self.party.set_active("kess", True)
        self.assertFalse(ok)
        self.assertIn("full", reason.lower())

    def test_dismiss_removes_from_either_list(self):
        self.party.recruit(self._make("rook"))
        self.assertTrue(self.party.dismiss("rook")[0])
        self.assertEqual(len(self.party), 0)

    def test_battle_allies_excludes_reserve_and_dead(self):
        for companion_id in ("rook", "sister_elen", "kess"):
            self.party.recruit(self._make(companion_id))
        self.party.active[0].kill()
        allies = self.party.battle_allies()
        self.assertEqual(len(allies), 1)
        self.assertTrue(all(a.is_alive for a in allies))

    def test_revive_fallen_restores_at_partial_hp(self):
        self.party.recruit(self._make("rook"))
        member = self.party.active[0]
        member.kill()
        self.party.revive_fallen()
        self.assertTrue(member.is_alive)
        self.assertLess(member.hp_fraction, 0.5)

    def test_sync_levels_moves_everyone(self):
        self.party.recruit(self._make("rook"))
        self.party.sync_levels(40)
        self.assertTrue(all(c.level >= 39 for c in self.party.all_members))


# ======================================================================
class TestRecruitment(unittest.TestCase):
    """Requirement checking through the Game facade."""

    def setUp(self):
        self.game = new_game()

    def test_requirements_block_and_are_itemised(self):
        self.game.create_character("Hero", "male", "squire")  # level 1, 50 gold
        ok, unmet = self.game.check_recruit("rook")
        self.assertFalse(ok)
        self.assertTrue(any("Level" in u for u in unmet))
        self.assertTrue(any("gold" in u for u in unmet))

    def test_recruiting_consumes_gold(self):
        ready_player(self.game, level=10, gold=1000)
        before = self.game.player.inventory.gold
        self.assertTrue(self.game.recruit("rook")[0])
        self.assertEqual(self.game.player.inventory.gold, before - 120)

    def test_recruiting_consumes_items(self):
        ready_player(self.game)
        self.game.player.affinity["sister_elen"] = 50
        self.game.items.grant(self.game.player.inventory, "minor_ether", 2)
        self.assertTrue(self.game.recruit("sister_elen")[0])
        self.assertEqual(self.game.player.inventory.count("minor_ether"), 0)

    def test_affinity_requirement_enforced(self):
        ready_player(self.game)
        self.game.items.grant(self.game.player.inventory, "minor_ether", 2)
        ok, unmet = self.game.check_recruit("sister_elen")
        self.assertFalse(ok)
        self.assertTrue(any("Affinity" in u for u in unmet))

    def test_failed_recruit_spends_nothing(self):
        ready_player(self.game, level=1, gold=1000)
        before = self.game.player.inventory.gold
        self.game.recruit("rook")
        self.assertEqual(self.game.player.inventory.gold, before)

    def test_recruitable_here_is_location_scoped(self):
        ready_player(self.game)
        town = {d.id for d in self.game.recruitable_here()}
        self.assertIn("rook", town)
        self.game.travel_to("greenfields")
        self.assertEqual(self.game.recruitable_here(), [])

    def test_recruited_companion_disappears_from_available(self):
        recruit_rook(self.game)
        self.assertNotIn("rook", {d.id for d in self.game.recruitable_here()})

    def test_dismissed_companion_keeps_affinity(self):
        recruit_rook(self.game)
        self.game.player.change_affinity("rook", 40)
        self.game.dismiss_companion("rook")
        self.assertEqual(self.game.player.affinity_with("rook"), 40)


# ======================================================================
class TestCompanionsInCombat(unittest.TestCase):
    def setUp(self):
        self.game = new_game(seed=31)
        recruit_rook(self.game)

    def _fight(self, spawns, max_turns: int = 120):
        battle = self.game.start_battle(spawns)
        turns = 0
        while not battle.is_over and turns < max_turns:
            if battle.waiting_for_player:
                targets = battle.living_enemies
                battle.player_attack(targets[0] if targets else None)
            battle.run_until_player_turn()
            turns += 1
        return battle

    def test_active_companion_joins_the_battle(self):
        battle = self.game.start_battle([("green_slime", 1)])
        self.assertIn("Rook", [a.name for a in battle.allies])

    def test_reserve_companion_does_not(self):
        self.game.set_companion_active("rook", False)
        battle = self.game.start_battle([("green_slime", 1)])
        self.assertNotIn("Rook", [a.name for a in battle.allies])

    def test_companion_acts_on_its_own_turn(self):
        battle = self._fight([("green_slime", 3)])
        self.assertTrue(any("Rook" in entry.text for entry in battle.log))

    def test_companion_targets_enemies_not_the_player(self):
        """Allies must never be routed as foes by the AI turn logic."""
        battle = self._fight([("green_slime", 2)])
        hits_on_player = [
            e.text for e in battle.log if e.text.startswith("Rook hits Hero")
        ]
        self.assertEqual(hits_on_player, [])

    def test_companion_appears_in_turn_order(self):
        battle = self.game.start_battle([("green_slime", 1)])
        self.assertIn("Rook", [c.name for c in battle.turn_order])

    def test_ally_lines_render_for_the_gui(self):
        battle = self.game.start_battle([("green_slime", 1)])
        self.assertTrue(any("Rook" in line for line in battle.ally_lines()))

    def test_ally_lines_without_companions(self):
        game = new_game()
        ready_player(game)
        battle = game.start_battle([("green_slime", 1)])
        self.assertEqual(battle.ally_lines(), ["(none)"])

    def test_victory_grants_affinity_to_active_companions(self):
        before = self.game.player.affinity_with("rook")
        battle = self._fight([("green_slime", 1)])
        self.assertEqual(battle.state, CombatState.VICTORY)
        self.game.finish_battle()
        self.assertGreater(self.game.player.affinity_with("rook"), before)

    def test_fallen_companion_revives_after_battle(self):
        battle = self.game.start_battle([("green_slime", 1)])
        rook = next(a for a in battle.allies if a.name == "Rook")
        rook.kill()
        while not battle.is_over:
            if battle.waiting_for_player:
                targets = battle.living_enemies
                battle.player_attack(targets[0] if targets else None)
            battle.run_until_player_turn()
        self.game.finish_battle()
        self.assertTrue(self.game.party.get("rook").is_alive)

    def test_battle_statuses_cleared_from_companions(self):
        battle = self.game.start_battle([("green_slime", 1)])
        rook = next(a for a in battle.allies if a.name == "Rook")
        rook.apply_status(self.game.skills.get_status("poison").clone())
        while not battle.is_over:
            if battle.waiting_for_player:
                targets = battle.living_enemies
                battle.player_attack(targets[0] if targets else None)
            battle.run_until_player_turn()
        self.game.finish_battle()
        self.assertEqual(self.game.party.get("rook").statuses, [])

    def test_player_death_still_ends_the_battle_with_allies_alive(self):
        """A living companion must not keep a lost battle running."""
        battle = self.game.start_battle([("shadow_warden", 60)])
        turns = 0
        while not battle.is_over and turns < 200:
            if battle.waiting_for_player:
                battle.player_defend()
            battle.run_until_player_turn()
            turns += 1
        self.assertEqual(battle.state, CombatState.DEFEAT)

    def test_resting_heals_companions(self):
        self.game.party.active[0].current_hp = 1
        self.game.player.inventory.add_gold(100)
        self.game.rest_at_inn()
        member = self.game.party.get("rook")
        self.assertEqual(member.current_hp, float(member.max_hp))


# ======================================================================
class TestRelationships(unittest.TestCase):
    """Affinity and marriage rules, shared by NPCs and companions."""

    def setUp(self):
        self.rules = RelationshipRules(
            {
                "affinity_per_talk": 2,
                "affinity_gift": 5,
                "affinity_gift_liked": 15,
                "affinity_talk_falloff_after": 3,
                "marriage_item_id": "eternal_band",
            }
        )

    def test_talk_gain_falls_off_but_never_to_zero(self):
        self.assertEqual(self.rules.talk_gain(0), 2)
        self.assertGreaterEqual(self.rules.talk_gain(99), 1)
        self.assertLess(self.rules.talk_gain(99), self.rules.talk_gain(0))

    def test_liked_gift_is_worth_more(self):
        suitor = type("S", (), {"id": "x", "name": "X", "marriageable": True,
                                "marriage_affinity": 50, "gift_item_ids": ["rose"]})()
        liked, was_liked = self.rules.gift_gain(suitor, "rose")
        plain, not_liked = self.rules.gift_gain(suitor, "rock")
        self.assertTrue(was_liked)
        self.assertFalse(not_liked)
        self.assertGreater(liked, plain)

    def test_affinity_is_clamped(self):
        self.assertEqual(self.rules.clamp(9999), AFFINITY_MAX)
        self.assertEqual(self.rules.clamp(-9999), AFFINITY_MIN)

    def test_tier_labels_ascend(self):
        self.assertEqual(self.rules.tier_label(-100), "Hostile")
        self.assertEqual(self.rules.tier_label(0), "Neutral")
        self.assertEqual(self.rules.tier_label(100), "Devoted")

    def test_check_lists_each_unmet_requirement(self):
        suitor = type("S", (), {"id": "x", "name": "X", "marriageable": True,
                                "marriage_affinity": 50, "gift_item_ids": []})()
        check = self.rules.check_marriage(
            suitor, affinity=0, has_ring=False, current_spouse_id=None
        )
        self.assertFalse(check.eligible)
        self.assertEqual(len(check.unmet), 2)

    def test_unmarriageable_is_refused(self):
        suitor = type("S", (), {"id": "x", "name": "X", "marriageable": False,
                                "marriage_affinity": 0, "gift_item_ids": []})()
        check = self.rules.check_marriage(
            suitor, affinity=100, has_ring=True, current_spouse_id=None
        )
        self.assertFalse(check.eligible)
        self.assertIn("not interested", check.reason)

    def test_unrecruited_companion_cannot_be_proposed_to(self):
        suitor = type("S", (), {"id": "x", "name": "X", "marriageable": True,
                                "marriage_affinity": 0, "gift_item_ids": []})()
        check = self.rules.check_marriage(
            suitor, affinity=100, has_ring=True, current_spouse_id=None, recruited=False
        )
        self.assertFalse(check.eligible)
        self.assertTrue(any("party" in u for u in check.unmet))


# ======================================================================
class TestMarriageThroughTheGame(unittest.TestCase):
    """End-to-end marriage, for both NPCs and companions."""

    def setUp(self):
        self.game = new_game(seed=17)

    def _prepare(self, target_id: str) -> None:
        self.game.player.affinity[target_id] = 100
        self.game.items.grant(self.game.player.inventory, "eternal_band", 1)

    def test_marrying_a_companion(self):
        recruit_rook(self.game)
        self._prepare("rook")
        ok, _ = self.game.marry("rook")
        self.assertTrue(ok)
        self.assertEqual(self.game.player.spouse_id, "rook")

    def test_marrying_an_npc_still_works(self):
        ready_player(self.game)
        self._prepare("innkeeper_mara")
        self.assertTrue(self.game.marry("innkeeper_mara")[0])

    def test_marriage_is_gender_agnostic_for_companions(self):
        """Bible section 15: possible regardless of gender."""
        for gender in ("male", "female"):
            game = new_game()
            game.create_character("Hero", gender, "acolyte")
            game.player.level = 10
            game.player._recalculate_base_stats()
            game.player.inventory.add_gold(3000)
            game.recruit("rook")  # Rook is male
            game.player.affinity["rook"] = 100
            game.items.grant(game.player.inventory, "eternal_band", 1)
            self.assertTrue(game.marry("rook")[0], gender)

    def test_marriage_consumes_the_ring(self):
        recruit_rook(self.game)
        self._prepare("rook")
        self.game.marry("rook")
        self.assertFalse(self.game.player.inventory.has("eternal_band"))

    def test_marriage_requires_the_ring(self):
        recruit_rook(self.game)
        self.game.player.affinity["rook"] = 100
        ok, reason = self.game.can_marry("rook")
        self.assertFalse(ok)
        self.assertIn("Eternal Band", reason)

    def test_marriage_requires_affinity(self):
        recruit_rook(self.game)
        self.game.items.grant(self.game.player.inventory, "eternal_band", 1)
        ok, reason = self.game.can_marry("rook")
        self.assertFalse(ok)
        self.assertIn("Affinity", reason)

    def test_cannot_marry_an_unrecruited_companion(self):
        ready_player(self.game)
        self._prepare("rook")
        self.assertFalse(self.game.can_marry("rook")[0])

    def test_cannot_marry_twice(self):
        recruit_rook(self.game)
        self._prepare("rook")
        self.game.marry("rook")
        self.game.player.affinity["innkeeper_mara"] = 100
        self.game.items.grant(self.game.player.inventory, "eternal_band", 1)
        self.assertFalse(self.game.marry("innkeeper_mara")[0])

    def test_spouse_gains_a_combat_bonus(self):
        recruit_rook(self.game)
        rook = self.game.party.get("rook")
        before_hp = rook.max_hp
        before_atk = rook.derived_stats().physical_power
        self._prepare("rook")
        self.game.marry("rook")
        self.assertGreater(rook.max_hp, before_hp)
        self.assertGreater(rook.derived_stats().physical_power, before_atk)

    def test_only_the_spouse_gets_the_bonus(self):
        recruit_rook(self.game)
        self.game.player.affinity["sister_elen"] = 50
        self.game.items.grant(self.game.player.inventory, "minor_ether", 2)
        self.game.recruit("sister_elen")
        elen_before = self.game.party.get("sister_elen").max_hp
        self._prepare("rook")
        self.game.marry("rook")
        self.assertEqual(self.game.party.get("sister_elen").max_hp, elen_before)

    def test_spouse_cannot_be_dismissed(self):
        recruit_rook(self.game)
        self._prepare("rook")
        self.game.marry("rook")
        ok, reason = self.game.dismiss_companion("rook")
        self.assertFalse(ok)
        self.assertIn("spouse", reason.lower())

    def test_talking_raises_affinity(self):
        recruit_rook(self.game)
        before = self.game.player.affinity_with("rook")
        ok, lines = self.game.talk_to("rook")
        self.assertTrue(ok)
        self.assertGreater(self.game.player.affinity_with("rook"), before)
        self.assertTrue(lines)

    def test_repeated_talking_yields_less(self):
        recruit_rook(self.game)
        gains = []
        for _ in range(6):
            before = self.game.player.affinity_with("rook")
            self.game.talk_to("rook")
            gains.append(self.game.player.affinity_with("rook") - before)
        self.assertLess(gains[-1], gains[0])

    def test_gifting_a_companion_works(self):
        recruit_rook(self.game)
        self.game.items.grant(self.game.player.inventory, "troll_hide", 1)
        before = self.game.player.affinity_with("rook")
        ok, _ = self.game.give_gift("rook", "troll_hide")
        self.assertTrue(ok)
        self.assertGreater(self.game.player.affinity_with("rook") - before, 5)

    def test_marriage_checklist_is_itemised_for_the_gui(self):
        recruit_rook(self.game)
        check = self.game.marriage_check("rook")
        self.assertFalse(check.eligible)
        self.assertTrue(check.unmet)
        self.assertTrue(check.summary_lines())


# ======================================================================
class TestCompanionPersistence(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.save_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _prepared(self) -> Game:
        game = new_game(seed=63, save_dir=self.save_dir)
        ready_player(game)
        game.recruit("rook")
        game.player.affinity["sister_elen"] = 50
        game.items.grant(game.player.inventory, "minor_ether", 2)
        game.recruit("sister_elen")
        return game

    def test_party_survives_a_round_trip(self):
        game = self._prepared()
        game.save_game("slot")
        fresh = new_game(seed=1, save_dir=self.save_dir)
        fresh.load_game("slot")
        self.assertEqual(
            {c.id for c in fresh.party.all_members},
            {c.id for c in game.party.all_members},
        )

    def test_reserve_membership_survives(self):
        game = self._prepared()
        game.set_companion_active("rook", False)
        game.save_game("slot")
        fresh = new_game(seed=1, save_dir=self.save_dir)
        fresh.load_game("slot")
        self.assertFalse(fresh.party.is_active("rook"))
        self.assertTrue(fresh.party.has("rook"))

    def test_companion_hp_survives(self):
        game = self._prepared()
        member = game.party.get("rook")
        member.current_hp = member.max_hp * 0.5
        expected = member.current_hp
        game.save_game("slot")
        fresh = new_game(seed=1, save_dir=self.save_dir)
        fresh.load_game("slot")
        self.assertAlmostEqual(fresh.party.get("rook").current_hp, expected, places=2)

    def test_marriage_and_spouse_bonus_survive(self):
        game = self._prepared()
        game.player.affinity["rook"] = 100
        game.items.grant(game.player.inventory, "eternal_band", 1)
        game.marry("rook")
        expected_hp = game.party.get("rook").max_hp
        game.save_game("slot")

        fresh = new_game(seed=1, save_dir=self.save_dir)
        fresh.load_game("slot")
        self.assertEqual(fresh.player.spouse_id, "rook")
        self.assertEqual(fresh.party.get("rook").max_hp, expected_hp)

    def test_affinity_survives(self):
        game = self._prepared()
        game.player.change_affinity("rook", 33)
        expected = game.player.affinity_with("rook")
        game.save_game("slot")
        fresh = new_game(seed=1, save_dir=self.save_dir)
        fresh.load_game("slot")
        self.assertEqual(fresh.player.affinity_with("rook"), expected)

    def test_save_without_party_block_still_loads(self):
        """Backwards compatibility: pre-companion saves (bible section 5)."""
        import json

        game = self._prepared()
        game.save_game("legacy")
        path = self.save_dir / "legacy.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.pop("party", None)
        path.write_text(json.dumps(payload), encoding="utf-8")

        fresh = new_game(seed=1, save_dir=self.save_dir)
        ok, _ = fresh.load_game("legacy")
        self.assertTrue(ok)
        self.assertEqual(len(fresh.party), 0)

    def test_unknown_companion_id_is_dropped_not_fatal(self):
        import json

        game = self._prepared()
        game.save_game("slot")
        path = self.save_dir / "slot.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["party"]["active"].append({"companion_id": "deleted_ally", "name": "Ghost"})
        path.write_text(json.dumps(payload), encoding="utf-8")

        fresh = new_game(seed=1, save_dir=self.save_dir)
        ok, _ = fresh.load_game("slot")
        self.assertTrue(ok)
        self.assertIsNone(fresh.party.get("deleted_ally"))

    def test_new_character_starts_with_no_party(self):
        game = self._prepared()
        game.create_character("Second", "female", "maiden")
        self.assertEqual(len(game.party), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
