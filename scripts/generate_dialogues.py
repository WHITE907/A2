#!/usr/bin/env python3
"""Generate additional branching dialogue trees."""

import json

with open('data/dialogues.json') as f:
    data = json.load(f)

new_dialogues = [
    # 1. Thane Dorrim's Lost Clan (dwarf/goliath race-specific)
    {
        "id": "dorrim_lost_clan",
        "speaker_id": "thane_dorrim",
        "title": "The Erased Ledger",
        "nodes": [
            {"id": "start", "text": "Thane Dorrim holds a blank stone tablet. 'My clan's name was erased from this ledger. Someone wanted us forgotten. I need to know why.'", "options": [
                {"id": "accept", "text": "I'll help you find the truth.", "next_node_id": "investigate"},
                {"id": "dwarf_response", "text": "[Dwarf] 'An erased name is a grave insult. I'll find who did this.'", "conditions": {"race_ids": ["dwarf"]}, "actions": [{"type": "affinity", "target_id": "thane_dorrim", "amount": 10}], "next_node_id": "dwarf_path"},
                {"id": "goliath_response", "text": "[Goliath] 'Among my people, score-keeping is sacred. This is a crime.'", "conditions": {"race_ids": ["goliath"]}, "actions": [{"type": "affinity", "target_id": "thane_dorrim", "amount": 10}], "next_node_id": "goliath_path"},
                {"id": "decline", "text": "That sounds like dwarven politics. I'll pass.", "next_node_id": "end"}
            ]},
            {"id": "investigate", "text": "'Start in the deep mines. The old records are kept there, if they haven't been destroyed.'", "options": [
                {"id": "go", "text": "To the mines, then.", "actions": [{"type": "quest", "quest_id": "dwarf_deep_roads"}], "next_node_id": "end"}
            ]},
            {"id": "dwarf_path", "text": "Dorrim grips your arm. 'A dwarf who understands. The deep mines hold the answer. Go with my blessing — and my axe, if you need it.'", "options": [
                {"id": "dwarf_go", "text": "I won't fail you, Thane.", "actions": [{"type": "quest", "quest_id": "dwarf_deep_roads"}, {"type": "reputation", "faction_id": "stonehaven_clans", "amount": 10}], "next_node_id": "end"}
            ]},
            {"id": "goliath_path", "text": "Dorrim nods slowly. 'A goliath who respects the score. The deep mines hold the answer. Bring me proof, and the clans will remember your name.'", "options": [
                {"id": "goliath_go", "text": "The score will be settled.", "actions": [{"type": "quest", "quest_id": "goliath_score_keeping"}, {"type": "reputation", "faction_id": "stonehaven_clans", "amount": 10}], "next_node_id": "end"}
            ]},
            {"id": "end", "text": "", "options": []}
        ]
    },
    # 2. Abbess Sol's Vision (class-specific: cleric/paladin/oracle)
    {
        "id": "sol_divine_vision",
        "speaker_id": "abbess_sol",
        "title": "The Roofless Chapel",
        "nodes": [
            {"id": "start", "text": "Abbess Sol stares at the open sky above her chapel. 'The roof was not destroyed. It was taken. Something in the skyreach ruins wants to be seen.'", "options": [
                {"id": "cleric_response", "text": "[Cleric/High Priest/Inquisitor] 'I feel it too. A divine presence, calling from above.'", "conditions": {"class_ids": ["cleric", "high_priest", "inquisitor", "oracle"]}, "next_node_id": "divine_path"},
                {"id": "paladin_response", "text": "[Paladin/Templar] 'My oath compels me to investigate. What do you need?'", "conditions": {"class_ids": ["paladin", "templar", "crusader", "godsworn"]}, "next_node_id": "oath_path"},
                {"id": "generic", "text": "What do you think took the roof?", "next_node_id": "explain"},
                {"id": "decline", "text": "Sounds like a structural problem, not a spiritual one.", "next_node_id": "end"}
            ]},
            {"id": "divine_path", "text": "Sol's eyes widen. 'You can feel it? Then you must go. The ruins hold something sacred — or something that wants to be.'", "options": [
                {"id": "divine_go", "text": "I'll seek the source.", "actions": [{"type": "quest", "quest_id": "genasi_elemental_heritage"}, {"type": "reputation", "faction_id": "skyreach_archivists", "amount": 10}], "next_node_id": "end"}
            ]},
            {"id": "oath_path", "text": "Sol smiles. 'An oath-bound warrior. The ruins are dangerous, but your conviction will light the way. Bring back what you find.'", "options": [
                {"id": "oath_go", "text": "My oath is my compass.", "actions": [{"type": "quest", "quest_id": "dragonkin_oath"}, {"type": "reputation", "faction_id": "skyreach_archivists", "amount": 10}], "next_node_id": "end"}
            ]},
            {"id": "explain", "text": "'Something ancient. Something that remembers when the sky was different. The archivists know more, but they won't speak to just anyone.'", "options": [
                {"id": "accept", "text": "I'll talk to the archivists.", "actions": [{"type": "quest", "quest_id": "dragonkin_oath"}], "next_node_id": "end"},
                {"id": "decline2", "text": "Maybe later.", "next_node_id": "end"}
            ]},
            {"id": "end", "text": "", "options": []}
        ]
    },
    # 3. Archivist Lume's Forbidden Knowledge (race-specific: lamia/elf)
    {
        "id": "lume_forbidden",
        "speaker_id": "archivist_lume",
        "title": "The Weather Records",
        "nodes": [
            {"id": "start", "text": "Archivist Lume shuffles through scrolls. 'I've found something in the weather records. A pattern that shouldn't exist. Someone — or something — has been manipulating the storms for centuries.'", "options": [
                {"id": "lamia_response", "text": "[Lamia] 'Centuries? I remember when the storms first changed. Let me help.'", "conditions": {"race_ids": ["lamia"]}, "actions": [{"type": "affinity", "target_id": "archivist_lume", "amount": 15}], "next_node_id": "lamia_path"},
                {"id": "elf_response", "text": "[Elf] 'The old songs speak of storm-weavers. Perhaps they were real.'", "conditions": {"race_ids": ["elf", "half_elf"]}, "actions": [{"type": "affinity", "target_id": "archivist_lume", "amount": 10}], "next_node_id": "elf_path"},
                {"id": "genasi_response", "text": "[Genasi] 'Storms? That's my domain. Show me the records.'", "conditions": {"race_ids": ["genasi"]}, "actions": [{"type": "affinity", "target_id": "archivist_lume", "amount": 10}], "next_node_id": "genasi_path"},
                {"id": "generic", "text": "What kind of pattern?", "next_node_id": "explain"}
            ]},
            {"id": "lamia_path", "text": "Lume stares. 'You... remember? Three hundred years of weather data and you can verify it from memory? This changes everything. Come, let us compare notes.'", "options": [
                {"id": "lamia_go", "text": "My memory is long, Archivist.", "actions": [{"type": "quest", "quest_id": "lamia_coil_memory"}, {"type": "reputation", "faction_id": "skyreach_archivists", "amount": 15}], "next_node_id": "end"}
            ]},
            {"id": "elf_path", "text": "Lume's eyes light up. 'Storm-weavers! I've read references but never confirmation. The storm plateau may hold answers. Will you investigate?'", "options": [
                {"id": "elf_go", "text": "The old songs don't lie.", "actions": [{"type": "quest", "quest_id": "genasi_storm_calling"}, {"type": "reputation", "faction_id": "skyreach_archivists", "amount": 10}], "next_node_id": "end"}
            ]},
            {"id": "genasi_path", "text": "Lume pushes a stack of scrolls toward you. 'Read these. Your elemental heritage may let you sense what I cannot. The storm plateau is where the pattern converges.'", "options": [
                {"id": "genasi_go", "text": "I'll read the storms themselves.", "actions": [{"type": "quest", "quest_id": "genasi_storm_calling"}, {"type": "reputation", "faction_id": "skyreach_archivists", "amount": 10}], "next_node_id": "end"}
            ]},
            {"id": "explain", "text": "'Every 47 years, a storm of unusual intensity strikes the same location. The next one is due in three months. I need someone to investigate the convergence point.'", "options": [
                {"id": "accept", "text": "I'll investigate.", "actions": [{"type": "quest", "quest_id": "genasi_elemental_heritage"}], "next_node_id": "end"},
                {"id": "decline", "text": "Sounds dangerous. Maybe someone else.", "next_node_id": "end"}
            ]},
            {"id": "end", "text": "", "options": []}
        ]
    },
    # 4. Keth Cloudscar's Gate History (dragonkin race-specific)
    {
        "id": "keth_gate_history",
        "speaker_id": "keth_cloudscar",
        "title": "The First Gate Oath",
        "nodes": [
            {"id": "start", "text": "Keth Cloudscar unrolls a crumbling scroll. 'The first oath at the Obsidian Gate was not what the histories say. I have fragments of the true account. Will you help me reconstruct it?'", "options": [
                {"id": "dragonkin_response", "text": "[Dragonkin] 'The gate oath is in my blood. I must know the truth.'", "conditions": {"race_ids": ["dragonkin"]}, "actions": [{"type": "affinity", "target_id": "keth_cloudscar", "amount": 15}, {"type": "reputation", "faction_id": "dragonkin_oathkeepers", "amount": 10}], "next_node_id": "dragonkin_path"},
                {"id": "warrior_response", "text": "[Squire/Knight] 'An oath is an oath. The truth matters.'", "conditions": {"class_ids": ["squire", "knight", "paladin", "berserker", "warlord"]}, "next_node_id": "warrior_path"},
                {"id": "scholar_response", "text": "[Acolyte/Mage] 'Historical truth is worth any risk.'", "conditions": {"class_ids": ["acolyte", "mage", "chronomancer", "necromancer"]}, "next_node_id": "scholar_path"},
                {"id": "decline", "text": "History is written by the victors. Let it stay that way.", "next_node_id": "end"}
            ]},
            {"id": "dragonkin_path", "text": "Keth's scales shimmer. 'A dragonkin who seeks the truth. The fragments point to the cloud ruins and the obsidian gate. Go, and let the oath speak through you.'", "options": [
                {"id": "dk_go", "text": "The oath will be remembered.", "actions": [{"type": "quest", "quest_id": "dragonkin_oath"}], "next_node_id": "end"}
            ]},
            {"id": "warrior_path", "text": "Keth nods. 'A warrior who values honour. The fragments are scattered across the ruins. Bring them to me.'", "options": [
                {"id": "war_go", "text": "I'll find them.", "actions": [{"type": "quest", "quest_id": "dragonkin_oath"}], "next_node_id": "end"}
            ]},
            {"id": "scholar_path", "text": "Keth smiles. 'A scholar after my own heart. The cloud ruins hold the oldest fragments. The obsidian gate holds the newest. Both are dangerous.'", "options": [
                {"id": "sch_go", "text": "Knowledge is worth the risk.", "actions": [{"type": "quest", "quest_id": "dragonkin_oath"}], "next_node_id": "end"}
            ]},
            {"id": "end", "text": "", "options": []}
        ]
    },
    # 5. Reeve Marta's Council Politics (faction-specific)
    {
        "id": "marta_council",
        "speaker_id": "reeve_marta",
        "title": "The Council Divided",
        "nodes": [
            {"id": "start", "text": "Reeve Marta pinches the bridge of her nose. 'The Ashvale council is split. The merchants want to open trade with the Ash Court. The wardens want to seal the borders. I need a tiebreaker.'", "options": [
                {"id": "merchant_support", "text": "Trade brings prosperity. Support the merchants.", "actions": [{"type": "reputation", "faction_id": "merchant_caravans", "amount": 15}, {"type": "reputation", "faction_id": "ashvale_council", "amount": -5}], "next_node_id": "merchant_end"},
                {"id": "warden_support", "text": "Security first. Support the wardens.", "actions": [{"type": "reputation", "faction_id": "emberwatch_wardens", "amount": 15}, {"type": "reputation", "faction_id": "ashvale_council", "amount": -5}], "next_node_id": "warden_end"},
                {"id": "compromise", "text": "There must be a middle path.", "next_node_id": "compromise_path"},
                {"id": "demon_response", "text": "[Demon/Tiefling] 'The Ash Court is my people. I can negotiate terms.'", "conditions": {"race_ids": ["demon", "tiefling"]}, "actions": [{"type": "reputation", "faction_id": "ash_court", "amount": 10}, {"type": "reputation", "faction_id": "ashvale_council", "amount": 10}], "next_node_id": "demon_path"}
            ]},
            {"id": "merchant_end", "text": "Marta sighs. 'The merchants win. I hope you're right about the prosperity.'", "options": [
                {"id": "me_done", "text": "Trade will strengthen us all.", "actions": [{"type": "flag", "key": "council_decision", "value": "trade"}], "next_node_id": "end"}
            ]},
            {"id": "warden_end", "text": "Marta nods grimly. 'The borders stay sealed. Safety over profit.'", "options": [
                {"id": "wa_done", "text": "Better safe than sorry.", "actions": [{"type": "flag", "key": "council_decision", "value": "seal"}], "next_node_id": "end"}
            ]},
            {"id": "compromise_path", "text": "Marta raises an eyebrow. 'A compromise? Limited trade through Emberwatch, with warden oversight. It might work, but both sides will need convincing.'", "options": [
                {"id": "comp_go", "text": "I'll talk to both factions.", "actions": [{"type": "reputation", "faction_id": "ashvale_council", "amount": 10}, {"type": "flag", "key": "council_decision", "value": "compromise"}], "next_node_id": "end"}
            ]},
            {"id": "demon_path", "text": "Marta's eyes widen. 'A demon offering to negotiate with the Ash Court? That's... actually perfect. You understand both sides. Can you broker terms?'", "options": [
                {"id": "demon_go", "text": "Consider it done.", "actions": [{"type": "flag", "key": "council_decision", "value": "demon_broker"}, {"type": "reputation", "faction_id": "ash_court", "amount": 15}], "next_node_id": "end"}
            ]},
            {"id": "end", "text": "", "options": []}
        ]
    },
    # 6. Rope Wright Fenn's Trust (halfling/gnome race-specific)
    {
        "id": "fenn_trust",
        "speaker_id": "ropewright_fenn",
        "title": "Rope and Trust",
        "nodes": [
            {"id": "start", "text": "Ropewright Fenn coils a length of silk rope. 'Trust rope more than stone and people less than either. But you... you might be different. Maybe.'", "options": [
                {"id": "halfling_response", "text": "[Halfling] 'I know good rope when I see it. And good people.'", "conditions": {"race_ids": ["halfling"]}, "actions": [{"type": "affinity", "target_id": "ropewright_fenn", "amount": 10}], "next_node_id": "halfling_path"},
                {"id": "gnome_response", "text": "[Gnome] 'Interesting tensile strength! What's the core material?'", "conditions": {"race_ids": ["gnome"]}, "actions": [{"type": "affinity", "target_id": "ropewright_fenn", "amount": 10}], "next_node_id": "gnome_path"},
                {"id": "arachne_response", "text": "[Arachne] 'That silk... it's from my people, isn't it?'", "conditions": {"race_ids": ["arachne"]}, "actions": [{"type": "affinity", "target_id": "ropewright_fenn", "amount": 15}], "next_node_id": "arachne_path"},
                {"id": "generic", "text": "What do you need?", "next_node_id": "explain"}
            ]},
            {"id": "halfling_path", "text": "Fenn almost smiles. 'A halfling who appreciates rope. Rare. I need someone to test a new line in the glassmarsh. The bogs eat everything else.'", "options": [
                {"id": "h_go", "text": "I'll test it. Carefully.", "actions": [{"type": "quest", "quest_id": "halfling_thief"}], "next_node_id": "end"}
            ]},
            {"id": "gnome_path", "text": "Fenn's eyes light up. 'You know materials? Spider silk core, treated with alchemical resin. I need a gnome's eye to improve the formula.'", "options": [
                {"id": "g_go", "text": "Show me the formula!", "actions": [{"type": "quest", "quest_id": "gnome_invention"}], "next_node_id": "end"}
            ]},
            {"id": "arachne_path", "text": "Fenn freezes. 'You... recognise the silk? I bought it from a trader years ago. I've been trying to find the source ever since. Can you help?'", "options": [
                {"id": "a_go", "text": "I'll find the weaver who made this.", "actions": [{"type": "quest", "quest_id": "arachne_web_fate"}], "next_node_id": "end"}
            ]},
            {"id": "explain", "text": "'Need someone trustworthy to test equipment in dangerous places. Most people break my ropes. Or my trust. Usually both.'", "options": [
                {"id": "accept", "text": "I'm trustworthy.", "actions": [{"type": "quest", "quest_id": "halfling_thief"}], "next_node_id": "end"},
                {"id": "decline", "text": "Find someone else.", "next_node_id": "end"}
            ]},
            {"id": "end", "text": "", "options": []}
        ]
    },
    # 7. Miner Joss's Depths (orc/goliath race-specific)
    {
        "id": "joss_depths",
        "speaker_id": "miner_joss",
        "title": "The Deepest Shaft",
        "nodes": [
            {"id": "start", "text": "Miner Joss wipes soot from his face. 'Found something in the deepest shaft. Something that shouldn't be there. Something alive.'", "options": [
                {"id": "orc_response", "text": "[Orc] 'Alive? Then it can be fought. Show me.'", "conditions": {"race_ids": ["orc", "half_orc"]}, "next_node_id": "orc_path"},
                {"id": "goliath_response", "text": "[Goliath] 'The deeper the stone, the stronger it is. I'm not afraid.'", "conditions": {"race_ids": ["goliath"]}, "next_node_id": "goliath_path"},
                {"id": "dwarf_response", "text": "[Dwarf] 'Something alive in the deep? That's my domain.'", "conditions": {"race_ids": ["dwarf"]}, "next_node_id": "dwarf_path"},
                {"id": "generic", "text": "What did you find?", "next_node_id": "explain"}
            ]},
            {"id": "orc_path", "text": "Joss grins. 'An orc who doesn't flinch. Good. It's big, it's angry, and it's blocking the deepest vein. Clear it out and the miners will sing your name.'", "options": [
                {"id": "orc_go", "text": "Point me at it.", "actions": [{"type": "quest", "quest_id": "orc_war_song"}], "next_node_id": "end"}
            ]},
            {"id": "goliath_path", "text": "Joss nods. 'A goliath. Perfect. It's a stone creature — golem or something older. Needs someone who can match its strength.'", "options": [
                {"id": "gol_go", "text": "I'll break it like any other stone.", "actions": [{"type": "quest", "quest_id": "goliath_endurance"}], "next_node_id": "end"}
            ]},
            {"id": "dwarf_path", "text": "Joss relaxes slightly. 'A dwarf. Thank the stone. It's some kind of construct — old dwarven make, maybe. Might respond to dwarven commands.'", "options": [
                {"id": "dw_go", "text": "I'll speak to it in the old tongue.", "actions": [{"type": "quest", "quest_id": "dwarf_deep_roads"}], "next_node_id": "end"}
            ]},
            {"id": "explain", "text": "'Big. Stone. Angry. Blocking the best vein we've found in decades. I need someone tough enough to deal with it.'", "options": [
                {"id": "accept", "text": "I'm tough enough.", "actions": [{"type": "quest", "quest_id": "goliath_endurance"}], "next_node_id": "end"},
                {"id": "decline", "text": "Sounds like a job for someone else.", "next_node_id": "end"}
            ]},
            {"id": "end", "text": "", "options": []}
        ]
    },
    # 8. Nima Crossroads's Routes (faction-specific with race conditions)
    {
        "id": "nima_routes",
        "speaker_id": "nima_crossroads",
        "title": "Which Roads Accept Which Name",
        "nodes": [
            {"id": "start", "text": "Nima Crossroads leans against a signpost. 'Every road has a name it accepts. Some open for merchants, some for soldiers, some for... other people. Which road are you walking?'", "options": [
                {"id": "merchant", "text": "The merchant's road. Gold opens all doors.", "actions": [{"type": "reputation", "faction_id": "merchant_caravans", "amount": 5}], "next_node_id": "merchant_path"},
                {"id": "warden", "text": "The warden's road. Duty before all.", "actions": [{"type": "reputation", "faction_id": "emberwatch_wardens", "amount": 5}], "next_node_id": "warden_path"},
                {"id": "ash_court", "text": "The Ash Court's road. Power speaks loudest.", "actions": [{"type": "reputation", "faction_id": "ash_court", "amount": 5}], "next_node_id": "ash_path"},
                {"id": "half_elf_response", "text": "[Half-Elf] 'Between worlds, like you. Which road accepts us?'", "conditions": {"race_ids": ["half_elf"]}, "actions": [{"type": "affinity", "target_id": "nima_crossroads", "amount": 15}], "next_node_id": "half_elf_path"}
            ]},
            {"id": "merchant_path", "text": "Nima nods. 'The merchant road is wide but toll-heavy. I know shortcuts that save gold. Interested?'", "options": [
                {"id": "m_go", "text": "Always interested in saving gold.", "actions": [{"type": "reputation", "faction_id": "merchant_caravans", "amount": 10}], "next_node_id": "end"}
            ]},
            {"id": "warden_path", "text": "Nima salutes. 'The warden road is hard but honest. I can show you the safe routes through dangerous territory.'", "options": [
                {"id": "w_go", "text": "Show me.", "actions": [{"type": "reputation", "faction_id": "emberwatch_wardens", "amount": 10}], "next_node_id": "end"}
            ]},
            {"id": "ash_path", "text": "Nima's expression darkens. 'The Ash Court road is dangerous. But I know which doors it opens — and which it closes forever.'", "options": [
                {"id": "a_go", "text": "I'll take the risk.", "actions": [{"type": "reputation", "faction_id": "ash_court", "amount": 10}], "next_node_id": "end"}
            ]},
            {"id": "half_elf_path", "text": "Nima smiles — the first genuine smile you've seen. 'Between worlds. Yes. There's a road that only opens for people like us. I'll show you, when you're ready.'", "options": [
                {"id": "he_go", "text": "I'm ready now.", "actions": [{"type": "reputation", "faction_id": "elven_pathkeepers", "amount": 10}, {"type": "flag", "key": "nima_road", "value": "between_worlds"}], "next_node_id": "end"}
            ]},
            {"id": "end", "text": "", "options": []}
        ]
    }
]

data["dialogues"].extend(new_dialogues)

with open('data/dialogues.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"Added {len(new_dialogues)} new dialogue trees")
print(f"Total dialogues: {len(data['dialogues'])}")
for dlg in data["dialogues"]:
    print(f"  {dlg['id']}: speaker={dlg.get('speaker_id')}, nodes={len(dlg.get('nodes', []))}")
