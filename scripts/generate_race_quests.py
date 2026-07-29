#!/usr/bin/env python3
"""Generate race-specific questlines for all 15 races."""

import json

with open('data/quests.json') as f:
    data = json.load(f)

# Race-specific quests
new_quests = [
    # HUMAN
    {
        "id": "human_heritage",
        "name": "The Many Roads",
        "description": "A human traveller asks you to deliver letters to three settlements, proving that humans belong everywhere.",
        "min_level": 5,
        "giver_id": "innkeeper_mara",
        "start_area_id": "town_ashvale",
        "turn_in_area_id": "town_ashvale",
        "required_race_ids": ["human"],
        "objectives": [
            {"kind": "visit_area", "target_id": "town_emberwatch", "quantity": 1},
            {"kind": "visit_area", "target_id": "town_stonehaven", "quantity": 1},
            {"kind": "visit_area", "target_id": "town_skyreach", "quantity": 1}
        ],
        "rewards": {"exp": 500, "gold": 200}
    },
    
    # ELF
    {
        "id": "elf_songs",
        "name": "Songs of the Silver Wood",
        "description": "Elder Amariel asks you to recover three lost elven songs from the depths of Mosswood.",
        "min_level": 12,
        "giver_id": "elder_amariel",
        "start_area_id": "mosswood",
        "turn_in_area_id": "mosswood",
        "required_race_ids": ["elf", "half_elf"],
        "objectives": [
            {"kind": "defeat_enemy", "target_id": "briar_witch", "quantity": 3},
            {"kind": "collect_item", "target_id": "moonleaf_brooch", "quantity": 2}
        ],
        "rewards": {"exp": 1200, "gold": 400}
    },
    
    # DWARF
    {
        "id": "dwarf_deep_roads",
        "name": "The Deep Roads",
        "description": "Thane Dorrim sends you into the crystal mines to reopen a collapsed tunnel and recover a lost clan relic.",
        "min_level": 22,
        "giver_id": "thane_dorrim",
        "start_area_id": "town_stonehaven",
        "turn_in_area_id": "town_stonehaven",
        "required_race_ids": ["dwarf"],
        "objectives": [
            {"kind": "visit_area", "target_id": "crystal_mines", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "crystal_beetle", "quantity": 5},
            {"kind": "collect_item", "target_id": "granite_core", "quantity": 3}
        ],
        "rewards": {"exp": 2000, "gold": 800}
    },
    
    # DRAGONKIN
    {
        "id": "dragonkin_oath",
        "name": "The First Oath",
        "description": "Keth Cloudscar asks you to honour the first dragonkin oath by defeating a thunder drake at the Obsidian Gate.",
        "min_level": 32,
        "giver_id": "keth_cloudscar",
        "start_area_id": "town_skyreach",
        "turn_in_area_id": "town_skyreach",
        "required_race_ids": ["dragonkin"],
        "objectives": [
            {"kind": "visit_area", "target_id": "obsidian_gate", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "thunder_drake", "quantity": 1}
        ],
        "rewards": {"exp": 3000, "gold": 1200}
    },
    
    # DEMON / TIEFLING
    {
        "id": "demon_ash_court",
        "name": "The Ash Court Summons",
        "description": "Mother Sable delivers a summons from the Ash Court. You must prove your worth or face the consequences.",
        "min_level": 18,
        "giver_id": "mother_sable",
        "start_area_id": "town_emberwatch",
        "turn_in_area_id": "town_emberwatch",
        "required_race_ids": ["demon", "tiefling"],
        "objectives": [
            {"kind": "defeat_enemy", "target_id": "ash_hound", "quantity": 5},
            {"kind": "talk_to", "target_id": "alchemist_pell", "quantity": 1}
        ],
        "rewards": {"exp": 1500, "gold": 600}
    },
    
    # BEASTKIN
    {
        "id": "beastkin_migration",
        "name": "The Great Migration",
        "description": "Siv Quickpaw asks you to scout the migration route and clear the path of threats.",
        "min_level": 10,
        "giver_id": "siv_quickpaw",
        "start_area_id": "old_road",
        "turn_in_area_id": "old_road",
        "required_race_ids": ["beastkin"],
        "objectives": [
            {"kind": "visit_area", "target_id": "mosswood", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "grey_wolf", "quantity": 4},
            {"kind": "visit_area", "target_id": "glassmarsh", "quantity": 1}
        ],
        "rewards": {"exp": 800, "gold": 300}
    },
    
    # ORC
    {
        "id": "orc_blood_debt",
        "name": "The Blood Debt",
        "description": "Gruk Ironjaw tells you of a blood debt owed to his clan. You must defeat the bandits who wronged them.",
        "min_level": 8,
        "giver_id": "gruk_ironjaw",
        "start_area_id": "old_road",
        "turn_in_area_id": "old_road",
        "required_race_ids": ["orc", "half_orc"],
        "objectives": [
            {"kind": "defeat_enemy", "target_id": "bandit", "quantity": 6},
            {"kind": "defeat_enemy", "target_id": "bandit_chief", "quantity": 1}
        ],
        "rewards": {"exp": 900, "gold": 350}
    },
    {
        "id": "orc_war_song",
        "name": "The War Song",
        "description": "An orc elder asks you to prove your strength in the arena, earning the right to sing the war song.",
        "min_level": 15,
        "giver_id": "gruk_ironjaw",
        "start_area_id": "old_road",
        "turn_in_area_id": "old_road",
        "required_race_ids": ["orc", "half_orc"],
        "objectives": [
            {"kind": "defeat_enemy", "target_id": "road_reaver", "quantity": 5},
            {"kind": "defeat_enemy", "target_id": "redcap_raider", "quantity": 3}
        ],
        "rewards": {"exp": 1400, "gold": 500}
    },
    
    # GNOME
    {
        "id": "gnome_invention",
        "name": "The Grand Invention",
        "description": "Pip Sprocket needs rare components for a device that will revolutionise travel. Gather the parts!",
        "min_level": 12,
        "giver_id": "pip_sprocket",
        "start_area_id": "town_emberwatch",
        "turn_in_area_id": "town_emberwatch",
        "required_race_ids": ["gnome"],
        "objectives": [
            {"kind": "collect_item", "target_id": "ember_scale", "quantity": 3},
            {"kind": "collect_item", "target_id": "crystal_carapace", "quantity": 2},
            {"kind": "visit_area", "target_id": "crystal_mines", "quantity": 1}
        ],
        "rewards": {"exp": 1100, "gold": 450}
    },
    {
        "id": "gnome_explosion",
        "name": "Controlled Demolition",
        "description": "Pip's latest invention has gone haywire in the mines. Shut it down before it brings the ceiling down!",
        "min_level": 18,
        "giver_id": "pip_sprocket",
        "start_area_id": "town_emberwatch",
        "turn_in_area_id": "town_emberwatch",
        "required_race_ids": ["gnome"],
        "objectives": [
            {"kind": "visit_area", "target_id": "crystal_mines", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "ruin_sentinel", "quantity": 3}
        ],
        "rewards": {"exp": 1600, "gold": 600}
    },
    
    # HALFLING
    {
        "id": "halfling_pie_contest",
        "name": "The Great Pie Contest",
        "description": "Rose Underhill challenges you to gather the finest ingredients for the annual halfling pie contest.",
        "min_level": 5,
        "giver_id": "rose_underhill",
        "start_area_id": "town_ashvale",
        "turn_in_area_id": "town_ashvale",
        "required_race_ids": ["halfling"],
        "objectives": [
            {"kind": "collect_item", "target_id": "wolf_pelt", "quantity": 2},
            {"kind": "collect_item", "target_id": "minor_potion", "quantity": 3},
            {"kind": "talk_to", "target_id": "innkeeper_mara", "quantity": 1}
        ],
        "rewards": {"exp": 400, "gold": 200}
    },
    {
        "id": "halfling_thief",
        "name": "The Uninvited Guest",
        "description": "A halfling thief has stolen from the community. Track them down and recover the goods.",
        "min_level": 10,
        "giver_id": "rose_underhill",
        "start_area_id": "town_ashvale",
        "turn_in_area_id": "town_ashvale",
        "required_race_ids": ["halfling"],
        "objectives": [
            {"kind": "defeat_enemy", "target_id": "bandit", "quantity": 4},
            {"kind": "collect_item", "target_id": "bandit_coin", "quantity": 5}
        ],
        "rewards": {"exp": 800, "gold": 350}
    },
    
    # GENASI
    {
        "id": "genasi_elemental_heritage",
        "name": "Elemental Heritage",
        "description": "Ember Skysong asks you to commune with the elemental planes at four sacred sites.",
        "min_level": 22,
        "giver_id": "ember_skysong",
        "start_area_id": "town_emberwatch",
        "turn_in_area_id": "town_emberwatch",
        "required_race_ids": ["genasi"],
        "objectives": [
            {"kind": "visit_area", "target_id": "storm_plateau", "quantity": 1},
            {"kind": "visit_area", "target_id": "glassmarsh", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "storm_harpy", "quantity": 3}
        ],
        "rewards": {"exp": 2200, "gold": 900}
    },
    {
        "id": "genasi_storm_calling",
        "name": "The Storm Calling",
        "description": "A genasi elder asks you to calm a raging elemental storm threatening Skyreach.",
        "min_level": 30,
        "giver_id": "ember_skysong",
        "start_area_id": "town_skyreach",
        "turn_in_area_id": "town_skyreach",
        "required_race_ids": ["genasi"],
        "objectives": [
            {"kind": "visit_area", "target_id": "storm_plateau", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "thunder_drake", "quantity": 2}
        ],
        "rewards": {"exp": 2800, "gold": 1100}
    },
    
    # GOLIATH
    {
        "id": "goliath_endurance",
        "name": "The Mountain's Test",
        "description": "Korrath Peaks challenges you to survive the mountain's trials — a test of endurance and will.",
        "min_level": 25,
        "giver_id": "korrath_peaks",
        "start_area_id": "town_stonehaven",
        "turn_in_area_id": "town_stonehaven",
        "required_race_ids": ["goliath"],
        "objectives": [
            {"kind": "visit_area", "target_id": "red_pass", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "hill_troll", "quantity": 3},
            {"kind": "defeat_enemy", "target_id": "granite_golem", "quantity": 2}
        ],
        "rewards": {"exp": 2500, "gold": 1000}
    },
    {
        "id": "goliath_score_keeping",
        "name": "The Reckoning",
        "description": "Among goliaths, every deed is scored. Prove your worth by defeating the strongest foes in the land.",
        "min_level": 35,
        "giver_id": "korrath_peaks",
        "start_area_id": "town_stonehaven",
        "turn_in_area_id": "town_stonehaven",
        "required_race_ids": ["goliath"],
        "objectives": [
            {"kind": "defeat_enemy", "target_id": "iron_colossus", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "shadow_warden", "quantity": 1}
        ],
        "rewards": {"exp": 3500, "gold": 1400}
    },
    
    # LAMIA
    {
        "id": "lamia_ancient_library",
        "name": "The Lost Library",
        "description": "Sythia Coils asks you to recover three ancient tomes from the Drowned Archive.",
        "min_level": 20,
        "giver_id": "sythia_coils",
        "start_area_id": "hollow_cave",
        "turn_in_area_id": "hollow_cave",
        "required_race_ids": ["lamia"],
        "objectives": [
            {"kind": "visit_area", "target_id": "drowned_archive", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "lantern_wraith", "quantity": 3},
            {"kind": "collect_item", "target_id": "shadow_essence", "quantity": 3}
        ],
        "rewards": {"exp": 1800, "gold": 700}
    },
    {
        "id": "lamia_coil_memory",
        "name": "The Serpent's Memory",
        "description": "An ancient lamia asks you to visit the places where her kind once ruled, recovering lost history.",
        "min_level": 30,
        "giver_id": "sythia_coils",
        "start_area_id": "hollow_cave",
        "turn_in_area_id": "hollow_cave",
        "required_race_ids": ["lamia"],
        "objectives": [
            {"kind": "visit_area", "target_id": "cloud_ruins", "quantity": 1},
            {"kind": "visit_area", "target_id": "obsidian_gate", "quantity": 1},
            {"kind": "defeat_enemy", "target_id": "ruin_sentinel", "quantity": 4}
        ],
        "rewards": {"exp": 2800, "gold": 1100}
    },
    
    # ARACHNE
    {
        "id": "arachne_web_fate",
        "name": "Threads of Fate",
        "description": "Nethys Websong asks you to gather silk from three ancient spider nests to weave a tapestry of prophecy.",
        "min_level": 18,
        "giver_id": "nethys_websong",
        "start_area_id": "mosswood",
        "turn_in_area_id": "mosswood",
        "required_race_ids": ["arachne"],
        "objectives": [
            {"kind": "defeat_enemy", "target_id": "cave_spider", "quantity": 6},
            {"kind": "collect_item", "target_id": "wraith_lantern", "quantity": 2}
        ],
        "rewards": {"exp": 1500, "gold": 600}
    },
    {
        "id": "arachne_predator_hunt",
        "name": "The Great Hunt",
        "description": "An arachne elder challenges you to prove your hunting prowess by defeating the most dangerous prey.",
        "min_level": 28,
        "giver_id": "nethys_websong",
        "start_area_id": "mosswood",
        "turn_in_area_id": "mosswood",
        "required_race_ids": ["arachne"],
        "objectives": [
            {"kind": "defeat_enemy", "target_id": "thorn_stalker", "quantity": 4},
            {"kind": "defeat_enemy", "target_id": "mire_oracle", "quantity": 1}
        ],
        "rewards": {"exp": 2600, "gold": 1000}
    },
]

data["quests"].extend(new_quests)

with open('data/quests.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"Added {len(new_quests)} race-specific quests")
print(f"Total quests: {len(data['quests'])}")

# Show coverage
races_covered = set()
for q in new_quests:
    for race in q.get("required_race_ids", []):
        races_covered.add(race)
print(f"Races with quests: {sorted(races_covered)}")
