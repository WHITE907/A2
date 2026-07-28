# Changelog

Bible §18: update the changelog after versions.

## v0.2.0 - Companions and Relationships

Implements roadmap v0.0.9 (Companions) and completes bible §15.

### Companions (bible §6, roadmap v0.0.9)
- `Companion` entity extending `Entity`, plus `CompanionDefinition` -
  one class each, four JSON entries, same pattern as Skill/Enemy/Item.
- `CompanionManager` factory reading `data/companions.json`.
- `Party` with an active roster (capped by `party.max_active`) and a
  reserve bench, so battles stay readable.
- Companions **level with the player** via `level_offset` rather than
  earning separate EXP - a companion that falls behind is one the player
  benches, which defeats the point of having them.
- They fight through the existing AI registry: `Battle` already accepted
  `allies`, so no combat special-case was needed.
- Fallen companions revive at 25% HP after a battle instead of dying
  permanently; resting and respawning heal the whole party.
- Recruitment gated on level, affinity, gold, items and quests, with an
  itemised checklist in the same style as promotion.

### Relationships (bible §15)
- New `engine/relationships.py` owns affinity and marriage **once** for
  both NPCs and companions - both satisfy the same `Suitor` shape, so
  companions are marriageable on identical terms.
- Gender is never consulted anywhere in the module.
- Affinity tiers (Hostile -> Devoted) for display.
- Talking repeatedly in one day yields less, so the optimal play is not
  clicking Talk a hundred times.
- Companions gain affinity for fighting beside the player.
- A married companion gains a real combat bonus
  (`marriage_spouse_bonus` in config) and cannot be dismissed.

### GUI
- New Party window: roster, recruitable locals, and a detail pane.
- Combat screen gained an Allies panel.
- Talk window now serves companions and NPCs, and lists the exact
  outstanding marriage requirements instead of just greying out Propose.

### Tests
366 total, up from 267: 76 new companion/relationship engine tests and
23 new GUI tests.

### Fixed
- `can_marry` reported a generic "Requirements not met." instead of
  naming what was missing.
- Party window overwrote its recruitment checklist immediately after
  showing it.
- Long status lists overflowed the combat side panels.

## v0.1.0 - Playable Foundation

First playable build. Implements the roadmap from v0.0.4 through v0.0.9 in one
pass, against `PROJECT_BIBLE_v1.md` and the notes in `docs/`.

### Engine
- `Formulas` - every combat coefficient loaded from `data/config.json`; no
  gameplay value is hardcoded (§5).
- `StatBlock` / `ModifierSet` / `DerivedStats` - flat-then-percent modifier
  layering, additive percentage stacking.
- `Entity` supertype with `Player` and `Enemy`; damage, healing, shields,
  reflect and the status-effect lifecycle live here.
- Five composable `Effect` strategies (`damage`, `heal`, `resource`, `shield`,
  `apply_status`) - one `Skill` class covers all 42 skills.
- `StatusEffect` with refresh/stack/ignore/separate stacking rules, DOT/HOT
  ticks, absorb pools and reflect.
- Mastery tracks F→Master with cumulative per-rank bonuses (§14).
- `ClassDefinition` with seven promotion tiers, gender restriction, and
  requirement checks over level, stats, mastery, items, quests and gold (§10).
- Item, equipment and inventory systems with slot rules and stack handling.
- Combat turn loop with speed-based ordering recomputed each round, plus a
  five-behaviour AI registry (the piece `ENGINE_DESIGN.md` flagged as missing).
- World, areas, weighted encounter tables, shops, NPCs, affinity and marriage.
- Seedable, serialisable RNG - reloading a save resumes the same roll stream.
- Versioned save slots with atomic writes, forward migration, morning autosave
  and inn respawn (§16).

### GUI
- Tkinter shell with launcher, main menu, world and combat as main screens;
  save browser, character creation, inventory, equipment, skills, status,
  settings, shop and talk as `Toplevel` sub-windows (§7).
- Theme built from `docs/GUI_STYLE_REFERENCE.md`.
- `exportselection=False` on every Listbox, fixing the PRIMARY-selection
  conflict documented in `docs/GUI_VERIFICATION.md`.

### Content
19 classes, 42 skills, 16 statuses, 41 items, 11 enemies, 5 areas - all
cross-validated at startup.

### Tests
267 tests (178 engine, 89 GUI), no third-party dependencies. Includes guards on
the engine/UI separation and the no-hardcoded-content rules.

### Tools
- `main.py --check` validates content without a GUI.
- `tools/render_mockups.py` renders screen layouts headlessly via Pillow.
