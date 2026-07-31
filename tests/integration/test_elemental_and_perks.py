"""Unit tests for elemental resistances, vulnerabilities, and combat perk specials (lifesteal, reflect, counter)."""
from __future__ import annotations
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.game import Game
from engine.skills.effects import build_effect

ROOT = Path(__file__).resolve().parents[2]

class TestElementalAndPerksIntegration(unittest.TestCase):
    def setUp(self):
        self.g = Game(data_dir=ROOT/'data', save_dir=None, seed=42)
        self.g.load_content()
        ok, _ = self.g.create_character('Hero', 'female', 'maiden', 'human')
        self.assertTrue(ok)

    def test_lifesteal_perk_or_special(self):
        enemy = self.g.enemies.spawn('green_slime', 1)
        original_special_effects = self.g.player.special_effects
        self.g.player.special_effects = lambda: [{'type': 'lifesteal', 'value': 0.5}]
        
        self.g.player.current_hp = 50.0
        before_hp = self.g.player.current_hp
        
        effect = build_effect({'type': 'damage', 'damage_type': 'physical', 'base': 40, 'can_miss': False})
        effect.apply(self.g.player, enemy, self.g.skills.make_context(self.g.rng, self.g.formulas))
        
        self.assertGreater(self.g.player.current_hp, before_hp)
        self.g.player.special_effects = original_special_effects

    def test_reflect_and_recursion_guard(self):
        enemy = self.g.enemies.spawn('green_slime', 1)
        status = self.g.skills.get_status('stormguard').clone()
        status.reflect_pct = 0.5
        enemy.apply_status(status)

        outcome = enemy.take_raw_damage(100, damage_type='physical', attacker=self.g.player, allow_reflect=True)
        self.assertAlmostEqual(outcome.reflected, 50.0)

    def test_counter_special(self):
        enemy = self.g.enemies.spawn('green_slime', 1)
        original_special = enemy.special_effects
        enemy.special_effects = lambda: [{'type': 'counter', 'value': 0.3}]

        player_before = self.g.player.current_hp
        enemy.take_raw_damage(50, damage_type='physical', attacker=self.g.player, allow_reflect=True)
        self.assertLess(self.g.player.current_hp, player_before)
        enemy.special_effects = original_special

    def test_elemental_resistance_and_vulnerability_multiplier(self):
        enemy = self.g.enemies.spawn('magma_sovereign', 45)
        fire_effect = build_effect({'type': 'damage', 'damage_type': 'magic', 'base': 100, 'element': 'fire', 'can_miss': False})
        res = fire_effect.apply(self.g.player, enemy, self.g.skills.make_context(self.g.rng, self.g.formulas))
        self.assertTrue(any('resists Fire' in m for m in [res.message]))

        ice_effect = build_effect({'type': 'damage', 'damage_type': 'magic', 'base': 100, 'element': 'ice', 'can_miss': False})
        res_ice = ice_effect.apply(self.g.player, enemy, self.g.skills.make_context(self.g.rng, self.g.formulas))
        self.assertTrue(any('vulnerable to Ice' in m for m in [res_ice.message]))

    def test_elemental_skill_loading(self):
        skill = self.g.skills.get('flame_blast')
        self.assertIsNotNone(skill)
        self.assertIn('fire', skill.tags)
        self.assertEqual(skill.effects[0].element, 'fire')

if __name__ == '__main__':
    unittest.main()
