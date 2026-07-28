# Changelog

Bible §18: update the changelog after versions.

## v0.7.0 - Living Systems

A broad engine expansion focused on reusable behaviours rather than one-off
content branches.

### Quest objectives and branching dialogue
- QuestManager now supports 11 generic objective behaviours: enemy defeats,
  item collection, area visits, NPC conversations, recruitment, companion
  travel, equipment types, affinity thresholds, no-down victories, turn-limit
  victories, and story choices.
- Added data-driven dialogue trees with conditional responses over race, class,
  flags, reputation, affinity, party composition, and marriage.
- Dialogue actions can set flags, change affinity/loyalty/reputation, accept
  quests, grant items, and record mutually exclusive choices.
- Added a branching Story window and an intentionally morally-grey Ash Court
  contract with factional, hostile, and class/race-reactive outcomes.

### Loyalty, banter, and tactics
- Added Wary/Trusted/Devoted/Sworn companion loyalty ranks, combat bonuses,
  skill unlocks, titles, and outfit ids.
- Severe disagreements cause temporary departures with a guaranteed rejoin
  date rather than permanent companion loss.
- Added contextual banter triggers for travel, areas, party combinations,
  player race/class, enemy families, boss victories, rests, marriage, and
  downed companions.
- Companion tactics persist per save: stance, preferred target, MP preservation,
  healing threshold, ultimate policy, and protect target. A Tactics GUI exposes
  the principal controls without moving decision calculations into the UI.

### Boss framework and combat effects
- Boss JSON now supports HP phases, changing modifiers/resistances, phase
  shields, summoned reinforcements, enrages, environmental damage, telegraphed
  attacks with defend counters, and survive-round victory conditions.
- The Dawn Tyrant now uses three phases, a summon, arena damage, enrage, and a
  defend-counter telegraph as the reference encounter.
- Added 12 effect strategies: life drain, cleanse, dispel, revive, taunt,
  cooldown manipulation, execute, counter, status transfer, delayed attack,
  damage redirection, and explicit resource drain.

### Factions, race reactivity, and equipment
- Added eight independent factions with rival reputation changes and
  reputation-based shop discounts.
- Shops can expose race-specific stock and prices; dialogue and banter also
  support race-specific conditions without hardcoded race ids.
- Equipment now supports JSON set bonuses, enchantment slots, five upgrade
  levels, item-bound skills, and low-health conditional modifiers.
- Added four enchantments, an Emberwatch set reference implementation, a
  boss-bound skill item, and the Blood-Oath Ring conditional item.
- Faction, loyalty, tactics, enchantments, and upgrades persist in save v6.

### Tests
- 442 tests pass. New integration coverage exercises every system above,
  persistence, GUI story/tactics entry points, boss phases, advanced effects,
  objective events, and mutually exclusive faction choices.

## v0.6.0 - Races and Companion Stories

### Races
- Added one data-driven `RaceDefinition` content class and `RaceManager`, with
  eight playable/world races: Human, Elf, Half-Elf, Dwarf, Dragonkin, Demon,
  Tiefling, and Beastkin.
- Character Creation now includes race selection and a combined race/class
  preview. Human remains the backwards-compatible default.
- Racial primary adjustments, derived modifiers, and traits apply to players
  and companions without race-specific branches in engine logic.
- Player race persists in save schema v5; older saves migrate to the configured
  default race.

### Racial equipment and world population
- Added eight obtainable racial heirlooms (87 items total). Their base effects
  work for everyone and their JSON `race_modifiers` grant an additional bonus
  to the matching race.
- Assigned races to all companions and NPCs and added six new multi-racial
  townspeople with local lore, humour, and relationship content.
- Added four recruitable, marriageable companions (14 total): Lethira Vale,
  Brokk Embervein, Veyra Ashhorn, and Rhazek Dawnscale.
- Expanded every existing companion from four dialogue lines to at least seven,
  including lore, personality, jokes, food opinions, and questionable advice.

### Companion questlines
- Added four two-part personal questlines (eight quests; 18 total). Intro quests
  are offered by unrecruited companions at home and unlock recruitment; second
  chapters require that companion to be in the party and can travel with them.
- Companion quest rewards include racial heirlooms, EXP, gold, and story
  resolution, all using the existing objective/reward engine.
- Quest-giver validation now accepts both NPCs and companion definitions, and
  validates required companion references.

### Tests
- Tests were written first to prove the previous engine lacked race selection,
  racial modifiers, race persistence, mixed-race world content, and companion
  story support.
- 422 tests pass after implementation, including 14 new race/storyline tests
  plus GUI race-selection and legacy-save coverage.

## v0.5.0 - Quest Givers, World State, and Balance

### Quests and NPCs
- Every quest now defines a validated NPC giver, acceptance town, and turn-in
  town. Quests are only offered while visiting the correct location.
- NPC Talk windows show available/in-progress quests and link directly to the
  Quest Log; quest details name the giver and both required locations.
- Completed objectives can only be turned in after returning to the giver's
  town.
- Defeating a one-time boss before accepting its quest is handled safely: the
  saved world deed is applied retroactively on acceptance instead of creating a
  permanently blocked quest.

### Persistent bosses
- Boss encounters now carry a stable boss id and disappear from random encounter
  tables after victory while ordinary encounters in the area remain repeatable.
- Defeated boss ids persist in save schema v4 and migrate safely from older
  saves.
- Content validation rejects boss encounters whose boss id is absent or points
  to a non-boss enemy.
- Regional bosses grant three promotion tokens, covering the cumulative tier-4
  and tier-5 requirements despite being one-time fights.

### Balance
- Executed seeded real-battle passes with Templar, Nightblade, and Archon builds,
  plus measured EXP and economy pacing across all level-16–40 regions.
- Reduced normal-enemy EXP where early regions required only 1.5–2.4 encounters
  per level. The measured range is now 2.7–5.6 encounters per level.
- Shop prices and enemy/boss HP were retained after measured upgrade times and
  real combat outcomes fell within the intended range.
- Added `docs/BALANCE_REPORT_LEVEL_40.md` with methodology, results, changes,
  and known follow-up risks.

### Tests
- 406 tests pass. New coverage includes giver/location gates, return-to-giver
  turn-in, retroactive boss credit, boss encounter removal, world-state
  persistence, promotion-token quantities, NPC quest UI, and EXP pacing bounds.

## v0.4.0 - The Road to Skyreach

### World
- Expanded the connected map from 5 to 17 areas, covering level bands 1–40.
- Added three populated towns: Emberwatch, Stonehaven, and Skyreach. Each has
  its own description, routes, two shops, three NPCs, and two companions.
- Added nine wilderness/dungeon areas across burning roads, living woods,
  marshes, a drowned archive, mountain passes, crystal mines, stormlands,
  cloud ruins, and the Obsidian Gate.
- Added eight exploration flavour events and enforced reciprocal connections at
  content validation so one-way map mistakes fail at startup.

### Encounters and progression
- Added 19 enemy templates across beasts, plants, undead, constructs, insects,
  dragons, celestials, and humanoids, bringing the total to 30.
- Added regional bosses at levels 27, 34, and 40: the Mire Oracle, Iron
  Colossus, and Dawn Tyrant.
- Moved the three upper promotion drops from the level-15 Shadow Warden to those
  regional bosses, and updated the first branch quests to use those encounters.
- Added 38 items (79 total): six weapon families, armour for seven equipment
  slots, high-level consumables, and nine region-specific materials. Every new
  material has a loot source and every equipment band has shop or boss support.

### Skills and party
- Added 18 skills (60 total), including three new passives and two advanced
  actions for each tier-3/4 class line, plus nine enemy abilities.
- Added five statuses: Electrified, Brittle, Rooted, Valor, and Stormguard.
- Added six recruitable, marriageable companions (10 total), with distinct
  roles, stat growth, AI styles, requirements, gifts, and dialogue.
- Added nine townspeople with local dialogue and relationship content.

### Validation and tests
- Startup now validates skill class requirements and reciprocal map links.
- 398 tests pass, including 13 expansion tests for reachability, town density,
  encounter variety, boss coverage, equipment bands, material availability,
  class passives, and regional quest targets.

## v0.3.0 - Quests and Promotion Progression

### Quests
- Added one data-driven `QuestDefinition` content class and `QuestManager`, with
  ten class-gated quests covering every quest requirement across 12 upper-tier
  promotions.
- Enemy-defeat objectives advance after victories, clamp at their configured
  quantity, and grant JSON-defined EXP, gold, and item rewards on turn-in.
- Active quests and objective progress persist in save schema v3; older saves
  migrate forward with an empty quest log.
- Startup validation now checks promotion, companion, prerequisite, class,
  enemy, and reward references across quest content.

### Progression
- The Bandit Chief now guarantees `oath_sigil`, `shadow_pact`, and
  `grimoire_of_ages`, unblocking all tier-3 class lines.
- The Shadow Warden now guarantees `sacred_relic`, `void_shard`, and
  `codex_infinite`, supplying the repeatable quantities upper promotions need.
- Promotion tokens now stack to 99 so repeatable guaranteed boss drops do not
  consume a new inventory slot on every victory.

### GUI
- Added a Quest Log for available, active, and completed quests, with objective
  progress, reward details, acceptance, and turn-in controls.

### Tests
- 385 tests total. New coverage includes quest content validation, class/level
  and prerequisite gates, objective progression, rewards, save round-trips,
  guaranteed promotion loot, and headless Quest Log interactions.

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
