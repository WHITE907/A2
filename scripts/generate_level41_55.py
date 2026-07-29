#!/usr/bin/env python3
"""Generate levels 41-55 content: areas, enemies, bosses, quests."""

import json

# ============================================================================
# NEW AREAS
# ============================================================================
new_areas = [
    {
        "id": "ironveil_approach",
        "name": "Ironveil Approach",
        "description": "The road to Ironveil winds through petrified forest, where ancient trees stand as stone sentinels.",
        "is_town": False,
        "recommended_level": 41,
        "connections": ["obsidian_gate", "town_ironveil"],
        "encounters": [
            {"enemy_ids": ["stone_revenant"], "weight": 1.0, "level_min": 41, "level_max": 43},
            {"enemy_ids": ["petrified_treant", "stone_revenant"], "weight": 0.8, "level_min": 42, "level_max": 44},
            {"enemy_ids": ["void_stalker"], "weight": 0.5, "level_min": 43, "level_max": 45}
        ],
        "quiet_chance": 0.2,
        "unlock_level": 40
    },
    {
        "id": "town_ironveil",
        "name": "Ironveil",
        "description": "A fortress-city carved into a mountainside, seat of the Iron Covenant faction. The walls hum with ancient wards.",
        "is_town": True,
        "recommended_level": 42,
        "connections": ["ironveil_approach", "ashen_wastes", "sunken_citadel"],
        "npc_ids": ["commander_vex", "artificer_zara", "chronicler_thon"],
        "shop_ids": ["ironveil_armory", "ironveil_arcanist"],
        "quiet_chance": 0.8,
        "unlock_level": 40
    },
    {
        "id": "ashen_wastes",
        "name": "Ashen Wastes",
        "description": "A blasted landscape where an ancient battle scorched the earth. Embers still glow beneath the ash.",
        "is_town": False,
        "recommended_level": 44,
        "connections": ["town_ironveil", "cinder_depths"],
        "encounters": [
            {"enemy_ids": ["ash_wraith"], "weight": 1.0, "level_min": 44, "level_max": 46},
            {"enemy_ids": ["ember_elemental", "ash_wraith"], "weight": 0.8, "level_min": 45, "level_max": 47},
            {"enemy_ids": ["cinder_fiend"], "weight": 0.5, "level_min": 46, "level_max": 48}
        ],
        "quiet_chance": 0.15,
        "unlock_level": 42
    },
    {
        "id": "cinder_depths",
        "name": "Cinder Depths",
        "description": "Volcanic caverns where magma rivers flow between obsidian pillars. The heat is oppressive.",
        "is_town": False,
        "recommended_level": 47,
        "connections": ["ashen_wastes", "molten_sanctum"],
        "encounters": [
            {"enemy_ids": ["magma_golem"], "weight": 1.0, "level_min": 47, "level_max": 49},
            {"enemy_ids": ["fire_drake", "ember_elemental"], "weight": 0.8, "level_min": 48, "level_max": 50},
            {"enemy_ids": ["cinder_fiend", "magma_golem"], "weight": 0.6, "level_min": 49, "level_max": 51}
        ],
        "quiet_chance": 0.15,
        "unlock_level": 45
    },
    {
        "id": "sunken_citadel",
        "name": "Sunken Citadel",
        "description": "A drowned fortress rising from a black lake. The water is unnaturally still and cold.",
        "is_town": False,
        "recommended_level": 46,
        "connections": ["town_ironveil", "abyssal_halls"],
        "encounters": [
            {"enemy_ids": ["drowned_knight"], "weight": 1.0, "level_min": 46, "level_max": 48},
            {"enemy_ids": ["abyssal_horror"], "weight": 0.7, "level_min": 47, "level_max": 49},
            {"enemy_ids": ["drowned_knight", "void_stalker"], "weight": 0.5, "level_min": 48, "level_max": 50}
        ],
        "quiet_chance": 0.15,
        "unlock_level": 44
    },
    {
        "id": "abyssal_halls",
        "name": "Abyssal Halls",
        "description": "The deepest chambers of the Sunken Citadel, where reality thins and the void seeps through.",
        "is_town": False,
        "recommended_level": 50,
        "connections": ["sunken_citadel", "void_throne"],
        "encounters": [
            {"enemy_ids": ["void_stalker", "abyssal_horror"], "weight": 1.0, "level_min": 50, "level_max": 52},
            {"enemy_ids": ["void_archon"], "weight": 0.5, "level_min": 51, "level_max": 53},
            {"enemy_ids": ["void_stalker", "void_stalker", "abyssal_horror"], "weight": 0.3, "level_min": 52, "level_max": 54}
        ],
        "quiet_chance": 0.1,
        "unlock_level": 48
    },
    {
        "id": "molten_sanctum",
        "name": "Molten Sanctum",
        "description": "The heart of the volcano, where an ancient dragon once forged weapons of terrible power.",
        "is_town": False,
        "recommended_level": 52,
        "connections": ["cinder_depths", "void_throne"],
        "encounters": [
            {"enemy_ids": ["fire_drake", "magma_golem"], "weight": 1.0, "level_min": 52, "level_max": 54},
            {"enemy_ids": ["infernal_titan"], "weight": 0.4, "level_min": 53, "level_max": 55},
            {"enemy_ids": ["cinder_fiend", "fire_drake"], "weight": 0.6, "level_min": 53, "level_max": 55}
        ],
        "quiet_chance": 0.1,
        "unlock_level": 50
    },
    {
        "id": "void_throne",
        "name": "The Void Throne",
        "description": "A chamber at the edge of reality, where the Void Sovereign sits upon a throne of nothing.",
        "is_town": False,
        "recommended_level": 55,
        "connections": ["abyssal_halls", "molten_sanctum"],
        "encounters": [
            {"enemy_ids": ["void_archon", "void_stalker"], "weight": 1.0, "level_min": 54, "level_max": 56},
            {"enemy_ids": ["void_archon", "void_archon"], "weight": 0.4, "level_min": 55, "level_max": 57},
            {"enemy_ids": ["void_sovereign"], "weight": 0.1, "level_min": 55, "level_max": 55, "is_boss": True, "boss_id": "void_sovereign"}
        ],
        "quiet_chance": 0.1,
        "unlock_level": 52
    }
]

# ============================================================================
# NEW NPCs
# ============================================================================
new_npcs = [
    {
        "id": "commander_vex",
        "name": "Commander Vex",
        "race_id": "human",
        "gender": "female",
        "description": "The stern commander of Ironveil, scarred from decades of border wars.",
        "location_id": "town_ironveil",
        "marriageable": False,
        "dialogue": [
            "Ironveil stands because we do not bend.",
            "The Void Sovereign grows stronger. We must act before it's too late.",
            "Every soldier under my command has earned their place. Have you?",
            "The walls are old. Older than the city. Older than the mountain.",
            "I've buried too many good people. I won't bury more if I can help it.",
            "You want to help? Good. We need every blade we can get."
        ]
    },
    {
        "id": "artificer_zara",
        "name": "Artificer Zara",
        "race_id": "gnome",
        "gender": "female",
        "description": "A gnome artificer whose workshop fills half a city block with humming machinery.",
        "location_id": "town_ironveil",
        "marriageable": True,
        "marriage_affinity": 85,
        "gift_item_ids": ["ember_scale", "crystal_carapace", "runed_staff"],
        "dialogue": [
            "This machine? Oh, it only explodes on Tuesdays. Today is... not Tuesday.",
            "I've been working on a device that can fold space. It currently folds my laundry instead.",
            "The Void Throne interests me. Scientifically. Not existentially. Mostly.",
            "My last apprentice was very talented. Unfortunately, so was the explosion.",
            "Ironveil's wards are my design. They hum at exactly 440 Hz. Perfect A.",
            "You want enchantments? I want test subjects. Fair trade?"
        ]
    },
    {
        "id": "chronicler_thon",
        "name": "Chronicler Thon",
        "race_id": "lamia",
        "gender": "male",
        "description": "An ancient lamia who has recorded every event in Ironveil's history.",
        "location_id": "town_ironveil",
        "marriageable": False,
        "dialogue": [
            "I remember when this mountain was a hill. Time is a funny thing.",
            "The Void Sovereign is not new. It has waited since before the first city.",
            "History is not just dates and battles. It's the smell of bread on a winter morning.",
            "I've written four hundred volumes. I'm running out of shelves.",
            "The old texts speak of a weapon that can seal the void. If they're not lying.",
            "You remind me of someone. Someone who didn't come back. Be careful."
        ]
    }
]

# ============================================================================
# NEW SHOPS
# ============================================================================
new_shops = [
    {
        "id": "ironveil_armory",
        "name": "Ironveil Armory",
        "item_ids": ["iron_sword", "steel_sword", "leather_vest", "chain_mail", "greater_potion", "greater_ether"],
        "buy_rate": 1.0,
        "sell_rate": 0.45,
        "faction_id": "iron_covenant",
        "race_buy_rates": {"dwarf": 0.85, "goliath": 0.9},
        "race_item_ids": {"dwarf": ["masterwork_plate"], "goliath": ["giant_hammer"]}
    },
    {
        "id": "ironveil_arcanist",
        "name": "Zara's Workshop",
        "item_ids": ["apprentice_staff", "runed_staff", "minor_ether", "ether", "greater_ether", "alchemical_kit"],
        "buy_rate": 1.0,
        "sell_rate": 0.45,
        "race_buy_rates": {"gnome": 0.8, "elf": 0.9},
        "race_item_ids": {"gnome": ["tinker_tools"], "elf": ["elven_bow", "moonstone_amulet"]}
    }
]

# ============================================================================
# NEW ENEMIES
# ============================================================================
new_enemies = [
    {"id": "stone_revenant", "name": "Stone Revenant", "level": 42, "family": "construct", "stats": {"STR": 30, "END": 35, "INT": 5, "AGI": 10}, "hp": 280, "mp": 20, "skill_ids": ["enemy_crush", "enemy_stone_fist"], "ai_behavior_id": "defensive", "loot": [{"item_id": "granite_core", "chance": 0.3}]},
    {"id": "petrified_treant", "name": "Petrified Treant", "level": 43, "family": "construct", "stats": {"STR": 28, "END": 40, "INT": 3, "AGI": 5}, "hp": 320, "mp": 10, "skill_ids": ["enemy_thorn_lash", "enemy_crush"], "ai_behavior_id": "defensive", "loot": [{"item_id": "briar_heart", "chance": 0.25}]},
    {"id": "void_stalker", "name": "Void Stalker", "level": 44, "family": "void", "stats": {"STR": 20, "END": 22, "INT": 35, "AGI": 40}, "hp": 200, "mp": 120, "skill_ids": ["enemy_dark_bolt", "enemy_spectral_touch", "shadowstep"], "ai_behavior_id": "aggressive", "loot": [{"item_id": "shadow_essence", "chance": 0.4}]},
    {"id": "ash_wraith", "name": "Ash Wraith", "level": 45, "family": "undead", "stats": {"STR": 18, "END": 20, "INT": 38, "AGI": 30}, "hp": 220, "mp": 140, "skill_ids": ["enemy_dark_bolt", "enemy_ember_bite", "enemy_spectral_touch"], "ai_behavior_id": "aggressive", "loot": [{"item_id": "wraith_lantern", "chance": 0.3}]},
    {"id": "ember_elemental", "name": "Ember Elemental", "level": 46, "family": "elemental", "stats": {"STR": 25, "END": 28, "INT": 30, "AGI": 20}, "hp": 260, "mp": 100, "skill_ids": ["enemy_ember_bite", "enemy_sunfire"], "ai_behavior_id": "aggressive", "loot": [{"item_id": "ember_scale", "chance": 0.35}]},
    {"id": "cinder_fiend", "name": "Cinder Fiend", "level": 48, "family": "demon", "stats": {"STR": 35, "END": 30, "INT": 28, "AGI": 25}, "hp": 300, "mp": 80, "skill_ids": ["enemy_ember_bite", "enemy_crush", "enemy_dark_bolt"], "ai_behavior_id": "berserk", "loot": [{"item_id": "shadow_essence", "chance": 0.3}]},
    {"id": "magma_golem", "name": "Magma Golem", "level": 48, "family": "construct", "stats": {"STR": 40, "END": 45, "INT": 5, "AGI": 8}, "hp": 400, "mp": 30, "skill_ids": ["enemy_stone_fist", "enemy_crush", "enemy_ember_bite"], "ai_behavior_id": "defensive", "loot": [{"item_id": "granite_core", "chance": 0.4}]},
    {"id": "fire_drake", "name": "Fire Drake", "level": 50, "family": "dragon", "stats": {"STR": 38, "END": 35, "INT": 25, "AGI": 30}, "hp": 350, "mp": 100, "skill_ids": ["enemy_ember_bite", "enemy_frost_breath", "enemy_sunfire"], "ai_behavior_id": "aggressive", "loot": [{"item_id": "drake_scale", "chance": 0.3}, {"item_id": "ember_scale", "chance": 0.4}]},
    {"id": "drowned_knight", "name": "Drowned Knight", "level": 47, "family": "undead", "stats": {"STR": 32, "END": 38, "INT": 15, "AGI": 18}, "hp": 320, "mp": 40, "skill_ids": ["enemy_crush", "enemy_stone_fist", "shadow_bind"], "ai_behavior_id": "defensive", "loot": [{"item_id": "steel_sword", "chance": 0.2}]},
    {"id": "abyssal_horror", "name": "Abyssal Horror", "level": 49, "family": "void", "stats": {"STR": 30, "END": 35, "INT": 40, "AGI": 15}, "hp": 340, "mp": 150, "skill_ids": ["enemy_dark_bolt", "enemy_bog_hex", "enemy_crystal_burst"], "ai_behavior_id": "tactical", "loot": [{"item_id": "shadow_essence", "chance": 0.5}]},
    {"id": "void_archon", "name": "Void Archon", "level": 53, "family": "void", "stats": {"STR": 35, "END": 38, "INT": 45, "AGI": 35}, "hp": 380, "mp": 180, "skill_ids": ["enemy_dark_bolt", "enemy_tempest", "enemy_crystal_burst", "shadow_bind"], "ai_behavior_id": "tactical", "loot": [{"item_id": "void_shard", "chance": 0.2}]},
    {"id": "infernal_titan", "name": "Infernal Titan", "level": 54, "family": "demon", "stats": {"STR": 50, "END": 48, "INT": 20, "AGI": 15}, "hp": 500, "mp": 60, "skill_ids": ["enemy_crush", "enemy_stone_fist", "enemy_sunfire", "enemy_ember_bite"], "ai_behavior_id": "berserk", "loot": [{"item_id": "drake_scale", "chance": 0.3}]},
    {"id": "void_sovereign", "name": "Void Sovereign", "level": 55, "family": "void", "is_boss": True, "stats": {"STR": 45, "END": 50, "INT": 60, "AGI": 40}, "hp": 800, "mp": 300, "skill_ids": ["enemy_dark_bolt", "enemy_tempest", "enemy_crystal_burst", "shadow_bind", "enemy_spectral_touch"], "ai_behavior_id": "tactical", "boss_phases": [
        {"hp_fraction": 0.7, "name": "Void Shield", "modifiers": {"flat": {"magic_resist": 25, "armor": 20}}, "shield_hp": 150},
        {"hp_fraction": 0.4, "name": "Summon Void Spawn", "modifiers": {"pct": {"magic_power": 0.4}}, "summons": [{"enemy_id": "void_stalker", "level": 52}, {"enemy_id": "void_stalker", "level": 52}]},
        {"hp_fraction": 0.15, "name": "Void Nova", "modifiers": {"pct": {"magic_power": 0.7, "speed": 0.4}}, "shield_hp": 200}
    ], "boss_rules": {
        "enrage_round": 12,
        "enrage_modifiers": {"pct": {"magic_power": 0.5, "physical_power": 0.3}},
        "telegraph": {"interval": 4, "damage": 70, "counter_damage": 90, "warning": "The Void Sovereign tears open a rift in reality!", "impact": "A wave of void energy erupts from the rift!"},
        "environment": {"per_round_damage": 10, "message": "The void itself lashes out at everyone!"}
    }, "loot": [{"item_id": "void_shard", "chance": 1.0}, {"item_id": "codex_infinite", "chance": 0.3}]}
]

# ============================================================================
# NEW QUESTS
# ============================================================================
new_quests = [
    {
        "id": "ironveil_welcome",
        "name": "Welcome to Ironveil",
        "description": "Commander Vex wants to test your worth before granting access to the city's inner sanctum.",
        "min_level": 41,
        "giver_id": "commander_vex",
        "start_area_id": "town_ironveil",
        "turn_in_area_id": "town_ironveil",
        "objectives": [
            {"kind": "defeat_enemy", "target_id": "stone_revenant", "quantity": 5},
            {"kind": "defeat_enemy", "target_id": "void_stalker", "quantity": 3}
        ],
        "rewards": {"exp": 4000, "gold": 1500}
    },
    {
        "id": "ashen_expedition",
        "name": "The Ashen Expedition",
        "description": "Chronicler Thon needs someone to recover artifacts from the Ashen Wastes before they're lost forever.",
        "min_level": 44,
        "giver_id": "chronicler_thon",
        "start_area_id": "town_ironveil",
        "turn_in_area_id": "town_ironveil",
        "objectives": [
            {"kind": "visit_area", "target_id": "ashen_wastes", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "ash_wraith", "quantity": 5},
            {"kind": "collect_item", "target_id": "wraith_lantern", "quantity": 2}
        ],
        "rewards": {"exp": 5000, "gold": 2000}
    },
    {
        "id": "cinder_heart",
        "name": "Heart of Cinder",
        "description": "Artificer Zara needs a core sample from the deepest magma flow to power her latest invention.",
        "min_level": 48,
        "giver_id": "artificer_zara",
        "start_area_id": "town_ironveil",
        "turn_in_area_id": "town_ironveil",
        "objectives": [
            {"kind": "visit_area", "target_id": "cinder_depths", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "magma_golem", "quantity": 3},
            {"kind": "collect_item", "target_id": "ember_scale", "quantity": 5}
        ],
        "rewards": {"exp": 6000, "gold": 2500}
    },
    {
        "id": "void_throne_assault",
        "name": "The Void Throne",
        "description": "Commander Vex is assembling a strike force to assault the Void Throne. You are the tip of the spear.",
        "min_level": 53,
        "giver_id": "commander_vex",
        "start_area_id": "town_ironveil",
        "turn_in_area_id": "town_ironveil",
        "objectives": [
            {"kind": "visit_area", "target_id": "void_throne", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "void_sovereign", "quantity": 1}
        ],
        "rewards": {"exp": 10000, "gold": 5000}
    },
    {
        "id": "sunken_secrets",
        "name": "Secrets of the Sunken Citadel",
        "description": "Chronicler Thon believes the Sunken Citadel holds records of the first war against the void.",
        "min_level": 46,
        "giver_id": "chronicler_thon",
        "start_area_id": "town_ironveil",
        "turn_in_area_id": "town_ironveil",
        "objectives": [
            {"kind": "visit_area", "target_id": "sunken_citadel", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "drowned_knight", "quantity": 5},
            {"kind": "defeat_enemy", "target_id": "abyssal_horror", "quantity": 2}
        ],
        "rewards": {"exp": 5500, "gold": 2200}
    }
]

# ============================================================================
# NEW FACTION
# ============================================================================
new_faction = {
    "id": "iron_covenant",
    "name": "Iron Covenant",
    "rivals": ["ash_court"],
    "shop_discount_per_point": 0.0015,
    "max_discount": 0.18
}

# ============================================================================
# WRITE FILES
# ============================================================================

# World
with open('data/world.json') as f:
    world = json.load(f)

world["areas"].extend(new_areas)
world["npcs"].extend(new_npcs)
world["shops"].extend(new_shops)

# Update obsidian_gate connections to include ironveil_approach
for area in world["areas"]:
    if area["id"] == "obsidian_gate":
        if "ironveil_approach" not in area.get("connections", []):
            area.setdefault("connections", []).append("ironveil_approach")

with open('data/world.json', 'w') as f:
    json.dump(world, f, indent=2)

# Enemies
with open('data/enemies.json') as f:
    enemies = json.load(f)
enemies["enemies"].extend(new_enemies)
with open('data/enemies.json', 'w') as f:
    json.dump(enemies, f, indent=2)

# Quests
with open('data/quests.json') as f:
    quests = json.load(f)
quests["quests"].extend(new_quests)
with open('data/quests.json', 'w') as f:
    json.dump(quests, f, indent=2)

# Factions
with open('data/factions.json') as f:
    factions = json.load(f)
factions["factions"].append(new_faction)
with open('data/factions.json', 'w') as f:
    json.dump(factions, f, indent=2)

print(f"Areas: {len(world['areas'])} (was 17)")
print(f"NPCs: {len(world['npcs'])} (was 25)")
print(f"Shops: {len(world['shops'])} (was 8)")
print(f"Enemies: {len(enemies['enemies'])} (was 30)")
print(f"Quests: {len(quests['quests'])} (was 39)")
print(f"Factions: {len(factions['factions'])} (was 8)")
