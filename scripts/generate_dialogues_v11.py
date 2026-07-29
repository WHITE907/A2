#!/usr/bin/env python3
"""Generate additional branching dialogue trees for v0.11.0."""

import json

with open('data/dialogues.json') as f:
    data = json.load(f)

new_dialogues = [
    # 1. Commander Vex's Iron Covenant recruitment
    {
        "id": "vex_iron_covenant",
        "speaker_id": "commander_vex",
        "title": "The Iron Covenant",
        "nodes": [
            {"id": "start", "text": "Commander Vex studies you with hard eyes. 'The Iron Covenant needs fighters. Not soldiers — fighters. People who think. Are you one?'", "options": [
                {"id": "warrior_response", "text": "[Warrior classes] 'I've fought my way through worse. Point me at the enemy.'", "conditions": {"class_ids": ["squire", "knight", "paladin", "berserker", "warlord", "maiden", "duelist"]}, "next_node_id": "warrior_path"},
                {"id": "mage_response", "text": "[Mage classes] 'My magic has felled armies. The Covenant could use that.'", "conditions": {"class_ids": ["acolyte", "mage", "archmage", "cleric", "warlock"]}, "next_node_id": "mage_path"},
                {"id": "rogue_response", "text": "[Rogue classes] 'I work best alone, but I can scout your borders.'", "conditions": {"class_ids": ["shadow_dancer", "ranger"]}, "next_node_id": "rogue_path"},
                {"id": "demon_response", "text": "[Demon/Tiefling] 'The Ash Court and the Covenant are rivals. I can bridge that gap.'", "conditions": {"race_ids": ["demon", "tiefling"]}, "next_node_id": "demon_path"},
                {"id": "decline", "text": "I work alone.", "next_node_id": "end"}
            ]},
            {"id": "warrior_path", "text": "Vex nods approvingly. 'Good. The front lines need someone who can take a hit and keep fighting. Report to the eastern gate at dawn.'", "options": [
                {"id": "w_join", "text": "I'll be there.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 15}, {"type": "flag", "key": "covenant_role", "value": "frontline"}], "next_node_id": "end"}
            ]},
            {"id": "mage_path", "text": "Vex considers. 'We have plenty of sword-arms. What we lack is firepower. Can you hold a ward-line under pressure?'", "options": [
                {"id": "m_join", "text": "My wards are unbreakable.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 15}, {"type": "flag", "key": "covenant_role", "value": "ward_mage"}], "next_node_id": "end"}
            ]},
            {"id": "rogue_path", "text": "Vex's expression softens slightly. 'Scouts are worth their weight in gold. The void spawn have been probing our eastern border. Find out where they're coming from.'", "options": [
                {"id": "r_join", "text": "Consider it done.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 15}, {"type": "flag", "key": "covenant_role", "value": "scout"}, {"type": "quest", "quest_id": "ironveil_welcome"}], "next_node_id": "end"}
            ]},
            {"id": "demon_path", "text": "Vex's hand drifts to her sword, then stops. 'Bold. Very bold. If you can negotiate with the Ash Court without starting a war... the Covenant would owe you a great debt.'", "options": [
                {"id": "d_join", "text": "I'll arrange a meeting.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 10}, {"type": "reputation", "faction_id": "ash_court", "amount": 10}, {"type": "flag", "key": "covenant_role", "value": "diplomat"}], "next_node_id": "end"}
            ]},
            {"id": "end", "text": "", "options": []}
        ]
    },
    # 2. Artificer Zara's invention (gnome/genasi race-specific)
    {
        "id": "zara_invention",
        "speaker_id": "artificer_zara",
        "title": "The Resonance Engine",
        "nodes": [
            {"id": "start", "text": "Artificer Zara gestures at a humming machine the size of a house. 'The Resonance Engine! It can amplify magical energy a hundredfold. Or explode. Still working out the details.'", "options": [
                {"id": "gnome_response", "text": "[Gnome] 'The harmonic dampeners are wrong. Let me fix them.'", "conditions": {"race_ids": ["gnome"]}, "actions": [{"type": "affinity", "target_id": "artificer_zara", "amount": 15}], "next_node_id": "gnome_path"},
                {"id": "genasi_response", "text": "[Genasi] 'I can feel the elemental resonance. It's unstable because the fire channel is overloaded.'", "conditions": {"race_ids": ["genasi"]}, "actions": [{"type": "affinity", "target_id": "artificer_zara", "amount": 15}], "next_node_id": "genasi_path"},
                {"id": "mage_response", "text": "[Mage] 'I can channel mana directly into the core. Would that help?'", "conditions": {"class_ids": ["mage", "archmage", "chronomancer", "necromancer", "warlock", "dread_lord"]}, "next_node_id": "mage_path"},
                {"id": "generic", "text": "What does it do, exactly?", "next_node_id": "explain"},
                {"id": "decline", "text": "I'll stand back. Way back.", "next_node_id": "end"}
            ]},
            {"id": "gnome_path", "text": "Zara's eyes widen. 'You can see the harmonics? Of course you can — fellow gnome! The dampeners need recalibrating to 440 Hz. Can you help?'", "options": [
                {"id": "g_help", "text": "Hand me a wrench.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 10}, {"type": "quest", "quest_id": "cinder_heart"}], "next_node_id": "end"}
            ]},
            {"id": "genasi_path", "text": "Zara stares. 'You can feel it? The elemental resonance? That's... that's exactly what we need! Someone who can tune the channels by instinct!'", "options": [
                {"id": "ge_help", "text": "Show me the channels.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 10}, {"type": "quest", "quest_id": "cinder_heart"}], "next_node_id": "end"}
            ]},
            {"id": "mage_path", "text": "Zara grins. 'A mana battery! Perfect! If you can sustain a steady flow, the engine might actually stabilise. Ready?'", "options": [
                {"id": "m_help", "text": "I'm ready.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 10}, {"type": "quest", "quest_id": "cinder_heart"}], "next_node_id": "end"}
            ]},
            {"id": "explain", "text": "'It amplifies magical energy. Think of it as a lens for spells. Point it at a ward, the ward gets stronger. Point it at a fireball...' She trails off. 'Let's not point it at fireballs.'", "options": [
                {"id": "accept", "text": "I'll help test it.", "actions": [{"type": "quest", "quest_id": "cinder_heart"}], "next_node_id": "end"},
                {"id": "decline2", "text": "Sounds dangerous.", "next_node_id": "end"}
            ]},
            {"id": "end", "text": "", "options": []}
        ]
    },
    # 3. Chronicler Thon's history (lamia/elf race-specific)
    {
        "id": "thon_history",
        "speaker_id": "chronicler_thon",
        "title": "The First War",
        "nodes": [
            {"id": "start", "text": "Chronicler Thon unrolls a scroll that seems to go on forever. 'The First War against the Void. Fought before humans built their first city. Before the elves sang their first song. Do you want to know what happened?'", "options": [
                {"id": "lamia_response", "text": "[Lamia] 'I was there. Or my ancestors were. The memory is... fragmented.'", "conditions": {"race_ids": ["lamia"]}, "actions": [{"type": "affinity", "target_id": "chronicler_thon", "amount": 20}], "next_node_id": "lamia_path"},
                {"id": "elf_response", "text": "[Elf] 'The old songs speak of the Void War. But they're vague on details.'", "conditions": {"race_ids": ["elf", "half_elf"]}, "actions": [{"type": "affinity", "target_id": "chronicler_thon", "amount": 15}], "next_node_id": "elf_path"},
                {"id": "scholar_response", "text": "[Acolyte/Mage] 'Historical knowledge is power. Tell me everything.'", "conditions": {"class_ids": ["acolyte", "mage", "archmage", "chronomancer", "oracle", "cleric"]}, "next_node_id": "scholar_path"},
                {"id": "dragonkin_response", "text": "[Dragonkin] 'The first oath was sworn during that war. I need to know why.'", "conditions": {"race_ids": ["dragonkin"]}, "actions": [{"type": "affinity", "target_id": "chronicler_thon", "amount": 15}, {"type": "reputation", "faction_id": "dragonkin_oathkeepers", "amount": 10}], "next_node_id": "dragonkin_path"},
                {"id": "generic", "text": "What happened?", "next_node_id": "explain"}
            ]},
            {"id": "lamia_path", "text": "Thon's eyes fill with tears. 'You remember. After all these centuries, someone remembers. The war was won, but at a terrible cost. The Void Sovereign was sealed, not destroyed. And now the seal is weakening.'", "options": [
                {"id": "l_quest", "text": "How do we strengthen the seal?", "actions": [{"type": "quest", "quest_id": "sunken_secrets"}], "next_node_id": "end"}
            ]},
            {"id": "elf_path", "text": "Thon nods. 'The songs are right, but incomplete. The war was won by an alliance of every race — dragonkin, elves, dwarves, even the Ash Court. They sealed the Void Sovereign in a throne of nothing.'", "options": [
                {"id": "e_quest", "text": "And now the seal is failing?", "actions": [{"type": "quest", "quest_id": "sunken_secrets"}], "next_node_id": "end"}
            ]},
            {"id": "scholar_path", "text": "Thon smiles. 'A scholar! The war lasted seven years. The alliance was forged by a dragonkin oath-keeper and an elven pathkeeper. They created the Void Throne to imprison the Sovereign.'", "options": [
                {"id": "s_quest", "text": "Where is the Void Throne?", "actions": [{"type": "quest", "quest_id": "sunken_secrets"}], "next_node_id": "end"}
            ]},
            {"id": "dragonkin_path", "text": "Thon bows his head. 'The first oath was sworn by Kaelthas the Golden, ancestor of your line. He gave his life to seal the Void Sovereign. The oath was to guard the seal forever.'", "options": [
                {"id": "d_quest", "text": "Then I will honour that oath.", "actions": [{"type": "quest", "quest_id": "void_throne_assault"}, {"type": "reputation", "faction_id": "dragonkin_oathkeepers", "amount": 15}], "next_node_id": "end"}
            ]},
            {"id": "explain", "text": "'The Void Sovereign was a being of pure entropy. It consumed everything it touched. The alliance sealed it away, but the seal is weakening. The Void Throne is where it's imprisoned.'", "options": [
                {"id": "accept", "text": "I'll investigate the Void Throne.", "actions": [{"type": "quest", "quest_id": "void_throne_assault"}], "next_node_id": "end"},
                {"id": "decline", "text": "That sounds like someone else's problem.", "next_node_id": "end"}
            ]},
            {"id": "end", "text": "", "options": []}
        ]
    },
    # 4. Mother Sable's Ash Court negotiation (demon/tiefling/faction-specific)
    {
        "id": "sable_ironveil",
        "speaker_id": "mother_sable",
        "title": "The Ash Court and Ironveil",
        "nodes": [
            {"id": "start", "text": "Mother Sable appears in Ironveil's marketplace, drawing wary glances. 'Interesting place. The Iron Covenant and the Ash Court have been rivals for centuries. But the Void changes everything.'", "options": [
                {"id": "demon_response", "text": "[Demon/Tiefling] 'The Ash Court is my people. I can negotiate.'", "conditions": {"race_ids": ["demon", "tiefling"]}, "actions": [{"type": "affinity", "target_id": "mother_sable", "amount": 15}], "next_node_id": "demon_path"},
                {"id": "ash_court_rep", "text": "[Ash Court reputation ≥ 20] 'I have standing with the Ash Court. I can arrange a meeting.'", "next_node_id": "rep_path"},
                {"id": "iron_covenant_rep", "text": "[Iron Covenant reputation ≥ 20] 'Commander Vex trusts me. I can convince her to listen.'", "next_node_id": "covenant_path"},
                {"id": "generic", "text": "What do you propose?", "next_node_id": "explain"}
            ]},
            {"id": "demon_path", "text": "Sable's eyes gleam. 'A demon who can walk both courts. Perfect. The Ash Court has knowledge the Covenant needs — and vice versa. A temporary alliance against the Void could save us all.'", "options": [
                {"id": "d_negotiate", "text": "I'll arrange a summit.", "actions": [{"type": "reputation", "faction_id": "ash_court", "amount": 10}, {"type": "reputation", "faction_id": "iron_covenant", "amount": 10}, {"type": "flag", "key": "ash_ironveil_alliance", "value": "negotiated"}], "next_node_id": "end"}
            ]},
            {"id": "rep_path", "text": "Sable nods. 'If you have standing with the Ash Court, you can speak for them. The Covenant needs to understand that the Void threatens us all equally.'", "options": [
                {"id": "r_negotiate", "text": "I'll speak to both sides.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 10}, {"type": "flag", "key": "ash_ironveil_alliance", "value": "negotiated"}], "next_node_id": "end"}
            ]},
            {"id": "covenant_path", "text": "Sable smiles. 'If Commander Vex trusts you, she might listen. The Covenant's stubbornness is legendary, but even they can see the Void is worse than the Ash Court.'", "options": [
                {"id": "c_negotiate", "text": "I'll convince Vex.", "actions": [{"type": "reputation", "faction_id": "ash_court", "amount": 10}, {"type": "flag", "key": "ash_ironveil_alliance", "value": "negotiated"}], "next_node_id": "end"}
            ]},
            {"id": "explain", "text": "'A temporary alliance. The Ash Court has ancient knowledge about the Void. The Covenant has the military strength to act on it. Together, they might actually win.'", "options": [
                {"id": "accept", "text": "I'll try to broker peace.", "actions": [{"type": "flag", "key": "ash_ironveil_alliance", "value": "attempted"}], "next_node_id": "end"},
                {"id": "decline", "text": "Let them fight their own battles.", "next_node_id": "end"}
            ]},
            {"id": "end", "text": "", "options": []}
        ]
    },
    # 5. Generic Ironveil citizen dialogue (class/race reactive)
    {
        "id": "ironveil_citizen",
        "speaker_id": "commander_vex",
        "title": "Life in Ironveil",
        "nodes": [
            {"id": "start", "text": "An Ironveil guard stops you. 'New face. We don't get many visitors. What brings you to the edge of the world?'", "options": [
                {"id": "orc_response", "text": "[Orc] 'Fighting. The Void needs to be punched.'", "conditions": {"race_ids": ["orc", "half_orc"]}, "next_node_id": "orc_path"},
                {"id": "dwarf_response", "text": "[Dwarf] 'Stone calls to stone. Your walls are impressive.'", "conditions": {"race_ids": ["dwarf"]}, "next_node_id": "dwarf_path"},
                {"id": "halfling_response", "text": "[Halfling] 'Honestly? I got lost. Very lost.'", "conditions": {"race_ids": ["halfling"]}, "next_node_id": "halfling_path"},
                {"id": "aracne_response", "text": "[Arachne] 'The threads of fate led me here. Literally.'", "conditions": {"race_ids": ["arachne"]}, "next_node_id": "arachne_path"},
                {"id": "warrior_response", "text": "[Warrior] 'I heard you need fighters. I'm a fighter.'", "conditions": {"class_ids": ["squire", "knight", "paladin", "berserker", "warlord", "maiden", "duelist"]}, "next_node_id": "warrior_path"},
                {"id": "generic", "text": "Just passing through.", "next_node_id": "passing"}
            ]},
            {"id": "orc_path", "text": "The guard grins. 'An orc who speaks plainly! I like that. The Void spawn are tough, but we're tougher. Welcome to Ironveil.'", "options": [
                {"id": "o_done", "text": "Point me at the nearest fight.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 5}], "next_node_id": "end"}
            ]},
            {"id": "dwarf_path", "text": "The guard straightens. 'A dwarf who appreciates good masonry! The walls are three thousand years old. Still standing. Like us.'", "options": [
                {"id": "d_done", "text": "Three thousand years. Impressive.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 5}], "next_node_id": "end"}
            ]},
            {"id": "halfling_path", "text": "The guard laughs. 'Lost? In Ironveil? That's a first. Most people come here on purpose. Or get dragged here. Welcome anyway.'", "options": [
                {"id": "h_done", "text": "Is there an inn? I need a pie.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 5}], "next_node_id": "end"}
            ]},
            {"id": "arachne_path", "text": "The guard blinks. 'Fate threads? That's... poetic. And slightly terrifying. Welcome to Ironveil. Try not to web anything important.'", "options": [
                {"id": "a_done", "text": "No promises.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 5}], "next_node_id": "end"}
            ]},
            {"id": "warrior_path", "text": "The guard nods. 'We always need fighters. Commander Vex is in the keep. Tell her Briggs sent you.'", "options": [
                {"id": "w_done", "text": "Thanks, Briggs.", "actions": [{"type": "reputation", "faction_id": "iron_covenant", "amount": 5}], "next_node_id": "end"}
            ]},
            {"id": "passing", "text": "The guard shrugs. 'Passing through? Watch your step. The Void spawn don't care about tourists.'", "options": [
                {"id": "p_done", "text": "I'll keep that in mind.", "next_node_id": "end"}
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
