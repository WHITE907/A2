#!/usr/bin/env python3
"""Generate tier-3 lateral promotion classes for all tier-2 classes."""

import json

with open('data/classes.json') as f:
    data = json.load(f)

# Define new tier-3 classes for each tier-2 class
new_tier3_classes = [
    # From Knight (already has paladin)
    {
        "id": "dark_knight",
        "name": "Dark Knight",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A warrior who channels shadow into steel, trading holy light for devastating dark power.",
        "base_stats": {"STR": 38, "END": 36, "INT": 22, "AGI": 16},
        "growth": {"STR": 4, "END": 4, "INT": 3, "AGI": 1},
        "core_skill_id": "smite",
        "granted_skill_ids": ["shadow_bind", "executioners_arc"],
        "skill_tree_ids": ["toughness", "sunder_armor", "keen_edge", "smoke_veil"],
        "weapon_types": ["sword", "axe"],
        "passive_modifiers": {"flat": {"armor": 12, "physical_power": 8}, "pct": {"crit_damage": 0.1}},
        "promotions": {
            "shadow_reaver": {
                "level": 35,
                "stats": {"STR": 62, "END": 58, "INT": 36},
                "mastery": {"sword": "B", "shadow": "C"},
                "items": {"void_shard": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "sentinel",
        "name": "Sentinel",
        "tier": 3,
        "gender_restriction": "any",
        "description": "An immovable guardian whose shield becomes a wall between allies and death.",
        "base_stats": {"STR": 34, "END": 42, "INT": 18, "AGI": 12},
        "growth": {"STR": 3, "END": 5, "INT": 2, "AGI": 1},
        "core_skill_id": "strike",
        "granted_skill_ids": ["shield_wall", "taunt_skill"],
        "skill_tree_ids": ["toughness", "guardian_resolve", "warding_spirit", "rallying_cry"],
        "weapon_types": ["sword", "mace"],
        "passive_modifiers": {"flat": {"armor": 18, "max_hp": 80, "status_resist": 0.1}},
        "promotions": {
            "iron_bastion": {
                "level": 35,
                "stats": {"STR": 56, "END": 70, "INT": 30},
                "mastery": {"sword": "B"},
                "items": {"sacred_relic": 1},
                "gold": 2000
            }
        }
    },
    
    # From Duelist (already has assassin)
    {
        "id": "blademaster",
        "name": "Blademaster",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A warrior whose blade moves faster than thought, striking a dozen times before the enemy falls.",
        "base_stats": {"STR": 30, "END": 22, "INT": 12, "AGI": 48},
        "growth": {"STR": 3, "END": 2, "INT": 1, "AGI": 6},
        "core_skill_id": "pierce",
        "granted_skill_ids": ["thousand_cuts", "shadowstep"],
        "skill_tree_ids": ["fleet_footed", "keen_edge", "predatory_focus", "heartseeker"],
        "weapon_types": ["dagger", "sword"],
        "passive_modifiers": {"flat": {"crit_chance": 0.08, "speed": 6}, "pct": {"crit_damage": 0.12}},
        "promotions": {
            "stormblade": {
                "level": 35,
                "stats": {"STR": 50, "AGI": 78},
                "mastery": {"dagger": "B"},
                "items": {"void_shard": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "trickster",
        "name": "Trickster",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A cunning fighter who wins through misdirection, evasion, and perfectly-timed debuffs.",
        "base_stats": {"STR": 22, "END": 18, "INT": 18, "AGI": 46},
        "growth": {"STR": 2, "END": 2, "INT": 2, "AGI": 5},
        "core_skill_id": "pierce",
        "granted_skill_ids": ["venom_edge", "smoke_veil"],
        "skill_tree_ids": ["fleet_footed", "shadowstep", "hunters_mark", "curse_mirror"],
        "weapon_types": ["dagger", "bow"],
        "passive_modifiers": {"flat": {"evasion": 0.08, "crit_chance": 0.05, "speed": 4}},
        "promotions": {
            "illusionist": {
                "level": 35,
                "stats": {"AGI": 74, "INT": 32},
                "mastery": {"dagger": "B", "shadow": "C"},
                "items": {"phantom_mask": 1},
                "gold": 2000
            }
        }
    },
    
    # From Mage (already has archmage)
    {
        "id": "chronomancer",
        "name": "Chronomancer",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A mage who bends time itself, accelerating allies and freezing foes in temporal loops.",
        "base_stats": {"STR": 6, "END": 20, "INT": 52, "AGI": 18},
        "growth": {"STR": 0, "END": 2, "INT": 6, "AGI": 2},
        "core_skill_id": "arcane_bolt",
        "granted_skill_ids": ["temporal_shift", "glacial_prison"],
        "skill_tree_ids": ["arcane_mind", "warding_spirit", "ley_attunement", "mind_over_matter"],
        "weapon_types": ["staff"],
        "passive_modifiers": {"flat": {"max_mp": 60, "speed": 4}, "pct": {"magic_power": 0.18}},
        "promotions": {
            "time_weaver": {
                "level": 35,
                "stats": {"INT": 82},
                "mastery": {"fire": "C", "ice": "C"},
                "items": {"codex_infinite": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "necromancer",
        "name": "Necromancer",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A master of death magic who drains life from foes and commands the undead.",
        "base_stats": {"STR": 8, "END": 22, "INT": 48, "AGI": 14},
        "growth": {"STR": 1, "END": 3, "INT": 5, "AGI": 1},
        "core_skill_id": "arcane_bolt",
        "granted_skill_ids": ["vampiric_strike", "shadow_bind"],
        "skill_tree_ids": ["arcane_mind", "warding_spirit", "mind_over_matter", "steady_breath"],
        "weapon_types": ["staff", "dagger"],
        "passive_modifiers": {"flat": {"magic_power": 10, "max_mp": 40}, "pct": {"magic_power": 0.15}},
        "promotions": {
            "lich_lord": {
                "level": 35,
                "stats": {"INT": 78, "END": 36},
                "mastery": {"shadow": "B", "fire": "C"},
                "items": {"soul_gem": 1},
                "gold": 2000
            }
        }
    },
    
    # From Berserker (3 new tier-3 classes)
    {
        "id": "berserker_champion",
        "name": "Berserker Champion",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A warrior whose rage knows no bounds, dealing devastating damage at the cost of all defence.",
        "base_stats": {"STR": 44, "END": 28, "INT": 4, "AGI": 18},
        "growth": {"STR": 5, "END": 3, "INT": 0, "AGI": 2},
        "core_skill_id": "strike",
        "granted_skill_ids": ["power_strike", "executioners_arc", "whirlwind"],
        "skill_tree_ids": ["toughness", "cleave", "keen_edge", "predatory_focus"],
        "weapon_types": ["axe", "sword"],
        "passive_modifiers": {"flat": {"physical_power": 12}, "pct": {"crit_damage": 0.2}},
        "promotions": {
            "bloodlord": {
                "level": 35,
                "stats": {"STR": 72, "END": 46},
                "mastery": {"axe": "B"},
                "items": {"berserker_totem": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "bloodrager",
        "name": "Bloodrager",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A warrior who feeds on the life force of enemies, healing through carnage.",
        "base_stats": {"STR": 40, "END": 32, "INT": 8, "AGI": 16},
        "growth": {"STR": 4, "END": 4, "INT": 1, "AGI": 2},
        "core_skill_id": "strike",
        "granted_skill_ids": ["vampiric_strike", "cleave", "second_wind"],
        "skill_tree_ids": ["toughness", "keen_edge", "sunder_armor", "guardian_resolve"],
        "weapon_types": ["axe", "mace"],
        "passive_modifiers": {"flat": {"physical_power": 8, "max_hp": 60}},
        "promotions": {
            "blood_sovereign": {
                "level": 35,
                "stats": {"STR": 66, "END": 54},
                "mastery": {"axe": "B"},
                "items": {"berserker_totem": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "warchief",
        "name": "Warchief",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A berserker who leads through strength, inspiring allies with devastating war cries.",
        "base_stats": {"STR": 42, "END": 30, "INT": 10, "AGI": 16},
        "growth": {"STR": 5, "END": 3, "INT": 1, "AGI": 2},
        "core_skill_id": "strike",
        "granted_skill_ids": ["rallying_cry", "power_strike", "cleave"],
        "skill_tree_ids": ["toughness", "keen_edge", "sunder_armor", "whirlwind"],
        "weapon_types": ["axe", "sword", "mace"],
        "passive_modifiers": {"flat": {"physical_power": 10, "max_hp": 40}},
        "promotions": {
            "horde_lord": {
                "level": 35,
                "stats": {"STR": 70, "END": 48},
                "mastery": {"axe": "B"},
                "items": {"commanders_banner": 1},
                "gold": 2000
            }
        }
    },
    
    # From Warlord (3 new tier-3 classes)
    {
        "id": "high_commander",
        "name": "High Commander",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A battlefield general whose presence alone strengthens every ally within sight.",
        "base_stats": {"STR": 30, "END": 34, "INT": 22, "AGI": 16},
        "growth": {"STR": 3, "END": 4, "INT": 3, "AGI": 1},
        "core_skill_id": "strike",
        "granted_skill_ids": ["rallying_cry", "shield_wall", "challenging_shout"],
        "skill_tree_ids": ["toughness", "guardian_resolve", "warding_spirit", "sunder_armor"],
        "weapon_types": ["sword", "mace"],
        "passive_modifiers": {"flat": {"armor": 12, "max_hp": 60}},
        "promotions": {
            "supreme_commander": {
                "level": 35,
                "stats": {"STR": 52, "END": 58, "INT": 38},
                "mastery": {"sword": "B"},
                "items": {"commanders_banner": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "tactician",
        "name": "Tactician",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A master strategist who reads the battlefield like a chess board and counters every move.",
        "base_stats": {"STR": 26, "END": 30, "INT": 28, "AGI": 18},
        "growth": {"STR": 3, "END": 3, "INT": 3, "AGI": 2},
        "core_skill_id": "strike",
        "granted_skill_ids": ["riposte_stance", "sunder_armor", "hunters_mark"],
        "skill_tree_ids": ["toughness", "keen_edge", "warding_spirit", "guardian_resolve"],
        "weapon_types": ["sword", "mace"],
        "passive_modifiers": {"flat": {"armor": 8, "accuracy": 0.06, "crit_chance": 0.04}},
        "promotions": {
            "grand_strategist": {
                "level": 35,
                "stats": {"STR": 48, "END": 52, "INT": 46},
                "mastery": {"sword": "B"},
                "items": {"commanders_sigil": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "banneret",
        "name": "Banneret",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A mounted warrior whose banner inspires charges and whose lance breaks formations.",
        "base_stats": {"STR": 32, "END": 32, "INT": 16, "AGI": 22},
        "growth": {"STR": 4, "END": 3, "INT": 2, "AGI": 3},
        "core_skill_id": "strike",
        "granted_skill_ids": ["rallying_cry", "power_strike", "executioners_arc"],
        "skill_tree_ids": ["toughness", "keen_edge", "fleet_footed", "cleave"],
        "weapon_types": ["sword", "mace", "axe"],
        "passive_modifiers": {"flat": {"physical_power": 6, "speed": 6, "armor": 8}},
        "promotions": {
            "cavalry_lord": {
                "level": 35,
                "stats": {"STR": 56, "END": 52, "AGI": 38},
                "mastery": {"sword": "B"},
                "items": {"commanders_banner": 1},
                "gold": 2000
            }
        }
    },
    
    # From Ranger (3 new tier-3 classes)
    {
        "id": "pathfinder",
        "name": "Pathfinder",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A wilderness master who reads the land like a book and never loses their way.",
        "base_stats": {"STR": 20, "END": 26, "INT": 16, "AGI": 44},
        "growth": {"STR": 2, "END": 3, "INT": 2, "AGI": 5},
        "core_skill_id": "pierce",
        "granted_skill_ids": ["aimed_shot", "hunters_mark", "fleet_footed"],
        "skill_tree_ids": ["fleet_footed", "keen_edge", "shadowstep", "steady_breath"],
        "weapon_types": ["bow", "dagger", "sword"],
        "passive_modifiers": {"flat": {"accuracy": 0.08, "evasion": 0.05, "speed": 6}},
        "promotions": {
            "trail_warden": {
                "level": 35,
                "stats": {"AGI": 72, "END": 42},
                "mastery": {"bow": "B"},
                "items": {"wardens_oath": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "beastmaster",
        "name": "Beastmaster",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A ranger who bonds with wild creatures, fighting alongside loyal animal companions.",
        "base_stats": {"STR": 22, "END": 24, "INT": 18, "AGI": 42},
        "growth": {"STR": 3, "END": 3, "INT": 2, "AGI": 4},
        "core_skill_id": "pierce",
        "granted_skill_ids": ["aimed_shot", "hunters_mark", "challenging_shout"],
        "skill_tree_ids": ["fleet_footed", "keen_edge", "toughness", "guardian_resolve"],
        "weapon_types": ["bow", "sword", "axe"],
        "passive_modifiers": {"flat": {"physical_power": 6, "max_hp": 40, "accuracy": 0.05}},
        "promotions": {
            "alpha_predator": {
                "level": 35,
                "stats": {"STR": 40, "AGI": 68, "END": 42},
                "mastery": {"bow": "B"},
                "items": {"rangers_compass": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "marksman",
        "name": "Marksman",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A precision shooter whose arrows find the smallest gap in any armour.",
        "base_stats": {"STR": 18, "END": 20, "INT": 14, "AGI": 50},
        "growth": {"STR": 2, "END": 2, "INT": 1, "AGI": 6},
        "core_skill_id": "pierce",
        "granted_skill_ids": ["aimed_shot", "heartseeker", "hunters_mark"],
        "skill_tree_ids": ["fleet_footed", "keen_edge", "predatory_focus", "steady_breath"],
        "weapon_types": ["bow", "dagger"],
        "passive_modifiers": {"flat": {"accuracy": 0.1, "crit_chance": 0.06, "crit_damage": 0.08}},
        "promotions": {
            "deadeye": {
                "level": 35,
                "stats": {"AGI": 80},
                "mastery": {"bow": "B"},
                "items": {"wardens_oath": 1},
                "gold": 2000
            }
        }
    },
    
    # From Shadow Dancer (3 new tier-3 classes)
    {
        "id": "phantom",
        "name": "Phantom",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A ghost-like assassin who moves unseen and strikes from impossible angles.",
        "base_stats": {"STR": 24, "END": 18, "INT": 20, "AGI": 50},
        "growth": {"STR": 3, "END": 2, "INT": 2, "AGI": 6},
        "core_skill_id": "pierce",
        "granted_skill_ids": ["shadowstep", "shadow_bind", "venom_edge"],
        "skill_tree_ids": ["fleet_footed", "keen_edge", "smoke_veil", "predatory_focus"],
        "weapon_types": ["dagger"],
        "passive_modifiers": {"flat": {"evasion": 0.1, "crit_chance": 0.07, "speed": 6}},
        "promotions": {
            "wraith_lord": {
                "level": 35,
                "stats": {"AGI": 80, "INT": 34},
                "mastery": {"dagger": "B", "shadow": "B"},
                "items": {"phantom_mask": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "nightstalker",
        "name": "Nightstalker",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A shadow-mage who blends dark magic with blade work, striking from the void itself.",
        "base_stats": {"STR": 26, "END": 20, "INT": 28, "AGI": 44},
        "growth": {"STR": 3, "END": 2, "INT": 3, "AGI": 5},
        "core_skill_id": "pierce",
        "granted_skill_ids": ["shadow_bind", "shadowstep", "vampiric_strike"],
        "skill_tree_ids": ["fleet_footed", "keen_edge", "arcane_mind", "smoke_veil"],
        "weapon_types": ["dagger", "sword"],
        "passive_modifiers": {"flat": {"magic_power": 8, "crit_chance": 0.06, "evasion": 0.06}},
        "promotions": {
            "void_walker": {
                "level": 35,
                "stats": {"AGI": 72, "INT": 46},
                "mastery": {"dagger": "B", "shadow": "B"},
                "items": {"shadow_pact": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "saboteur",
        "name": "Saboteur",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A master of traps, poisons, and sabotage who weakens enemies before the killing blow.",
        "base_stats": {"STR": 22, "END": 22, "INT": 24, "AGI": 46},
        "growth": {"STR": 2, "END": 2, "INT": 3, "AGI": 5},
        "core_skill_id": "pierce",
        "granted_skill_ids": ["venom_edge", "time_bomb", "sunder_armor"],
        "skill_tree_ids": ["fleet_footed", "keen_edge", "hunters_mark", "smoke_veil"],
        "weapon_types": ["dagger", "bow"],
        "passive_modifiers": {"flat": {"accuracy": 0.06, "crit_chance": 0.05, "speed": 4}},
        "promotions": {
            "demolitionist": {
                "level": 35,
                "stats": {"AGI": 74, "INT": 42},
                "mastery": {"dagger": "B", "shadow": "C"},
                "items": {"phantom_mask": 1},
                "gold": 2000
            }
        }
    },
    
    # From Cleric (3 new tier-3 classes)
    {
        "id": "high_priest",
        "name": "High Priest",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A divine conduit whose healing power can pull allies back from the brink of death.",
        "base_stats": {"STR": 14, "END": 26, "INT": 44, "AGI": 12},
        "growth": {"STR": 1, "END": 3, "INT": 5, "AGI": 1},
        "core_skill_id": "arcane_bolt",
        "granted_skill_ids": ["mend", "renewal", "purifying_light"],
        "skill_tree_ids": ["arcane_mind", "warding_spirit", "steady_breath", "guardian_resolve"],
        "weapon_types": ["mace", "staff"],
        "passive_modifiers": {"flat": {"max_mp": 50, "magic_resist": 10}, "pct": {"magic_power": 0.12}},
        "promotions": {
            "divine_oracle": {
                "level": 35,
                "stats": {"INT": 72, "END": 42},
                "mastery": {"light": "B"},
                "items": {"holy_symbol": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "inquisitor",
        "name": "Inquisitor",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A holy warrior who burns away corruption with righteous fire and purifying steel.",
        "base_stats": {"STR": 24, "END": 28, "INT": 36, "AGI": 14},
        "growth": {"STR": 3, "END": 3, "INT": 4, "AGI": 1},
        "core_skill_id": "smite",
        "granted_skill_ids": ["purifying_light", "executioners_arc", "mend"],
        "skill_tree_ids": ["toughness", "keen_edge", "warding_spirit", "arcane_mind"],
        "weapon_types": ["mace", "sword"],
        "passive_modifiers": {"flat": {"physical_power": 6, "magic_power": 8, "armor": 8}},
        "promotions": {
            "purifier": {
                "level": 35,
                "stats": {"STR": 46, "INT": 60, "END": 46},
                "mastery": {"light": "B", "sword": "C"},
                "items": {"sacred_relic": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "oracle",
        "name": "Oracle",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A seer who glimpses the threads of fate, bending time and fortune to protect allies.",
        "base_stats": {"STR": 10, "END": 22, "INT": 48, "AGI": 16},
        "growth": {"STR": 1, "END": 2, "INT": 6, "AGI": 2},
        "core_skill_id": "arcane_bolt",
        "granted_skill_ids": ["temporal_shift", "renewal", "curse_mirror"],
        "skill_tree_ids": ["arcane_mind", "warding_spirit", "ley_attunement", "mind_over_matter"],
        "weapon_types": ["staff"],
        "passive_modifiers": {"flat": {"max_mp": 45, "magic_resist": 8, "speed": 4}, "pct": {"magic_power": 0.15}},
        "promotions": {
            "fate_weaver": {
                "level": 35,
                "stats": {"INT": 76, "AGI": 28},
                "mastery": {"light": "B"},
                "items": {"holy_symbol": 1},
                "gold": 2000
            }
        }
    },
    
    # From Warlock (3 new tier-3 classes)
    {
        "id": "dread_lord",
        "name": "Dread Lord",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A master of forbidden arts whose dark power corrupts everything it touches.",
        "base_stats": {"STR": 10, "END": 22, "INT": 52, "AGI": 14},
        "growth": {"STR": 1, "END": 2, "INT": 6, "AGI": 1},
        "core_skill_id": "arcane_bolt",
        "granted_skill_ids": ["shadow_bind", "flame_wave", "vampiric_strike"],
        "skill_tree_ids": ["arcane_mind", "warding_spirit", "mind_over_matter", "frost_lance"],
        "weapon_types": ["staff"],
        "passive_modifiers": {"flat": {"magic_power": 12, "crit_damage": 0.1}, "pct": {"magic_power": 0.18}},
        "promotions": {
            "archfiend": {
                "level": 35,
                "stats": {"INT": 82},
                "mastery": {"shadow": "B", "fire": "B"},
                "items": {"soul_gem": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "hexblade",
        "name": "Hexblade",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A warrior-mage who channels dark magic through their weapon, striking with cursed steel.",
        "base_stats": {"STR": 26, "END": 24, "INT": 38, "AGI": 18},
        "growth": {"STR": 3, "END": 3, "INT": 4, "AGI": 2},
        "core_skill_id": "smite",
        "granted_skill_ids": ["shadow_bind", "venom_edge", "vampiric_strike"],
        "skill_tree_ids": ["keen_edge", "arcane_mind", "warding_spirit", "sunder_armor"],
        "weapon_types": ["sword", "dagger"],
        "passive_modifiers": {"flat": {"physical_power": 6, "magic_power": 8, "crit_chance": 0.04}},
        "promotions": {
            "doom_blade": {
                "level": 35,
                "stats": {"STR": 48, "INT": 62},
                "mastery": {"shadow": "B", "sword": "C"},
                "items": {"soul_gem": 1},
                "gold": 2000
            }
        }
    },
    {
        "id": "soulbinder",
        "name": "Soulbinder",
        "tier": 3,
        "gender_restriction": "any",
        "description": "A warlock who binds enemy souls, draining their essence and turning it against them.",
        "base_stats": {"STR": 12, "END": 26, "INT": 48, "AGI": 16},
        "growth": {"STR": 1, "END": 3, "INT": 5, "AGI": 2},
        "core_skill_id": "arcane_bolt",
        "granted_skill_ids": ["vampiric_strike", "curse_mirror", "shadow_bind"],
        "skill_tree_ids": ["arcane_mind", "warding_spirit", "mind_over_matter", "steady_breath"],
        "weapon_types": ["staff", "dagger"],
        "passive_modifiers": {"flat": {"magic_power": 10, "max_hp": 40, "max_mp": 35}},
        "promotions": {
            "soul_reaper": {
                "level": 35,
                "stats": {"INT": 76, "END": 44},
                "mastery": {"shadow": "B"},
                "items": {"soul_gem": 1},
                "gold": 2000
            }
        }
    },
]

# Add new classes
data["classes"].extend(new_tier3_classes)

# Update tier-2 promotions to include 3 paths each
tier2_promotions = {
    "knight": {
        "dark_knight": {
            "level": 20,
            "stats": {"STR": 38, "END": 34, "INT": 22},
            "mastery": {"sword": "C", "shadow": "E"},
            "items": {"shadow_pact": 1},
            "gold": 600
        },
        "sentinel": {
            "level": 20,
            "stats": {"STR": 32, "END": 40},
            "mastery": {"sword": "C"},
            "items": {"oath_sigil": 1},
            "gold": 600
        }
    },
    "duelist": {
        "blademaster": {
            "level": 20,
            "stats": {"STR": 28, "AGI": 46},
            "mastery": {"dagger": "C"},
            "items": {"duelists_token": 1},
            "gold": 600
        },
        "trickster": {
            "level": 20,
            "stats": {"AGI": 44, "INT": 18},
            "mastery": {"dagger": "C", "shadow": "E"},
            "items": {"shadow_cloak": 1},
            "gold": 600
        }
    },
    "mage": {
        "chronomancer": {
            "level": 20,
            "stats": {"INT": 50},
            "mastery": {"fire": "C", "ice": "E"},
            "items": {"arcane_focus": 1},
            "gold": 600
        },
        "necromancer": {
            "level": 20,
            "stats": {"INT": 46, "END": 20},
            "mastery": {"shadow": "C", "fire": "E"},
            "items": {"soul_gem": 1},
            "gold": 600
        }
    },
    "berserker": {
        "berserker_champion": {
            "level": 20,
            "stats": {"STR": 42, "END": 26},
            "mastery": {"axe": "C"},
            "items": {"berserker_horn": 1},
            "gold": 600
        },
        "bloodrager": {
            "level": 20,
            "stats": {"STR": 38, "END": 30},
            "mastery": {"axe": "C"},
            "items": {"berserker_horn": 1},
            "gold": 600
        },
        "warchief": {
            "level": 20,
            "stats": {"STR": 40, "END": 28},
            "mastery": {"axe": "C", "sword": "E"},
            "items": {"commanders_sigil": 1},
            "gold": 600
        }
    },
    "warlord": {
        "high_commander": {
            "level": 20,
            "stats": {"STR": 28, "END": 32, "INT": 20},
            "mastery": {"sword": "C"},
            "items": {"commanders_sigil": 1},
            "gold": 600
        },
        "tactician": {
            "level": 20,
            "stats": {"STR": 24, "END": 28, "INT": 26},
            "mastery": {"sword": "C"},
            "items": {"commanders_sigil": 1},
            "gold": 600
        },
        "banneret": {
            "level": 20,
            "stats": {"STR": 30, "END": 30, "AGI": 20},
            "mastery": {"sword": "C"},
            "items": {"commanders_banner": 1},
            "gold": 600
        }
    },
    "ranger": {
        "pathfinder": {
            "level": 20,
            "stats": {"AGI": 42, "END": 24},
            "mastery": {"bow": "C"},
            "items": {"rangers_compass": 1},
            "gold": 600
        },
        "beastmaster": {
            "level": 20,
            "stats": {"STR": 20, "AGI": 40, "END": 22},
            "mastery": {"bow": "C"},
            "items": {"rangers_compass": 1},
            "gold": 600
        },
        "marksman": {
            "level": 20,
            "stats": {"AGI": 48},
            "mastery": {"bow": "C"},
            "items": {"wardens_oath": 1},
            "gold": 600
        }
    },
    "shadow_dancer": {
        "phantom": {
            "level": 20,
            "stats": {"AGI": 48, "INT": 18},
            "mastery": {"dagger": "C", "shadow": "E"},
            "items": {"phantom_mask": 1},
            "gold": 600
        },
        "nightstalker": {
            "level": 20,
            "stats": {"AGI": 42, "INT": 26},
            "mastery": {"dagger": "C", "shadow": "C"},
            "items": {"shadow_pact": 1},
            "gold": 600
        },
        "saboteur": {
            "level": 20,
            "stats": {"AGI": 44, "INT": 22},
            "mastery": {"dagger": "C", "shadow": "E"},
            "items": {"phantom_mask": 1},
            "gold": 600
        }
    },
    "cleric": {
        "high_priest": {
            "level": 20,
            "stats": {"INT": 42, "END": 24},
            "mastery": {"light": "C"},
            "items": {"holy_water": 1},
            "gold": 600
        },
        "inquisitor": {
            "level": 20,
            "stats": {"STR": 22, "INT": 34, "END": 26},
            "mastery": {"light": "C", "sword": "E"},
            "items": {"holy_symbol": 1},
            "gold": 600
        },
        "oracle": {
            "level": 20,
            "stats": {"INT": 46, "AGI": 14},
            "mastery": {"light": "C"},
            "items": {"holy_water": 1},
            "gold": 600
        }
    },
    "warlock": {
        "dread_lord": {
            "level": 20,
            "stats": {"INT": 50},
            "mastery": {"shadow": "C", "fire": "C"},
            "items": {"eldritch_pact": 1},
            "gold": 600
        },
        "hexblade": {
            "level": 20,
            "stats": {"STR": 24, "INT": 36},
            "mastery": {"shadow": "C", "sword": "E"},
            "items": {"eldritch_pact": 1},
            "gold": 600
        },
        "soulbinder": {
            "level": 20,
            "stats": {"INT": 46, "END": 24},
            "mastery": {"shadow": "C"},
            "items": {"soul_gem": 1},
            "gold": 600
        }
    }
}

# Apply promotions to tier-2 classes
for cls in data["classes"]:
    if cls["id"] in tier2_promotions:
        cls["promotions"].update(tier2_promotions[cls["id"]])

# Add new promotion items
new_items = [
    {"id": "berserker_totem", "name": "Berserker Totem", "kind": "key", "description": "A carved totem pulsing with primal rage.", "value": 400},
    {"id": "commanders_banner", "name": "Commander's Banner", "kind": "key", "description": "A battle standard that inspires courage.", "value": 400},
    {"id": "phantom_mask", "name": "Phantom Mask", "kind": "key", "description": "A mask that blurs the wearer's features.", "value": 400},
    {"id": "wardens_oath", "name": "Warden's Oath", "kind": "key", "description": "A sworn promise to protect the wild.", "value": 400},
    {"id": "holy_symbol", "name": "Holy Symbol", "kind": "key", "description": "A sacred emblem of divine power.", "value": 400},
    {"id": "soul_gem", "name": "Soul Gem", "kind": "key", "description": "A crystallised fragment of trapped essence.", "value": 400},
]

with open('data/items.json') as f:
    items_data = json.load(f)

existing_ids = {i["id"] for i in items_data["items"]}
for item in new_items:
    if item["id"] not in existing_ids:
        items_data["items"].append(item)

with open('data/items.json', 'w') as f:
    json.dump(items_data, f, indent=2)

# Add taunt_skill to skills.json (used by sentinel)
with open('data/skills.json') as f:
    skills_data = json.load(f)

skill_ids = {s["id"] for s in skills_data["skills"]}
if "taunt_skill" not in skill_ids:
    skills_data["skills"].append({
        "id": "taunt_skill",
        "name": "Provoke",
        "category": "active",
        "description": "Force an enemy to focus their attacks on you.",
        "mp_cost": 0,
        "sp_cost": 8,
        "cooldown": 4,
        "tags": ["physical", "defense", "taunt"],
        "targeting": "enemy",
        "effects": [{"type": "taunt", "duration": 3}]
    })

with open('data/skills.json', 'w') as f:
    json.dump(skills_data, f, indent=2)

# Save classes
with open('data/classes.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"Total classes: {len(data['classes'])}")
print(f"Tier-3 classes: {sum(1 for c in data['classes'] if c['tier'] == 3)}")
print(f"Tier-4 classes: {sum(1 for c in data['classes'] if c['tier'] == 4)}")

# Verify all tier-2 classes have 3 promotions
for cls in data["classes"]:
    if cls["tier"] == 2:
        promos = list(cls.get("promotions", {}).keys())
        status = "✅" if len(promos) >= 3 else "❌"
        print(f"  {status} {cls['id']}: {len(promos)} promotions → {promos}")
