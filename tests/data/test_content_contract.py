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
