"""Engine test-suite.

Per docs/ENGINE_DESIGN.md these are not placeholder tests - they exercise the
real chain: JSON on disk -> Managers -> Entities -> Skill.use() -> Effects ->
combat log, including full DOT lifecycles and save/load round-trips.

Run with::

    python3 -m unittest discover -s tests -v

or just ``python3 -m unittest tests.logic.test_core``.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.classes import ClassDefinition, PromotionRequirement
from engine.combat.ai import default_registry
from engine.combat.combat import Battle, CombatState
from engine.entities.player import Player
from engine.game import Game
from engine.items.item import Inventory, Item, ItemKind
from engine.managers.data_loader import ContentError, DataLoader
from engine.managers.save_manager import SAVE_VERSION, SaveManager
from engine.mastery import MASTERY_RANKS, MasteryBook, rank_at_least
from engine.rng import GameRandom
from engine.skills.effects import build_effect, known_effect_types
from engine.skills.skill import Skill, SkillCategory
from engine.skills.status import StatusEffect, StatusStacking
from engine.stats import Formulas, ModifierSet, StatBlock

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def new_game(seed: int = 1234, save_dir: Path | str | None = None) -> Game:
    """A fully loaded Game pointed at the real content files."""
    game = Game(data_dir=PROJECT_ROOT / "data", save_dir=save_dir, seed=seed)
    game.load_content()
    return game


# ======================================================================
class TestRNG(unittest.TestCase):
    """A seeded RNG must be reproducible and serialisable."""

    def test_same_seed_same_stream(self):
        a = GameRandom(99)
        b = GameRandom(99)
        self.assertEqual([a.randint(1, 100) for _ in range(20)], [b.randint(1, 100) for _ in range(20)])

    def test_chance_bounds_never_roll(self):
        rng = GameRandom(1)
        self.assertFalse(rng.chance(0.0))
        self.assertTrue(rng.chance(1.0))
        self.assertFalse(rng.chance(-5.0))
        self.assertTrue(rng.chance(5.0))

    def test_weighted_choice_skips_zero_weight(self):
        rng = GameRandom(3)
        picks = {rng.weighted_choice([("a", 0), ("b", 1)]) for _ in range(50)}
        self.assertEqual(picks, {"b"})

    def test_weighted_choice_requires_positive_weight(self):
        with self.assertRaises(ValueError):
            GameRandom(1).weighted_choice([("a", 0), ("b", 0)])

    def test_state_round_trip_resumes_identical_stream(self):
        rng = GameRandom(5)
        [rng.random() for _ in range(10)]
        snapshot = rng.to_dict()
        expected = [rng.randint(0, 999) for _ in range(10)]

        restored = GameRandom()
        restored.load_state(snapshot)
        self.assertEqual([restored.randint(0, 999) for _ in range(10)], expected)

    def test_corrupt_state_does_not_raise(self):
        rng = GameRandom(5)
        rng.load_state({"seed": 5, "state": {"version": "bad"}})
        self.assertIsInstance(rng.random(), float)

    def test_shuffled_does_not_mutate_source(self):
        source = [1, 2, 3, 4, 5]
        GameRandom(2).shuffled(source)
        self.assertEqual(source, [1, 2, 3, 4, 5])


# ======================================================================
class TestStats(unittest.TestCase):
    """Formulas are data-driven and modifiers layer flat-then-percent."""

    def setUp(self):
        self.formulas = Formulas.from_dict(
            {
                "hp": {"base": 40, "per_end": 8.0, "per_level": 6.0},
                "physical_power": {"base": 3, "per_str": 1.6},
                "crit_chance": {"base": 0.03, "per_agi": 0.004, "max": 0.75},
                "evasion": {"base": 0.02, "per_agi": 0.005, "max": 0.6},
                "accuracy": {"base": 0.88, "max": 0.99},
                "mitigation_constant": 100.0,
            }
        )

    def test_statblock_dict_access_and_validation(self):
        block = StatBlock(STR=5)
        self.assertEqual(block["STR"], 5)
        block["str"] = 9
        self.assertEqual(block.STR, 9)
        with self.assertRaises(KeyError):
            block["LUCK"]

    def test_statblock_from_dict_ignores_unknown_keys(self):
        block = StatBlock.from_dict({"STR": 4, "LUCK": 99})
        self.assertEqual(block.STR, 4)
        self.assertEqual(block.total(), 4)

    def test_derive_uses_config_coefficients(self):
        derived = self.formulas.derive(StatBlock(END=10), level=1)
        self.assertEqual(derived.max_hp, round(40 + 8 * 10 + 6 * 1))

    def test_flat_applies_before_percent(self):
        mods = ModifierSet()
        mods.add_flat("physical_power", 10)
        mods.add_pct("physical_power", 0.5)
        # (3 + 1.6*10 + 10) * 1.5
        self.assertAlmostEqual(
            self.formulas.derive(StatBlock(STR=10), 1, mods).physical_power, (3 + 16 + 10) * 1.5
        )

    def test_percent_modifiers_stack_additively(self):
        mods = ModifierSet()
        mods.add_pct("armor", 0.2)
        mods.add_pct("armor", 0.2)
        self.assertAlmostEqual(mods.apply("armor", 100.0), 140.0)

    def test_derived_stats_are_clamped_to_config_max(self):
        derived = self.formulas.derive(StatBlock(AGI=10_000), level=1)
        self.assertLessEqual(derived.crit_chance, 0.75)
        self.assertLessEqual(derived.evasion, 0.60)

    def test_mitigation_is_asymptotic(self):
        self.assertAlmostEqual(self.formulas.mitigation(100), 0.5)
        self.assertLess(self.formulas.mitigation(10_000_000), 1.0)

    def test_penetration_percent_applies_before_flat(self):
        # 50% pen on 100 armor -> 50; then -20 flat -> 30 effective.
        result = self.formulas.apply_mitigation(100, 100, penetration_pct=0.5, penetration_flat=20)
        expected = 100 * (1 - self.formulas.mitigation(30))
        self.assertAlmostEqual(result, expected)

    def test_true_damage_has_no_defence(self):
        derived = self.formulas.derive(StatBlock(END=50), 10)
        self.assertEqual(derived.defence_for("true"), 0.0)

    def test_hit_chance_respects_floor_and_ceiling(self):
        self.assertAlmostEqual(self.formulas.hit_chance(0.0, 5.0), self.formulas.hit_floor)
        self.assertAlmostEqual(self.formulas.hit_chance(5.0, 0.0), self.formulas.hit_ceiling)

    def test_modifierset_accepts_bare_mapping(self):
        mods = ModifierSet.from_dict({"STR": 3, "armor_pct": 0.5})
        self.assertEqual(mods.flat["STR"], 3)
        self.assertEqual(mods.pct["armor"], 0.5)


# ======================================================================
class TestStatusEffects(unittest.TestCase):
    """Stacking rules, shields and serialisation."""

    def test_refresh_extends_to_longer_duration(self):
        base = StatusEffect(id="p", name="P", duration=3, stacking=StatusStacking.REFRESH)
        base.merge_with(StatusEffect(id="p", name="P", duration=1))
        self.assertEqual(base.duration, 3)

    def test_stack_respects_max_stacks(self):
        base = StatusEffect(id="p", name="P", duration=3, stacking=StatusStacking.STACK, max_stacks=2)
        base.merge_with(StatusEffect(id="p", name="P", duration=3))
        base.merge_with(StatusEffect(id="p", name="P", duration=3))
        self.assertEqual(base.stacks, 2)

    def test_ignore_stacking_is_a_no_op(self):
        base = StatusEffect(id="p", name="P", duration=1, stacking=StatusStacking.IGNORE)
        base.merge_with(StatusEffect(id="p", name="P", duration=9))
        self.assertEqual(base.duration, 1)

    def test_stacks_scale_tick_and_modifiers(self):
        status = StatusEffect(id="p", name="P", duration=3, per_turn_hp=-5, stacks=3)
        status.modifiers.add_flat("armor", 2)
        self.assertEqual(status.tick_hp(), -15)
        self.assertEqual(status.scaled_modifiers().flat["armor"], 6)

    def test_shield_absorbs_then_expires(self):
        shield = StatusEffect(id="s", name="S", duration=5, category="shield", shield_hp=30)
        self.assertEqual(shield.absorb(10), 0)
        self.assertEqual(shield.shield_hp, 20)
        self.assertEqual(shield.absorb(50), 30)
        self.assertTrue(shield.expired)

    def test_round_trip_serialisation(self):
        original = StatusEffect(id="p", name="Poison", duration=3, category="dot", per_turn_hp=-6, stacks=2)
        original.modifiers.add_pct("armor", -0.2)
        restored = StatusEffect.from_dict(original.to_dict())
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_unknown_stacking_falls_back_to_refresh(self):
        restored = StatusEffect.from_dict({"id": "x", "stacking": "nonsense"})
        self.assertEqual(restored.stacking, StatusStacking.REFRESH)


# ======================================================================
class TestEffectsAndCombatMath(unittest.TestCase):
    """The five effect strategies, driven through real entities."""

    def setUp(self):
        self.game = new_game(seed=11)
        self.game.create_character("Tester", "male", "squire")
        self.player = self.game.player
        self.ctx = self.game.skills.make_context(self.game.rng, self.game.formulas)
        self.enemy = self.game.enemies.spawn("green_slime", 1)

    def test_core_effect_types_are_registered(self):
        self.assertTrue(
            {"damage", "heal", "resource", "shield", "apply_status"} <= set(known_effect_types())
        )

    def test_unknown_effect_type_raises(self):
        with self.assertRaises(ValueError):
            build_effect({"type": "teleport"})

    def test_damage_reduces_hp(self):
        effect = build_effect({"type": "damage", "base": 20, "can_miss": False, "can_crit": False})
        before = self.enemy.current_hp
        result = effect.apply(self.player, self.enemy, self.ctx)
        self.assertEqual(result.kind, "damage")
        self.assertLess(self.enemy.current_hp, before)

    def test_guaranteed_miss_deals_no_damage(self):
        effect = build_effect({"type": "damage", "base": 999})
        self.enemy.base_stats["AGI"] = 100000
        self.enemy.invalidate_stats()
        before = self.enemy.current_hp
        result = effect.apply(self.player, self.enemy, self.ctx)
        # Hit ceiling caps at 99%, so retry until the miss lands.
        for _ in range(200):
            if result and result.missed:
                break
            result = effect.apply(self.player, self.enemy, self.ctx)
        self.assertTrue(result.missed)

    def test_true_damage_ignores_armor(self):
        self.enemy.base_stats["END"] = 500
        self.enemy.invalidate_stats()
        physical = build_effect({"type": "damage", "base": 100, "can_miss": False, "can_crit": False})
        true_dmg = build_effect(
            {"type": "damage", "damage_type": "true", "base": 100, "can_miss": False, "can_crit": False}
        )
        phys_result = physical.apply(self.player, self.enemy, self.ctx)
        self.enemy.restore_fully()
        true_result = true_dmg.apply(self.player, self.enemy, self.ctx)
        self.assertGreater(true_result.amount, phys_result.amount)

    def test_multi_hit_applies_each_hit(self):
        effect = build_effect(
            {"type": "damage", "base": 5, "hits": 3, "can_miss": False, "can_crit": False}
        )
        single = build_effect(
            {"type": "damage", "base": 5, "hits": 1, "can_miss": False, "can_crit": False}
        )
        multi_result = effect.apply(self.player, self.enemy, self.ctx)
        self.enemy.restore_fully()
        single_result = single.apply(self.player, self.enemy, self.ctx)
        self.assertAlmostEqual(multi_result.amount, single_result.amount * 3, places=4)

    def test_heal_never_exceeds_max_hp(self):
        self.player.current_hp = 10
        effect = build_effect({"type": "heal", "base": 100000})
        effect.apply(self.player, self.player, self.ctx)
        self.assertEqual(self.player.current_hp, float(self.player.max_hp))

    def test_resource_effect_can_drain(self):
        self.player.current_mp = 20
        effect = build_effect({"type": "resource", "amount": -15})
        effect.apply(self.player, self.player, self.ctx)
        self.assertEqual(self.player.current_mp, 5)

    def test_shield_absorbs_incoming_damage(self):
        build_effect({"type": "shield", "base": 50}).apply(self.player, self.player, self.ctx)
        before = self.player.current_hp
        outcome = self.player.take_raw_damage(30, damage_type="physical")
        self.assertEqual(outcome.absorbed, 30)
        self.assertEqual(self.player.current_hp, before)

    def test_shield_overflow_reaches_hp(self):
        build_effect({"type": "shield", "base": 10}).apply(self.player, self.player, self.ctx)
        outcome = self.player.take_raw_damage(30, damage_type="physical")
        self.assertEqual(outcome.absorbed, 10)
        self.assertEqual(outcome.damage, 20)

    def test_reflect_is_reported_not_self_applied(self):
        build_effect({"type": "shield", "base": 0, "reflect_pct": 0.5}).apply(
            self.player, self.player, self.ctx
        )
        outcome = self.player.take_raw_damage(40, damage_type="physical", attacker=self.enemy)
        self.assertAlmostEqual(outcome.reflected, 20.0)
        self.assertEqual(self.enemy.current_hp, float(self.enemy.max_hp))

    def test_apply_status_attaches_template(self):
        effect = build_effect({"type": "apply_status", "status_id": "poison"})
        effect.apply(self.player, self.enemy, self.ctx)
        self.assertTrue(self.enemy.has_status("poison"))

    def test_apply_status_with_zero_chance_never_fires(self):
        effect = build_effect({"type": "apply_status", "status_id": "poison", "chance": 0.0})
        for _ in range(50):
            effect.apply(self.player, self.enemy, self.ctx)
        self.assertFalse(self.enemy.has_status("poison"))

    def test_effect_target_override_redirects(self):
        effect = build_effect({"type": "heal", "base": 20, "target": "self"})
        self.assertEqual(effect.target_override, "self")


# ======================================================================
class TestDOTLifecycle(unittest.TestCase):
    """The full apply -> tick -> tick -> expire chain ENGINE_DESIGN.md calls for."""

    def setUp(self):
        self.game = new_game(seed=21)
        self.game.create_character("Tester", "male", "squire")
        self.enemy = self.game.enemies.spawn("green_slime", 1)
        self.ctx = self.game.skills.make_context(self.game.rng, self.game.formulas)

    def test_dot_ticks_each_turn_then_expires(self):
        poison = self.game.skills.get_status("poison").clone()
        poison.duration = 2
        self.enemy.apply_status(poison)
        start_hp = self.enemy.current_hp

        first = self.enemy.tick_status_effects()
        self.assertLess(self.enemy.current_hp, start_hp)
        self.assertTrue(self.enemy.has_status("poison"))
        self.assertTrue(any("Poison" in m for m in first.messages))

        after_first = self.enemy.current_hp
        second = self.enemy.tick_status_effects()
        self.assertLess(self.enemy.current_hp, after_first)
        self.assertIn("Poison", second.expired)
        self.assertFalse(self.enemy.has_status("poison"))

        after_expiry = self.enemy.current_hp
        self.enemy.tick_status_effects()
        self.assertEqual(self.enemy.current_hp, after_expiry)

    def test_hot_heals_then_expires(self):
        self.enemy.current_hp = 1
        regen = self.game.skills.get_status("regeneration").clone()
        regen.duration = 2
        self.enemy.apply_status(regen)
        self.enemy.tick_status_effects()
        self.assertGreater(self.enemy.current_hp, 1)

    def test_dot_can_kill_and_is_reported(self):
        self.enemy.current_hp = 1
        poison = self.game.skills.get_status("poison").clone()
        self.enemy.apply_status(poison)
        report = self.enemy.tick_status_effects()
        self.assertTrue(report.died)
        self.assertFalse(self.enemy.is_alive)

    def test_buff_modifier_applies_then_reverts(self):
        base_power = self.enemy.derived_stats().physical_power
        might = self.game.skills.get_status("might").clone()
        might.duration = 1
        self.enemy.apply_status(might)
        self.assertGreater(self.enemy.derived_stats().physical_power, base_power)
        self.enemy.tick_status_effects()
        self.assertAlmostEqual(self.enemy.derived_stats().physical_power, base_power)

    def test_stun_prevents_action_flag(self):
        stun = self.game.skills.get_status("stunned").clone()
        self.enemy.apply_status(stun)
        self.assertTrue(self.enemy.is_stunned)

    def test_clear_debuffs_keeps_buffs(self):
        self.enemy.apply_status(self.game.skills.get_status("poison").clone())
        self.enemy.apply_status(self.game.skills.get_status("might").clone())
        removed = self.enemy.clear_debuffs()
        self.assertIn("Poison", removed)
        self.assertTrue(self.enemy.has_status("might"))

    def test_losing_max_hp_buff_does_not_heal(self):
        entity = self.enemy
        entity.current_hp = 5
        buff = StatusEffect(id="hp_up", name="HP Up", duration=1)
        buff.modifiers.add_flat("max_hp", 100)
        entity.apply_status(buff)
        self.assertEqual(entity.current_hp, 5)
        entity.tick_status_effects()
        self.assertEqual(entity.current_hp, 5)


# ======================================================================
class TestSkills(unittest.TestCase):
    """Skill.use(), costs, cooldowns and targeting."""

    def setUp(self):
        self.game = new_game(seed=31)
        self.game.create_character("Tester", "male", "squire")
        self.player = self.game.player
        self.ctx = self.game.skills.make_context(self.game.rng, self.game.formulas)

    def test_skill_use_spends_mp(self):
        skill = self.game.skills.require("power_strike")
        enemy = self.game.enemies.spawn("green_slime", 1)
        before = self.player.current_mp
        result = skill.use(self.player, [enemy], self.ctx, enemies=[enemy])
        self.assertTrue(result.success)
        self.assertEqual(self.player.current_mp, before - skill.mp_cost)

    def test_insufficient_mp_is_rejected_and_costs_nothing(self):
        skill = self.game.skills.require("fireball")
        enemy = self.game.enemies.spawn("green_slime", 1)
        self.player.current_mp = 0
        result = skill.use(self.player, [enemy], self.ctx, enemies=[enemy])
        self.assertFalse(result.success)
        self.assertEqual(self.player.current_mp, 0)
        self.assertEqual(enemy.current_hp, float(enemy.max_hp))

    def test_insufficient_sp_is_rejected_and_costs_nothing(self):
        skill = self.game.skills.require("power_strike")
        enemy = self.game.enemies.spawn("green_slime", 1)
        self.player.current_sp = 0
        result = skill.use(self.player, [enemy], self.ctx, enemies=[enemy])
        self.assertFalse(result.success)
        self.assertEqual(self.player.current_sp, 0)
        self.assertEqual(enemy.current_hp, float(enemy.max_hp))

    def test_cooldown_blocks_reuse_then_clears(self):
        skill = self.game.skills.require("sunder_armor")
        enemy = self.game.enemies.spawn("green_slime", 5)
        self.player.current_mp = 500
        self.assertTrue(skill.use(self.player, [enemy], self.ctx, enemies=[enemy]).success)
        self.assertFalse(skill.can_use(self.player)[0])
        for _ in range(skill.cooldown + 1):
            self.player.tick_cooldowns()
        self.assertTrue(skill.can_use(self.player)[0])

    def test_all_enemies_targeting_hits_everyone(self):
        skill = self.game.skills.require("whirlwind")
        enemies = [self.game.enemies.spawn("green_slime", 1, s) for s in ("A", "B", "C")]
        self.player.current_mp = 500
        result = skill.use(self.player, [], self.ctx, enemies=enemies)
        self.assertEqual(len({r.target_name for r in result.results}), 3)

    def test_passive_skill_cannot_be_used(self):
        passive = self.game.skills.require("toughness")
        self.assertFalse(passive.can_use(self.player)[0])

    def test_skill_with_no_target_falls_back_to_first_living(self):
        skill = self.game.skills.require("strike")
        enemy = self.game.enemies.spawn("green_slime", 1)
        result = skill.use(self.player, [], self.ctx, enemies=[enemy])
        self.assertTrue(result.success)

    def test_dead_targets_are_skipped(self):
        skill = self.game.skills.require("strike")
        enemy = self.game.enemies.spawn("green_slime", 1)
        enemy.kill()
        result = skill.use(self.player, [enemy], self.ctx, enemies=[enemy])
        self.assertEqual(result.results, [])

    def test_self_targeted_effect_hits_caster_not_enemy(self):
        skill = self.game.skills.require("shadowstep")
        enemy = self.game.enemies.spawn("green_slime", 8)
        self.player.current_mp = 500
        result = skill.use(self.player, [enemy], self.ctx, enemies=[enemy])
        self.assertTrue(self.player.has_status("haste"))

    def test_invalid_category_rejected_at_load(self):
        with self.assertRaises(ValueError):
            Skill.from_dict({"id": "x", "category": "bogus"})

    def test_skill_requires_id(self):
        with self.assertRaises(ValueError):
            Skill.from_dict({"name": "Nameless"})


# ======================================================================
class TestPlayerProgression(unittest.TestCase):
    """Bible section 9: levels, +5 stat points, +1 skill point."""

    def setUp(self):
        self.game = new_game(seed=41)
        self.game.create_character("Tester", "male", "squire")
        self.player = self.game.player

    def test_level_up_grants_configured_points(self):
        report = self.player.gain_exp(self.player.exp_to_next_level())
        self.assertEqual(report.levels_gained, 1)
        self.assertEqual(self.player.unspent_stat_points, 5)
        self.assertEqual(self.player.unspent_skill_points, 1)

    def test_massive_exp_grants_multiple_levels(self):
        report = self.player.gain_exp(1_000_000)
        self.assertGreater(report.levels_gained, 5)
        self.assertEqual(self.player.level, report.new_level)

    def test_exp_curve_is_monotonic(self):
        costs = []
        for _ in range(10):
            costs.append(self.player.exp_to_next_level())
            self.player.level += 1
        self.assertEqual(costs, sorted(costs))

    def test_allocate_stat_consumes_points(self):
        self.player.gain_exp(self.player.exp_to_next_level())
        before = self.player.base_stats["STR"]
        self.assertTrue(self.player.allocate_stat("STR", 3))
        self.assertEqual(self.player.base_stats["STR"], before + 3)
        self.assertEqual(self.player.unspent_stat_points, 2)

    def test_cannot_overspend_stat_points(self):
        self.assertFalse(self.player.allocate_stat("STR", 99))

    def test_level_up_raises_max_hp(self):
        before = self.player.max_hp
        self.player.gain_exp(1_000_000)
        self.assertGreater(self.player.max_hp, before)

    def test_learn_skill_requires_points(self):
        skill = self.game.skills.require("toughness")
        ok, reason = self.player.learn_skill(skill)
        self.assertFalse(ok)
        self.assertIn("skill points", reason.lower())

    def test_learn_skill_applies_passive_modifiers(self):
        self.player.unspent_skill_points = 5
        before = self.player.max_hp
        ok, _ = self.player.learn_skill(self.game.skills.require("toughness"))
        self.assertTrue(ok)
        self.assertEqual(self.player.max_hp, before + 25)

    def test_prerequisites_block_learning(self):
        gated = Skill.from_dict({"id": "gated", "name": "Gated", "prerequisites": ["nope"]})
        self.player.unspent_skill_points = 9
        ok, reason = self.player.learn_skill(gated)
        self.assertFalse(ok)
        self.assertIn("requires", reason.lower())

    def test_required_level_blocks_learning(self):
        self.player.unspent_skill_points = 9
        ok, _ = self.player.learn_skill(self.game.skills.require("whirlwind"))
        self.assertFalse(ok)

    def test_cannot_learn_same_skill_twice(self):
        self.player.unspent_skill_points = 9
        skill = self.game.skills.require("toughness")
        self.assertTrue(self.player.learn_skill(skill)[0])
        self.assertFalse(self.player.learn_skill(skill)[0])


# ======================================================================
class TestEquipment(unittest.TestCase):
    """Slots, stat contribution, and swap behaviour."""

    def setUp(self):
        self.game = new_game(seed=51)
        self.game.create_character("Tester", "male", "squire")
        self.player = self.game.player

    def test_equipping_raises_stats(self):
        self.player.unequip("weapon")
        before = self.player.derived_stats().physical_power
        self.game.items.grant(self.player.inventory, "steel_sword", 1)
        self.player.level = 20
        self.player.equip(self.game.items.require("steel_sword"))
        self.assertGreater(self.player.derived_stats().physical_power, before)

    def test_swapping_returns_old_item_to_inventory(self):
        self.game.items.grant(self.player.inventory, "iron_mace", 1)
        self.player.equip(self.game.items.require("iron_mace"))
        self.assertTrue(self.player.inventory.has("iron_sword"))
        self.assertEqual(self.player.equipment["weapon"].id, "iron_mace")

    def test_class_weapon_restriction_enforced(self):
        self.game.items.grant(self.player.inventory, "apprentice_staff", 1)
        ok, reason = self.player.equip(self.game.items.require("apprentice_staff"))
        self.assertFalse(ok)
        self.assertIn("cannot wield", reason.lower())

    def test_level_requirement_enforced(self):
        self.game.items.grant(self.player.inventory, "steel_sword", 1)
        ok, reason = self.player.equip(self.game.items.require("steel_sword"))
        self.assertFalse(ok)
        self.assertIn("level", reason.lower())

    def test_stat_requirement_enforced(self):
        self.player.level = 50
        self.game.items.grant(self.player.inventory, "battle_axe", 1)
        ok, reason = self.player.equip(self.game.items.require("battle_axe"))
        self.assertFalse(ok)
        self.assertIn("STR", reason)

    def test_unequip_returns_to_inventory(self):
        ok, _ = self.player.unequip("weapon")
        self.assertTrue(ok)
        self.assertIsNone(self.player.equipment["weapon"])
        self.assertTrue(self.player.inventory.has("iron_sword"))

    def test_weapon_skills_gated_by_equipped_weapon(self):
        self.player.unspent_skill_points = 9
        self.player.learn_skill(self.game.skills.require("cleave"))
        self.assertIn("cleave", [s.id for s in self.player.usable_skills()])
        self.player.unequip("weapon")
        self.assertNotIn("cleave", [s.id for s in self.player.usable_skills()])

    def test_equipment_never_stacks(self):
        inventory = Inventory()
        sword = self.game.items.require("iron_sword")
        inventory.add(sword, 1)
        inventory.add(sword, 1)
        self.assertEqual(len([e for e in inventory.entries if e.item.id == "iron_sword"]), 2)


# ======================================================================
class TestInventory(unittest.TestCase):
    """Stacking, capacity and gold."""

    def setUp(self):
        self.game = new_game(seed=61)
        self.inventory = Inventory(capacity=3)
        self.potion = self.game.items.require("minor_potion")

    def test_stacks_merge_up_to_stack_size(self):
        self.inventory.add(self.potion, 5)
        self.assertEqual(self.inventory.count("minor_potion"), 5)
        self.assertEqual(len(self.inventory.entries), 1)

    def test_capacity_limits_new_stacks(self):
        small = Item.from_dict({"id": "rock", "name": "Rock", "kind": "material", "stack_size": 1})
        added = self.inventory.add(small, 10)
        self.assertEqual(added, 3)
        self.assertTrue(self.inventory.is_full)

    def test_remove_is_all_or_nothing(self):
        self.inventory.add(self.potion, 2)
        self.assertFalse(self.inventory.remove("minor_potion", 5))
        self.assertEqual(self.inventory.count("minor_potion"), 2)

    def test_gold_cannot_go_negative(self):
        self.inventory.add_gold(10)
        self.assertFalse(self.inventory.spend_gold(50))
        self.assertEqual(self.inventory.gold, 10)

    def test_has_all_accepts_mapping_and_list(self):
        self.inventory.add(self.potion, 3)
        self.assertTrue(self.inventory.has_all({"minor_potion": 2}))
        self.assertTrue(self.inventory.has_all(["minor_potion"]))
        self.assertFalse(self.inventory.has_all({"minor_potion": 9}))

    def test_consumable_use_removes_one(self):
        game = new_game(seed=62)
        game.create_character("Tester", "male", "squire")
        game.player.current_hp = 10
        before = game.player.inventory.count("minor_potion")
        ok, _ = game.use_item("minor_potion")
        self.assertTrue(ok)
        self.assertEqual(game.player.inventory.count("minor_potion"), before - 1)
        self.assertGreater(game.player.current_hp, 10)

    def test_using_missing_item_fails_cleanly(self):
        game = new_game(seed=63)
        game.create_character("Tester", "male", "squire")
        ok, messages = game.use_item("elixir_of_might")
        self.assertFalse(ok)
        self.assertTrue(messages)


# ======================================================================
class TestMastery(unittest.TestCase):
    """Bible section 14: F..Master, gained by use, grants bonuses."""

    def setUp(self):
        self.book = MasteryBook(
            thresholds=[0, 100, 300], rank_bonuses={"E": {"physical_power": 1}, "D": {"physical_power": 2}}
        )

    def test_rank_order_matches_bible(self):
        self.assertEqual(MASTERY_RANKS, ("F", "E", "D", "C", "B", "A", "S", "SS", "Master"))

    def test_gain_promotes_at_threshold(self):
        rank, promoted = self.book.gain("sword", 100)
        self.assertEqual(rank, "E")
        self.assertEqual(promoted, "E")

    def test_no_promotion_below_threshold(self):
        _, promoted = self.book.gain("sword", 50)
        self.assertIsNone(promoted)

    def test_rank_comparison(self):
        self.assertTrue(rank_at_least("S", "B"))
        self.assertFalse(rank_at_least("D", "A"))
        self.assertTrue(rank_at_least("Master", "Master"))

    def test_bonuses_accumulate_across_ranks(self):
        self.book.gain("sword", 300)
        self.assertEqual(self.book.modifiers().flat["physical_power"], 3)

    def test_meets_requirements(self):
        self.book.gain("sword", 300)
        self.assertTrue(self.book.meets({"sword": "D"}))
        self.assertFalse(self.book.meets({"sword": "A"}))

    def test_highest_rank_across_tracks(self):
        self.book.gain("sword", 300)
        self.book.gain("axe", 100)
        self.assertEqual(self.book.highest_rank(), "D")

    def test_round_trip(self):
        self.book.gain("sword", 250)
        restored = MasteryBook(thresholds=[0, 100, 300])
        restored.load_dict(self.book.to_dict())
        self.assertEqual(restored.exp_of("sword"), 250)

    def test_combat_trains_weapon_mastery(self):
        game = new_game(seed=71)
        game.create_character("Tester", "male", "squire")
        battle = game.start_battle([("green_slime", 1)])
        if battle.waiting_for_player:
            battle.player_attack(battle.living_enemies[0])
        self.assertGreater(game.player.mastery.exp_of("sword"), 0)


# ======================================================================
class TestClassesAndPromotion(unittest.TestCase):
    """Bible section 10: gender restriction, 7 tiers, promotion rules."""

    def setUp(self):
        self.game = new_game(seed=81)

    def test_seven_tiers_exist_in_content(self):
        tiers = {c.tier for c in self.game.classes.all_classes()}
        self.assertEqual(tiers, {1, 2, 3, 4, 5, 6, 7})

    def test_gender_restricted_starting_classes(self):
        male_ids = {c.id for c in self.game.classes.starting_classes("male")}
        female_ids = {c.id for c in self.game.classes.starting_classes("female")}
        self.assertIn("squire", male_ids)
        self.assertNotIn("squire", female_ids)
        self.assertIn("maiden", female_ids)
        self.assertNotIn("maiden", male_ids)
        self.assertIn("acolyte", male_ids & female_ids)

    def test_cannot_create_gender_restricted_character(self):
        ok, reason = self.game.create_character("X", "female", "squire")
        self.assertFalse(ok)
        self.assertIn("not available", reason.lower())

    def test_promotion_blocked_when_requirements_unmet(self):
        self.game.create_character("Tester", "male", "squire")
        ok, messages = self.game.promote("knight")
        self.assertFalse(ok)
        self.assertTrue(messages)

    def test_promotion_checklist_reports_each_requirement(self):
        self.game.create_character("Tester", "male", "squire")
        checks = self.game.promotion_options()
        self.assertEqual(len(checks), 3)  # Squire now has 3 promotion paths
        for check in checks:
            self.assertFalse(check.eligible)
            self.assertTrue(check.unmet)

    def test_successful_promotion_swaps_core_keeps_learned(self):
        self.game.create_character("Tester", "male", "squire")
        player = self.game.player
        player.gain_exp(500_000)
        player.level = 15
        player.allocated_stats["STR"] = 40
        player.allocated_stats["END"] = 40
        player._recalculate_base_stats()
        player.mastery.gain("sword", 5000)
        self.game.items.grant(player.inventory, "knights_seal", 1)
        player.inventory.add_gold(1000)

        player.unspent_skill_points = 5
        player.learn_skill(self.game.skills.require("toughness"))

        ok, messages = self.game.promote("knight")
        self.assertTrue(ok, messages)
        self.assertEqual(player.class_def.id, "knight")
        # Learned non-core skill survives; old core is replaced.
        self.assertIn("toughness", player.known_skills)
        self.assertNotIn("strike", player.known_skills)
        self.assertIn("smite", player.known_skills)
        self.assertFalse(player.inventory.has("knights_seal"))

    def test_promotion_consumes_gold(self):
        self.game.create_character("Tester", "male", "squire")
        player = self.game.player
        player.level = 15
        player.allocated_stats["STR"] = 40
        player.allocated_stats["END"] = 40
        player._recalculate_base_stats()
        player.mastery.gain("sword", 5000)
        self.game.items.grant(player.inventory, "knights_seal", 1)
        player.inventory.gold = 500
        self.game.promote("knight")
        self.assertEqual(player.inventory.gold, 300)

    def test_quest_requirement_is_enforced(self):
        definition = ClassDefinition(id="a", name="A", tier=1)
        definition.promotions["b"] = PromotionRequirement(level=1, quests=["q1"])
        check = definition.check_promotion(
            "b", level=5, stats=StatBlock(), mastery=MasteryBook(), inventory=Inventory(), completed_quests=[]
        )
        self.assertFalse(check.eligible)

    def test_missing_inventory_is_flagged_not_ignored(self):
        """ENGINE_DESIGN.md: flag unenforced requirements rather than dropping them."""
        definition = ClassDefinition(id="a", name="A", tier=1)
        definition.promotions["b"] = PromotionRequirement(level=1, items={"orb": 1})
        check = definition.check_promotion(
            "b", level=5, stats=StatBlock(), mastery=MasteryBook(), inventory=None, completed_quests=[]
        )
        self.assertTrue(check.unenforced)
        self.assertIn("not enforced", check.unenforced[0])

    def test_ultimates_locked_until_unlock_level(self):
        paladin = self.game.classes.require("paladin")
        self.assertEqual(paladin.unlocked_ultimates(10), [])
        self.assertIn("divine_judgment", paladin.unlocked_ultimates(30))

    def test_promotion_target_must_be_higher_tier(self):
        self.assertGreater(
            self.game.classes.require("knight").tier, self.game.classes.require("squire").tier
        )

    def test_every_promotion_chain_reaches_tier_seven(self):
        """Walking any starter's promotion chain must terminate at tier 7."""
        for starter in self.game.classes.starting_classes():
            current = starter
            seen = {current.id}
            while current.promotions:
                target_id = next(iter(current.promotions))
                self.assertNotIn(target_id, seen, "promotion cycle detected")
                seen.add(target_id)
                current = self.game.classes.require(target_id)
            self.assertEqual(current.tier, 7, f"{starter.id} chain ends at tier {current.tier}")


# ======================================================================
class TestEnemiesAndAI(unittest.TestCase):
    """Spawning, scaling, loot and the AI registry."""

    def setUp(self):
        self.game = new_game(seed=91)

    def test_spawn_scales_with_level(self):
        low = self.game.enemies.spawn("grey_wolf", 3)
        high = self.game.enemies.spawn("grey_wolf", 20)
        self.assertGreater(high.max_hp, low.max_hp)

    def test_rewards_scale_with_level(self):
        low_exp, low_gold = self.game.enemies.spawn("grey_wolf", 3).rewards()
        high_exp, high_gold = self.game.enemies.spawn("grey_wolf", 20).rewards()
        self.assertGreater(high_exp, low_exp)
        self.assertGreater(high_gold, low_gold)

    def test_spawn_group_labels_duplicates(self):
        group = self.game.enemies.spawn_group([("green_slime", 1)] * 3)
        self.assertEqual([e.name for e in group], ["Green Slime A", "Green Slime B", "Green Slime C"])

    def test_single_spawn_has_no_suffix(self):
        self.assertEqual(self.game.enemies.spawn_group([("green_slime", 1)])[0].name, "Green Slime")

    def test_unknown_template_raises(self):
        with self.assertRaises(ContentError):
            self.game.enemies.spawn("does_not_exist", 1)

    def test_guaranteed_loot_always_drops(self):
        chief = self.game.enemies.spawn("bandit_chief", 9)
        drops = dict(chief.roll_loot(GameRandom(1)))
        self.assertIn("knights_seal", drops)

    def test_all_ai_behaviors_registered(self):
        registry = default_registry()
        self.assertEqual(
            set(registry.ids()), {"aggressive", "opportunist", "tactical", "defensive", "berserk"}
        )

    def test_unknown_behavior_falls_back(self):
        self.assertEqual(default_registry().get("nonsense").id, "aggressive")

    def test_every_enemy_ai_id_is_registered(self):
        registry = default_registry()
        for template in self.game.enemies.all_templates():
            self.assertIn(template.ai_behavior_id, registry.ids(), template.id)

    def test_stunned_actor_passes_turn(self):
        enemy = self.game.enemies.spawn("green_slime", 1)
        enemy.apply_status(self.game.skills.get_status("stunned").clone())
        game_player = new_game(seed=92)
        game_player.create_character("T", "male", "squire")
        decision = default_registry().get("aggressive").decide(
            enemy, [enemy], [game_player.player], GameRandom(1)
        )
        self.assertTrue(decision.pass_turn)
        self.assertEqual(decision.note, "stunned")

    def test_opportunist_targets_lowest_hp(self):
        game = new_game(seed=93)
        game.create_character("T", "male", "squire")
        wolf = game.enemies.spawn("grey_wolf", 3)
        weak = game.enemies.spawn("green_slime", 1)
        weak.current_hp = 1
        strong = game.enemies.spawn("green_slime", 1)
        decision = default_registry().get("opportunist").decide(wolf, [wolf], [strong, weak], GameRandom(1))
        self.assertEqual(decision.targets, [weak])


# ======================================================================
class TestCombatLoop(unittest.TestCase):
    """Battle: turn order, victory/defeat, flee, rewards."""

    def setUp(self):
        self.game = new_game(seed=101)
        self.game.create_character("Hero", "male", "squire")
        self.player = self.game.player

    def _resolve(self, battle: Battle, max_turns: int = 200) -> Battle:
        turns = 0
        while not battle.is_over and turns < max_turns:
            if battle.waiting_for_player:
                targets = battle.living_enemies
                battle.player_attack(targets[0] if targets else None)
            battle.run_until_player_turn()
            turns += 1
        return battle

    def test_victory_against_weak_enemy(self):
        battle = self.game.start_battle([("green_slime", 1)])
        self._resolve(battle)
        self.assertEqual(battle.state, CombatState.VICTORY)

    def test_defeat_against_overwhelming_enemy(self):
        battle = self.game.start_battle([("shadow_warden", 60)])
        self._resolve(battle)
        self.assertEqual(battle.state, CombatState.DEFEAT)

    def test_victory_grants_exp_and_gold(self):
        before_gold = self.player.inventory.gold
        battle = self.game.start_battle([("green_slime", 1)])
        self._resolve(battle)
        self.assertGreater(battle.rewards.exp, 0)
        self.assertGreater(self.player.inventory.gold, before_gold)

    def test_turn_order_is_speed_sorted(self):
        battle = self.game.start_battle([("green_slime", 1)])
        speeds = [c.derived_stats().speed for c in battle.turn_order]
        self.assertEqual(speeds, sorted(speeds, reverse=True))

    def test_defend_reduces_incoming_damage(self):
        battle = self.game.start_battle([("green_slime", 1)])
        base_armor = self.player.derived_stats().armor
        if battle.waiting_for_player:
            battle.player_defend()
        self.assertGreater(self.player.derived_stats().armor, base_armor)

    def test_cannot_flee_from_boss(self):
        battle = self.game.start_battle([("bandit_chief", 9)])
        if battle.waiting_for_player:
            self.assertFalse(battle.player_flee())
        self.assertNotEqual(battle.state, CombatState.FLED)

    def test_flee_eventually_succeeds_from_normal_enemy(self):
        for seed in range(40):
            game = new_game(seed=seed)
            game.create_character("Hero", "male", "squire")
            battle = game.start_battle([("green_slime", 1)])
            if battle.waiting_for_player and battle.player_flee():
                self.assertEqual(battle.state, CombatState.FLED)
                return
        self.fail("fleeing never succeeded in 40 attempts")

    def test_defeat_respawns_at_inn_fully_healed(self):
        battle = self.game.start_battle([("shadow_warden", 60)])
        self._resolve(battle)
        self.game.finish_battle()
        self.assertTrue(self.player.is_alive)
        self.assertEqual(self.player.current_hp, float(self.player.max_hp))
        self.assertEqual(self.game.world.current_area_id, "town_ashvale")

    def test_battle_statuses_cleared_after_battle(self):
        battle = self.game.start_battle([("green_slime", 1)])
        if battle.waiting_for_player:
            battle.player_defend()
        self._resolve(battle)
        self.game.finish_battle()
        self.assertEqual(self.player.statuses, [])

    def test_loot_reaches_inventory(self):
        for seed in range(40):
            game = new_game(seed=seed)
            game.create_character("Hero", "male", "squire")
            battle = game.start_battle([("green_slime", 1)])
            self._resolve(battle)
            if battle.state == CombatState.VICTORY and battle.rewards.items:
                before = sum(e.quantity for e in game.player.inventory.entries)
                game.finish_battle()
                after = sum(e.quantity for e in game.player.inventory.entries)
                self.assertGreater(after, before)
                return
        self.fail("no loot dropped in 40 battles")

    def test_multi_enemy_battle_resolves(self):
        battle = self.game.start_battle([("green_slime", 1), ("field_rat", 1)])
        self._resolve(battle)
        self.assertTrue(battle.is_over)

    def test_ensure_finished_reconciles_indirect_last_enemy_defeat(self):
        battle = self.game.start_battle([("green_slime", 1)])
        battle.enemies[0].current_hp = 0
        self.assertTrue(battle.ensure_finished())
        self.assertEqual(battle.state, CombatState.VICTORY)
        self.assertGreater(battle.rewards.exp, 0)

    def test_combat_log_is_populated(self):
        battle = self.game.start_battle([("green_slime", 1)])
        self._resolve(battle)
        self.assertGreater(len(battle.log), 3)

    def test_finish_battle_is_idempotent(self):
        battle = self.game.start_battle([("green_slime", 1)])
        self._resolve(battle)
        self.game.finish_battle()
        self.assertEqual(self.game.finish_battle(), [])

    def test_battle_terminates_with_pacifist_player(self):
        """Even if the player never attacks, the loop must not hang."""
        battle = self.game.start_battle([("green_slime", 1)])
        for _ in range(300):
            if battle.is_over:
                break
            if battle.waiting_for_player:
                battle.player_defend()
            battle.run_until_player_turn()
        self.assertTrue(battle.is_over)


# ======================================================================
class TestWorld(unittest.TestCase):
    """Travel, exploration, day cycle."""

    def setUp(self):
        self.game = new_game(seed=111)
        self.game.create_character("Hero", "male", "squire")

    def test_starts_in_town(self):
        self.assertTrue(self.game.world.is_in_town())

    def test_cannot_explore_in_town(self):
        message, battle = self.game.explore()
        self.assertIsNone(battle)
        self.assertIn("peaceful", message.lower())

    def test_travel_to_connected_area(self):
        ok, _ = self.game.travel_to("greenfields")
        self.assertTrue(ok)
        self.assertEqual(self.game.world.current_area_id, "greenfields")

    def test_cannot_travel_to_unconnected_area(self):
        ok, _ = self.game.travel_to("sunken_shrine")
        self.assertFalse(ok)

    def test_level_gated_area_hidden(self):
        options = {a.id for a in self.game.travel_options()}
        self.assertNotIn("old_road", options)
        self.game.player.level = 10
        self.assertIn("old_road", {a.id for a in self.game.travel_options()})

    def test_exploration_eventually_finds_an_encounter(self):
        self.game.travel_to("greenfields")
        for _ in range(60):
            _, battle = self.game.explore()
            if battle is not None:
                self.assertTrue(battle.living_enemies)
                return
        self.fail("no encounter in 60 exploration steps")

    def test_rest_advances_day_and_heals(self):
        self.game.player.current_hp = 1
        self.game.player.inventory.add_gold(100)
        ok, lines = self.game.rest_at_inn()
        self.assertTrue(ok, lines)
        self.assertEqual(self.game.world.day, 2)
        self.assertEqual(self.game.player.current_hp, float(self.game.player.max_hp))

    def test_rest_requires_gold(self):
        self.game.player.inventory.gold = 0
        ok, _ = self.game.rest_at_inn()
        self.assertFalse(ok)

    def test_cannot_rest_outside_town(self):
        self.game.travel_to("greenfields")
        ok, _ = self.game.rest_at_inn()
        self.assertFalse(ok)

    def test_rest_triggers_autosave(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = new_game(seed=112, save_dir=tmp)
            game.create_character("Hero", "male", "squire")
            game.player.inventory.add_gold(100)
            ok, lines = game.rest_at_inn()
            self.assertTrue(ok)
            self.assertTrue(any("autosave" in line.lower() for line in lines))
            self.assertTrue(game.save_slots())


# ======================================================================
class TestShopsAndNPCs(unittest.TestCase):
    """Buying, selling, affinity and marriage (bible section 15)."""

    def setUp(self):
        self.game = new_game(seed=121)
        self.game.create_character("Hero", "male", "squire")

    def test_buy_deducts_gold_and_adds_item(self):
        self.game.player.inventory.gold = 1000
        ok, _ = self.game.buy_item("ashvale_general", "potion")
        self.assertTrue(ok)
        self.assertTrue(self.game.player.inventory.has("potion"))
        self.assertLess(self.game.player.inventory.gold, 1000)

    def test_cannot_buy_without_gold(self):
        self.game.player.inventory.gold = 0
        ok, _ = self.game.buy_item("ashvale_general", "potion")
        self.assertFalse(ok)

    def test_cannot_buy_item_not_in_stock(self):
        self.game.player.inventory.gold = 100000
        ok, _ = self.game.buy_item("ashvale_general", "shadow_fang")
        self.assertFalse(ok)

    def test_sell_adds_gold_and_removes_item(self):
        before = self.game.player.inventory.gold
        ok, _ = self.game.sell_item("ashvale_general", "minor_potion")
        self.assertTrue(ok)
        self.assertGreater(self.game.player.inventory.gold, before)

    def test_talking_raises_affinity(self):
        ok, _ = self.game.talk_to("innkeeper_mara")
        self.assertTrue(ok)
        self.assertGreater(self.game.player.affinity_with("innkeeper_mara"), 0)

    def test_liked_gift_gives_more_affinity(self):
        self.game.items.grant(self.game.player.inventory, "wolf_pelt", 1)
        self.game.items.grant(self.game.player.inventory, "slime_core", 1)
        self.game.give_gift("innkeeper_mara", "wolf_pelt")
        liked = self.game.player.affinity_with("innkeeper_mara")
        self.game.give_gift("innkeeper_mara", "slime_core")
        total = self.game.player.affinity_with("innkeeper_mara")
        self.assertGreater(liked, total - liked)

    def test_marriage_requires_affinity_and_item(self):
        ok, reason = self.game.can_marry("innkeeper_mara")
        self.assertFalse(ok)
        self.game.player.affinity["innkeeper_mara"] = 100
        ok, reason = self.game.can_marry("innkeeper_mara")
        self.assertFalse(ok)
        self.assertIn("Eternal Band", reason)

    def test_marriage_succeeds_and_consumes_ring(self):
        self.game.player.affinity["innkeeper_mara"] = 100
        self.game.items.grant(self.game.player.inventory, "eternal_band", 1)
        ok, _ = self.game.marry("innkeeper_mara")
        self.assertTrue(ok)
        self.assertEqual(self.game.player.spouse_id, "innkeeper_mara")
        self.assertFalse(self.game.player.inventory.has("eternal_band"))

    def test_marriage_is_gender_agnostic(self):
        """Bible section 15: marriage possible regardless of gender."""
        game = new_game(seed=122)
        game.create_character("Hero", "male", "squire")
        game.player.affinity["smith_dorn"] = 100
        game.items.grant(game.player.inventory, "eternal_band", 1)
        ok, _ = game.marry("smith_dorn")
        self.assertTrue(ok)

    def test_cannot_marry_twice(self):
        self.game.player.affinity["innkeeper_mara"] = 100
        self.game.items.grant(self.game.player.inventory, "eternal_band", 2)
        self.game.marry("innkeeper_mara")
        self.game.player.affinity["smith_dorn"] = 100
        ok, _ = self.game.marry("smith_dorn")
        self.assertFalse(ok)


# ======================================================================
class TestSaveLoad(unittest.TestCase):
    """Bible section 16 + the backwards-compatibility rule in section 5."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.save_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _prepared_game(self) -> Game:
        game = new_game(seed=131, save_dir=self.save_dir)
        game.create_character("Aria", "female", "maiden")
        player = game.player
        player.gain_exp(400)
        player.allocate_stat("AGI", 2)
        player.unspent_skill_points = 3
        player.learn_skill(game.skills.require("fleet_footed"))
        player.mastery.gain("dagger", 350)
        player.change_affinity("innkeeper_mara", 25)
        player.complete_quest("tutorial")
        game.items.grant(player.inventory, "potion", 4)
        game.travel_to("greenfields")
        return game

    def test_round_trip_preserves_everything(self):
        game = self._prepared_game()
        original = game.player
        ok, _ = game.save_game("slot_a")
        self.assertTrue(ok)

        fresh = new_game(seed=999, save_dir=self.save_dir)
        ok, _ = fresh.load_game("slot_a")
        self.assertTrue(ok)
        loaded = fresh.player

        self.assertEqual(loaded.name, original.name)
        self.assertEqual(loaded.gender, original.gender)
        self.assertEqual(loaded.level, original.level)
        self.assertAlmostEqual(loaded.exp, original.exp)
        self.assertEqual(loaded.class_def.id, original.class_def.id)
        self.assertEqual(loaded.base_stats.to_dict(), original.base_stats.to_dict())
        self.assertEqual(set(loaded.known_skills), set(original.known_skills))
        self.assertEqual(loaded.inventory.gold, original.inventory.gold)
        self.assertEqual(loaded.inventory.count("potion"), original.inventory.count("potion"))
        self.assertEqual(loaded.mastery.exp_of("dagger"), original.mastery.exp_of("dagger"))
        self.assertEqual(loaded.affinity, original.affinity)
        self.assertEqual(loaded.completed_quests, original.completed_quests)
        self.assertEqual(loaded.max_hp, original.max_hp)
        self.assertEqual(fresh.world.current_area_id, game.world.current_area_id)
        self.assertEqual(fresh.world.day, game.world.day)

    def test_equipment_survives_round_trip(self):
        game = self._prepared_game()
        game.save_game("slot_eq")
        fresh = new_game(seed=1, save_dir=self.save_dir)
        fresh.load_game("slot_eq")
        self.assertEqual(
            {s: (i.id if i else None) for s, i in fresh.player.equipment.items()},
            {s: (i.id if i else None) for s, i in game.player.equipment.items()},
        )

    def test_statuses_survive_round_trip(self):
        game = self._prepared_game()
        game.player.apply_status(game.skills.get_status("poison").clone())
        game.save_game("slot_status")
        fresh = new_game(seed=1, save_dir=self.save_dir)
        fresh.load_game("slot_status")
        self.assertTrue(fresh.player.has_status("poison"))

    def test_rng_state_survives_round_trip(self):
        game = self._prepared_game()
        game.save_game("slot_rng")
        expected = [game.rng.randint(0, 10_000) for _ in range(10)]

        fresh = new_game(seed=1, save_dir=self.save_dir)
        fresh.load_game("slot_rng")
        self.assertEqual([fresh.rng.randint(0, 10_000) for _ in range(10)], expected)

    def test_multiple_slots_are_independent(self):
        game = self._prepared_game()
        game.save_game("slot_one")
        game.player.inventory.add_gold(5000)
        game.save_game("slot_two")

        fresh = new_game(seed=1, save_dir=self.save_dir)
        fresh.load_game("slot_one")
        first_gold = fresh.player.inventory.gold
        fresh.load_game("slot_two")
        self.assertEqual(fresh.player.inventory.gold, first_gold + 5000)

    def test_slot_listing_metadata(self):
        game = self._prepared_game()
        game.save_game("slot_meta")
        info = next(i for i in game.save_slots() if i.slot == "slot_meta")
        self.assertEqual(info.character_name, "Aria")
        self.assertEqual(info.class_name, "Maiden")
        self.assertFalse(info.corrupt)
        self.assertTrue(info.detail_lines())

    def test_delete_removes_slot(self):
        game = self._prepared_game()
        game.save_game("slot_del")
        ok, _ = game.delete_save("slot_del")
        self.assertTrue(ok)
        self.assertNotIn("slot_del", [i.slot for i in game.save_slots()])

    def test_corrupt_save_is_reported_not_crashed(self):
        (self.save_dir / "broken.json").write_text("{not json", encoding="utf-8")
        manager = SaveManager(self.save_dir)
        info = next(i for i in manager.list_slots() if i.slot == "broken")
        self.assertTrue(info.corrupt)
        self.assertIsNone(manager.read("broken"))

    def test_loading_missing_slot_fails_gracefully(self):
        game = new_game(seed=1, save_dir=self.save_dir)
        ok, message = game.load_game("nope")
        self.assertFalse(ok)
        self.assertTrue(message)

    def test_v1_save_migrates_forward(self):
        """Bible section 5: preserve backwards compatibility."""
        game = self._prepared_game()
        game.save_game("legacy")

        import json

        path = self.save_dir / "legacy.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["save_version"] = 1
        payload.pop("rng", None)
        payload.pop("world", None)
        for key in ("completed_quests", "affinity", "spouse_id", "flags", "class_history"):
            payload["player"].pop(key, None)
        path.write_text(json.dumps(payload), encoding="utf-8")

        fresh = new_game(seed=1, save_dir=self.save_dir)
        ok, _ = fresh.load_game("legacy")
        self.assertTrue(ok)
        self.assertEqual(fresh.player.name, "Aria")
        self.assertEqual(fresh.player.completed_quests, [])
        self.assertEqual(fresh.player.race_id, fresh.config["default_race_id"])
        self.assertEqual(fresh.world.defeated_bosses, set())

    def test_save_written_atomically_leaves_no_temp_file(self):
        game = self._prepared_game()
        game.save_game("atomic")
        self.assertEqual(list(self.save_dir.glob("*.tmp")), [])

    def test_slot_name_is_sanitised(self):
        manager = SaveManager(self.save_dir)
        path = manager.slot_path("../../evil")
        self.assertEqual(path.parent, self.save_dir)

    def test_suggest_slot_avoids_collisions(self):
        game = self._prepared_game()
        first = game.saves.suggest_slot("Aria")
        game.save_game(first)
        self.assertNotEqual(game.saves.suggest_slot("Aria"), first)

    def test_save_version_is_stamped(self):
        game = self._prepared_game()
        game.save_game("versioned")
        self.assertEqual(game.saves.read("versioned")["save_version"], SAVE_VERSION)


# ======================================================================
class TestContentIntegrity(unittest.TestCase):
    """Every id referenced anywhere in content must resolve."""

    def setUp(self):
        self.game = new_game(seed=141)

    def test_content_loads_and_cross_validates(self):
        self.game.load_content()  # raises ContentError on any dangling id

    def test_all_content_present(self):
        self.assertGreater(self.game.classes.count(), 0)
        self.assertGreater(self.game.skills.count(), 0)
        self.assertGreater(self.game.items.count(), 0)
        self.assertGreater(self.game.enemies.count(), 0)
        self.assertGreater(self.game.world_manager.count(), 0)

    def test_every_class_core_skill_exists(self):
        for definition in self.game.classes.all_classes():
            if definition.core_skill_id:
                self.assertIsNotNone(self.game.skills.get(definition.core_skill_id), definition.id)

    def test_every_skill_status_reference_exists(self):
        from engine.skills.effects import ApplyStatusEffect

        for skill in self.game.skills.all_skills():
            for effect in skill.effects:
                if isinstance(effect, ApplyStatusEffect):
                    self.assertIsNotNone(self.game.skills.get_status(effect.status_id), skill.id)

    def test_every_area_connection_is_bidirectional_or_intentional(self):
        for area in self.game.world_manager.all_areas():
            for target_id in area.connections:
                self.assertIsNotNone(self.game.world_manager.get_area(target_id))

    def test_respawn_area_exists(self):
        self.assertIsNotNone(self.game.world_manager.get_area(self.game.config["respawn_area_id"]))

    def test_marriage_item_exists_and_is_tagged(self):
        item = self.game.items.get(self.game.config["marriage_item_id"])
        self.assertIsNotNone(item)
        self.assertTrue(item.has_tag("marriage"))

    def test_every_starting_class_is_playable(self):
        for definition in self.game.classes.starting_classes():
            game = new_game(seed=142)
            gender = "male" if definition.gender_restriction in ("any", "male") else "female"
            ok, message = game.create_character("Probe", gender, definition.id)
            self.assertTrue(ok, f"{definition.id}: {message}")
            self.assertTrue(game.player.usable_skills(), definition.id)
            self.assertGreater(game.player.max_hp, 0)

    def test_missing_required_file_raises_content_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ContentError):
                DataLoader(tmp).load("config.json")

    def test_malformed_json_raises_content_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "bad.json").write_text("{oops", encoding="utf-8")
            with self.assertRaises(ContentError):
                DataLoader(tmp).load("bad.json")

    def test_data_loader_caches(self):
        loader = DataLoader(PROJECT_ROOT / "data")
        self.assertIs(loader.load("config.json"), loader.load("config.json"))


# ======================================================================
class TestArchitecturalConstraints(unittest.TestCase):
    """Guards on the rules the design documents actually state."""

    def test_gui_never_imports_managers_directly(self):
        """Bible section 5/18: UI holds no gameplay logic."""
        gui_dir = PROJECT_ROOT / "gui"
        if not gui_dir.is_dir():
            self.skipTest("gui package not present")
        offenders = []
        for path in gui_dir.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for banned in (
                "from engine.managers",
                "import engine.managers",
                "from engine.combat.combat import",
                "SkillManager(",
                "EnemyManager(",
                "ClassManager(",
                "ItemManager(",
                "DataLoader(",
                "json.load",
            ):
                if banned in text:
                    offenders.append(f"{path.name}: {banned}")
        self.assertEqual(offenders, [], "GUI must only talk to engine.game.Game")

    def test_one_class_per_content_type(self):
        """ENGINE_DESIGN.md: class count scales with behaviour, not content."""
        from engine.classes import ClassDefinition as CD
        from engine.entities.enemy import Enemy
        from engine.skills.skill import Skill as S

        game = new_game(seed=151)
        self.assertTrue(all(type(s) is S for s in game.skills.all_skills()))
        self.assertTrue(all(type(c) is CD for c in game.classes.all_classes()))
        self.assertIs(type(game.enemies.spawn("green_slime", 1)), Enemy)

    def test_no_hardcoded_content_ids_in_engine_logic(self):
        """No `if skill.id == "fireball"` style special-casing.

        Parsed via ``ast`` rather than plain text search so that docstrings and
        comments explaining the rule are not themselves flagged - only string
        literals that real code evaluates count.
        """
        import ast

        content_ids = {
            "fireball",
            "power_strike",
            "green_slime",
            "squire",
            "iron_sword",
            "town_ashvale",
            "poison",
        }

        def docstring_nodes(tree: ast.AST) -> set[int]:
            """ids() of Constant nodes that are docstrings, to be skipped."""
            skip: set[int] = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = getattr(node, "body", [])
                    if (
                        body
                        and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)
                    ):
                        skip.add(id(body[0].value))
            return skip

        offenders = []
        for path in (PROJECT_ROOT / "engine").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            skip = docstring_nodes(tree)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and id(node) not in skip
                    and node.value in content_ids
                ):
                    offenders.append(f"{path.name}:{node.lineno}: {node.value!r}")
        self.assertEqual(offenders, [], "engine must not reference specific content ids")

    def test_formulas_come_from_config_not_code(self):
        game = new_game(seed=152)
        tweaked = Formulas.from_dict({**game.config["formulas"], "hp": {"base": 1000}})
        self.assertEqual(tweaked.derive(StatBlock(), 1).max_hp, 1000)

    def test_effect_registry_is_extensible(self):
        self.assertGreaterEqual(len(known_effect_types()), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
