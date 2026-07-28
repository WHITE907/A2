# Changelog

Bible §18: update the changelog after versions.

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
