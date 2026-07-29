"""Integration coverage for the v0.7 high-value systems expansion."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from engine.game import Game
from engine.skills.effects import build_effect, known_effect_types

ROOT=Path(__file__).resolve().parents[1]
def game(save_dir=None):
 g=Game(data_dir=ROOT/'data',save_dir=save_dir,seed=7070);g.load_content();g.create_character('Systems','female','maiden','tiefling');return g

class TestQuestObjectiveStrategies(unittest.TestCase):
 def test_all_generic_objectives_are_registered(self):
  g=game(); self.assertTrue({'defeat_enemy','collect_item','visit_area','talk_to','recruit_companion','travel_with_companion','equip_item_type','affinity','battle_no_downs','battle_turn_limit','choice'} <= g.quests.SUPPORTED_OBJECTIVES)
 def test_world_and_social_events_advance_objectives(self):
  g=game();g.player.accept_quest('systems_field_test')
  g.quests.record_event(g.player,'visit_area','greenfields');g.quests.record_event(g.player,'talk_to','innkeeper_mara')
  p=g.player.quest_progress['systems_field_test'];self.assertEqual(p['visit_area:greenfields'],1);self.assertEqual(p['talk_to:innkeeper_mara'],1)
 def test_collection_affinity_and_equipment_refresh_from_state(self):
  g=game();g.player.accept_quest('systems_field_test');g.items.grant(g.player.inventory,'slime_core',3);g.player.affinity['innkeeper_mara']=20
  g.refresh_quest_objectives();p=g.player.quest_progress['systems_field_test'];self.assertEqual(p['collect_item:slime_core'],3);self.assertEqual(p['affinity:innkeeper_mara'],20)

class TestDialogueAndFactions(unittest.TestCase):
 def test_dialogue_tree_filters_race_specific_options(self):
  g=game();view=g.start_dialogue('mother_sable_contract');labels=[o['text'] for o in view['options']];self.assertTrue(any('Ash Court' in x for x in labels))
 def test_dialogue_choice_applies_flags_affinity_reputation_and_exclusion(self):
  g=game();g.start_dialogue('mother_sable_contract');result=g.choose_dialogue('mother_sable_contract','sign_clause')
  self.assertEqual(g.player.flags['sable_clause'],'signed');self.assertGreater(g.player.faction_reputation['ash_court'],0);self.assertLess(g.player.faction_reputation['emberwatch_wardens'],0);self.assertTrue(result['text'])
 def test_faction_reputation_changes_shop_price(self):
  g=game();g.player.inventory.add_gold(99999);base=g.shop_price('emberwatch_outfitter','embersteel_blade');g.change_reputation('emberwatch_wardens',60);self.assertLess(g.shop_price('emberwatch_outfitter','embersteel_blade'),base)

class TestLoyaltyAndBanter(unittest.TestCase):
 def setUp(self):
  self.g=game();self.g.player.level=40;self.g.player.inventory.add_gold(99999);c=self.g.companions.create('rook',40);self.g.party.recruit(c)
 def test_loyalty_ranks_and_bonus_apply(self):
  before=self.g.party.get('rook').max_hp;self.g.change_loyalty('rook',80);self.assertEqual(self.g.loyalty_rank('rook'),'Sworn');self.assertGreater(self.g.party.get('rook').max_hp,before)
 def test_disagreement_is_temporary(self):
  self.g.companion_disagrees('rook',severity=100);self.assertFalse(self.g.party.has('rook'));self.assertFalse(self.g.can_rejoin_companion('rook'));self.g.world.day+=10;self.assertTrue(self.g.can_rejoin_companion('rook'))
 def test_contextual_banter_uses_party_and_race_conditions(self):
  lines=self.g.trigger_banter('travel',area_id='old_road');self.assertTrue(lines);self.assertTrue(any('Rook' in x for x in lines))

class TestEquipmentProgression(unittest.TestCase):
 def test_set_bonus_activates_at_piece_threshold(self):
  g=game();g.player.level=40
  for iid in ('ember_plate','ember_helm'):
   i=g.items.require(iid);g.player.inventory.add(i);g.player.equipment[i.slot]=i
  g.player.invalidate_stats();self.assertIn('Emberwatch Bulwark (2)',g.player.active_set_bonuses())
 def test_enchantment_and_upgrade_modify_equipment_stats_and_persist(self):
  with tempfile.TemporaryDirectory() as tmp:
   g=game(tmp);g.player.level=40;g.player.inventory.add_gold(99999);i=g.items.require('embersteel_blade');g.player.inventory.add(i);g.player.equipment['weapon']=i;g.player.invalidate_stats();before=g.player.derived_stats().physical_power
   self.assertTrue(g.enchant_item(i.id,'keen')[0]);self.assertTrue(g.upgrade_item(i.id)[0]);self.assertGreater(g.player.derived_stats().physical_power,before);g.save_game('gear');r=game(tmp);r.load_game('gear');self.assertIn('keen', r.player.item_enchantments[i.id]);self.assertEqual(r.player.item_upgrades[i.id],1)
   # Test multi-slot enchantments
   g2=game(tmp);g2.player.level=40;g2.player.inventory.add_gold(99999);j=g2.items.require('dawnblade');g2.player.inventory.add(j);g2.player.equipment['weapon']=j;self.assertTrue(g2.enchant_item(j.id,'keen')[0]);self.assertTrue(g2.enchant_item(j.id,'warded')[0]);self.assertEqual(len(g2.player.item_enchantments[j.id]),2)
 def test_low_health_conditional_modifier(self):
  g=game();g.player.level=40;i=g.items.require('blood_oath_ring');g.player.inventory.add(i);g.player.equipment[i.slot]=i;g.player.current_hp=g.player.max_hp*0.2;g.player.invalidate_stats();low=g.player.derived_stats().physical_power;g.player.current_hp=g.player.max_hp;g.player.invalidate_stats();self.assertGreater(low,g.player.derived_stats().physical_power)

class TestExpandedEffects(unittest.TestCase):
 def test_effect_registry_contains_new_behaviours(self):
  self.assertTrue({'life_drain','cleanse','dispel','revive','taunt','cooldown','execute','counter','status_transfer','delayed_attack'} <= set(known_effect_types()))
 def test_life_drain_heals_caster(self):
  g=game();enemy=g.enemies.spawn('green_slime',1);g.player.current_hp=max(1,g.player.current_hp-20);before=g.player.current_hp;e=build_effect({'type':'life_drain','base':20,'can_miss':False});r=e.apply(g.player,enemy,g.skills.make_context(g.rng,g.formulas));self.assertGreater(g.player.current_hp,before);self.assertEqual(r.kind,'damage')
 def test_cleanse_dispel_and_revive(self):
  g=game();ctx=g.skills.make_context(g.rng,g.formulas);poison=g.skills.get_status('poison').clone();g.player.apply_status(poison);build_effect({'type':'cleanse'}).apply(g.player,g.player,ctx);self.assertFalse(g.player.statuses)
  c=g.companions.create('rook',1);c.kill();build_effect({'type':'revive','percent_max_hp':.25}).apply(g.player,c,ctx);self.assertTrue(c.is_alive)

class TestBossFrameworkAndTactics(unittest.TestCase):
 def test_dawn_tyrant_has_data_driven_phases_and_hazard(self):
  g=game();t=g.enemies.get_template('dawn_tyrant');self.assertGreaterEqual(len(t.boss_phases),2);self.assertTrue(t.boss_rules.get('environment'))
 def test_phase_transition_changes_boss_and_logs(self):
  g=game();g.player.level=40;g.player.allocated_stats['STR']=2000;g.player.allocated_stats['END']=2000;g.player._recalculate_base_stats();g.player.restore_fully();b=g.start_battle([('dawn_tyrant',40)]);boss=b.enemies[0];boss.current_hp=boss.max_hp*.49;b.check_boss_rules();self.assertGreaterEqual(boss.boss_phase,1);self.assertTrue(any('phase' in e.text.lower() for e in b.log))
 def test_companion_tactics_persist_and_filter_ultimate_use(self):
  with tempfile.TemporaryDirectory() as tmp:
   g=game(tmp);c=g.companions.create('rook',20);g.party.recruit(c);g.set_companion_tactics('rook',{'stance':'defensive','preserve_mp':True,'ultimate_policy':'never','healing_threshold':.7});self.assertEqual(c.ai_behavior_id,'defensive');g.save_game('tactics');r=game(tmp);r.load_game('tactics');self.assertEqual(r.party.get('rook').tactics['healing_threshold'],.7)

if __name__=='__main__': unittest.main(verbosity=2)
