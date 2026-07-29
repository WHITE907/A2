# Handoff — Project Ascension

Knowledge transfer for a new coding session. Read this first, then
`PROJECT_BIBLE_v1.md`, then `docs/ENGINE_DESIGN.md`.

---

## 1. Immediate task

**The dual-resource and content expansion is complete on the current branch.**
v0.8.0 adds a stamina system alongside mana, skill tags for categorisation
and resource routing, mandatory sub-races for all 15 races, three lateral
promotion paths per starting class, 7 new races (Orc, Gnome, Halfling, Genasi,
Goliath, Lamia, Arachne), 7 new companions, 7 new NPCs, and gender display
for all companions and NPCs. The full suite contains 443 tests.

The next milestone should use these systems in **levels 41–70 content** rather
than adding another disconnected framework:

1. **Build out the tier-2→3 promotion chains** for the 6 new tier-2 classes
   (Berserker, Warlord, Ranger, Shadow Dancer, Cleric, Warlock). They
   currently have `promotions: {}` — their tier-3 targets don't exist yet.
2. **Build levels 41–55** around a factional capital using branching quest
   outcomes, reputation shops, loyalty chapters, set gear, and a phased
   level-50 promotion boss.
3. **Add race-specific questlines** for the 7 new races — Orc blood-debt
   quests, Gnome invention chains, Halfling community stories, Genasi
   elemental heritage, Goliath endurance trials, Lamia ancient lore, and
   Arachne fate-weaving.
4. **Expand dialogue trees** per settlement so race/class/faction reactivity
   is a normal part of play rather than a single reference conversation.

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
python3 -m unittest discover -s tests    # 443 tests
```

**Current state:** v0.1.0 and v0.2.0 are merged. v0.3.0–v0.8.0 are implemented
on the current branch: quests, level-40 world content, persistent bosses,
races/stories, the Living Systems expansion, and the Resources/Races/Branching
Paths expansion. The next unsupported promotion band begins at level 50.

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
| Skills | 1 (`Skill`) | 60 |
| Effects | 17 strategies | — |
| Classes | 1 (`ClassDefinition`) | 25 |
| Enemies | 1 (`Enemy`) | 30 |
| Items | 1 (`Item`) | 94 |
| Statuses | 1 (`StatusEffect`) | 21 |
| Races | 1 (`RaceDefinition`) + `SubRace` | 15 (with 35 sub-races) |
| Companions | 1 (`Companion`) | 21 |

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
| `docs/BALANCE_REPORT_LEVEL_40.md` | Executed EXP, economy, and combat baselines. |
| `README.md` | Current state, known limitations. |
| `CHANGELOG.md` | What shipped when (bible §18 requires updating this). |

### Engine — the single entry point
| File | Responsibility |
|---|---|
| **`engine/game.py`** | **The facade. The GUI's only contact with the engine.** Start here. |
| `engine/stats.py` | `StatBlock`, `ModifierSet`, `DerivedStats` (now includes `max_sp`), `Formulas` (now includes SP formula). All combat maths. |
| `engine/skills/effects.py` | The 17 composable effect strategies. `ResourceEffect` now handles both MP and SP via `"resource"` key. New behaviours go here. |
| `engine/skills/skill.py` | The one `Skill` class. Now has `sp_cost`, `tags` list, and `is_physical`/`is_magical`/`is_hybrid` helpers. |
| `engine/skills/status.py` | Buffs/debuffs/DOT/HOT/shields/stuns. |
| `engine/entities/entity.py` | Shared supertype: HP/**MP/SP**, damage, status lifecycle, `regenerate_resources()` for per-turn regen. |
| `engine/entities/player.py` | Levels, skill learning, equipment, promotion. Now stores `sub_race_id`, uses `combined_stats()`/`combined_modifiers()`. |
| `engine/entities/enemy.py` | Monsters + loot rolls. |
| `engine/entities/companion.py` | *(v0.2.0)* Recruitable allies. Now has `gender` field. |
| `engine/combat/combat.py` | The turn loop. Speed-ordered, recomputed each round. End-of-round now calls `regenerate_resources()` for MP+SP regen. |
| `engine/combat/ai.py` | Behaviour registry: 5 strategies selected by id. |
| `engine/classes.py` | `ClassDefinition` + promotion requirement checks. |
| `engine/mastery.py` | F→Master tracks, earned by use. |
| `engine/quests.py` | *(v0.3.0)* Quest definitions and objective data. |
| `engine/races.py` | *(v0.6.0, updated v0.8.0)* `RaceDefinition` + `SubRace` dataclass. Methods: `combined_stats()`, `combined_modifiers()`, `combined_traits()`, `get_sub_race()`. |
| `engine/story.py` | *(v0.7.0)* Dialogue, faction, and banter definitions. |
| `engine/world/world.py` | *(v0.4.0, updated v0.8.0)* Areas, encounters, shops. `NPC` now has `gender` field. |
| `engine/managers/race_manager.py` | *(v0.6.0)* Race content loading. |
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
| `gui/screens/character_creation.py` | *(updated v0.8.0)* Now has Race → Sub-Race → Class flow with sub-race validation. |
| `gui/screens/talk.py` | *(updated v0.8.0)* Shows NPC gender alongside race. |
| `gui/screens/*.py` | One module per screen. |

### Content — `data/`
`config.json` (every coefficient, now includes `sp` formula) · `skills.json`
(now with `tags` and `sp_cost` on every skill) · `statuses.json` ·
`classes.json` (25 classes, 3 promotion paths per starter) · `items.json`
(94 items including 6 new promotion keys) · `races.json` (15 races with 35
sub-races) · `enemies.json` · `quests.json` · `companions.json` (21 companions
with genders) · `world.json` (25 NPCs with genders)

All cross-validated at startup. A skill referencing a missing status, or an
area spawning an unknown enemy, raises `ContentError` naming the exact ids.

### Tests
| File | Coverage |
|---|---|
| `tests/test_engine.py` | 179 tests. Real chain: JSON → managers → entities → `Skill.use()` → effects → log. Includes SP insufficient-resource test. |
| `tests/test_gui.py` | 116 tests. Builds real screens, invokes real handlers. |
| `tests/test_companions.py` | *(v0.2.0)* 76 tests. |
| `tests/test_quests.py` | *(v0.3.0)* Quest progression, persistence, and loot. |
| `tests/test_races_storylines.py` | *(v0.6.0, updated v0.8.0)* Races (now 15), heirlooms, and companion stories (now 21). |
| `tests/test_systems_expansion.py` | *(v0.7.0)* Objectives, story, loyalty, gear, effects, bosses. |
| `tests/test_world_expansion.py` | *(v0.4.0, updated v0.8.0)* Level-40 density, reachability, and content counts. |
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

## 7. What v0.8.0 contains

**Dual resources — Mana and Stamina.** Every entity now tracks both MP and SP.
MP continues to scale off INT; SP scales off END (+ STR minor). Both regenerate
per turn in combat via `Entity.regenerate_resources()`, called from
`Battle.end_round()`. The formula is in `data/config.json` under the `"sp"` key,
following the same `base + per_<stat> * stat + per_level * level` pattern as
every other formula.

Three deliberate design calls:

- **Physical skills spend SP, magical skills spend MP.** This is driven by the
  `tags` array on each skill: `"physical"` → SP, `"magical"` → MP. A skill with
  both tags (like Smite) uses both resources. The `Skill.can_use()` method
  checks both pools; `Skill.use()` spends both.
- **Hybrid skills pay both costs simultaneously** rather than letting the player
  choose. This makes hybrid classes (Paladin, Spellblade) genuinely different
  — they need both stats, not just one.
- **SP regen scales off END the way MP regen scales off INT.** Both use the
  same formula structure so neither feels like an afterthought. Warriors get
  natural stamina recovery; mages get natural mana recovery.

**Sub-races.** Every race now has 2–3 sub-races, each with `bonus_stats`,
`bonus_modifiers`, and `bonus_traits` that stack on top of the base race. The
`RaceDefinition` class provides `combined_stats()`, `combined_modifiers()`, and
`combined_traits()` that accept a `sub_race_id`. The `Player` stores
`sub_race_id` and calls the combined methods during stat recalculation. Sub-race
selection is mandatory in character creation — the UI validates that a sub-race
is chosen before allowing creation.

**Skill tags.** Every skill carries a `tags` list (e.g. `["physical", "melee",
"fire"]`). The `is_physical`, `is_magical`, and `is_hybrid` properties derive
resource routing from tags. Tags are displayed in skill tooltips and available
for UI filtering. They do not yet drive achievement tracking — that is a planned
follow-up.

**Lateral promotions.** The three starting classes (Squire, Maiden, Acolyte)
each now have 3 promotion targets instead of 1. Six new tier-2 classes were
added: Berserker, Warlord, Ranger, Shadow Dancer, Cleric, Warlock. These have
`promotions: {}` — their tier-3 targets are the next content task.

**New races.** 7 new races (Orc, Gnome, Halfling, Genasi, Goliath, Lamia,
Arachne), each with sub-races, bringing the total to 15 races. Each new race
has one companion and one NPC with full dialogue. Companions and NPCs now carry
a `gender` field displayed in the Party and Talk screens.

---

## 8. Known limitations — verified, not guessed

The reusable systems now cover the requested behaviours, but content breadth is
intentionally smaller than engine breadth: one branching dialogue is the
reference tree, one equipment set demonstrates thresholds, and the Dawn Tyrant
is the reference phased boss. New content should copy those data patterns, not
add NPC-, item-, or boss-specific Python.

**The progression limit still begins at level 50.** Tier-5+ quest entries use
placeholder objectives until level-41–70 regions and bosses exist. The next
content pass should exercise factions, race reactions, companion loyalty,
branching outcomes, set gear, advanced effects, and phased bosses together.

**The 6 new tier-2 classes have no tier-3 promotions yet.** Berserker, Warlord,
Ranger, Shadow Dancer, Cleric, and Warlock are at `promotions: {}`. Their
promotion trees need to be built out alongside the level 41–55 content.

**Skill tags don't yet drive achievement tracking or damage interactions.**
Tags are used for resource routing (MP vs SP), displayed in tooltips, and
available for UI filtering. Using them for elemental damage interactions
(e.g. fire tag → bonus vs ice enemies) or achievement triggers is a planned
follow-up, not yet wired up.

**Sub-race content is structural, not narrative.** Sub-races modify stats and
traits but don't yet have sub-race-specific quests, dialogue, or NPC reactions.
A Red Dragonkin and a Gold Dragonkin play differently mechanically but the
world doesn't react to the distinction yet.

Damage redirection stores its protector as battle-only runtime state, so it is
not intended to persist outside combat. Temporary companion departures are
recoverable after the configured number of days; do not turn them into permanent
loss without a clear restoration path.

---

## 9. Roadmap

### Completed
- ✅ v0.1–v0.2: playable foundation, companions, relationships.
- ✅ v0.3: quest engine and promotion progression.
- ✅ v0.4: connected world and content through level 40.
- ✅ v0.5: NPC quest givers, persistent bosses, measured balance.
- ✅ v0.6: eight races, racial heirlooms, companion stories.
- ✅ v0.7: generic objectives, branching dialogue, loyalty/banter/tactics,
  factions, advanced gear/effects, and phased boss framework.
- ✅ v0.8: stamina system, skill tags, sub-races, lateral promotions,
  7 new races with companions and NPCs, gender display.

### Next
1. **Build out tier-2→3 promotion chains** for Berserker, Warlord, Ranger,
   Shadow Dancer, Cleric, and Warlock. Each needs a tier-3 class definition,
   promotion requirements, and a tier-3→4 chain.
2. **Build levels 41–55** around a factional capital using branching quest
   outcomes, reputation shops, loyalty chapters, set gear, and a phased level-50
   promotion boss.
3. **Add race-specific questlines** for the 7 new races, leveraging the
   existing quest objective system and branching dialogue.
4. **Build levels 56–70** with hostile/otherworldly settlements, heritage quests,
   advanced enchantments, and level-70 promotion bosses.
5. **Wire up tag-based interactions**: elemental damage bonuses, achievement
   tracking, and skill filtering in the Skills screen.
6. Run party, faction-economy, dual-resource, and phased-boss balance passes.
7. Continue toward level 99 before post-game guild/housing/crafting systems.

---

## 10. Gotchas that will cost you time

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

**The character creation screen initialises sub-race list after all widgets.**
The `_on_race_selected()` call that populates the sub-race list must happen
*after* `class_list` is created, because `_refresh_preview()` reads all three
lists. Moving the initialisation order breaks the GUI tests with an
`AttributeError` that looks like a race condition but is actually widget
creation order.

**SP costs broke one existing test.** `test_insufficient_mp_is_rejected` used
Power Strike as its test skill, which switched from MP to SP in v0.8.0. The
test was updated to use Fireball (MP) and a new `test_insufficient_sp` was
added for Power Strike (SP). When adding new skills with SP costs, remember
that existing tests may reference them by id.

**Content count assertions are fragile.** Several tests check exact counts of
races, companions, items, and classes. When adding content, search for
`assertEqual.*count()` in the test files and update the expected values.
Currently: 25 classes, 15 races, 21 companions, 94 items, 60 skills.

**Verify claims before making them.** The tier-4 error in section 8 came from
asserting something plausible without running it. If you state a limitation,
demonstrate it with executed code first.

---

## 11. House style

- Type hints and dataclasses throughout (bible §17).
- Comments explain **why**, not what. Non-obvious tradeoffs get a sentence.
- One responsibility per class; composition preferred.
- Content ids never appear in engine logic.
- Update `CHANGELOG.md` and this `HANDOFF.md` after a version (bible §18).
- Keep `assets/mockups/` and `saves/*.json` out of git (already in
  `.gitignore`).
- Full suite must pass before commit: `python3 -m unittest discover -s tests`.

---

## 12. Quick reference — new systems API

### Stamina (SP)
```python
# Entity methods
entity.max_sp                    # derived stat, scales off END+STR
entity.current_sp                # runtime pool
entity.sp_text()                 # "45/79"
entity.sp_fraction               # 0.0–1.0
entity.can_afford_sp(cost)       # bool
entity.spend_sp(cost)            # bool, False if insufficient
entity.change_sp(amount)         # delta after clamping
entity.regenerate_resources()    # (mp_gained, sp_gained), called per round

# Config (data/config.json → formulas.sp)
"sp": {"base": 20, "per_end": 6.0, "per_str": 2.0, "per_level": 3.0}
```

### Skill tags
```python
# Skill properties
skill.tags              # ["physical", "melee", "fire"]
skill.is_physical       # True if "physical" in tags
skill.is_magical        # True if "magical" in tags
skill.is_hybrid         # True if both

# Skill costs
skill.mp_cost           # mana cost (magical skills)
skill.sp_cost           # stamina cost (physical skills)
# Hybrid skills can have both
```

### Sub-races
```python
# RaceDefinition methods
race.sub_races                           # tuple[SubRace, ...]
race.get_sub_race("high_elf")            # SubRace | None
race.combined_stats("high_elf")          # StatBlock (base + sub-race bonus)
race.combined_modifiers("high_elf")      # ModifierSet (base + sub-race bonus)
race.combined_traits("high_elf")         # tuple[str, ...] (base + sub-race bonus)

# Player
player.sub_race_id                       # str, persisted in save
player.race_def.combined_stats(player.sub_race_id)  # used in _recalculate_base_stats
```

### Gender display
```python
# CompanionDefinition
companion.gender                         # str ("male", "female", etc.)

# NPC (engine/world/world.py)
npc.gender                               # str ("male", "female", "nonbinary", etc.)
```

### ResourceEffect (MP or SP)
```json
{"type": "resource", "resource": "mp", "amount": 14}
{"type": "resource", "resource": "sp", "percent_max_sp": 0.2}
```
