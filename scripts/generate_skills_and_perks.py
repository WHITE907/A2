#!/usr/bin/env python3
"""Generate class perks, race-specific skills, class-specific skills, and general skills."""

import json

# ============================================================================
# CLASS PERKS - Unique abilities for each class
# ============================================================================
class_perks = {
    # Tier 1 - Starting classes
    "squire": [{"id": "iron_will", "name": "Iron Will", "description": "Below 30% HP, gain +15% armor", "trigger": "low_hp", "threshold": 0.3, "modifiers": {"pct": {"armor": 0.15}}}],
    "maiden": [{"id": "evasive_grace", "name": "Evasive Grace", "description": "+5% evasion at all times", "trigger": "always", "modifiers": {"flat": {"evasion": 0.05}}}],
    "acolyte": [{"id": "arcane_focus", "name": "Arcane Focus", "description": "+8% magic power", "trigger": "always", "modifiers": {"pct": {"magic_power": 0.08}}}],
    
    # Tier 2 - First promotion
    "knight": [{"id": "shield_mastery", "name": "Shield Mastery", "description": "+10% armor, shields last 1 extra turn", "trigger": "always", "modifiers": {"pct": {"armor": 0.1}}}],
    "berserker": [{"id": "blood_rage", "name": "Blood Rage", "description": "Below 40% HP, gain +25% physical power", "trigger": "low_hp", "threshold": 0.4, "modifiers": {"pct": {"physical_power": 0.25}}}],
    "warlord": [{"id": "inspirational_presence", "name": "Inspirational Presence", "description": "+5% physical power for you and allies", "trigger": "always", "modifiers": {"pct": {"physical_power": 0.05}}}],
    "duelist": [{"id": "precision_strikes", "name": "Precision Strikes", "description": "+8% crit chance", "trigger": "always", "modifiers": {"flat": {"crit_chance": 0.08}}}],
    "ranger": [{"id": "hunters_eye", "name": "Hunter's Eye", "description": "+10% accuracy, +5% crit chance", "trigger": "always", "modifiers": {"flat": {"accuracy": 0.1, "crit_chance": 0.05}}}],
    "shadow_dancer": [{"id": "shadow_step", "name": "Shadow Step", "description": "+10% evasion, +5% speed", "trigger": "always", "modifiers": {"flat": {"evasion": 0.1, "speed": 5}}}],
    "mage": [{"id": "mana_efficiency", "name": "Mana Efficiency", "description": "Below 30% MP, gain +20% magic power", "trigger": "low_mp", "threshold": 0.3, "modifiers": {"pct": {"magic_power": 0.2}}}],
    "cleric": [{"id": "divine_grace", "name": "Divine Grace", "description": "+15% healing done, +10% magic resist", "trigger": "always", "modifiers": {"flat": {"magic_resist": 5}, "pct": {"healing_done": 0.15}}}],
    "warlock": [{"id": "soul_siphon", "name": "Soul Siphon", "description": "10% lifesteal on magical attacks", "trigger": "always", "special": "lifesteal", "special_value": 0.1}],
    
    # Tier 3 - Second promotion
    "paladin": [{"id": "holy_shield", "name": "Holy Shield", "description": "+15% armor, +10% magic resist", "trigger": "always", "modifiers": {"pct": {"armor": 0.15, "magic_resist": 0.1}}}],
    "dark_knight": [{"id": "shadow_embrace", "name": "Shadow Embrace", "description": "Below 30% HP, gain +30% physical power and +15% lifesteal", "trigger": "low_hp", "threshold": 0.3, "modifiers": {"pct": {"physical_power": 0.3}}, "special": "lifesteal", "special_value": 0.15}],
    "sentinel": [{"id": "unbreakable", "name": "Unbreakable", "description": "+20% armor, +15% max HP", "trigger": "always", "modifiers": {"pct": {"armor": 0.2, "max_hp": 0.15}}}],
    "assassin": [{"id": "lethal_precision", "name": "Lethal Precision", "description": "+12% crit chance, +20% crit damage", "trigger": "always", "modifiers": {"flat": {"crit_chance": 0.12}, "pct": {"crit_damage": 0.2}}}],
    "blademaster": [{"id": "whirlwind_stance", "name": "Whirlwind Stance", "description": "+10% physical power, +8% speed", "trigger": "always", "modifiers": {"pct": {"physical_power": 0.1}, "flat": {"speed": 8}}}],
    "trickster": [{"id": "misdirection", "name": "Misdirection", "description": "+15% evasion, enemies have -10% accuracy against you", "trigger": "always", "modifiers": {"flat": {"evasion": 0.15}}}],
    "archmage": [{"id": "arcane_mastery", "name": "Arcane Mastery", "description": "+20% magic power, +15% max MP", "trigger": "always", "modifiers": {"pct": {"magic_power": 0.2, "max_mp": 0.15}}}],
    "chronomancer": [{"id": "time_warp", "name": "Time Warp", "description": "+10% speed, cooldowns reduced by 1 turn", "trigger": "always", "modifiers": {"flat": {"speed": 10}}}],
    "necromancer": [{"id": "death_embrace", "name": "Death Embrace", "description": "15% lifesteal, +10% magic power below 40% HP", "trigger": "always", "special": "lifesteal", "special_value": 0.15, "modifiers": {"pct": {"magic_power": 0.1}}}],
    "berserker_champion": [{"id": "unbridled_fury", "name": "Unbridled Fury", "description": "Below 50% HP, gain +40% physical power and +20% speed", "trigger": "low_hp", "threshold": 0.5, "modifiers": {"pct": {"physical_power": 0.4}, "flat": {"speed": 20}}}],
    "bloodrager": [{"id": "blood_feast", "name": "Blood Feast", "description": "20% lifesteal, +15% physical power below 40% HP", "trigger": "low_hp", "threshold": 0.4, "modifiers": {"pct": {"physical_power": 0.15}}, "special": "lifesteal", "special_value": 0.2}],
    "warchief": [{"id": "battle_command", "name": "Battle Command", "description": "+10% physical power, +10% armor for you and allies", "trigger": "always", "modifiers": {"pct": {"physical_power": 0.1, "armor": 0.1}}}],
    "high_commander": [{"id": "tactical_genius", "name": "Tactical Genius", "description": "+15% accuracy, +10% evasion for you and allies", "trigger": "always", "modifiers": {"flat": {"accuracy": 0.15, "evasion": 0.1}}}],
    "tactician": [{"id": "counter_stance", "name": "Counter Stance", "description": "15% chance to counter attacks, +10% armor", "trigger": "always", "modifiers": {"pct": {"armor": 0.1}}, "special": "counter", "special_value": 0.15}],
    "banneret": [{"id": "rallying_banner", "name": "Rallying Banner", "description": "+10% all stats for you and allies", "trigger": "always", "modifiers": {"pct": {"physical_power": 0.1, "magic_power": 0.1, "armor": 0.1}}}],
    "pathfinder": [{"id": "wilderness_mastery", "name": "Wilderness Mastery", "description": "+12% speed, +10% evasion, +8% accuracy", "trigger": "always", "modifiers": {"flat": {"speed": 12, "evasion": 0.1, "accuracy": 0.08}}}],
    "beastmaster": [{"id": "pack_leader", "name": "Pack Leader", "description": "+15% physical power, summons deal +20% damage", "trigger": "always", "modifiers": {"pct": {"physical_power": 0.15}}}],
    "marksman": [{"id": "dead_eye", "name": "Dead Eye", "description": "+15% accuracy, +12% crit chance, +25% crit damage", "trigger": "always", "modifiers": {"flat": {"accuracy": 0.15, "crit_chance": 0.12}, "pct": {"crit_damage": 0.25}}}],
    "phantom": [{"id": "ghost_walk", "name": "Ghost Walk", "description": "+20% evasion, +15% speed, untargetable for 1 turn after killing", "trigger": "always", "modifiers": {"flat": {"evasion": 0.2, "speed": 15}}}],
    "nightstalker": [{"id": "shadow_fusion", "name": "Shadow Fusion", "description": "+15% magic power, +15% physical power, +10% evasion", "trigger": "always", "modifiers": {"pct": {"magic_power": 0.15, "physical_power": 0.15}, "flat": {"evasion": 0.1}}}],
    "saboteur": [{"id": "trap_master", "name": "Trap Master", "description": "Traps deal +30% damage, +10% accuracy", "trigger": "always", "modifiers": {"flat": {"accuracy": 0.1}}}],
    "high_priest": [{"id": "divine_conduit", "name": "Divine Conduit", "description": "+25% healing done, +15% magic resist, +10% max MP", "trigger": "always", "modifiers": {"flat": {"magic_resist": 8}, "pct": {"max_mp": 0.1, "healing_done": 0.25}}}],
    "inquisitor": [{"id": "righteous_fury", "name": "Righteous Fury", "description": "+15% physical power, +15% magic power, +10% armor", "trigger": "always", "modifiers": {"pct": {"physical_power": 0.15, "magic_power": 0.15, "armor": 0.1}}}],
    "oracle": [{"id": "fate_weaver", "name": "Fate Weaver", "description": "+12% speed, cooldowns reduced by 1, +10% magic power", "trigger": "always", "modifiers": {"flat": {"speed": 12}, "pct": {"magic_power": 0.1}}}],
    "dread_lord": [{"id": "void_embrace", "name": "Void Embrace", "description": "20% lifesteal, +20% magic power, +15% max MP", "trigger": "always", "modifiers": {"pct": {"magic_power": 0.2, "max_mp": 0.15}}, "special": "lifesteal", "special_value": 0.2}],
    "hexblade": [{"id": "cursed_blade", "name": "Cursed Blade", "description": "+15% physical power, +15% magic power, 15% lifesteal", "trigger": "always", "modifiers": {"pct": {"physical_power": 0.15, "magic_power": 0.15}}, "special": "lifesteal", "special_value": 0.15}],
    "soulbinder": [{"id": "soul_harvest", "name": "Soul Harvest", "description": "25% lifesteal, +15% magic power, gain 5% max HP on kill", "trigger": "always", "modifiers": {"pct": {"magic_power": 0.15}}, "special": "lifesteal", "special_value": 0.25}],
    
    # Tier 4 - Third promotion (abbreviated - same pattern)
    "templar": [{"id": "divine_aegis", "name": "Divine Aegis", "description": "+20% armor, +15% magic resist, +10% max HP", "trigger": "always", "modifiers": {"pct": {"armor": 0.2, "magic_resist": 0.15, "max_hp": 0.1}}}],
    "nightblade": [{"id": "shadow_mastery", "name": "Shadow Mastery", "description": "+15% crit chance, +25% crit damage, +12% evasion", "trigger": "always", "modifiers": {"flat": {"crit_chance": 0.15, "evasion": 0.12}, "pct": {"crit_damage": 0.25}}}],
    "archon": [{"id": "arcane_supremacy", "name": "Arcane Supremacy", "description": "+25% magic power, +20% max MP, spells cost 10% less", "trigger": "always", "modifiers": {"pct": {"magic_power": 0.25, "max_mp": 0.2}}}],
    "shadow_reaver": [{"id": "void_blade", "name": "Void Blade", "description": "Below 30% HP, +40% physical power, 20% lifesteal", "trigger": "low_hp", "threshold": 0.3, "modifiers": {"pct": {"physical_power": 0.4}}, "special": "lifesteal", "special_value": 0.2}],
    "iron_bastion": [{"id": "fortress", "name": "Fortress", "description": "+25% armor, +20% max HP, reflect 10% damage", "trigger": "always", "modifiers": {"pct": {"armor": 0.25, "max_hp": 0.2}}, "special": "reflect", "special_value": 0.1}],
    "stormblade": [{"id": "lightning_reflexes", "name": "Lightning Reflexes", "description": "+15% speed, +12% crit chance, +20% crit damage", "trigger": "always", "modifiers": {"flat": {"speed": 15, "crit_chance": 0.12}, "pct": {"crit_damage": 0.2}}}],
    "illusionist": [{"id": "mirror_image", "name": "Mirror Image", "description": "+20% evasion, 15% chance to dodge completely", "trigger": "always", "modifiers": {"flat": {"evasion": 0.2}}}],
    "time_weaver": [{"id": "temporal_mastery", "name": "Temporal Mastery", "description": "+15% speed, cooldowns reduced by 2, +15% magic power", "trigger": "always", "modifiers": {"flat": {"speed": 15}, "pct": {"magic_power": 0.15}}}],
    "lich_lord": [{"id": "undying_will", "name": "Undying Will", "description": "25% lifesteal, +20% magic power, survive lethal blow once per battle", "trigger": "always", "modifiers": {"pct": {"magic_power": 0.2}}, "special": "lifesteal", "special_value": 0.25}],
    "bloodlord": [{"id": "savage_fury", "name": "Savage Fury", "description": "Below 50% HP, +50% physical power, +25% speed", "trigger": "low_hp", "threshold": 0.5, "modifiers": {"pct": {"physical_power": 0.5}, "flat": {"speed": 25}}}],
    "blood_sovereign": [{"id": "blood_lord", "name": "Blood Lord", "description": "30% lifesteal, +20% physical power below 40% HP", "trigger": "low_hp", "threshold": 0.4, "modifiers": {"pct": {"physical_power": 0.2}}, "special": "lifesteal", "special_value": 0.3}],
    "horde_lord": [{"id": "warlords_banner", "name": "Warlord's Banner", "description": "+15% physical power, +15% armor for you and allies", "trigger": "always", "modifiers": {"pct": {"physical_power": 0.15, "armor": 0.15}}}],
    "supreme_commander": [{"id": "grand_strategy", "name": "Grand Strategy", "description": "+20% accuracy, +15% evasion for you and allies", "trigger": "always", "modifiers": {"flat": {"accuracy": 0.2, "evasion": 0.15}}}],
    "grand_strategist": [{"id": "perfect_defense", "name": "Perfect Defense", "description": "20% counter chance, +15% armor, +10% evasion", "trigger": "always", "modifiers": {"pct": {"armor": 0.15}, "flat": {"evasion": 0.1}}, "special": "counter", "special_value": 0.2}],
    "cavalry_lord": [{"id": "charging_strike", "name": "Charging Strike", "description": "+15% physical power, +15% speed, +10% armor", "trigger": "always", "modifiers": {"pct": {"physical_power": 0.15, "armor": 0.1}, "flat": {"speed": 15}}}],
    "trail_warden": [{"id": "pathfinder_mastery", "name": "Pathfinder Mastery", "description": "+15% speed, +12% evasion, +10% accuracy", "trigger": "always", "modifiers": {"flat": {"speed": 15, "evasion": 0.12, "accuracy": 0.1}}}],
    "alpha_predator": [{"id": "apex_predator", "name": "Apex Predator", "description": "+20% physical power, summons deal +30% damage", "trigger": "always", "modifiers": {"pct": {"physical_power": 0.2}}}],
    "deadeye": [{"id": "perfect_aim", "name": "Perfect Aim", "description": "+20% accuracy, +15% crit chance, +30% crit damage", "trigger": "always", "modifiers": {"flat": {"accuracy": 0.2, "crit_chance": 0.15}, "pct": {"crit_damage": 0.3}}}],
    "wraith_lord": [{"id": "spectral_form", "name": "Spectral Form", "description": "+25% evasion, +20% speed, 50% chance to avoid AoE", "trigger": "always", "modifiers": {"flat": {"evasion": 0.25, "speed": 20}}}],
    "void_walker": [{"id": "void_mastery", "name": "Void Mastery", "description": "+20% magic power, +20% physical power, +15% evasion", "trigger": "always", "modifiers": {"pct": {"magic_power": 0.2, "physical_power": 0.2}, "flat": {"evasion": 0.15}}}],
    "demolitionist": [{"id": "master_saboteur", "name": "Master Saboteur", "description": "Traps deal +50% damage, +15% accuracy", "trigger": "always", "modifiers": {"flat": {"accuracy": 0.15}}}],
    "divine_oracle": [{"id": "divine_mastery", "name": "Divine Mastery", "description": "+35% healing done, +20% magic resist, +15% max MP", "trigger": "always", "modifiers": {"flat": {"magic_resist": 12}, "pct": {"max_mp": 0.15, "healing_done": 0.35}}}],
    "purifier": [{"id": "holy_wrath", "name": "Holy Wrath", "description": "+20% physical power, +20% magic power, +15% armor", "trigger": "always", "modifiers": {"pct": {"physical_power": 0.2, "magic_power": 0.2, "armor": 0.15}}}],
    "fate_weaver": [{"id": "fate_mastery", "name": "Fate Mastery", "description": "+15% speed, cooldowns reduced by 2, +15% magic power", "trigger": "always", "modifiers": {"flat": {"speed": 15}, "pct": {"magic_power": 0.15}}}],
    "archfiend": [{"id": "infernal_mastery", "name": "Infernal Mastery", "description": "30% lifesteal, +25% magic power, +20% max MP", "trigger": "always", "modifiers": {"pct": {"magic_power": 0.25, "max_mp": 0.2}}, "special": "lifesteal", "special_value": 0.3}],
    "doom_blade": [{"id": "cursed_mastery", "name": "Cursed Mastery", "description": "+20% physical power, +20% magic power, 20% lifesteal", "trigger": "always", "modifiers": {"pct": {"physical_power": 0.2, "magic_power": 0.2}}, "special": "lifesteal", "special_value": 0.2}],
    "soul_reaper": [{"id": "soul_mastery", "name": "Soul Mastery", "description": "35% lifesteal, +20% magic power, gain 8% max HP on kill", "trigger": "always", "modifiers": {"pct": {"magic_power": 0.2}}, "special": "lifesteal", "special_value": 0.35}],
}

# ============================================================================
# RACE-SPECIFIC SKILLS
# ============================================================================
race_skills = [
    {"id": "human_adaptive_strike", "name": "Adaptive Strike", "category": "active", "description": "A versatile attack that scales with your highest stat.", "mp_cost": 8, "sp_cost": 8, "cooldown": 2, "tags": ["physical", "melee", "adaptive"], "required_race_ids": ["human"], "effects": [{"type": "damage", "damage_type": "physical", "base": 12, "power_ratio": 1.4}]},
    {"id": "elf_moonlight_arrow", "name": "Moonlight Arrow", "category": "active", "description": "A magical arrow imbued with lunar energy.", "mp_cost": 10, "cooldown": 2, "tags": ["magical", "ranged", "light"], "required_race_ids": ["elf", "half_elf"], "effects": [{"type": "damage", "damage_type": "magic", "base": 14, "power_ratio": 1.5, "penetration_pct": 0.15}]},
    {"id": "dwarf_stoneguard", "name": "Stoneguard", "category": "active", "description": "Harden your skin like stone, gaining massive armor.", "sp_cost": 12, "cooldown": 4, "tags": ["physical", "defense", "buff"], "required_race_ids": ["dwarf"], "effects": [{"type": "apply_status", "status_id": "iron_skin", "duration": 3}]},
    {"id": "dragonkin_breath", "name": "Dragon Breath", "category": "active", "description": "Unleash a cone of elemental fire.", "mp_cost": 15, "cooldown": 3, "tags": ["magical", "aoe", "fire"], "required_race_ids": ["dragonkin"], "targeting": "all_enemies", "effects": [{"type": "damage", "damage_type": "magic", "base": 18, "power_ratio": 1.6}, {"type": "apply_status", "status_id": "burn", "chance": 0.4}]},
    {"id": "demon_hellfire", "name": "Hellfire", "category": "active", "description": "Call down infernal flames that damage enemies and heal you.", "mp_cost": 14, "cooldown": 3, "tags": ["magical", "fire", "sustain"], "required_race_ids": ["demon"], "effects": [{"type": "damage", "damage_type": "magic", "base": 16, "power_ratio": 1.5}, {"type": "heal", "base": 8, "scaling": {"INT": 0.5}}]},
    {"id": "tiefling_infernal_charm", "name": "Infernal Charm", "category": "active", "description": "Charm an enemy, confusing them for 2 turns.", "mp_cost": 12, "cooldown": 5, "tags": ["magical", "cc", "shadow"], "required_race_ids": ["tiefling"], "effects": [{"type": "apply_status", "status_id": "confused", "chance": 0.7, "duration": 2}]},
    {"id": "beastkin_predators_rush", "name": "Predator's Rush", "category": "active", "description": "Dash forward with bestial speed, gaining evasion and crit.", "sp_cost": 10, "cooldown": 3, "tags": ["physical", "mobility", "buff"], "required_race_ids": ["beastkin"], "effects": [{"type": "apply_status", "status_id": "haste", "duration": 2}, {"type": "apply_status", "status_id": "predatory_focus", "duration": 2}]},
    {"id": "half_elf_dual_nature", "name": "Dual Nature", "category": "active", "description": "Strike with both physical and magical force.", "mp_cost": 6, "sp_cost": 6, "cooldown": 2, "tags": ["physical", "magical", "melee"], "required_race_ids": ["half_elf"], "effects": [{"type": "damage", "damage_type": "physical", "base": 8, "power_ratio": 1.0}, {"type": "damage", "damage_type": "magic", "base": 8, "power_ratio": 1.0}]},
    {"id": "orc_blood_fury", "name": "Blood Fury", "category": "active", "description": "Enter a berserk rage, gaining power at the cost of health.", "sp_cost": 8, "cooldown": 4, "tags": ["physical", "buff", "sustain"], "required_race_ids": ["orc", "half_orc"], "effects": [{"type": "apply_status", "status_id": "might", "duration": 3}, {"type": "damage", "damage_type": "true", "base": 15, "target": "self"}]},
    {"id": "gnome_tinkers_trap", "name": "Tinker's Trap", "category": "active", "description": "Deploy a mechanical trap that explodes after 2 turns.", "mp_cost": 10, "cooldown": 4, "tags": ["magical", "delayed", "aoe"], "required_race_ids": ["gnome"], "targeting": "enemy", "effects": [{"type": "delayed_attack", "base": 35, "delay": 2, "name": "Tinker's Trap"}]},
    {"id": "halfling_lucky_dodge", "name": "Lucky Dodge", "category": "active", "description": "Your natural luck helps you avoid the next attack.", "sp_cost": 6, "cooldown": 3, "tags": ["physical", "defense", "buff"], "required_race_ids": ["halfling"], "effects": [{"type": "apply_status", "status_id": "evasion_up", "duration": 2}]},
    {"id": "genasi_elemental_burst", "name": "Elemental Burst", "category": "active", "description": "Release a burst of elemental energy matching your heritage.", "mp_cost": 12, "cooldown": 2, "tags": ["magical", "aoe"], "required_race_ids": ["genasi"], "targeting": "all_enemies", "effects": [{"type": "damage", "damage_type": "magic", "base": 15, "power_ratio": 1.4}]},
    {"id": "goliath_mountains_endurance", "name": "Mountain's Endurance", "category": "active", "description": "Draw on your giant heritage, gaining HP and armor.", "sp_cost": 10, "cooldown": 4, "tags": ["physical", "defense", "buff"], "required_race_ids": ["goliath"], "effects": [{"type": "heal", "base": 25, "percent_max_hp": 0.15}, {"type": "apply_status", "status_id": "iron_skin", "duration": 2}]},
    {"id": "lamia_constrict", "name": "Constrict", "category": "active", "description": "Wrap your coils around an enemy, stunning and damaging them.", "sp_cost": 12, "cooldown": 4, "tags": ["physical", "cc", "melee"], "required_race_ids": ["lamia"], "effects": [{"type": "damage", "damage_type": "physical", "base": 14, "power_ratio": 1.3}, {"type": "apply_status", "status_id": "stunned", "chance": 0.6, "duration": 1}]},
    {"id": "arachne_web_trap", "name": "Web Trap", "category": "active", "description": "Shoot a web that slows and damages the target.", "mp_cost": 8, "cooldown": 3, "tags": ["magical", "cc", "ranged"], "required_race_ids": ["arachne"], "effects": [{"type": "damage", "damage_type": "magic", "base": 10, "power_ratio": 1.2}, {"type": "apply_status", "status_id": "slowed", "chance": 0.8, "duration": 2}]},
]

# ============================================================================
# CLASS-SPECIFIC SKILLS
# ============================================================================
class_skills = [
    # Knight line
    {"id": "knight_oath_strike", "name": "Oath Strike", "category": "active", "description": "A holy strike empowered by your knightly oath.", "mp_cost": 5, "sp_cost": 5, "cooldown": 2, "tags": ["physical", "magical", "melee"], "required_class_ids": ["knight", "paladin", "templar", "crusader", "godsworn"], "effects": [{"type": "damage", "damage_type": "physical", "base": 12, "scaling": {"STR": 1.0, "INT": 0.5}}]},
    {"id": "dark_knight_shadow_cleave", "name": "Shadow Cleave", "category": "active", "description": "A dark sweep that damages all enemies.", "sp_cost": 14, "cooldown": 3, "tags": ["physical", "aoe", "shadow"], "required_class_ids": ["dark_knight", "shadow_reaver"], "targeting": "all_enemies", "effects": [{"type": "damage", "damage_type": "physical", "base": 16, "power_ratio": 1.4}]},
    {"id": "sentinel_fortify", "name": "Fortify", "category": "active", "description": "Brace yourself, gaining massive damage reduction.", "sp_cost": 10, "cooldown": 4, "tags": ["physical", "defense", "buff"], "required_class_ids": ["sentinel", "iron_bastion"], "effects": [{"type": "apply_status", "status_id": "fortified", "duration": 2}]},
    
    # Duelist line
    {"id": "duelist_flourish", "name": "Blade Flourish", "category": "active", "description": "A quick series of strikes that builds momentum.", "sp_cost": 8, "cooldown": 2, "tags": ["physical", "melee"], "required_class_ids": ["duelist", "assassin", "nightblade", "eclipse"], "effects": [{"type": "damage", "damage_type": "physical", "base": 10, "power_ratio": 1.2, "hits": 2}]},
    {"id": "ranger_multishot", "name": "Multishot", "category": "active", "description": "Fire multiple arrows at all enemies.", "sp_cost": 12, "cooldown": 3, "tags": ["physical", "ranged", "aoe"], "required_class_ids": ["ranger", "pathfinder", "marksman", "trail_warden", "deadeye"], "targeting": "all_enemies", "effects": [{"type": "damage", "damage_type": "physical", "base": 12, "power_ratio": 1.3}]},
    {"id": "shadow_dancer_vanish", "name": "Vanish", "category": "active", "description": "Disappear into shadows, becoming untargetable.", "sp_cost": 10, "cooldown": 5, "tags": ["physical", "mobility", "buff"], "required_class_ids": ["shadow_dancer", "phantom", "wraith_lord"], "effects": [{"type": "apply_status", "status_id": "stealth", "duration": 2}]},
    
    # Mage line
    {"id": "mage_arcane_barrage", "name": "Arcane Barrage", "category": "active", "description": "Unleash a rapid series of arcane missiles.", "mp_cost": 12, "cooldown": 2, "tags": ["magical", "ranged"], "required_class_ids": ["mage", "archmage", "archon", "sorcerer_king", "worldweaver"], "effects": [{"type": "damage", "damage_type": "magic", "base": 8, "power_ratio": 1.0, "hits": 3}]},
    {"id": "chronomancer_time_stop", "name": "Time Stop", "category": "active", "description": "Freeze time for all enemies for 1 turn.", "mp_cost": 20, "cooldown": 6, "tags": ["magical", "cc", "aoe"], "required_class_ids": ["chronomancer", "time_weaver"], "targeting": "all_enemies", "effects": [{"type": "apply_status", "status_id": "stunned", "chance": 0.8, "duration": 1}]},
    {"id": "necromancer_raise_dead", "name": "Raise Dead", "category": "active", "description": "Summon a skeletal warrior to fight for you.", "mp_cost": 15, "cooldown": 5, "tags": ["magical", "summon", "shadow"], "required_class_ids": ["necromancer", "lich_lord"], "effects": [{"type": "summon", "enemy_id": "skeleton", "level_offset": -2, "duration": 4}]},
    
    # Berserker line
    {"id": "berserker_rampage", "name": "Rampage", "category": "active", "description": "Attack all enemies in a frenzy.", "sp_cost": 16, "cooldown": 3, "tags": ["physical", "aoe", "melee"], "required_class_ids": ["berserker", "berserker_champion", "bloodlord", "warchief", "horde_lord"], "targeting": "all_enemies", "effects": [{"type": "damage", "damage_type": "physical", "base": 14, "power_ratio": 1.5}]},
    {"id": "bloodrager_blood_strike", "name": "Blood Strike", "category": "active", "description": "A vicious strike that heals you for damage dealt.", "sp_cost": 10, "cooldown": 2, "tags": ["physical", "melee", "sustain"], "required_class_ids": ["bloodrager", "blood_sovereign", "bloodlord"], "effects": [{"type": "life_drain", "damage_type": "physical", "base": 12, "power_ratio": 1.4, "drain_ratio": 0.5}]},
    
    # Warlord line
    {"id": "warlord_command", "name": "Command: Attack", "category": "active", "description": "Order all allies to attack, boosting their damage.", "mp_cost": 8, "cooldown": 4, "tags": ["support", "buff"], "required_class_ids": ["warlord", "high_commander", "supreme_commander", "banneret", "cavalry_lord"], "targeting": "all_allies", "effects": [{"type": "apply_status", "status_id": "command_attack", "duration": 2}]},
    {"id": "tactician_analyze", "name": "Analyze Weakness", "category": "active", "description": "Study an enemy, reducing their defenses.", "mp_cost": 6, "cooldown": 3, "tags": ["support", "debuff"], "required_class_ids": ["tactician", "grand_strategist"], "effects": [{"type": "apply_status", "status_id": "analyzed", "duration": 3}]},
    
    # Cleric line
    {"id": "cleric_mass_heal", "name": "Mass Heal", "category": "active", "description": "Heal all allies.", "mp_cost": 18, "cooldown": 4, "tags": ["magical", "healing", "aoe"], "required_class_ids": ["cleric", "high_priest", "divine_oracle"], "targeting": "all_allies", "effects": [{"type": "heal", "base": 20, "scaling": {"INT": 1.2}}]},
    {"id": "inquisitor_smite_evil", "name": "Smite Evil", "category": "active", "description": "A holy strike that deals extra damage to undead and demons.", "mp_cost": 8, "sp_cost": 8, "cooldown": 3, "tags": ["physical", "magical", "melee", "light"], "required_class_ids": ["inquisitor", "purifier"], "effects": [{"type": "damage", "damage_type": "magic", "base": 15, "power_ratio": 1.5}]},
    {"id": "oracle_prophecy", "name": "Prophecy", "category": "active", "description": "Glimpse the future, gaining evasion and accuracy.", "mp_cost": 10, "cooldown": 4, "tags": ["magical", "buff"], "required_class_ids": ["oracle", "fate_weaver"], "effects": [{"type": "apply_status", "status_id": "prophecy", "duration": 3}]},
    
    # Warlock line
    {"id": "warlock_curse", "name": "Curse of Agony", "category": "active", "description": "Curse an enemy, dealing damage over time.", "mp_cost": 10, "cooldown": 3, "tags": ["magical", "debuff", "shadow"], "required_class_ids": ["warlock", "dread_lord", "archfiend", "soulbinder", "soul_reaper"], "effects": [{"type": "apply_status", "status_id": "curse_of_agony", "duration": 4}]},
    {"id": "hexblade_cursed_strike", "name": "Cursed Strike", "category": "active", "description": "A melee strike imbued with dark magic.", "mp_cost": 6, "sp_cost": 6, "cooldown": 2, "tags": ["physical", "magical", "melee", "shadow"], "required_class_ids": ["hexblade", "doom_blade"], "effects": [{"type": "damage", "damage_type": "physical", "base": 10, "scaling": {"STR": 0.8, "INT": 0.8}}, {"type": "apply_status", "status_id": "weakened", "chance": 0.5, "duration": 2}]},
    
    # Tier 4+ ultimate skills
    {"id": "templar_divine_judgment", "name": "Divine Judgment", "category": "ultimate", "description": "Call down divine wrath upon all enemies.", "mp_cost": 30, "cooldown": 6, "skill_point_cost": 3, "tags": ["magical", "aoe", "light", "ultimate"], "required_class_ids": ["templar", "crusader", "godsworn"], "targeting": "all_enemies", "effects": [{"type": "damage", "damage_type": "magic", "base": 40, "power_ratio": 2.5}]},
    {"id": "nightblade_shadow_dance", "name": "Shadow Dance", "category": "ultimate", "description": "Become a blur of shadows, striking all enemies multiple times.", "sp_cost": 25, "cooldown": 5, "skill_point_cost": 3, "tags": ["physical", "aoe", "shadow", "ultimate"], "required_class_ids": ["nightblade", "shadowlord", "eclipse"], "targeting": "all_enemies", "effects": [{"type": "damage", "damage_type": "physical", "base": 15, "power_ratio": 1.5, "hits": 3}]},
]

# ============================================================================
# GENERAL UTILITY SKILLS
# ============================================================================
general_skills = [
    {"id": "meditation", "name": "Meditation", "category": "active", "description": "Focus your mind, restoring MP.", "cooldown": 4, "tags": ["magical", "support"], "effects": [{"type": "resource", "resource": "mp", "percent_max_mp": 0.25}]},
    {"id": "catch_breath", "name": "Catch Breath", "category": "active", "description": "Rest briefly, restoring SP.", "cooldown": 4, "tags": ["physical", "support"], "effects": [{"type": "resource", "resource": "sp", "percent_max_sp": 0.25}]},
    {"id": "battle_cry", "name": "Battle Cry", "category": "active", "description": "Rally your allies, boosting their physical power.", "mp_cost": 8, "cooldown": 5, "tags": ["support", "buff"], "targeting": "all_allies", "effects": [{"type": "apply_status", "status_id": "might", "duration": 3}]},
    {"id": "war_horn", "name": "War Horn", "category": "active", "description": "Sound a horn that boosts all allies' speed and accuracy.", "mp_cost": 10, "cooldown": 5, "tags": ["support", "buff"], "targeting": "all_allies", "effects": [{"type": "apply_status", "status_id": "haste", "duration": 2}, {"type": "apply_status", "status_id": "true_strike", "duration": 2}]},
    {"id": "intimidate", "name": "Intimidate", "category": "active", "description": "Frighten an enemy, reducing their accuracy and damage.", "mp_cost": 6, "cooldown": 4, "tags": ["support", "debuff"], "effects": [{"type": "apply_status", "status_id": "intimidated", "duration": 3}]},
    {"id": "taunt_shout", "name": "Taunting Shout", "category": "active", "description": "Force all enemies to target you.", "sp_cost": 8, "cooldown": 5, "tags": ["physical", "defense", "taunt"], "targeting": "all_enemies", "effects": [{"type": "taunt", "duration": 2}]},
    {"id": "feint", "name": "Feint", "category": "active", "description": "Fake an attack, reducing enemy evasion.", "sp_cost": 6, "cooldown": 3, "tags": ["physical", "debuff"], "effects": [{"type": "apply_status", "status_id": "off_balance", "duration": 2}]},
    {"id": "arcane_shield", "name": "Arcane Shield", "category": "active", "description": "Create a magical barrier that absorbs damage.", "mp_cost": 12, "cooldown": 4, "tags": ["magical", "defense", "buff"], "effects": [{"type": "shield", "name": "Arcane Shield", "base": 30, "scaling": {"INT": 1.5}, "duration": 3}]},
    {"id": "iron_skin", "name": "Iron Skin", "category": "active", "description": "Harden your body, gaining armor.", "sp_cost": 10, "cooldown": 4, "tags": ["physical", "defense", "buff"], "effects": [{"type": "apply_status", "status_id": "iron_skin", "duration": 3}]},
    {"id": "berserker_rage", "name": "Berserker Rage", "category": "active", "description": "Enter a rage, gaining power but losing defense.", "sp_cost": 8, "cooldown": 5, "tags": ["physical", "buff", "debuff"], "effects": [{"type": "apply_status", "status_id": "berserk", "duration": 3}]},
    {"id": "focus_mind", "name": "Focus Mind", "category": "active", "description": "Concentrate, boosting your magic power.", "mp_cost": 8, "cooldown": 4, "tags": ["magical", "buff"], "effects": [{"type": "apply_status", "status_id": "focused", "duration": 3}]},
    {"id": "evasive_maneuvers", "name": "Evasive Maneuvers", "category": "active", "description": "Move unpredictably, gaining evasion.", "sp_cost": 8, "cooldown": 3, "tags": ["physical", "defense", "buff"], "effects": [{"type": "apply_status", "status_id": "evasive", "duration": 2}]},
    {"id": "steady_aim", "name": "Steady Aim", "category": "active", "description": "Take careful aim, boosting accuracy and crit.", "sp_cost": 6, "cooldown": 3, "tags": ["physical", "ranged", "buff"], "effects": [{"type": "apply_status", "status_id": "true_strike", "duration": 2}]},
    {"id": "blood_pact", "name": "Blood Pact", "category": "active", "description": "Sacrifice HP to restore MP.", "cooldown": 4, "tags": ["magical", "support"], "effects": [{"type": "damage", "damage_type": "true", "base": 20, "target": "self"}, {"type": "resource", "resource": "mp", "percent_max_mp": 0.3}]},
    {"id": "adrenaline_rush", "name": "Adrenaline Rush", "category": "active", "description": "Flood your body with adrenaline, reducing all cooldowns.", "sp_cost": 12, "cooldown": 6, "tags": ["physical", "support"], "effects": [{"type": "cooldown", "amount": -2}]},
]

# ============================================================================
# WRITE FILES
# ============================================================================

# Update classes with perks
with open('data/classes.json') as f:
    classes = json.load(f)

for cls in classes['classes']:
    if cls['id'] in class_perks:
        cls['perks'] = class_perks[cls['id']]

with open('data/classes.json', 'w') as f:
    json.dump(classes, f, indent=2)

print(f"Updated {len(class_perks)} classes with perks")

# Add new skills
with open('data/skills.json') as f:
    skills = json.load(f)

existing_ids = {s['id'] for s in skills['skills']}
added = 0

for skill_list in [race_skills, class_skills, general_skills]:
    for skill in skill_list:
        if skill['id'] not in existing_ids:
            skills['skills'].append(skill)
            added += 1

with open('data/skills.json', 'w') as f:
    json.dump(skills, f, indent=2)

print(f"Added {added} new skills")
print(f"Total skills: {len(skills['skills'])}")
