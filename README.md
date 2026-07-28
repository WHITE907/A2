# Project Ascension

A single-player, text-based RPG in Python and Tkinter, built to the
specification in [`PROJECT_BIBLE_v1.md`](PROJECT_BIBLE_v1.md) and the notes in
[`docs/`](docs).

Deep progression, seven promotion tiers, a JSON-driven content pipeline, and a
strict engine/UI separation.

```
python3 main.py            # play
python3 main.py --check    # validate all content, no GUI needed
python3 -m unittest discover -s tests
```

## Requirements

- Python 3.11+
- Tkinter (`sudo apt-get install python3-tk` on Debian/Ubuntu; bundled with
  the python.org installers on Windows and macOS)

No third-party packages. `--check` and the entire engine test-suite run without
Tkinter installed.

## Layout

```
ProjectAscension/
├── main.py              entry point (--check, --seed, --data-dir, --save-dir)
├── engine/              all gameplay logic
│   ├── game.py          Game facade - the only thing the GUI talks to
│   ├── stats.py         StatBlock, ModifierSet, DerivedStats, Formulas
│   ├── classes.py       ClassDefinition + promotion rules
│   ├── mastery.py       F..Master tracks
│   ├── party.py         active roster + reserve bench
│   ├── quests.py        quest definitions and objective data
│   ├── races.py         race definitions, stats, modifiers, traits
│   ├── relationships.py affinity and marriage (NPCs and companions)
│   ├── rng.py           seedable, serialisable RNG
│   ├── entities/        Entity -> Player, Enemy, Companion
│   ├── skills/          Skill, Effect strategies, StatusEffect
│   ├── items/           Item, Inventory, equipment slots
│   ├── combat/          turn loop + AI behaviour registry
│   ├── world/           areas, exploration, NPCs, shops
│   └── managers/        JSON -> object factories (the only JSON readers)
├── gui/                 Tkinter presentation layer
│   ├── theme.py         palette, fonts, widget factories
│   ├── widgets.py       StatPanel, ButtonStack, SelectList, LogPanel
│   ├── app.py           window shell + screen routing
│   └── screens/         one module per screen
├── data/                all gameplay content
├── docs/                design notes
├── tests/               422 tests
├── tools/               dev utilities
└── saves/               JSON save slots (created on first save)
```

## Architecture

Two rules from the bible drive the whole design.

**§5 — "UI only displays information. Engine performs all calculations."**
Every screen holds a reference to one `Game` object and calls methods on it. No
screen imports a manager, opens a file, or does arithmetic on a stat. A test
(`test_gui_never_imports_managers_directly`) enforces this by scanning the `gui`
package for forbidden imports.

**§5 — "Gameplay values are never hardcoded. All content loads from JSON."**
Every coefficient lives in `data/config.json`. `Formulas` reads
`base + per_<stat> * stat + per_level * level` blocks dynamically, so adding
`"per_agi"` to the HP formula works with no code change. A test proves the
engine references no specific content id — it parses the AST rather than
grepping, so docstrings explaining the rule don't trip it.

### Composition over content-subclassing

Per [`docs/ENGINE_DESIGN.md`](docs/ENGINE_DESIGN.md), class count scales with
**behaviour types**, not **content volume**:

| Concept | Python classes | JSON entries |
|---|---|---|
| Skills | 1 (`Skill`) | 60 |
| Effects | 5 (`damage`, `heal`, `resource`, `shield`, `apply_status`) | — |
| Classes | 1 (`ClassDefinition`) | 19 |
| Enemies | 1 (`Enemy`) | 30 |
| Items | 1 (`Item`) | 87 |
| Statuses | 1 (`StatusEffect`) | 21 |
| Races | 1 (`RaceDefinition`) | 8 |
| Companions | 1 (`Companion`) | 14 |
| Quests | 1 (`QuestDefinition`) | 18 |

Fireball is not a Python class. It is a JSON entry composing a `DamageEffect`
and an `ApplyStatusEffect`:

```json
{
  "id": "fireball",
  "category": "active",
  "mp_cost": 10,
  "mastery_track": "fire",
  "effects": [
    { "type": "damage", "damage_type": "magic", "base": 10, "power_ratio": 1.4 },
    { "type": "apply_status", "status_id": "burn", "chance": 0.45 }
  ]
}
```

Adding the 200th skill is a JSON diff. Adding code is only needed for a
genuinely new *behaviour* — one class plus one `@register_effect` line.

Inheritance is used where it is the right tool: `Player` and `Enemy` both
extend `Entity` because they genuinely share a supertype, not because they are
kinds of content.

### The AI registry

`ENGINE_DESIGN.md` noted `ai_behavior_id` was stored on `Enemy` with no
registry behind it, and that the same composition pattern should apply when it
was built. `engine/combat/ai.py` is that registry: five behaviours
(`aggressive`, `opportunist`, `tactical`, `defensive`, `berserk`) selected by
id, with an unknown id falling back to `aggressive` so a typo in one monster
never crashes a battle.

## Systems

| Bible § | System | Where |
|---|---|---|
| 9 | Unlimited levels, +5 stat / +1 skill point | `entities/player.py` |
| 10 | Gender-restricted starters, 7 promotion tiers | `classes.py`, `managers/class_manager.py` |
| 11 | core / active / passive / weapon / shared / ultimate | `skills/skill.py` |
| 12 | Physical/magic/true, crits, armour, penetration, evasion, DOT/HOT, shields, reflect | `skills/effects.py`, `stats.py` |
| 13 | JSON enemies with growth, AI, loot, scaling | `entities/enemy.py` |
| 14 | Mastery F→Master, earned by use | `mastery.py` |
| 6, 10 | Data-driven quests and promotion quest gates | `quests.py`, `managers/quest_manager.py` |
| 6 | Data-driven races, traits, and racial equipment bonuses | `races.py`, `managers/race_manager.py` |
| 6 | Companions, party roster | `entities/companion.py`, `party.py` |
| 15 | Affinity and gender-agnostic marriage | `relationships.py` |
| 16 | Multiple slots, morning autosave, inn respawn | `managers/save_manager.py` |

**Promotion** requires level, stats, mastery, items, quests and gold. It swaps
the core skill, keeps every other learned skill, and consumes the required
items. Where a requirement genuinely cannot be checked, `PromotionCheck`
reports it under `unenforced` rather than silently ignoring it — the behaviour
`ENGINE_DESIGN.md` asked for.

**Races** are selected during character creation and loaded entirely from
`data/races.json`. Eight playable races provide modest primary adjustments,
always-on combat modifiers, and described traits. The same definitions power
companion racial traits. Equipment may define a base bonus for everyone plus an
additional `race_modifiers` block for matching characters; no race id is
special-cased in Python.

**Quests** come from named NPCs or companions. Town quests must be turned in by
returning to that location, while recruited companions can offer the later
chapters of their personal stories on the road. NPC Talk windows surface their available and active
quests and link to the Quest Log. `QuestManager` loads ten class-gated promotion
quests, records data-driven enemy-defeat objectives, and grants JSON-defined
rewards. Active progress is save-versioned, and giver, location, class, enemy,
item, and prerequisite references are cross-validated at startup.

**Companions** are recruited with gold, items, level, affinity, and sometimes a
personal introductory quest, then either fight in the active roster (capped, so
battles stay readable) or wait in reserve. Four companions have two-part
questlines: the first earns their trust and unlocks recruitment; the second
requires them in the party and continues while travelling. They level with the player rather than earning separate EXP — a
companion that falls behind is one you bench, which defeats the point. They act
through the existing AI registry, so `Battle` needed no companion-shaped
special case. Downed companions revive at 25% HP after a fight rather than
dying permanently.

**Affinity and marriage** live in one module, `engine/relationships.py`, used by
townspeople and companions alike: both satisfy the same `Suitor` shape, so a
companion is marriageable on exactly the same terms as an innkeeper. Gender is
never consulted anywhere in that module — the cleanest way to honour §15 is to
have nothing to remove. Marrying a companion grants them a real combat bonus,
so it is a system rather than a checkbox.

**The world** is a connected 17-area route from Ashvale to the level-40
Obsidian Gate. Emberwatch, Stonehaven, and Skyreach each provide shops,
townspeople, companions, and a safe staging point between distinct regional
enemy families and bosses. Connections, encounters, shops, NPCs, loot, and
quest targets are cross-validated before play begins.

**Boss victories** are persistent world events. Once defeated, a boss is removed
from its area's random encounter table while ordinary fights remain available.
The world remembers defeated boss ids, quests recognise victories earned before
acceptance, and one-time regional bosses drop enough tokens for later promotion
requirements.

**Saves** are versioned and migrated forward (`SAVE_VERSION`), so a save from an
older build still loads (§5, backwards compatibility). Writes go to a temp file
and are atomically replaced, so a crash mid-write cannot corrupt a slot. The RNG
defeated-boss state, and selected race are serialised too. A corrupt file is
listed as a damaged slot rather than vanishing.

## GUI

Visual direction from [`docs/GUI_STYLE_REFERENCE.md`](docs/GUI_STYLE_REFERENCE.md):
dark navy `#1a1f2e`, off-white text, flat light-gray buttons with no gradients
or rounded corners, one thin maroon accent line along the bottom edge, and stat
displays as plain stacked `key: value` lines. Sub-screens open as `Toplevel`
windows over the main window, which stays visible behind them.

`docs/GUI_VERIFICATION.md` documents a subtle bug found by debugging rather
than inspection: two `tk.Listbox` widgets that both need a live selection will
silently fight over it, because Tk ties selection to the X PRIMARY clipboard.
`theme.stat_listbox()` sets `exportselection=False` by default, and three tests
cover it — including one that asserts the *test harness itself* still
reproduces the bug with Tk defaults, so the regression test cannot quietly stop
testing anything.

## Testing

422 tests, no third-party dependencies:

```
python3 -m unittest discover -s tests        # everything
python3 -m unittest tests.test_engine        # core engine tests
python3 -m unittest tests.test_quests        # quest/progression tests
python3 -m unittest tests.test_races_storylines # races + companion stories
python3 -m unittest tests.test_world_expansion # level-40 content tests
python3 -m unittest tests.test_gui           # headless GUI tests
```

`tests/test_engine.py` exercises the real chain — JSON on disk → managers →
entities → `Skill.use()` → effects → combat log — including full DOT lifecycles
(apply → tick → tick → expire), save/load round-trips, forward migration, and
guards on the architectural rules above.

`tests/test_gui.py` builds the real screens and invokes the same handlers a
click would trigger. It runs headlessly on `tests/tk_stub.py`, a recording
stand-in for Tkinter, so the GUI is covered on machines without a display.

[`docs/BALANCE_REPORT_LEVEL_40.md`](docs/BALANCE_REPORT_LEVEL_40.md) records the
executed EXP, economy, normal-enemy, and three-class boss baselines used for the
level-40 balance pass.

### Seeing the UI without a display

`docs/GUI_VERIFICATION.md`'s Xvfb + openbox + screenshot pipeline is the right
approach when `python3-tk`, `xvfb` and `openbox` can be installed. Where they
can't, `tools/render_mockups.py` gets close from pure Python: it builds the real
screens, runs a simplified `pack` geometry pass over the resulting widget tree,
and draws the result with Pillow.

```
pip install Pillow
python3 tools/render_mockups.py     # -> assets/mockups/*.png
```

This renders **layout**, not Tk: real font metrics, native button chrome and
window decoration will differ. What it does show faithfully is structure,
ordering, sizing, colour and text — enough to catch a panel packed on the wrong
side or a stat block rendering empty. Both were caught this way during
development. It does not replace running the app on your own machine.

## Content

All in `data/`, cross-validated at startup — a skill referencing a missing
status, an area spawning an unknown enemy, or a shop selling a nonexistent item
is reported as a `ContentError` with the exact ids, not discovered mid-battle.

| File | Contents |
|---|---|
| `config.json` | every formula coefficient, progression, mastery thresholds |
| `skills.json` | 60 skills across all six categories |
| `statuses.json` | 21 buffs, debuffs, DOTs, HOTs, stuns |
| `classes.json` | 19 classes, tiers 1–7, full promotion chains |
| `items.json` | 87 items: weapons, armour, consumables, racial heirlooms, materials, key items |
| `races.json` | 8 playable/world races with stats, modifiers, and traits |
| `enemies.json` | 30 enemies including 5 bosses |
| `quests.json` | 18 promotion and companion-story quests |
| `companions.json` | 14 recruitable allies, all marriageable |
| `world.json` | 17 areas, 8 shops, 18 NPCs, encounter tables |

Rebalancing is a JSON edit. Run `python3 main.py --check` afterwards.

## Known limitations

- Content now supports the full route through level 40, including regional
  bosses for the first quest-gated promotions, but still stops before the level
  50/70/99 gates. Tier-5+ quests temporarily reuse the one-time Shadow Warden;
  persistent victory credit prevents a dead end, but those are placeholder
  objectives until the next world region supplies suitable bosses.
- The three tier-3 class-line items still drop together from the Bandit Chief.
  This guarantees every starter path remains open, but a future level-20 region
  could distribute them among class-themed encounters.
- The §20 features (guilds, housing, crafting, arena, NG+) are not implemented;
  the roadmap places them after v1.0.
- `gui/theme.py` produces type-checker warnings on its `**options` widget
  factories. This is a known Tkinter/mypy variance limitation, documented in
  that file; the pattern is correct at runtime and is the only such finding in
  the project.
