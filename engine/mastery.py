"""Mastery tracks - bible section 14: ``F, E, D, C, B, A, S, SS, Master``.

Mastery is earned by *use*: swinging a sword trains ``sword``, casting fire
spells trains ``fire``.  Ranks gate promotions (section 10) and some skills
(section 11), and each rank grants a small passive bonus so investment is felt
in combat, not just on a checklist.

Thresholds and per-rank bonuses come from ``data/config.json``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from engine.stats import ModifierSet

__all__ = ["MASTERY_RANKS", "rank_index", "rank_at_least", "MasteryTrack", "MasteryBook"]

#: Ordered low -> high.  Index in this tuple *is* the rank's numeric value.
MASTERY_RANKS: tuple[str, ...] = ("F", "E", "D", "C", "B", "A", "S", "SS", "Master")

#: EXP required to *reach* each rank, used when config omits its own table.
_DEFAULT_THRESHOLDS: tuple[int, ...] = (0, 100, 300, 700, 1400, 2600, 4500, 7500, 12000)


def rank_index(rank: str) -> int:
    """Numeric value of a rank name; unknown names read as ``F`` (0)."""
    try:
        return MASTERY_RANKS.index(rank)
    except ValueError:
        return 0


def rank_at_least(current: str, required: str) -> bool:
    """``True`` if ``current`` meets or exceeds ``required``."""
    return rank_index(current) >= rank_index(required)


@dataclass
class MasteryTrack:
    """One trainable discipline (a weapon type, a magic school, a craft)."""

    id: str
    name: str
    exp: float = 0.0
    #: ``"weapon"``, ``"magic"``, ``"craft"`` - purely for GUI grouping.
    kind: str = "weapon"

    def rank(self, thresholds: Iterable[int]) -> str:
        """Highest rank whose threshold this track's EXP has passed."""
        current = MASTERY_RANKS[0]
        for index, needed in enumerate(thresholds):
            if self.exp >= needed and index < len(MASTERY_RANKS):
                current = MASTERY_RANKS[index]
        return current

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "exp": self.exp, "kind": self.kind}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MasteryTrack":
        return cls(
            id=str(payload.get("id", "unknown")),
            name=str(payload.get("name", payload.get("id", "Unknown"))),
            exp=float(payload.get("exp", 0.0)),
            kind=str(payload.get("kind", "weapon")),
        )


class MasteryBook:
    """All of one character's mastery tracks, plus the shared rank config."""

    def __init__(
        self,
        thresholds: Iterable[int] | None = None,
        rank_bonuses: Mapping[str, Mapping[str, float]] | None = None,
        catalog: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.thresholds: list[int] = list(thresholds) if thresholds else list(_DEFAULT_THRESHOLDS)
        #: Per-rank stat bonus, e.g. ``{"B": {"physical_power": 4}}``.
        self.rank_bonuses: dict[str, dict[str, float]] = {
            str(rank): {str(k): float(v) for k, v in bonus.items()}
            for rank, bonus in (rank_bonuses or {}).items()
        }
        #: Known track definitions from JSON, so display names survive saves.
        self.catalog: dict[str, dict[str, Any]] = {
            str(key): dict(value) for key, value in (catalog or {}).items()
        }
        self.tracks: dict[str, MasteryTrack] = {}

    # ------------------------------------------------------------------
    def ensure(self, track_id: str) -> MasteryTrack:
        """Fetch a track, creating it on first use."""
        track_id = track_id.lower()
        track = self.tracks.get(track_id)
        if track is None:
            meta = self.catalog.get(track_id, {})
            track = MasteryTrack(
                id=track_id,
                name=str(meta.get("name", track_id.replace("_", " ").title())),
                kind=str(meta.get("kind", "weapon")),
            )
            self.tracks[track_id] = track
        return track

    def gain(self, track_id: str, amount: float) -> tuple[str, str | None]:
        """Add EXP.  Returns ``(new_rank, rank_name_if_promoted)``."""
        if not track_id or amount <= 0:
            return (MASTERY_RANKS[0], None)
        track = self.ensure(track_id)
        before = track.rank(self.thresholds)
        track.exp += float(amount)
        after = track.rank(self.thresholds)
        return (after, after if after != before else None)

    def rank_of(self, track_id: str) -> str:
        track = self.tracks.get(track_id.lower())
        return MASTERY_RANKS[0] if track is None else track.rank(self.thresholds)

    def exp_of(self, track_id: str) -> float:
        track = self.tracks.get(track_id.lower())
        return 0.0 if track is None else track.exp

    def meets(self, requirements: Mapping[str, str] | None) -> bool:
        """``True`` if every ``{track: rank}`` requirement is satisfied."""
        if not requirements:
            return True
        return all(rank_at_least(self.rank_of(track), rank) for track, rank in requirements.items())

    def highest_rank(self) -> str:
        """Best rank across all tracks - the headline 'Mastery' value."""
        if not self.tracks:
            return MASTERY_RANKS[0]
        return max((t.rank(self.thresholds) for t in self.tracks.values()), key=rank_index)

    def modifiers(self) -> ModifierSet:
        """Cumulative passive bonuses from every rank reached in every track.

        Bonuses accumulate: reaching ``C`` also keeps the ``E``/``D`` bonuses,
        so progress never feels like it plateaus between rank-ups.
        """
        combined = ModifierSet()
        if not self.rank_bonuses:
            return combined
        for track in self.tracks.values():
            reached = rank_index(track.rank(self.thresholds))
            for index in range(reached + 1):
                bonus = self.rank_bonuses.get(MASTERY_RANKS[index])
                if bonus:
                    for key, value in bonus.items():
                        combined.add_flat(key, value)
        return combined

    def progress_to_next(self, track_id: str) -> tuple[float, float, str | None]:
        """``(current_exp_into_rank, exp_needed_for_rank, next_rank_name)``."""
        track = self.ensure(track_id)
        current = rank_index(track.rank(self.thresholds))
        if current >= len(MASTERY_RANKS) - 1 or current + 1 >= len(self.thresholds):
            return (track.exp, track.exp, None)
        floor = self.thresholds[current]
        ceiling = self.thresholds[current + 1]
        return (track.exp - floor, max(1.0, ceiling - floor), MASTERY_RANKS[current + 1])

    def display_lines(self) -> list[str]:
        """``Sword: B (1420 EXP) -> A 45%`` lines for the Status screen with progress."""
        lines = []
        for track in sorted(self.tracks.values(), key=lambda t: (-t.exp, t.name)):
            rank = track.rank(self.thresholds)
            exp = track.exp
            cur_into, needed, next_rank = self.progress_to_next(track.id)
            if next_rank:
                pct = (cur_into / needed * 100) if needed else 0
                bar_filled = int(pct // 10)
                bar = "█" * bar_filled + "░" * (10 - bar_filled)
                lines.append(f"{track.name}: {rank} ({exp:.0f} EXP) -> {next_rank} {pct:.0f}% [{bar}] {cur_into:.0f}/{needed:.0f}")
            else:
                lines.append(f"{track.name}: {rank} ({exp:.0f} EXP) [MAX]")
        return lines

    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {"tracks": [track.to_dict() for track in self.tracks.values()]}

    def load_dict(self, payload: Mapping[str, Any] | None) -> None:
        self.tracks.clear()
        if not payload:
            return
        for item in payload.get("tracks", []):
            track = MasteryTrack.from_dict(item)
            self.tracks[track.id] = track
