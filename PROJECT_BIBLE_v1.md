# PROJECT ASCENSION BIBLE
**Version:** Draft 1.0 (Living Document)

## 0. Purpose
This document is the authoritative reference for Project Ascension.

## 1. Vision
Project Ascension is a single-player, text-based RPG built in Python using Tkinter.
The focus is deep progression, replayability and a modular engine.

## 2. Scope
- Python RPG
- Text-based gameplay
- Tkinter GUI
- JSON-driven systems
- 60,000–100,000+ lines expected
- Hundreds of classes, enemies and skills
- Thousands of items

## 3. Tech Stack
Language:
- Python 3.12+

GUI:
- Tkinter

Architecture:
- Object-Oriented Programming
- JSON-driven
- Modular Engine

Persistence:
- JSON save files

Repository:
- Git
- GitHub
- main = stable
- develop = development

Platforms:
- Windows
- Linux

## 4. Folder Structure
ProjectAscension/
- assets
- characters
- data
- docs
- engine
- gui
- items
- logs
- saves

## 5. Design Philosophy
- UI only displays information.
- Engine performs all calculations.
- Gameplay values are never hardcoded.
- All content loads from JSON.
- Complete implementations over placeholders.
- Preserve backwards compatibility.

## 6. Architecture
Core:
- Player
- Enemy
- Companion (planned)
- NPC (planned)
- Entity (planned)

Managers:
- ClassManager
- SkillManager
- EnemyManager
- SaveManager
- ItemManager (planned)
- QuestManager
- RaceManager

## 7. GUI
Framework:
- Tkinter

Screens:
- Launcher
- Main Menu
- Save Browser
- Character Creation
- World
- Combat
- Inventory
- Equipment
- Skills
- Status
- Settings

## 8. Game Loop
Launcher → Main Menu → Character Creation/Load → Town → Explore → Combat → Rewards → Town → Sleep → Morning Autosave

## 9. Character System
Stats:
- STR
- END
- INT
- AGI

Progression:
- Data-driven playable race selection
- Race traits and racial equipment affinities
- Unlimited levels
- +5 stat points per level
- +1 skill point per level

## 10. Class System
- Gender-restricted starting classes
- Seven promotion tiers
- Promotion requires level, stats, mastery, items and quests
- Promotion expands skill tree
- Core skill changes
- Learned skills remain
- Ultimate skills unlock later

## 11. Skill System
Categories:
- Core
- Active
- Passive
- Weapon
- Shared
- Ultimate

Weapon skills are shared.
Class skills are unique.

## 12. Combat Goals
- Physical Damage
- Magic Damage
- True Damage
- Critical Hits
- Armor
- Magic Resistance
- Penetration
- Accuracy
- Evasion
- Buffs/Debuffs
- DOT/HOT
- Shields
- Reflect
- Future Elements

## 13. Enemy System
JSON-driven enemies:
- Stats
- Growth
- AI
- Skills
- Loot
- EXP
- Gold
- Scaling

## 14. Mastery
Ranks:
F, E, D, C, B, A, S, SS, Master

## 15. Affinity & Marriage
Affinity with NPCs.
Marriage possible regardless of gender using a special item.

## 16. Save System
- Multiple save slots
- Morning autosave
- Respawn at Inn after death
- JSON serialization

## 17. Coding Standards
- Type hints
- Dataclasses
- Composition preferred
- Cache JSON
- No duplicated logic
- One responsibility per class

## 18. Development Rules
- One commit at a time
- Complete files only
- No placeholder systems
- UI contains no gameplay logic
- Update CHANGELOG after versions

## 19. Roadmap
v0.0.4 ✅ Data Engine
v0.0.5 Combat
v0.0.6 Equipment
v0.0.7 Exploration
v0.0.8 World
v0.0.9 Companions
v1.0 Playable Foundation

## 20. Future Features
Guilds, Housing, Fishing, Mining, Smithing, Cooking, Alchemy, Arena, Legendary Classes, NG+, World Events, Pets.

## 21. AI Developer Guide
- Read this file first.
- Follow roadmap.
- Preserve compatibility.
- Complete replacement files only.
- Keep gameplay data in JSON.
- Keep UI separate from engine.
