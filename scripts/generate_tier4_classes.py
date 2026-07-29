#!/usr/bin/env python3
"""Generate tier-4 classes for all new tier-3 classes."""

import json

with open('data/classes.json') as f:
    data = json.load(f)

# Each new tier-3 class gets one tier-4 promotion target
tier4_definitions = [
    # From Knight line
    {"id": "shadow_reaver", "from": "dark_knight", "name": "Shadow Reaver", "desc": "A warrior consumed by shadow, wielding darkness as both weapon and armour.", "stats": {"STR": 62, "END": 58, "INT": 36, "AGI": 22}, "growth": {"STR": 5, "END": 4, "INT": 4, "AGI": 2}, "core": "smite", "granted": ["shadow_bind", "executioners_arc", "smoke_veil"], "tree": ["toughness", "sunder_armor", "keen_edge", "predatory_focus"], "weapons": ["sword", "axe"], "passive": {"flat": {"armor": 14, "physical_power": 10, "crit_chance": 0.05}, "pct": {"crit_damage": 0.15}}},
    {"id": "iron_bastion", "from": "sentinel", "name": "Iron Bastion", "desc": "An unbreakable wall of steel and will, the last line of defence.", "stats": {"STR": 56, "END": 70, "INT": 30, "AGI": 18}, "growth": {"STR": 4, "END": 6, "INT": 2, "AGI": 1}, "core": "strike", "granted": ["shield_wall", "rallying_cry", "challenging_shout"], "tree": ["toughness", "guardian_resolve", "warding_spirit", "toughness"], "weapons": ["sword", "mace"], "passive": {"flat": {"armor": 24, "max_hp": 120, "status_resist": 0.15}}},
    
    # From Duelist line
    {"id": "stormblade", "from": "blademaster", "name": "Stormblade", "desc": "A whirlwind of steel whose strikes fall like lightning.", "stats": {"STR": 50, "END": 34, "INT": 16, "AGI": 78}, "growth": {"STR": 4, "END": 3, "INT": 1, "AGI": 7}, "core": "pierce", "granted": ["thousand_cuts", "shadowstep", "heartseeker"], "tree": ["fleet_footed", "keen_edge", "predatory_focus", "executioners_arc"], "weapons": ["dagger", "sword"], "passive": {"flat": {"crit_chance": 0.12, "speed": 8}, "pct": {"crit_damage": 0.2}}},
    {"id": "illusionist", "from": "trickster", "name": "Illusionist", "desc": "A master of misdirection who fights with shadows and deceit.", "stats": {"STR": 34, "END": 28, "INT": 32, "AGI": 74}, "growth": {"STR": 3, "END": 2, "INT": 3, "AGI": 6}, "core": "pierce", "granted": ["venom_edge", "smoke_veil", "curse_mirror"], "tree": ["fleet_footed", "shadowstep", "hunters_mark", "shadow_bind"], "weapons": ["dagger", "bow"], "passive": {"flat": {"evasion": 0.12, "crit_chance": 0.07, "speed": 6}}},
    
    # From Mage line
    {"id": "time_weaver", "from": "chronomancer", "name": "Time Weaver", "desc": "A mage who bends the fabric of time itself, accelerating allies and freezing foes.", "stats": {"STR": 8, "END": 32, "INT": 82, "AGI": 28}, "growth": {"STR": 0, "END": 3, "INT": 8, "AGI": 3}, "core": "arcane_bolt", "granted": ["temporal_shift", "glacial_prison", "chain_lightning"], "tree": ["arcane_mind", "warding_spirit", "ley_attunement", "mind_over_matter"], "weapons": ["staff"], "passive": {"flat": {"max_mp": 80, "speed": 6}, "pct": {"magic_power": 0.25}}},
    {"id": "lich_lord", "from": "necromancer", "name": "Lich Lord", "desc": "A master of death who has transcended mortality, draining life from all who oppose.", "stats": {"STR": 12, "END": 36, "INT": 78, "AGI": 18}, "growth": {"STR": 1, "END": 4, "INT": 7, "AGI": 1}, "core": "arcane_bolt", "granted": ["vampiric_strike", "shadow_bind", "curse_mirror"], "tree": ["arcane_mind", "warding_spirit", "mind_over_matter", "steady_breath"], "weapons": ["staff", "dagger"], "passive": {"flat": {"magic_power": 14, "max_mp": 60, "max_hp": 40}, "pct": {"magic_power": 0.2}}},
    
    # From Berserker line
    {"id": "bloodlord", "from": "berserker_champion", "name": "Bloodlord", "desc": "A warrior whose rage is matched only by the devastation they leave behind.", "stats": {"STR": 72, "END": 46, "INT": 4, "AGI": 28}, "growth": {"STR": 6, "END": 4, "INT": 0, "AGI": 3}, "core": "strike", "granted": ["power_strike", "executioners_arc", "whirlwind", "titans_wrath"], "tree": ["toughness", "cleave", "keen_edge", "predatory_focus"], "weapons": ["axe", "sword"], "passive": {"flat": {"physical_power": 16}, "pct": {"crit_damage": 0.25}}},
    {"id": "blood_sovereign", "from": "bloodrager", "name": "Blood Sovereign", "desc": "A warrior who feasts on the life force of enemies, growing stronger with every kill.", "stats": {"STR": 66, "END": 54, "INT": 12, "AGI": 24}, "growth": {"STR": 5, "END": 5, "INT": 1, "AGI": 2}, "core": "strike", "granted": ["vampiric_strike", "cleave", "second_wind", "executioners_arc"], "tree": ["toughness", "keen_edge", "sunder_armor", "guardian_resolve"], "weapons": ["axe", "mace"], "passive": {"flat": {"physical_power": 12, "max_hp": 80}}},
    {"id": "horde_lord", "from": "warchief", "name": "Horde Lord", "desc": "A war leader whose battle cries inspire armies and shatter enemy morale.", "stats": {"STR": 70, "END": 48, "INT": 16, "AGI": 24}, "growth": {"STR": 6, "END": 4, "INT": 2, "AGI": 2}, "core": "strike", "granted": ["rallying_cry", "power_strike", "cleave", "whirlwind"], "tree": ["toughness", "keen_edge", "sunder_armor", "guardian_resolve"], "weapons": ["axe", "sword", "mace"], "passive": {"flat": {"physical_power": 14, "max_hp": 60, "armor": 6}}},
    
    # From Warlord line
    {"id": "supreme_commander", "from": "high_commander", "name": "Supreme Commander", "desc": "A general whose presence alone turns the tide of battle.", "stats": {"STR": 52, "END": 58, "INT": 38, "AGI": 22}, "growth": {"STR": 4, "END": 5, "INT": 4, "AGI": 2}, "core": "strike", "granted": ["rallying_cry", "shield_wall", "challenging_shout", "guardian_bond"], "tree": ["toughness", "guardian_resolve", "warding_spirit", "sunder_armor"], "weapons": ["sword", "mace"], "passive": {"flat": {"armor": 16, "max_hp": 80, "status_resist": 0.1}}},
    {"id": "grand_strategist", "from": "tactician", "name": "Grand Strategist", "desc": "A master of warfare who reads the battlefield like a chess grandmaster.", "stats": {"STR": 48, "END": 52, "INT": 46, "AGI": 28}, "growth": {"STR": 4, "END": 4, "INT": 4, "AGI": 3}, "core": "strike", "granted": ["riposte_stance", "sunder_armor", "hunters_mark", "executioners_arc"], "tree": ["toughness", "keen_edge", "warding_spirit", "guardian_resolve"], "weapons": ["sword", "mace"], "passive": {"flat": {"armor": 12, "accuracy": 0.08, "crit_chance": 0.06}}},
    {"id": "cavalry_lord", "from": "banneret", "name": "Cavalry Lord", "desc": "A mounted champion whose charge breaks formations and inspires charges.", "stats": {"STR": 56, "END": 52, "INT": 28, "AGI": 38}, "growth": {"STR": 5, "END": 4, "INT": 3, "AGI": 4}, "core": "strike", "granted": ["rallying_cry", "power_strike", "executioners_arc", "cleave"], "tree": ["toughness", "keen_edge", "fleet_footed", "sunder_armor"], "weapons": ["sword", "mace", "axe"], "passive": {"flat": {"physical_power": 10, "speed": 8, "armor": 10}}},
    
    # From Ranger line
    {"id": "trail_warden", "from": "pathfinder", "name": "Trail Warden", "desc": "A master of the wilderness who can track any prey and survive any terrain.", "stats": {"STR": 36, "END": 42, "INT": 28, "AGI": 72}, "growth": {"STR": 3, "END": 4, "INT": 3, "AGI": 6}, "core": "pierce", "granted": ["aimed_shot", "hunters_mark", "fleet_footed", "heartseeker"], "tree": ["fleet_footed", "keen_edge", "shadowstep", "steady_breath"], "weapons": ["bow", "dagger", "sword"], "passive": {"flat": {"accuracy": 0.1, "evasion": 0.07, "speed": 8}}},
    {"id": "alpha_predator", "from": "beastmaster", "name": "Alpha Predator", "desc": "A ranger who fights alongside a pack of loyal beasts, the alpha of all predators.", "stats": {"STR": 40, "END": 42, "INT": 30, "AGI": 68}, "growth": {"STR": 4, "END": 4, "INT": 3, "AGI": 5}, "core": "pierce", "granted": ["aimed_shot", "hunters_mark", "challenging_shout", "heartseeker"], "tree": ["fleet_footed", "keen_edge", "toughness", "guardian_resolve"], "weapons": ["bow", "sword", "axe"], "passive": {"flat": {"physical_power": 10, "max_hp": 60, "accuracy": 0.07}}},
    {"id": "deadeye", "from": "marksman", "name": "Deadeye", "desc": "A sniper whose arrows never miss and whose shots always find the kill zone.", "stats": {"STR": 32, "END": 34, "INT": 20, "AGI": 80}, "growth": {"STR": 3, "END": 3, "INT": 2, "AGI": 7}, "core": "pierce", "granted": ["aimed_shot", "heartseeker", "hunters_mark", "executioners_arc"], "tree": ["fleet_footed", "keen_edge", "predatory_focus", "steady_breath"], "weapons": ["bow", "dagger"], "passive": {"flat": {"accuracy": 0.14, "crit_chance": 0.08}, "pct": {"crit_damage": 0.15}}},
    
    # From Shadow Dancer line
    {"id": "wraith_lord", "from": "phantom", "name": "Wraith Lord", "desc": "A ghost-like assassin who exists between worlds, striking from the void.", "stats": {"STR": 42, "END": 30, "INT": 34, "AGI": 80}, "growth": {"STR": 4, "END": 3, "INT": 3, "AGI": 7}, "core": "pierce", "granted": ["shadowstep", "shadow_bind", "venom_edge", "thousand_cuts"], "tree": ["fleet_footed", "keen_edge", "smoke_veil", "predatory_focus"], "weapons": ["dagger"], "passive": {"flat": {"evasion": 0.14, "crit_chance": 0.1, "speed": 8}}},
    {"id": "void_walker", "from": "nightstalker", "name": "Void Walker", "desc": "A shadow-mage who steps through the void itself, appearing behind enemies.", "stats": {"STR": 46, "END": 32, "INT": 46, "AGI": 72}, "growth": {"STR": 4, "END": 3, "INT": 4, "AGI": 6}, "core": "pierce", "granted": ["shadow_bind", "shadowstep", "vampiric_strike", "curse_mirror"], "tree": ["fleet_footed", "keen_edge", "arcane_mind", "smoke_veil"], "weapons": ["dagger", "sword"], "passive": {"flat": {"magic_power": 10, "crit_chance": 0.08, "evasion": 0.08}}},
    {"id": "demolitionist", "from": "saboteur", "name": "Demolitionist", "desc": "A master of traps and sabotage who destroys enemies before they know they're in danger.", "stats": {"STR": 36, "END": 34, "INT": 42, "AGI": 74}, "growth": {"STR": 3, "END": 3, "INT": 4, "AGI": 6}, "core": "pierce", "granted": ["venom_edge", "time_bomb", "sunder_armor", "curse_mirror"], "tree": ["fleet_footed", "keen_edge", "hunters_mark", "smoke_veil"], "weapons": ["dagger", "bow"], "passive": {"flat": {"accuracy": 0.08, "crit_chance": 0.07, "speed": 6}}},
    
    # From Cleric line
    {"id": "divine_oracle", "from": "high_priest", "name": "Divine Oracle", "desc": "A conduit of divine power whose healing can pull allies back from death itself.", "stats": {"STR": 20, "END": 42, "INT": 72, "AGI": 18}, "growth": {"STR": 2, "END": 4, "INT": 6, "AGI": 1}, "core": "arcane_bolt", "granted": ["mend", "renewal", "purifying_light", "divine_judgment"], "tree": ["arcane_mind", "warding_spirit", "steady_breath", "guardian_resolve"], "weapons": ["mace", "staff"], "passive": {"flat": {"max_mp": 70, "magic_resist": 14}, "pct": {"magic_power": 0.18}}},
    {"id": "purifier", "from": "inquisitor", "name": "Purifier", "desc": "A holy warrior who burns away corruption with righteous fire and purifying steel.", "stats": {"STR": 46, "END": 46, "INT": 60, "AGI": 22}, "growth": {"STR": 4, "END": 4, "INT": 5, "AGI": 2}, "core": "smite", "granted": ["purifying_light", "executioners_arc", "mend", "divine_judgment"], "tree": ["toughness", "keen_edge", "warding_spirit", "arcane_mind"], "weapons": ["mace", "sword"], "passive": {"flat": {"physical_power": 10, "magic_power": 10, "armor": 10}}},
    {"id": "fate_weaver", "from": "oracle", "name": "Fate Weaver", "desc": "A seer who glimpses the threads of fate, bending time and fortune to protect allies.", "stats": {"STR": 16, "END": 36, "INT": 76, "AGI": 28}, "growth": {"STR": 1, "END": 3, "INT": 7, "AGI": 3}, "core": "arcane_bolt", "granted": ["temporal_shift", "renewal", "curse_mirror", "glacial_prison"], "tree": ["arcane_mind", "warding_spirit", "ley_attunement", "mind_over_matter"], "weapons": ["staff"], "passive": {"flat": {"max_mp": 65, "magic_resist": 10, "speed": 6}, "pct": {"magic_power": 0.2}}},
    
    # From Warlock line
    {"id": "archfiend", "from": "dread_lord", "name": "Archfiend", "desc": "A master of forbidden arts whose dark power corrupts everything it touches.", "stats": {"STR": 14, "END": 36, "INT": 82, "AGI": 20}, "growth": {"STR": 1, "END": 3, "INT": 8, "AGI": 2}, "core": "arcane_bolt", "granted": ["shadow_bind", "flame_wave", "vampiric_strike", "meteor"], "tree": ["arcane_mind", "warding_spirit", "mind_over_matter", "frost_lance"], "weapons": ["staff"], "passive": {"flat": {"magic_power": 16, "crit_damage": 0.12}, "pct": {"magic_power": 0.25}}},
    {"id": "doom_blade", "from": "hexblade", "name": "Doom Blade", "desc": "A warrior-mage whose cursed weapon drinks the souls of those it strikes.", "stats": {"STR": 48, "END": 38, "INT": 62, "AGI": 28}, "growth": {"STR": 4, "END": 4, "INT": 5, "AGI": 3}, "core": "smite", "granted": ["shadow_bind", "venom_edge", "vampiric_strike", "executioners_arc"], "tree": ["keen_edge", "arcane_mind", "warding_spirit", "sunder_armor"], "weapons": ["sword", "dagger"], "passive": {"flat": {"physical_power": 10, "magic_power": 10, "crit_chance": 0.06}}},
    {"id": "soul_reaper", "from": "soulbinder", "name": "Soul Reaper", "desc": "A warlock who harvests souls, growing stronger with each life claimed.", "stats": {"STR": 18, "END": 44, "INT": 76, "AGI": 24}, "growth": {"STR": 2, "END": 4, "INT": 7, "AGI": 2}, "core": "arcane_bolt", "granted": ["vampiric_strike", "curse_mirror", "shadow_bind", "status_transfer"], "tree": ["arcane_mind", "warding_spirit", "mind_over_matter", "steady_breath"], "weapons": ["staff", "dagger"], "passive": {"flat": {"magic_power": 14, "max_hp": 60, "max_mp": 50}}},
]

# Create tier-4 class definitions
new_tier4_classes = []
for t4 in tier4_definitions:
    cls = {
        "id": t4["id"],
        "name": t4["name"],
        "tier": 4,
        "gender_restriction": "any",
        "description": t4["desc"],
        "base_stats": t4["stats"],
        "growth": t4["growth"],
        "core_skill_id": t4["core"],
        "granted_skill_ids": t4["granted"],
        "skill_tree_ids": t4["tree"],
        "weapon_types": t4["weapons"],
        "passive_modifiers": t4["passive"],
        "promotions": {}  # Tier-4→5 chains can be added later
    }
    new_tier4_classes.append(cls)

# Add new tier-4 classes
data["classes"].extend(new_tier4_classes)

# Update tier-3 promotions to point to tier-4 targets
for cls in data["classes"]:
    if cls["tier"] == 3:
        for t4 in tier4_definitions:
            if t4["from"] == cls["id"]:
                cls["promotions"] = {
                    t4["id"]: {
                        "level": 35,
                        "stats": {k: v for k, v in t4["stats"].items() if k in ["STR", "END", "INT", "AGI"]},
                        "gold": 2000
                    }
                }

with open('data/classes.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"Added {len(new_tier4_classes)} tier-4 classes")
print(f"Total classes: {len(data['classes'])}")
print(f"Tier-4 classes: {sum(1 for c in data['classes'] if c['tier'] == 4)}")

# Verify all tier-3 classes have promotions
for cls in data["classes"]:
    if cls["tier"] == 3:
        promos = list(cls.get("promotions", {}).keys())
        status = "✅" if len(promos) >= 1 else "❌"
        print(f"  {status} {cls['id']}: promotes to {promos}")
