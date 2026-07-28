"""Stat model and every combat formula in the game.

Bible section 5: *"Gameplay values are never hardcoded."*  Nothing in this
module invents a number.  :class:`Formulas` is built from ``data/config.json``
and every coefficient it uses comes from there, so rebalancing the game is a
JSON edit and never a code change.

Layering, from raw to final:

``StatBlock`` (allocated points)
    -> ``ModifierSet`` (equipment + status effects, flat then percent)
    -> ``DerivedStats`` (HP, power, armour, crit, accuracy, ...)
    -> the damage/hit helpers at the bottom of this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

__all__ = [
    "PRIMARY_STATS",
    "PRIMARY_STAT_NAMES",
    "DERIVED_STATS",
    "DAMAGE_TYPES",
    "StatBlock",
    "ModifierSet",
    "DerivedStats",
    "Formulas",
]

#: Canonical primary stat keys, in display order (bible section 9).
PRIMARY_STATS: tuple[str, ...] = ("STR", "END", "INT", "AGI")

#: Human-readable names for the primary stats, for GUI labels.
PRIMARY_STAT_NAMES: dict[str, str] = {
    "STR": "Strength",
    "END": "Endurance",
    "INT": "Intellect",
    "AGI": "Agility",
}

#: Every stat the engine derives from primaries + modifiers.
DERIVED_STATS: tuple[str, ...] = (
    "max_hp",
    "max_mp",
    "physical_power",
    "magic_power",
    "armor",
    "magic_resist",
    "crit_chance",
    "crit_damage",
    "accuracy",
    "evasion",
    "speed",
)

#: Damage channels (bible section 12).  ``true`` ignores all mitigation.
DAMAGE_TYPES: tuple[str, ...] = ("physical", "magic", "true")

#: Which defence stat mitigates which damage channel.
_DEFENCE_FOR_DAMAGE: dict[str, str | None] = {
    "physical": "armor",
    "magic": "magic_resist",
    "true": None,
}

#: Which offensive stat a skill scales off by default, per damage channel.
_SCALING_FOR_DAMAGE: dict[str, str] = {
    "physical": "physical_power",
    "magic": "magic_power",
    "true": "physical_power",
}


# ----------------------------------------------------------------------
# Primary stats
# ----------------------------------------------------------------------
@dataclass
class StatBlock:
    """The four primary stats.

    Stored as named fields (not a bare dict) so typos are caught at import
    time, but indexable by the canonical ``"STR"``-style keys because that is
    what JSON content and the GUI both speak.
    """

    STR: int = 0
    END: int = 0
    INT: int = 0
    AGI: int = 0

    # -- dict-ish access -------------------------------------------------
    def __getitem__(self, key: str) -> int:
        try:
            return getattr(self, self._normalise(key))
        except AttributeError as exc:  # pragma: no cover - defensive
            raise KeyError(key) from exc

    def __setitem__(self, key: str, value: int) -> None:
        setattr(self, self._normalise(key), int(value))

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key.upper() in PRIMARY_STATS

    def __iter__(self):
        return iter(PRIMARY_STATS)

    @staticmethod
    def _normalise(key: str) -> str:
        upper = key.upper()
        if upper not in PRIMARY_STATS:
            raise KeyError(f"unknown primary stat {key!r}")
        return upper

    # -- arithmetic ------------------------------------------------------
    def total(self) -> int:
        """Sum of all four stats - used for promotion checks and displays."""
        return sum(self[key] for key in PRIMARY_STATS)

    def copy(self) -> "StatBlock":
        return StatBlock(**self.to_dict())

    def add(self, other: Mapping[str, Any] | "StatBlock") -> "StatBlock":
        """Return a new block with ``other`` added component-wise."""
        result = self.copy()
        for key in PRIMARY_STATS:
            result[key] = result[key] + int(_lookup(other, key, 0))
        return result

    def meets(self, requirement: Mapping[str, Any] | None) -> bool:
        """``True`` if every stat in ``requirement`` is met or exceeded."""
        if not requirement:
            return True
        return all(self[key] >= int(value) for key, value in requirement.items() if key.upper() in PRIMARY_STATS)

    # -- serialisation ---------------------------------------------------
    def to_dict(self) -> dict[str, int]:
        return {key: self[key] for key in PRIMARY_STATS}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "StatBlock":
        """Build from JSON.  Unknown keys are ignored, missing keys default 0."""
        if not payload:
            return cls()
        return cls(**{key: int(payload.get(key, payload.get(key.lower(), 0))) for key in PRIMARY_STATS})


def _lookup(source: Mapping[str, Any] | StatBlock, key: str, default: Any) -> Any:
    if isinstance(source, StatBlock):
        return source[key]
    return source.get(key, source.get(key.lower(), default))


# ----------------------------------------------------------------------
# Modifiers
# ----------------------------------------------------------------------
@dataclass
class ModifierSet:
    """Accumulated flat and percentage adjustments from equipment + statuses.

    Keys may be either primary stats (``"STR"``) or derived stats
    (``"armor"``).  Percentages are *additive with each other* and applied
    after flats - two +20% buffs give +40%, not +44%.  That is deliberate: it
    keeps buff stacking legible to the player and prevents multiplicative
    runaway once dozens of sources exist.
    """

    flat: dict[str, float] = field(default_factory=dict)
    pct: dict[str, float] = field(default_factory=dict)

    def add_flat(self, key: str, value: float) -> None:
        if value:
            self.flat[key] = self.flat.get(key, 0.0) + float(value)

    def add_pct(self, key: str, value: float) -> None:
        if value:
            self.pct[key] = self.pct.get(key, 0.0) + float(value)

    def merge(self, other: "ModifierSet") -> None:
        """Fold another set into this one, in place."""
        for key, value in other.flat.items():
            self.add_flat(key, value)
        for key, value in other.pct.items():
            self.add_pct(key, value)

    def apply(self, key: str, base: float) -> float:
        """Apply ``flat`` then ``pct`` for ``key`` to a base value."""
        return (base + self.flat.get(key, 0.0)) * (1.0 + self.pct.get(key, 0.0))

    def describe(self) -> list[str]:
        """Readable ``+5 STR`` / ``+20% armor`` lines for the GUI."""
        lines: list[str] = []
        for key, value in sorted(self.flat.items()):
            if value:
                lines.append(f"{value:+g} {key}")
        for key, value in sorted(self.pct.items()):
            if value:
                lines.append(f"{value * 100:+g}% {key}")
        return lines

    def is_empty(self) -> bool:
        return not any(self.flat.values()) and not any(self.pct.values())

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "ModifierSet":
        """Build from JSON of the form ``{"flat": {...}, "pct": {...}}``.

        A bare mapping (``{"STR": 3}``) is also accepted and read as flats,
        because that is by far the common case in item definitions and forcing
        content authors to nest it would be noise.
        """
        result = cls()
        if not payload:
            return result
        if "flat" in payload or "pct" in payload:
            for key, value in (payload.get("flat") or {}).items():
                result.add_flat(key, float(value))
            for key, value in (payload.get("pct") or {}).items():
                result.add_pct(key, float(value))
            return result
        for key, value in payload.items():
            if key.endswith("_pct"):
                result.add_pct(key[:-4], float(value))
            else:
                result.add_flat(key, float(value))
        return result


# ----------------------------------------------------------------------
# Derived stats
# ----------------------------------------------------------------------
@dataclass
class DerivedStats:
    """Fully-resolved combat stats for one entity at one moment in time."""

    max_hp: int = 1
    max_mp: int = 0
    physical_power: float = 0.0
    magic_power: float = 0.0
    armor: float = 0.0
    magic_resist: float = 0.0
    crit_chance: float = 0.0
    crit_damage: float = 1.5
    accuracy: float = 0.9
    evasion: float = 0.0
    speed: float = 10.0

    def __getitem__(self, key: str) -> float:
        if key not in DERIVED_STATS:
            raise KeyError(f"unknown derived stat {key!r}")
        return getattr(self, key)

    def to_dict(self) -> dict[str, float]:
        return {key: getattr(self, key) for key in DERIVED_STATS}

    def defence_for(self, damage_type: str) -> float:
        """Mitigation stat matching a damage channel (0 for ``true``)."""
        key = _DEFENCE_FOR_DAMAGE.get(damage_type)
        return 0.0 if key is None else float(getattr(self, key))

    def scaling_for(self, damage_type: str) -> float:
        """Default offensive stat a skill of this channel scales from."""
        return float(getattr(self, _SCALING_FOR_DAMAGE.get(damage_type, "physical_power")))


# ----------------------------------------------------------------------
# Formulas
# ----------------------------------------------------------------------
def _coeff(config: Mapping[str, Any], name: str) -> dict[str, float]:
    raw = config.get(name) or {}
    return {key: float(value) for key, value in raw.items()}


@dataclass
class Formulas:
    """Every derived-stat and damage formula, loaded from config JSON.

    One instance is shared by the whole engine.  It holds no per-entity state,
    which is what makes it safe to hand the same object to the player, every
    enemy, and the combat resolver simultaneously.
    """

    hp: dict[str, float] = field(default_factory=dict)
    mp: dict[str, float] = field(default_factory=dict)
    physical_power: dict[str, float] = field(default_factory=dict)
    magic_power: dict[str, float] = field(default_factory=dict)
    armor: dict[str, float] = field(default_factory=dict)
    magic_resist: dict[str, float] = field(default_factory=dict)
    crit_chance: dict[str, float] = field(default_factory=dict)
    crit_damage: dict[str, float] = field(default_factory=dict)
    accuracy: dict[str, float] = field(default_factory=dict)
    evasion: dict[str, float] = field(default_factory=dict)
    speed: dict[str, float] = field(default_factory=dict)
    mitigation_constant: float = 100.0
    hit_floor: float = 0.05
    hit_ceiling: float = 0.99

    @classmethod
    def from_dict(cls, config: Mapping[str, Any] | None) -> "Formulas":
        config = config or {}
        return cls(
            hp=_coeff(config, "hp"),
            mp=_coeff(config, "mp"),
            physical_power=_coeff(config, "physical_power"),
            magic_power=_coeff(config, "magic_power"),
            armor=_coeff(config, "armor"),
            magic_resist=_coeff(config, "magic_resist"),
            crit_chance=_coeff(config, "crit_chance"),
            crit_damage=_coeff(config, "crit_damage"),
            accuracy=_coeff(config, "accuracy"),
            evasion=_coeff(config, "evasion"),
            speed=_coeff(config, "speed"),
            mitigation_constant=float(config.get("mitigation_constant", 100.0)),
            hit_floor=float(config.get("hit_floor", 0.05)),
            hit_ceiling=float(config.get("hit_ceiling", 0.99)),
        )

    # -- internals -------------------------------------------------------
    @staticmethod
    def _linear(coeff: Mapping[str, float], stats: Mapping[str, float], level: int) -> float:
        """Evaluate ``base + sum(per_<stat> * stat) + per_level * level``.

        Coefficient keys are read dynamically so a designer can add
        ``"per_agi"`` to the HP formula in JSON and have it work immediately,
        with no code change here.
        """
        total = float(coeff.get("base", 0.0))
        total += float(coeff.get("per_level", 0.0)) * level
        for key, value in coeff.items():
            if key.startswith("per_") and key != "per_level":
                stat_key = key[4:].upper()
                if stat_key in PRIMARY_STATS:
                    total += float(value) * float(stats.get(stat_key, 0.0))
        return total

    def _effective_primaries(self, base: StatBlock, mods: ModifierSet) -> dict[str, float]:
        return {key: max(0.0, mods.apply(key, float(base[key]))) for key in PRIMARY_STATS}

    # -- public ----------------------------------------------------------
    def effective_primaries(self, base: StatBlock, mods: ModifierSet | None = None) -> dict[str, float]:
        """Primary stats after equipment/status modifiers - shown in Status."""
        return self._effective_primaries(base, mods or ModifierSet())

    def derive(self, base: StatBlock, level: int, mods: ModifierSet | None = None) -> DerivedStats:
        """Turn primaries + level + modifiers into final combat stats."""
        mods = mods or ModifierSet()
        primaries = self._effective_primaries(base, mods)

        def resolve(name: str, coeff: Mapping[str, float]) -> float:
            return mods.apply(name, self._linear(coeff, primaries, level))

        crit_chance = resolve("crit_chance", self.crit_chance)
        accuracy = resolve("accuracy", self.accuracy)
        evasion = resolve("evasion", self.evasion)

        return DerivedStats(
            max_hp=max(1, int(round(resolve("max_hp", self.hp)))),
            max_mp=max(0, int(round(resolve("max_mp", self.mp)))),
            physical_power=max(0.0, resolve("physical_power", self.physical_power)),
            magic_power=max(0.0, resolve("magic_power", self.magic_power)),
            armor=max(0.0, resolve("armor", self.armor)),
            magic_resist=max(0.0, resolve("magic_resist", self.magic_resist)),
            crit_chance=_clamp(crit_chance, 0.0, float(self.crit_chance.get("max", 1.0))),
            crit_damage=max(1.0, resolve("crit_damage", self.crit_damage)),
            accuracy=_clamp(accuracy, 0.0, float(self.accuracy.get("max", 1.0))),
            evasion=_clamp(evasion, 0.0, float(self.evasion.get("max", 1.0))),
            speed=max(0.0, resolve("speed", self.speed)),
        )

    # -- combat maths ----------------------------------------------------
    def mitigation(self, defence: float) -> float:
        """Fraction of damage absorbed by ``defence``.

        ``d / (d + K)`` - asymptotic, so armour always helps but never reaches
        100% immunity no matter how much is stacked.
        """
        defence = max(0.0, defence)
        return defence / (defence + self.mitigation_constant)

    def apply_mitigation(
        self,
        raw: float,
        defence: float,
        penetration_pct: float = 0.0,
        penetration_flat: float = 0.0,
    ) -> float:
        """Reduce ``raw`` by ``defence`` after penetration.

        Percentage penetration applies before flat, so flat penetration can't
        be scaled up by a percentage effect stacked on top of it.
        """
        effective = max(0.0, defence * (1.0 - _clamp(penetration_pct, 0.0, 1.0)) - max(0.0, penetration_flat))
        return max(0.0, raw * (1.0 - self.mitigation(effective)))

    def hit_chance(self, accuracy: float, evasion: float) -> float:
        """Chance to land an attack, clamped so nothing is ever un-hittable."""
        return _clamp(accuracy - evasion, self.hit_floor, self.hit_ceiling)


def _clamp(value: float, low: float, high: float) -> float:
    if high < low:
        high = low
    return max(low, min(high, value))
