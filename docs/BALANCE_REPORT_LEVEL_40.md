# Level 1–40 Balance Pass

Executed against v0.5.0 content. This is a measured pass, not a claim that the
numbers are final; real-player feedback should supersede the scripted baselines.

## Method

- Calculated EXP-to-next-level from the real `Player.exp_to_next_level()` curve.
- Calculated each area's weighted average encounter reward from its actual JSON
  table, excluding one-time bosses.
- Compared shop prices with the area's weighted average gold reward.
- Ran seeded, real `Battle` instances at levels 20, 27, 34, 36, and 40.
- For the Dawn Tyrant, ran Templar, Nightblade, and Archon builds at level 40
  with the best weapon available from shops (boss-only legendary gear excluded),
  their actual class skills, cooldowns, MP costs, enemy AI, and status effects.

## EXP pacing

The first measurement found only 1.5–2.4 average encounters per level through
most of levels 16–31. That made the new regions too easy to skip. Normal-enemy
EXP was reduced while one-time boss rewards were retained.

Post-adjustment estimates:

| Area | Recommended level | Average encounters per level |
|---|---:|---:|
| Cinder Road | 16 | 2.7 |
| Mosswood | 19 | 3.2 |
| Glassmarsh | 22 | 3.5 |
| Drowned Archive | 25 | 3.4 |
| Red Pass | 28 | 4.8 |
| Singing Mines | 31 | 4.8 |
| Storm Plateau | 35 | 4.7 |
| Cloud Ruins | 38 | 5.6 |
| Obsidian Gate | 40 | 4.3 |

Multi-enemy encounters count as one encounter in this table. Quiet exploration
steps and travel time make real progression slightly slower.

## Economy

Representative current-tier weapons cost roughly five to eight normal victories
in their home region:

- Emberwatch weapons: about 1,050–1,200 gold; normal rewards average roughly
  185–225 gold.
- Stonehaven weapons: about 2,600–3,400 gold; normal rewards average roughly
  540–615 gold.
- Skyreach weapons: about 4,300–4,600 gold; normal rewards average roughly
  740–1,020 gold.

This leaves room for consumables without making a full equipment tier immediate.
Dawnblade, Sunplate, and Dawn Signet were confirmed boss-only and are not sold by
Skyreach shops.

## Combat baselines

Normal enemies at their intended level generally took two to four basic attacks
from a suitably promoted, shop-equipped physical character. Boss basic-attack
baselines ranged from 9–21 actions, establishing that skills matter.

Seeded Dawn Tyrant runs using class skills and shop gear:

| Class | Player actions | Result |
|---|---:|---|
| Templar | 8 | Victory |
| Nightblade | 4 | Victory |
| Archon | 2 | Victory |

The burst difference is substantial but consistent with the existing ultimate
identities: Archon and Nightblade spend heavily for burst, while Templar wins
more slowly with much larger HP and defence. A future multi-target or phased boss
would test those identities better than lowering all magic damage around one
single-target fight.

## Changes made from this pass

- Reduced normal-enemy EXP from levels 16–38 to produce the pacing table above.
- Kept boss EXP high because bosses are now one-time world events.
- Made the three regional promotion bosses drop three copies of their token,
  enough for both tier-4 and tier-5 requirements after earlier copies are
  consumed.
- Kept shop prices unchanged; measured gold-to-upgrade time is within the target
  range.
- Kept current enemy HP and boss stats; real battles showed viable outcomes for
  all three advanced class lines when their actual skills are used.

## Follow-up balance risks

- Companion parties can shorten fights considerably; active party size and
  companion damage need a separate party-focused pass.
- The level-40 bosses are single-phase encounters. Future bosses should use
  adds, phase changes, or new behaviours rather than only larger stat blocks.
- Tier-5+ content does not exist yet, so level-50/70 promotion costs and pacing
  cannot be validated honestly until those regions are implemented.
