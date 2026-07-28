# Handoff — Project Ascension

Knowledge transfer for a new coding session. Read this first, then
`PROJECT_BIBLE_v1.md`, then `docs/ENGINE_DESIGN.md`.

---

## 1. Immediate task

**Quests and promotion-item availability are complete on the current branch.**
The v0.3.0 work adds `QuestManager`, ten data-driven promotion quests, a Quest
Log GUI, persisted objective progress, save migration, and guaranteed drops for
all six previously unobtainable promotion items. The full suite contains 385
tests and content validation reports 10 quests.

The next implementation task is to **extend world, enemy, boss, and reward
content toward level 99**. Existing content ends around level 18, so the upper
quest and promotion gates are mechanically reachable but require repetitive
low-level grinding. Preserve JSON-driven content and startup cross-validation.

Before handing off changes, run:

```bash
python3 -m unittest discover -s tests
python3 main.py --check
```

---

## 2. What this project is

A single-player text RPG in Python 3.11+ and Tkinter, spec'd by
`PROJECT_BIBLE_v1.md`. No third-party runtime dependencies.

```bash
python3 main.py                          # play (needs python3-tk)
python3 main.py --check                  # validate content, no GUI
python3 -m unittest discover -s tests    # 385 tests
```

**Current state:** v0.1.0 is merged in PR #1 and v0.2.0 is merged in PR #2.
v0.3.0 quests and promotion progression are implemented on the current branch;
world progression beyond level 18 is next.

---

## 3. The two rules that govern everything

Both come from bible §5, and both are **enforced by tests** — not convention.
Breaking either will fail the suite.

### Rule 1 — the GUI computes nothing

> *"UI only displays information. Engine performs all calculations."*

Every screen holds one `Game` object and calls methods on it. No screen imports
a manager, opens a file, or does arithmetic on a stat.

Guard: `test_gui_never_imports_managers_directly` scans `gui/` for forbidden
imports. If a screen needs a type for annotation, **re-export it through
`engine/game.py`** — that is why `SaveSlotInfo` is re-exported there.

### Rule 2 — no hardcoded gameplay values

> *"Gameplay values are never hardcoded. All content loads from JSON."*

Every coefficient lives in `data/config.json`. `Formulas` reads
`base + per_<stat> * stat + per_level * level` blocks **dynamically**, so adding
`"per_agi"` to the HP formula in JSON works with no code change.

Guard: `test_no_hardcoded_content_ids_in_engine_logic` parses the engine's AST
looking for string literals like `"fireball"` or `"green_slime"`. It uses AST
rather than grep so docstrings *explaining* the rule don't trip it.

---

## 4. Architecture: composition over content-subclassing

From `docs/ENGINE_DESIGN.md`. Class count scales with **behaviour**, not
**content volume**:

| Concept | Python classes | JSON entries |
|---|---|---|
| Skills | 1 (`Skill`) | 42 |
| Effects | 5 strategies | — |
| Classes | 1 (`ClassDefinition`) | 19 |
| Enemies | 1 (`Enemy`) | 11 |
| Items | 1 (`Item`) | 41 |
| Statuses | 1 (`StatusEffect`) | 16 |
| Companions | 1 (`Companion`) | 4 |

Fireball is **not** a Python class. It is a JSON entry composing a
`DamageEffect` and an `ApplyStatusEffect`.

**Adding content = a JSON diff. Adding code is only for a genuinely new
*behaviour*** — one class plus one `@register_effect` line. That should be rare.

Guard: `test_one_class_per_content_type`.

Inheritance is used where it is genuinely right: `Player`, `Enemy` and
`Companion` all extend `Entity` because they truly share a supertype.

---

## 5. File map — where to look for what

### Read these before writing code
| File | Why |
|---|---|
| `PROJECT_BIBLE_v1.md` | The spec. Sections are cited throughout the code. |
| `docs/ENGINE_DESIGN.md` | The composition pattern and why it exists. |
| `docs/GUI_STYLE_REFERENCE.md` | Exact palette, fonts, layout conventions. |
| `docs/GUI_VERIFICATION.md` | Hard-won Tkinter gotchas. Read before GUI work. |
| `README.md` | Current state, known limitations. |
| `CHANGELOG.md` | What shipped when (bible §18 requires updating this). |

### Engine — the single entry point
| File | Responsibility |
|---|---|
| **`engine/game.py`** | **The facade. The GUI's only contact with the engine.** Start here. |
| `engine/stats.py` | `StatBlock`, `ModifierSet`, `DerivedStats`, `Formulas`. All combat maths. |
| `engine/skills/effects.py` | The 5 composable effect strategies. New behaviours go here. |
| `engine/skills/skill.py` | The one `Skill` class. |
| `engine/skills/status.py` | Buffs/debuffs/DOT/HOT/shields/stuns. |
| `engine/entities/entity.py` | Shared supertype: HP/MP, damage, status lifecycle. |
| `engine/entities/player.py` | Levels, skill learning, equipment, promotion. |
| `engine/entities/enemy.py` | Monsters + loot rolls. |
| `engine/entities/companion.py` | *(v0.2.0)* Recruitable allies. |
| `engine/combat/combat.py` | The turn loop. Speed-ordered, recomputed each round. |
| `engine/combat/ai.py` | Behaviour registry: 5 strategies selected by id. |
| `engine/classes.py` | `ClassDefinition` + promotion requirement checks. |
| `engine/mastery.py` | F→Master tracks, earned by use. |
| `engine/quests.py` | *(v0.3.0)* Quest definitions and objective data. |
| `engine/managers/quest_manager.py` | *(v0.3.0)* Quest loading and progression. |
| `engine/relationships.py` | *(v0.2.0)* Affinity + marriage, shared by NPCs and companions. |
| `engine/party.py` | *(v0.2.0)* Active roster + reserve bench. |
| `engine/managers/*.py` | **The only code that reads JSON.** One per content type. |
| `engine/managers/save_manager.py` | Versioned, atomic, forward-migrating saves. |
| `engine/rng.py` | Seedable + serialisable, so saves resume the same roll stream. |

### GUI
| File | Responsibility |
|---|---|
| `gui/theme.py` | Palette, fonts, widget factories. **Change styling only here.** |
| `gui/widgets.py` | `StatPanel`, `ButtonStack`, `SelectList`, `LogPanel`. |
| `gui/app.py` | Window shell, screen routing, Toplevel lifecycle. |
| `gui/screens/*.py` | One module per screen. |

### Content — `data/`
`config.json` (every coefficient) · `skills.json` · `statuses.json` ·
`classes.json` · `items.json` · `enemies.json` · `quests.json` ·
`companions.json` · `world.json`

All cross-validated at startup. A skill referencing a missing status, or an
area spawning an unknown enemy, raises `ContentError` naming the exact ids.

### Tests
| File | Coverage |
|---|---|
| `tests/test_engine.py` | 178 tests. Real chain: JSON → managers → entities → `Skill.use()` → effects → log. |
| `tests/test_gui.py` | 116 tests. Builds real screens, invokes real handlers. |
| `tests/test_companions.py` | *(v0.2.0)* 76 tests. |
| `tests/test_quests.py` | *(v0.3.0)* Quest progression, persistence, and loot. |
| `tests/tk_stub.py` | Recording Tkinter stand-in for headless GUI testing. |
| `tools/render_mockups.py` | Renders screen layouts via Pillow. |

---

## 6. What v0.2.0 contains

**Companions** (bible §6, roadmap v0.0.9) — `Companion` + `CompanionDefinition`
+ `CompanionManager`, and a `Party` with a capped active roster plus reserve.

Two deliberate design calls, both worth preserving:

- **Companions level with the player** via `level_offset` instead of earning
  separate EXP. A companion that falls behind is one you bench — which defeats
  the point of having them.
- **Downed companions revive at 25% HP** after a fight. Permanent loss in a
  game with no resurrection item is a silent dead end.

Combat needed almost no change: `Battle` already accepted `allies` and routed
AI turns side-agnostically.

**Relationships** (bible §15) — extracted into `engine/relationships.py` and
used by **both** NPCs and companions. Both satisfy the same `Suitor` shape
(structural typing, not a base class), so a companion is marriageable on
identical terms to an innkeeper. **Gender is never consulted anywhere in that
module** — the cleanest way to honour §15 is to have nothing to remove.
Marrying a companion grants a real combat bonus, so it is a system rather than
a checkbox.

---

## 7. Known limitations — verified, not guessed

The two hard progression blockers are resolved in v0.3.0:

- `QuestManager` and `data/quests.json` cover all ten unique quest ids used by
  the 12 quest-gated promotions. Victory events update persisted objectives and
  `Game.complete_quest()` calls the existing `Player.complete_quest()` flow.
- The Bandit Chief guarantees the three tier-3 promotion items; the Shadow
  Warden guarantees the three repeatable upper-tier promotion items.

**The remaining progression limitation is content depth.** Areas and enemies
still top out around level 18, against promotion gates of 35 / 50 / 70 / 99.
Players can grind the existing repeatable encounters, but upper-tier quests all
reuse the Shadow Warden because no level-35+ bosses exist yet. When extending
the world, move each class-line reward and quest objective to thematically
appropriate bosses instead of changing the quest engine.

## 8. Roadmap

### Completed
- ✅ **Playable foundation (v0.1.0, PR #1):** data engine, combat, equipment,
  exploration, world, saves, and the initial GUI.
- ✅ **Companions and relationships (v0.2.0, PR #2):** four companions, active
  party and reserve bench, affinity, marriage, party combat, GUI, and tests.
- ✅ **Quests and promotion progression (v0.3.0):** ten promotion quests, Quest
  Log, persisted progress, cross-validation, and six obtainable promotion items.

### Next
1. **Extend world, enemy, boss, and reward content toward level 99.** Add content
   in JSON, distribute class-line promotion drops among suitable bosses, and
   replace the temporary repeated Shadow Warden objectives.
2. **Balance the full seven-tier progression path** by execution once content
   exists at each level band; verify EXP pacing, mastery gain, loot frequency,
   and promotion costs rather than guessing.
3. **Future features after the playable progression path is complete:** guilds,
   housing, fishing, mining, smithing, cooking, alchemy, arena, legendary
   classes, NG+, world events, and pets (bible §20).

---

## 9. Gotchas that will cost you time

**`exportselection=False` on every Listbox.** Documented in
`docs/GUI_VERIFICATION.md`: two `tk.Listbox` widgets that both hold a live
selection silently fight over it, because Tk ties selection to the X PRIMARY
clipboard. `curselection()` on the first then returns `()` — which looks
exactly like a logic bug. `theme.stat_listbox()` handles this. Three tests
cover it, including one asserting the *harness still reproduces the original
bug* — so the regression test cannot quietly stop testing anything.

**No tkinter in the sandbox.** Likely no `python3-tk`, `xvfb`, or root. So:
- `python3 main.py --check` validates content with no GUI.
- `tests/tk_stub.py` runs the GUI suite headlessly.
- `tools/render_mockups.py` (needs `pip install Pillow`) renders layouts to
  `assets/mockups/`. **This renders layout, not Tk** — font metrics and native
  chrome differ. It caught a panel pushed off-screen and a text-overflow bug,
  but it does not replace running the app on a real desktop.

**`gui/theme.py` type-checker noise.** ~74 `arg-type` warnings on the
`**options` widget factories. A known Tkinter/mypy variance limitation,
documented in that file. Correct at runtime; the only such findings in the
project. Don't "fix" them by rewriting the factories.

**Verify claims before making them.** The tier-4 error in section 7 came from
asserting something plausible without running it. If you state a limitation,
demonstrate it with executed code first.

---

## 10. House style

- Type hints and dataclasses throughout (bible §17).
- Comments explain **why**, not what. Non-obvious tradeoffs get a sentence.
- One responsibility per class; composition preferred.
- Content ids never appear in engine logic.
- Update `CHANGELOG.md` after a version (bible §18).
- Keep `assets/mockups/` and `saves/*.json` out of git (already in
  `.gitignore`).
- Full suite must pass before commit: `python3 -m unittest discover -s tests`.