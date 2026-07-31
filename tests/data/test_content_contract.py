"""Fast contract checks for the JSON content pipeline.

These tests deliberately validate data at the boundary: raw JSON must parse,
all required content documents must remain present, and the real ``Game``
facade must cross-validate their references.  Gameplay behaviour belongs in
``tests/logic`` or ``tests/integration`` instead.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.game import Game

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

#: Every document loaded by the game at startup.  Additional JSON files are
#: welcome; this guard only catches an accidental deletion or rename.
REQUIRED_DOCUMENTS = {
    "banter.json",
    "classes.json",
    "companions.json",
    "config.json",
    "dialogues.json",
    "enchantments.json",
    "enemies.json",
    "factions.json",
    "items.json",
    "quests.json",
    "races.json",
    "skills.json",
    "statuses.json",
    "world.json",
}


class TestContentFileContract(unittest.TestCase):
    def test_required_documents_are_present(self):
        available = {path.name for path in DATA_DIR.glob("*.json")}
        self.assertTrue(REQUIRED_DOCUMENTS <= available, REQUIRED_DOCUMENTS - available)

    def test_every_content_document_is_valid_json(self):
        for path in sorted(DATA_DIR.glob("*.json")):
            with self.subTest(document=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(payload, (dict, list))

    def test_game_cross_validates_the_complete_content_graph(self):
        """Missing ids and invalid cross-references must fail during startup."""
        game = Game(data_dir=DATA_DIR, seed=3030)
        game.load_content()
        self.assertGreater(game.classes.count(), 0)
        self.assertGreater(game.skills.count(), 0)
        self.assertGreater(len(game.world_manager.create_world().areas), 0)


class TestAncestryPresentationContract(unittest.TestCase):
    """Every selectable ancestry must have named mechanics and readable lore."""

    @classmethod
    def setUpClass(cls):
        cls.game = Game(data_dir=DATA_DIR, seed=3031)
        cls.game.load_content()

    def test_races_and_lineages_have_descriptive_traits(self):
        for race in self.game.race_options():
            with self.subTest(race=race.id):
                self.assertTrue(race.description)
                self.assertTrue(race.traits)
                self.assertTrue(all(":" in trait for trait in race.traits))
            for lineage in race.sub_races:
                with self.subTest(race=race.id, lineage=lineage.id):
                    self.assertTrue(lineage.description)
                    self.assertTrue(lineage.bonus_traits)
                    self.assertTrue(all(":" in trait for trait in lineage.bonus_traits))

    def test_every_race_and_lineage_has_a_named_gated_technique(self):
        names: set[str] = set()
        descriptions: set[str] = set()
        mechanics: set[str] = set()
        for race in self.game.race_options():
            ancestry = self.game.skills.require(race.racial_skill_id)
            with self.subTest(race=race.id, scope="ancestry"):
                self.assertFalse(ancestry.required_sub_race_ids)
                self.assertIn(race.id, ancestry.required_race_ids)
                self.assertTrue(ancestry.description)
                self.assertFalse(ancestry.name.endswith(" Gift"))
            names.add(ancestry.name)
            descriptions.add(ancestry.description)
            mechanics.add(
                json.dumps(
                    {
                        "targeting": ancestry.targeting,
                        "mp_cost": ancestry.mp_cost,
                        "sp_cost": ancestry.sp_cost,
                        "cooldown": ancestry.cooldown,
                        "effects": [effect.describe() for effect in ancestry.effects],
                    },
                    sort_keys=True,
                )
            )

            for lineage in race.sub_races:
                technique = self.game.skills.require(lineage.racial_skill_id)
                with self.subTest(race=race.id, lineage=lineage.id):
                    self.assertIn(race.id, technique.required_race_ids)
                    self.assertIn(lineage.id, technique.required_sub_race_ids)
                    self.assertTrue(technique.description)
                    self.assertFalse(technique.name.endswith(" Gift"))
                names.add(technique.name)
                descriptions.add(technique.description)
                mechanics.add(
                    json.dumps(
                        {
                            "targeting": technique.targeting,
                            "mp_cost": technique.mp_cost,
                            "sp_cost": technique.sp_cost,
                            "cooldown": technique.cooldown,
                            "effects": [effect.describe() for effect in technique.effects],
                        },
                        sort_keys=True,
                    )
                )

        expected_total = sum(1 + len(race.sub_races) for race in self.game.race_options())
        self.assertEqual(len(names), expected_total)
        self.assertEqual(len(descriptions), expected_total)
        self.assertEqual(len(mechanics), expected_total)

    def test_every_race_has_a_three_chapter_heritage_chain_and_upgrade_path(self):
        world = self.game.world_manager.create_world()
        actions = [action for area in world.areas.values() for action in area.ancestry_actions]
        for race in self.game.race_options():
            awakening_id = f"heritage_{race.id}_awakening"
            choice_id = f"heritage_{race.id}_choice"
            ascension_id = f"heritage_{race.id}_ascension"
            awakening = self.game.quests.require(awakening_id)
            choice = self.game.quests.require(choice_id)
            ascension = self.game.quests.require(ascension_id)
            with self.subTest(race=race.id, contract="quest chain"):
                self.assertIn(race.id, awakening.required_race_ids)
                self.assertIn(awakening.giver_id, world.areas[awakening.start_area_id].npc_ids)
                self.assertEqual(choice.prerequisite_quest_ids, (awakening_id,))
                self.assertEqual(ascension.prerequisite_quest_ids, (choice_id,))
                self.assertTrue(any(action.required_active_quest_id == choice_id for action in actions))
                self.assertTrue(any(action.required_active_quest_id == ascension_id for action in actions))

            for skill_id in (race.racial_skill_id, *(lineage.racial_skill_id for lineage in race.sub_races)):
                technique = self.game.skills.require(skill_id)
                with self.subTest(race=race.id, skill=skill_id):
                    self.assertEqual(len(technique.ancestry_upgrade_tiers), 3)
                    self.assertEqual(
                        [tier["required_quest_id"] for tier in technique.ancestry_upgrade_tiers],
                        [awakening_id, choice_id, ascension_id],
                    )
                    middle_tier = technique.ancestry_upgrade_tiers[1]
                    self.assertEqual(middle_tier["path_flag"], f"heritage_{race.id}_path")
                    self.assertEqual(len(middle_tier["path_add_effects"]), 2)
