"""Status effects: buffs, debuffs, DOT/HOT, shields and stuns.

A :class:`StatusEffect` is a *live instance* attached to an entity, built from
a JSON template.  Like skills, there is exactly one class here regardless of
how many hundreds of statuses the game eventually ships - the variety comes
from data, not subclasses (see docs/ENGINE_DESIGN.md).

Lifecycle, driven entirely by :meth:`Entity.tick_status_effects`:

``apply`` -> ``on_apply`` -> [``tick`` each turn] -> duration hits 0 -> ``on_expire``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from engine.stats import ModifierSet

__all__ = ["StatusEffect", "StatusStacking"]


class StatusStacking:
    """How a re-application of an already-present status behaves."""

    #: Reset duration to full, keep a single instance (default).
    REFRESH = "refresh"
    #: Add stacks up to ``max_stacks``, refreshing duration too.
    STACK = "stack"
    #: Keep the existing instance untouched; the new application is wasted.
    IGNORE = "ignore"
    #: Allow multiple independent instances side by side.
    SEPARATE = "separate"

    ALL = (REFRESH, STACK, IGNORE, SEPARATE)


@dataclass
class StatusEffect:
    """One active buff/debuff/DOT/HOT/shield/stun on an entity."""

    id: str
    name: str
    duration: int = 1
    #: ``"buff"``, ``"debuff"``, ``"dot"``, ``"hot"``, ``"shield"``, ``"stun"``.
    category: str = "buff"
    #: Per-turn HP change; positive = healing (HOT), negative = damage (DOT).
    per_turn_hp: float = 0.0
    #: Per-turn MP change, same sign convention.
    per_turn_mp: float = 0.0
    #: Damage channel used for DOT ticks - DOTs bypass armour by design.
    damage_type: str = "true"
    #: Stat modifiers contributed while this status is active.
    modifiers: ModifierSet = field(default_factory=ModifierSet)
    #: Remaining absorb pool for ``shield`` statuses.
    shield_hp: float = 0.0
    #: Fraction of incoming damage reflected to the attacker.
    reflect_pct: float = 0.0
    redirect_pct: float = 0.0
    redirect_target: Any = None
    stacks: int = 1
    max_stacks: int = 1
    stacking: str = StatusStacking.REFRESH
    #: Where the status came from, for combat-log wording.
    source_name: str = ""
    description: str = ""

    # ------------------------------------------------------------------
    # Classification helpers - keeps `category ==` string checks out of
    # the rest of the codebase.
    # ------------------------------------------------------------------
    @property
    def is_debuff(self) -> bool:
        return self.category in ("debuff", "dot", "stun")

    @property
    def is_buff(self) -> bool:
        return self.category in ("buff", "hot", "shield")

    @property
    def prevents_action(self) -> bool:
        """Stuns skip the holder's turn (bible section 12: buffs/debuffs)."""
        return self.category == "stun"

    @property
    def is_shield(self) -> bool:
        return self.category == "shield" and self.shield_hp > 0.0

    @property
    def expired(self) -> bool:
        """A shield that has been fully consumed drops immediately."""
        if self.category == "shield":
            return self.duration <= 0 or self.shield_hp <= 0.0
        return self.duration <= 0

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------
    def scaled_modifiers(self) -> ModifierSet:
        """Modifiers multiplied by the current stack count."""
        if self.stacks <= 1:
            return self.modifiers
        scaled = ModifierSet()
        for key, value in self.modifiers.flat.items():
            scaled.add_flat(key, value * self.stacks)
        for key, value in self.modifiers.pct.items():
            scaled.add_pct(key, value * self.stacks)
        return scaled

    def tick_hp(self) -> float:
        """HP delta this turn, scaled by stacks."""
        return self.per_turn_hp * self.stacks

    def tick_mp(self) -> float:
        """MP delta this turn, scaled by stacks."""
        return self.per_turn_mp * self.stacks

    def absorb(self, amount: float) -> float:
        """Consume shield HP; return the damage still getting through."""
        if not self.is_shield or amount <= 0:
            return amount
        absorbed = min(self.shield_hp, amount)
        self.shield_hp -= absorbed
        return amount - absorbed

    def merge_with(self, other: "StatusEffect") -> None:
        """Apply ``other`` onto this existing instance per the stacking rule."""
        if self.stacking == StatusStacking.IGNORE:
            return
        if self.stacking == StatusStacking.STACK:
            self.stacks = min(self.max_stacks, self.stacks + other.stacks)
        # Both STACK and REFRESH extend to the longer of the two durations, so
        # a short re-application can never cut an existing long buff short.
        self.duration = max(self.duration, other.duration)
        if other.category == "shield":
            self.shield_hp = max(self.shield_hp, other.shield_hp)

    def clone(self) -> "StatusEffect":
        """Deep-enough copy - each target needs its own countdown."""
        copied_mods = ModifierSet(flat=dict(self.modifiers.flat), pct=dict(self.modifiers.pct))
        return StatusEffect(
            id=self.id,
            name=self.name,
            duration=self.duration,
            category=self.category,
            per_turn_hp=self.per_turn_hp,
            per_turn_mp=self.per_turn_mp,
            damage_type=self.damage_type,
            modifiers=copied_mods,
            shield_hp=self.shield_hp,
            reflect_pct=self.reflect_pct,
            redirect_pct=self.redirect_pct,
            redirect_target=self.redirect_target,
            stacks=self.stacks,
            max_stacks=self.max_stacks,
            stacking=self.stacking,
            source_name=self.source_name,
            description=self.description,
        )

    # ------------------------------------------------------------------
    # Presentation
    # ------------------------------------------------------------------
    def summary(self) -> str:
        """Short ``Poison (3t x2)`` label for the combat/status panels."""
        label = self.name
        if self.stacks > 1:
            label = f"{label} x{self.stacks}"
        if self.category == "shield":
            return f"{label} ({int(self.shield_hp)} absorb, {self.duration}t)"
        return f"{label} ({self.duration}t)"

    def detail_lines(self) -> list[str]:
        """Multi-line breakdown for tooltips / the Status screen."""
        lines: list[str] = []
        if self.description:
            lines.append(self.description)
        if self.per_turn_hp:
            verb = "Heals" if self.per_turn_hp > 0 else "Deals"
            lines.append(f"{verb} {abs(self.tick_hp()):.0f} HP per turn")
        if self.per_turn_mp:
            verb = "Restores" if self.per_turn_mp > 0 else "Drains"
            lines.append(f"{verb} {abs(self.tick_mp()):.0f} MP per turn")
        if self.shield_hp:
            lines.append(f"Absorbs {self.shield_hp:.0f} damage")
        if self.reflect_pct:
            lines.append(f"Reflects {self.reflect_pct * 100:.0f}% of damage taken")
        lines.extend(self.scaled_modifiers().describe())
        return lines

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "duration": self.duration,
            "category": self.category,
            "per_turn_hp": self.per_turn_hp,
            "per_turn_mp": self.per_turn_mp,
            "damage_type": self.damage_type,
            "modifiers": {"flat": dict(self.modifiers.flat), "pct": dict(self.modifiers.pct)},
            "shield_hp": self.shield_hp,
            "reflect_pct": self.reflect_pct,
            "redirect_pct": self.redirect_pct,
            "stacks": self.stacks,
            "max_stacks": self.max_stacks,
            "stacking": self.stacking,
            "source_name": self.source_name,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StatusEffect":
        stacking = str(payload.get("stacking", StatusStacking.REFRESH))
        if stacking not in StatusStacking.ALL:
            stacking = StatusStacking.REFRESH
        return cls(
            id=str(payload.get("id", "unknown_status")),
            name=str(payload.get("name", payload.get("id", "Status"))),
            duration=int(payload.get("duration", 1)),
            category=str(payload.get("category", "buff")),
            per_turn_hp=float(payload.get("per_turn_hp", 0.0)),
            per_turn_mp=float(payload.get("per_turn_mp", 0.0)),
            damage_type=str(payload.get("damage_type", "true")),
            modifiers=ModifierSet.from_dict(payload.get("modifiers")),
            shield_hp=float(payload.get("shield_hp", 0.0)),
            reflect_pct=float(payload.get("reflect_pct", 0.0)),
            redirect_pct=float(payload.get("redirect_pct", 0.0)),
            stacks=int(payload.get("stacks", 1)),
            max_stacks=int(payload.get("max_stacks", payload.get("stacks", 1))),
            stacking=stacking,
            source_name=str(payload.get("source_name", "")),
            description=str(payload.get("description", "")),
        )
