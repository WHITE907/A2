"""Achievement and codex tracking system.

Tracks player discoveries: enemies defeated, areas visited, races met,
skills learned, bosses slain, marriages, banter heard. Gives exploration
purpose beyond stats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

__all__ = ["Achievement", "Codex", "ACHIEVEMENTS"]


@dataclass(frozen=True)
class Achievement:
    """One trackable accomplishment."""

    id: str
    name: str
    description: str = ""
    category: str = "exploration"
    #: How many of the thing you need (e.g. defeat 10 enemies).
    target_count: int = 1
    #: What to count: "enemies_defeated", "areas_visited", "bosses_slain", etc.
    track: str = ""
    #: Optional specific target (e.g. enemy_id for a specific boss).
    target_id: str = ""
    #: EXP reward for unlocking.
    exp_reward: int = 0


@dataclass
class Codex:
    """Player's collection of discoveries and achievements."""

    #: Counts per track: {"enemies_defeated": {"green_slime": 5, ...}, ...}
    counters: dict[str, dict[str, int]] = field(default_factory=dict)
    #: Unlocked achievement ids.
    unlocked: set[str] = field(default_factory=set)
    #: Total achievements available.
    total_achievements: int = 0

    # ------------------------------------------------------------------
    def record(self, track: str, key: str, amount: int = 1) -> list[str]:
        """Record an event. Returns list of newly unlocked achievement ids."""
        bucket = self.counters.setdefault(track, {})
        bucket[key] = bucket.get(key, 0) + amount

        newly_unlocked: list[str] = []
        for ach in ACHIEVEMENTS:
            if ach.id in self.unlocked:
                continue
            if ach.track != track:
                continue
            if ach.target_id and ach.target_id != key:
                continue
            current = bucket.get(key, 0) if ach.target_id else sum(bucket.values())
            if current >= ach.target_count:
                self.unlocked.add(ach.id)
                newly_unlocked.append(ach.id)
        return newly_unlocked

    def count_for(self, track: str, key: str = "") -> int:
        """Get count for a specific key or total for a track."""
        bucket = self.counters.get(track, {})
        if key:
            return bucket.get(key, 0)
        return sum(bucket.values())

    def has_achievement(self, achievement_id: str) -> bool:
        return achievement_id in self.unlocked

    def summary_lines(self) -> list[str]:
        """Display lines for the Codex screen."""
        lines = [f"Achievements: {len(self.unlocked)}/{self.total_achievements}"]
        lines.append("")

        # Group by category
        categories: dict[str, list[Achievement]] = {}
        for ach in ACHIEVEMENTS:
            categories.setdefault(ach.category, []).append(ach)

        for cat in sorted(categories.keys()):
            lines.append(f"--- {cat.title()} ---")
            for ach in categories[cat]:
                unlocked = "✅" if ach.id in self.unlocked else "❌"
                progress = ""
                if ach.target_count > 1:
                    current = self.count_for(ach.track, ach.target_id)
                    progress = f" ({min(current, ach.target_count)}/{ach.target_count})"
                lines.append(f"  {unlocked} {ach.name}{progress}")
            lines.append("")

        # Discovery stats
        lines.append("--- Discoveries ---")
        lines.append(f"  Enemies defeated: {self.count_for('enemies_defeated')}")
        lines.append(f"  Unique enemies: {len(self.counters.get('enemies_defeated', {}))}")
        lines.append(f"  Areas visited: {len(self.counters.get('areas_visited', {}))}")
        lines.append(f"  Skills learned: {len(self.counters.get('skills_learned', {}))}")
        lines.append(f"  Banter heard: {len(self.counters.get('banter_heard', {}))}")
        return lines

    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "counters": {k: dict(v) for k, v in self.counters.items()},
            "unlocked": sorted(self.unlocked),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "Codex":
        payload = payload or {}
        counters = {
            str(k): {str(ik): int(iv) for ik, iv in v.items()}
            for k, v in (payload.get("counters") or {}).items()
        }
        unlocked = set(str(u) for u in payload.get("unlocked", []))
        return cls(counters=counters, unlocked=unlocked, total_achievements=len(ACHIEVEMENTS))


# ======================================================================
# Achievement definitions — all data, no code
# ======================================================================
ACHIEVEMENTS: list[Achievement] = [
    # --- Combat ---
    Achievement("first_blood", "First Blood", "Defeat your first enemy.", "combat", 1, "enemies_defeated"),
    Achievement("slayer_10", "Slayer", "Defeat 10 enemies.", "combat", 10, "enemies_defeated"),
    Achievement("slayer_50", "Veteran", "Defeat 50 enemies.", "combat", 50, "enemies_defeated"),
    Achievement("slayer_100", "Champion", "Defeat 100 enemies.", "combat", 100, "enemies_defeated"),
    Achievement("slayer_500", "Legend", "Defeat 500 enemies.", "combat", 500, "enemies_defeated"),
    Achievement("unique_enemies_10", "Bestiary Scholar", "Defeat 10 different enemy types.", "combat", 10, "unique_enemies"),
    Achievement("unique_enemies_20", "Monster Hunter", "Defeat 20 different enemy types.", "combat", 20, "unique_enemies"),

    # --- Bosses ---
    Achievement("boss_bandit_chief", "Law and Order", "Defeat the Bandit Chief.", "bosses", 1, "bosses_slain", "bandit_chief"),
    Achievement("boss_shadow_warden", "Shadow Banished", "Defeat the Shadow Warden.", "bosses", 1, "bosses_slain", "shadow_warden"),
    Achievement("boss_mire_oracle", "Fate Defied", "Defeat the Mire Oracle.", "bosses", 1, "bosses_slain", "mire_oracle"),
    Achievement("boss_iron_colossus", "Iron Breaker", "Defeat the Iron Colossus.", "bosses", 1, "bosses_slain", "iron_colossus"),
    Achievement("boss_dawn_tyrant", "Dawn's End", "Defeat the Dawn Tyrant.", "bosses", 1, "bosses_slain", "dawn_tyrant"),
    Achievement("all_bosses", "World Conqueror", "Defeat all bosses.", "bosses", 5, "bosses_slain"),

    # --- Exploration ---
    Achievement("first_travel", "Wanderer", "Visit your first new area.", "exploration", 1, "areas_visited"),
    Achievement("areas_5", "Traveller", "Visit 5 different areas.", "exploration", 5, "areas_visited"),
    Achievement("areas_10", "Explorer", "Visit 10 different areas.", "exploration", 10, "areas_visited"),
    Achievement("areas_all", "Cartographer", "Visit every area in the world.", "exploration", 17, "areas_visited"),

    # --- Progression ---
    Achievement("level_10", "Apprentice", "Reach level 10.", "progression", 10, "level"),
    Achievement("level_25", "Journeyman", "Reach level 25.", "progression", 25, "level"),
    Achievement("level_50", "Expert", "Reach level 50.", "progression", 50, "level"),
    Achievement("level_75", "Master", "Reach level 75.", "progression", 75, "level"),
    Achievement("level_99", "Ascendant", "Reach level 99.", "progression", 99, "level"),
    Achievement("first_promotion", "Promoted", "Achieve your first class promotion.", "progression", 1, "promotions"),
    Achievement("promotions_3", "Veteran", "Achieve 3 class promotions.", "progression", 3, "promotions"),

    # --- Social ---
    Achievement("first_marriage", "Happily Ever After", "Get married.", "social", 1, "marriages"),
    Achievement("companions_5", "Party Leader", "Recruit 5 companions.", "social", 5, "companions_recruited"),
    Achievement("companions_10", "Full Roster", "Recruit 10 companions.", "social", 10, "companions_recruited"),
    Achievement("companions_all", "Everyone's Friend", "Recruit all companions.", "social", 21, "companions_recruited"),
    Achievement("banter_10", "Eavesdropper", "Hear 10 unique banter lines.", "social", 10, "banter_heard"),
    Achievement("banter_50", "Social Butterfly", "Hear 50 unique banter lines.", "social", 50, "banter_heard"),

    # --- Skills ---
    Achievement("skills_10", "Student", "Learn 10 skills.", "skills", 10, "skills_learned"),
    Achievement("skills_25", "Scholar", "Learn 25 skills.", "skills", 25, "skills_learned"),
    Achievement("skills_50", "Polymath", "Learn 50 skills.", "skills", 50, "skills_learned"),

    # --- Quests ---
    Achievement("quests_5", "Adventurer", "Complete 5 quests.", "quests", 5, "quests_completed"),
    Achievement("quests_15", "Hero", "Complete 15 quests.", "quests", 15, "quests_completed"),
    Achievement("quests_all", "Completionist", "Complete all quests.", "quests", 39, "quests_completed"),
]
