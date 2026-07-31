# Engine Core — Design Notes

## The problem this solves

The bible calls for hundreds of classes, enemies, and skills, and thousands
of items. The naive OOP instinct — one Python class per skill, one per
class, one per enemy — doesn't scale to that, and it's what caused the
refactor churn in the earlier ChatGPT-assisted attempt. It also directly
contradicts §5 of the bible: "Gameplay values are never hardcoded. All
content loads from JSON."

## The pattern: composition over content-subclassing

Class count scales with **behavior types** (currently 5 Effect types, ~1
Skill class, ~1 ClassDefinition class, ~1 Enemy class), not with **content
volume** (hundreds/thousands of JSON entries).

- `Skill` is ONE class. Every skill in the game — Fireball, Power Strike,
  a future Ultimate — is an *instance* of it, built by composing a list
  of `Effect` objects (`engine/skills/effects.py`).
- `ClassDefinition` is ONE class. Warrior, Mage, and all future classes
  are instances, not subclasses.
- `Enemy` is ONE class. Every monster in the game is an instance spawned
  by `EnemyManager.spawn(template_id, level)`.

**Adding new content = adding a JSON entry. Adding new code is only
needed for a genuinely new *behavior*** (e.g. a "life drain" effect that
doesn't decompose into damage + heal). That should be rare.

## Why this still counts as "proper OOP"

This isn't a shortcut around OOP — it's OOP applied at the system level:

- **Strategy pattern**: `Effect` subclasses are interchangeable strategies
  `Skill.use()` iterates over.
- **Factory pattern**: `SkillManager`, `ClassManager`, `EnemyManager` turn
  raw JSON into live objects; nothing outside these classes touches JSON
  directly.
- **Composition over inheritance**: a Skill *has* Effects; it doesn't
  inherit skill-specific behavior.
- **Single responsibility**: `stats.py` owns formulas, `effects.py` owns
  effect resolution, managers own loading/caching, entities own their
  own state transitions (`take_raw_damage`, `tick_status_effects`).

Inheritance is still used exactly where it's the right tool: `Player` and
`Enemy` both extend `Entity` because they genuinely share a supertype
(both are things with HP/MP/stats/turn effects), not because they're
"kinds of content."

## What this buys you going forward

- v0.0.5 (Combat) builds *on* this — the turn loop calls
  `skill.use(caster, targets)` and `entity.tick_status_effects()`; it
  doesn't need to know what any specific skill does.
- Adding the 200th skill is a JSON diff, not a new file.
- If a rule changes (e.g. "crits now also apply a debuff"), it's a
  change to `DamageEffect` in one file, not hundreds of skill files.
- Rebalancing is editing `stats.py` formulas or JSON numbers — never
  touching entity/skill logic.

## What's intentionally NOT built yet

- AI behavior execution (`ai_behavior_id` is stored on Enemy but no
  `AIBehavior` registry exists yet — same composition pattern should
  apply when it's built).
- Item/Inventory system (ClassManager already flags unenforced item/quest
  promotion requirements rather than silently ignoring them).
- The Combat turn loop itself (v0.0.5, next).
- GUI (Tkinter) — deliberately last. It should only ever call into these
  managers/entities and display results; per §5, it holds no gameplay logic.

## Running the proof

```
python3 -m unittest tests.logic.test_core
```

This isn't a placeholder test file — it exercises the real chain: JSON on
disk -> Managers -> Entities -> Skill.use() -> Effects -> combat log
messages, including a full DOT lifecycle (apply -> tick -> tick -> expire)
and a save/load round-trip.
