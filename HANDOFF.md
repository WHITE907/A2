# Handoff — Project Ascension

Knowledge transfer for a new coding session. Read this first, then
`PROJECT_BIBLE_v1.md`, then `docs/ENGINE_DESIGN.md`.

---

## 1. Immediate task

**Companions and relationships are complete.** The v0.2.0 patch was applied,
verified, and merged in PR #2. The repository now loads four companions and the
full suite contains 366 tests. `v0.2.0-companions.patch` remains only as a
historical recovery artifact; do not apply it again or rebuild the feature.

The next implementation task is **`QuestManager` + `data/quests.json`**. Quests
must be data-driven, integrated through the `Game` facade, and call the existing
`Player.complete_quest()` flow. This is the largest progression blocker because
all 12 tier-4+ promotions require completed quests. Follow the manager and
content-validation patterns already used by the other content types.

After implementation, run:

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
python3 -m unittest discover -s tests    # 366 tests
```

**Current state:** v0.1.0 is merged in PR #1. v0.2.0 (companions and
relationships) is merged in PR #2. Quest and upper-tier progression work is
next.

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
| **`engine/game.py`** (956 ln) | **The facade. The GUI's only contact with the engine.** Start here. |
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
`classes.json` · `items.json` · `enemies.json` · `companions.json` · `world.json`

All cross-validated at startup. A skill referencing a missing status, or an
area spawning an unknown enemy, raises `ContentError` naming the exact ids.

### Tests
| File | Coverage |
|---|---|
| `tests/test_engine.py` | 178 tests. Real chain: JSON → managers → entities → `Skill.use()` → effects → log. |
| `tests/test_gui.py` | 112 tests. Builds real screens, invokes real handlers. |
| `tests/test_companions.py` | *(v0.2.0)* 76 tests. |
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

## 7. Known blockers — verified, not guessed

An earlier summary claimed tiers 4–7 were "reachable but under-supported."
**That was wrong.** Re-audited by execution:

**The game is currently playable to tier 2 only.**

1. **Quests do not exist.** `QuestManager` (bible §6) was never built.
   `Player.complete_quest()` exists with **zero callers** — verified by grep —
   so no quest can ever complete. All 12 tier-4+ promotions require one, making
   them permanently ineligible.

2. **Six promotion items are unobtainable** — `oath_sigil`, `shadow_pact`,
   `grimoire_of_ages`, `sacred_relic`, `void_shard`, `codex_infinite` appear in
   no loot table, shop, starting kit or recruit cost. **This blocks tier 3.**

3. **Content tops out at level 18**, against gates of 35 / 50 / 70 / 99.

Reproduce blocker 2 in seconds (this exact snippet is verified — note the
promotion chain must be walked in order, Squire → Knight → Paladin):

```python
from engine.game import Game
g = Game(seed=1); g.load_content(); g.create_character('P','male','squire')
p = g.player
p.level = 25
p.allocated_stats['STR'] = 60; p.allocated_stats['END'] = 60
p.allocated_stats['INT'] = 40; p._recalculate_base_stats()
p.mastery.gain('sword', 5000); p.mastery.gain('light', 5000)
p.inventory.add_gold(9999)

# Tier 1 -> 2 works: knights_seal drops from bandit_chief.
g.items.grant(p.inventory, 'knights_seal', 1)
print(g.promote('knight')[0])        # -> True

# Tier 2 -> 3 is impossible: nothing in the game yields oath_sigil.
print(g.promote('paladin'))          # -> (False, ['Needs: Oath Sigil x1 (have 0)'])
```

## 8. Roadmap

### Completed
- ✅ **Playable foundation (v0.1.0, PR #1):** data engine, combat, equipment,
  exploration, world, saves, and the initial GUI.
- ✅ **Companions and relationships (v0.2.0, PR #2):** four companions, active
  party and reserve bench, affinity, marriage, party combat, GUI, and tests.

### Next
1. **`QuestManager` + `data/quests.json`** — unblocks 12 promotions. The
   *checking* side already exists: `ClassDefinition.check_promotion()` accepts
   and enforces `completed_quests`, and `Player.complete_quest()` is waiting for
   a caller. Follow the existing manager shape and expose all GUI interaction
   through `Game`.
2. **Add the 6 promotion items to boss loot** — JSON only, no Python. This
   unblocks tier 3.
3. **Extend world, enemy, and reward content toward level 99** — primarily JSON
   content, with startup cross-validation preserved.
4. **Future features after the playable progression path is complete:** guilds,
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