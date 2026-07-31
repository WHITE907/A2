# Test Suite Guide

The suite is deliberately organised by the boundary it protects rather than by
release number.  This makes a failing command answer the first debugging
question quickly: **is this a presentation, game-rule, content, or
cross-system regression?**

```
tests/
├── data/          JSON-document and content-graph contracts
├── logic/         deterministic engine and progression rules
├── integration/   behaviour spanning multiple engine systems or persistence
├── ui/            headless Tkinter presentation and event-handler coverage
└── support/       test-only helpers (not test modules)
```

Current coverage: **472 tests**.

| Area | Owns | Start here when… |
|---|---|---|
| `data/` | JSON syntax, required data documents, cross-references, world-content contracts | a content edit fails to load, an id is renamed, or world data changes |
| `logic/` | stats, combat primitives, progression, saves, companions, quests, races, stories, and architectural rules | one engine rule has the wrong result |
| `integration/` | elemental effects, perks, equipment progression, factions, tactics, bosses, persistence, and other multi-system flows | individual pieces work but their combination does not |
| `ui/` | real screen construction, widget state, navigation, and handlers through the headless Tk stub | a screen crashes, button wiring is wrong, or rendered state is stale |
| `support/` | `tk_stub.py` and shared test-only helpers | a test needs a deterministic harness, not production behaviour |

## Running tests

Run these commands from the repository root:

```bash
# Entire suite — required before committing.
python3 -m unittest discover -s tests

# Content loading and cross-reference contracts.
python3 -m unittest discover -s tests/data
python3 main.py --check

# Categories while developing a focused change.
python3 -m unittest discover -s tests/logic
python3 -m unittest discover -s tests/integration
python3 -m unittest discover -s tests/ui

# A focused module or test case.
python3 -m unittest tests.logic.test_core
python3 -m unittest tests.ui.test_screens.TestScrollableLayout
python3 -m unittest tests.data.test_content_contract.TestContentFileContract
```

`main.py --check` is complementary to the data tests: it uses the real startup
validation path without opening a GUI.

## Adding a test

### 1. Put it at the correct boundary

- Add a **data** test for malformed/renamed JSON, missing content documents, or
  reference validity.  It should load the real content and assert a contract;
  it should not duplicate combat arithmetic tests.
- Add a **logic** test for a deterministic rule with a clear input and output.
  Use a seeded `Game` and call the smallest public engine API that expresses
  the behaviour.
- Add an **integration** test when a player-visible result crosses boundaries,
  such as *equip → modifier recalculation → save → load*.
- Add a **UI** test when the screen’s construction, displayed state, navigation,
  or command wiring is at risk.  UI code must remain a thin view over `Game`.

If a bug crosses two categories, write the smallest direct regression in the
lowest useful category and add an integration/UI test only if the boundary
itself was part of the failure.

### 2. Make the setup isolated and deterministic

```python
import tempfile
import unittest
from pathlib import Path

from engine.game import Game

PROJECT_ROOT = Path(__file__).resolve().parents[2]

class TestExample(unittest.TestCase):
    def test_result_has_a_player_visible_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Game(data_dir=PROJECT_ROOT / "data", save_dir=tmp, seed=1234)
            game.load_content()
            ok, _ = game.create_character("Tester", "male", "squire")
            self.assertTrue(ok)

            ok, message = game.allocate_stat("STR", 1)

            self.assertFalse(ok)
            self.assertIn("No stat points", message)
```

- Use a fixed `seed` whenever randomness is involved.
- Use `TemporaryDirectory()` for save tests.  Never write a developer’s real
  `saves/` directory.
- Assert outcomes and state, not implementation details or incidental log
  order, unless the log is the requested feature.
- Name a test `test_<observable_behavior>` and keep one reason for failure per
  test method.  Use `subTest()` for the same contract across independent data
  records.

### 3. Follow the UI harness rules

`tests/ui/test_screens.py` installs `tests.support.tk_stub` **before** importing
`gui` or `tkinter`.  The stub constructs the real application and records
widgets without needing a display.  UI tests should call the same handler a
button uses (for example, `window._learn()` or `button.invoke()`) and then
assert the engine state and visible widget options.

Do not import the real Tkinter first, do not use `sleep`, and do not encode
pixel positions in these tests.  Use the screenshot procedure in
`docs/GUI_VERIFICATION.md` for pixel-level checks on a machine with Tk/Xvfb.

### 4. Write a regression test first for a bug

A regression test should recreate the broken precondition, execute the action
that failed, and assert the fixed observable result.  For example, the Status
mastery regression creates a real `MasteryTrack`, opens Status, triggers a
refresh through stat allocation, and verifies the mastery text remains visible.
This catches both the original crash and future API-shape drift.

### 5. Finish with the relevant category and the complete suite

```bash
python3 -m unittest discover -s tests/<category>
python3 -m unittest discover -s tests
python3 main.py --check
```

Update content thresholds/count assertions intentionally when content grows;
do not weaken a contract merely to make a test pass.  If a test exposes a new
persistent or UI-specific gotcha, record the rule in `HANDOFF.md` and the
appropriate design/verification document.
