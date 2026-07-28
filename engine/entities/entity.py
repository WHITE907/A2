"""``Entity`` - the shared supertype for everything that fights.

Per docs/ENGINE_DESIGN.md, inheritance is used here precisely because Player
and Enemy *are* genuinely the same kind of thing (HP/MP/stats/turn effects),
not because they are "kinds of content".  Content variety lives in JSON.

This class owns all state transitions an entity can undergo - taking damage,
healing, spending MP, gaining/ticking/losing statuses - so no other layer ever
mutates HP directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from engine.skills.status import StatusEffect, StatusStacking
from engine.stats import DerivedStats, Formulas, ModifierSet, StatBlock

__all__ = ["Entity", "DamageOutcome", "TickReport"]


@dataclass
class DamageOutcome:
    """Result of one damage application, after shields and reflect."""

    damage: float = 0.0
    absorbed: float = 0.0
    reflected: float = 0.0
    lethal: bool = False


@dataclass
class TickReport:
    """What happened to one entity during end-of-turn upkeep."""

    messages: list[str] = field(default_factory=list)
    hp_delta: float = 0.0
    mp_delta: float = 0.0
    expired: list[str] = field(default_factory=list)
    died: bool = False


class Entity(ABC):
    """Anything with HP, MP, stats and status effects."""

    def __init__(
        self,
        name: str,
        level: int,
        base_stats: StatBlock,
        formulas: Formulas,
    ) -> None:
        self.name = name
        self.level = max(1, int(level))
        self.base_stats = base_stats
        self.formulas = formulas
        self.statuses: list[StatusEffect] = []

        # Derived stats are recomputed only when something that feeds them
        # changes.  Combat asks for them constantly (every hit reads accuracy,
        # evasion, armour), so recomputing per call would be wasteful.
        self._cached: DerivedStats | None = None
        self._cache_token: int = 0

        derived = self.derived_stats()
        self.current_hp: float = float(derived.max_hp)
        self.current_mp: float = float(derived.max_mp)

    # ------------------------------------------------------------------
    # Modifier sourcing
    # ------------------------------------------------------------------
    @abstractmethod
    def _equipment_modifiers(self) -> ModifierSet:
        """Modifiers from gear.  Enemies return an empty set."""

    def _status_modifiers(self) -> ModifierSet:
        combined = ModifierSet()
        for status in self.statuses:
            if not status.modifiers.is_empty():
                combined.merge(status.scaled_modifiers())
        return combined

    def total_modifiers(self) -> ModifierSet:
        """Equipment + statuses, merged."""
        combined = ModifierSet()
        combined.merge(self._equipment_modifiers())
        combined.merge(self._status_modifiers())
        return combined

    # ------------------------------------------------------------------
    # Derived stats + caching
    # ------------------------------------------------------------------
    def invalidate_stats(self) -> None:
        """Drop the derived-stat cache.

        Called by anything that changes stats, level, gear or statuses.  HP/MP
        are clamped to the new maximums but *not* refilled - losing a +max-HP
        buff should not heal you.
        """
        self._cached = None
        self._cache_token += 1
        if self._cached is None and hasattr(self, "current_hp"):
            derived = self.derived_stats()
            self.current_hp = min(self.current_hp, float(derived.max_hp))
            self.current_mp = min(self.current_mp, float(derived.max_mp))

    def derived_stats(self) -> DerivedStats:
        if self._cached is None:
            self._cached = self.formulas.derive(self.base_stats, self.level, self.total_modifiers())
        return self._cached

    def effective_primaries(self) -> dict[str, float]:
        """Primary stats after modifiers - for the Status screen."""
        return self.formulas.effective_primaries(self.base_stats, self.total_modifiers())

    # -- convenience properties -----------------------------------------
    @property
    def max_hp(self) -> int:
        return self.derived_stats().max_hp

    @property
    def max_mp(self) -> int:
        return self.derived_stats().max_mp

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def hp_fraction(self) -> float:
        return 0.0 if self.max_hp <= 0 else max(0.0, min(1.0, self.current_hp / self.max_hp))

    @property
    def mp_fraction(self) -> float:
        return 0.0 if self.max_mp <= 0 else max(0.0, min(1.0, self.current_mp / self.max_mp))

    # ------------------------------------------------------------------
    # Damage / healing
    # ------------------------------------------------------------------
    def take_raw_damage(
        self,
        amount: float,
        damage_type: str = "true",
        ignore_shield: bool = False,
        attacker: "Entity | None" = None,
        allow_reflect: bool = True,
    ) -> DamageOutcome:
        """Apply already-mitigated damage.

        Mitigation happens in :class:`~engine.skills.effects.DamageEffect`;
        by the time damage reaches here it is final except for shields.  DOT
        ticks call this directly with ``damage_type="true"``.

        Reflect is *reported*, not applied - the caller applies it to the
        attacker.  Doing it here would recurse forever if both sides reflect.
        """
        if amount <= 0 or not self.is_alive:
            return DamageOutcome()

        remaining = float(amount)
        absorbed = 0.0

        if not ignore_shield:
            # Consume shields oldest-first so a fresh shield isn't wasted on
            # chip damage an expiring one could have eaten.
            for status in [s for s in self.statuses if s.is_shield]:
                before = remaining
                remaining = status.absorb(remaining)
                absorbed += before - remaining
                if remaining <= 0:
                    break
            if absorbed:
                self._drop_expired_shields()

        reflected = 0.0
        if allow_reflect and attacker is not None and remaining > 0:
            reflect_pct = sum(status.reflect_pct for status in self.statuses)
            if reflect_pct > 0:
                reflected = remaining * reflect_pct

        self.current_hp = max(0.0, self.current_hp - remaining)
        return DamageOutcome(
            damage=remaining,
            absorbed=absorbed,
            reflected=reflected,
            lethal=not self.is_alive,
        )

    def heal(self, amount: float) -> float:
        """Restore HP; returns how much was actually restored."""
        if amount <= 0 or not self.is_alive:
            return 0.0
        before = self.current_hp
        self.current_hp = min(float(self.max_hp), self.current_hp + float(amount))
        return self.current_hp - before

    def change_mp(self, amount: float) -> float:
        """Add (or subtract) MP; returns the actual delta after clamping."""
        before = self.current_mp
        self.current_mp = max(0.0, min(float(self.max_mp), self.current_mp + float(amount)))
        return self.current_mp - before

    def can_afford(self, cost: float) -> bool:
        return self.current_mp >= cost

    def spend_mp(self, cost: float) -> bool:
        """Pay an MP cost.  Returns ``False`` and spends nothing if too poor."""
        if not self.can_afford(cost):
            return False
        self.current_mp -= float(cost)
        return True

    def restore_fully(self) -> None:
        """Full heal and clear all statuses - inn rest, respawn, new battle."""
        self.statuses.clear()
        self.invalidate_stats()
        self.current_hp = float(self.max_hp)
        self.current_mp = float(self.max_mp)

    def kill(self) -> None:
        self.current_hp = 0.0

    # ------------------------------------------------------------------
    # Status handling
    # ------------------------------------------------------------------
    def apply_status(self, status: StatusEffect) -> None:
        """Attach a status, honouring its stacking rule."""
        if status.stacking != StatusStacking.SEPARATE:
            existing = next((s for s in self.statuses if s.id == status.id), None)
            if existing is not None:
                existing.merge_with(status)
                self.invalidate_stats()
                return
        self.statuses.append(status)
        self.invalidate_stats()

    def remove_status(self, status_id: str) -> bool:
        before = len(self.statuses)
        self.statuses = [s for s in self.statuses if s.id != status_id]
        if len(self.statuses) != before:
            self.invalidate_stats()
            return True
        return False

    def clear_debuffs(self) -> list[str]:
        """Cleanse - returns the names of everything removed."""
        removed = [s.name for s in self.statuses if s.is_debuff]
        if removed:
            self.statuses = [s for s in self.statuses if not s.is_debuff]
            self.invalidate_stats()
        return removed

    def has_status(self, status_id: str) -> bool:
        return any(s.id == status_id for s in self.statuses)

    @property
    def is_stunned(self) -> bool:
        return any(s.prevents_action for s in self.statuses)

    def status_resistance(self) -> float:
        """Chance to shrug off an incoming debuff.

        Sourced from modifiers so gear and buffs can grant it; clamped below 1
        so nothing is ever fully immune.
        """
        mods = self.total_modifiers()
        return max(0.0, min(0.95, mods.flat.get("status_resist", 0.0) + mods.pct.get("status_resist", 0.0)))

    def _drop_expired_shields(self) -> None:
        remaining = [s for s in self.statuses if not (s.category == "shield" and s.shield_hp <= 0)]
        if len(remaining) != len(self.statuses):
            self.statuses = remaining
            self.invalidate_stats()

    def tick_status_effects(self) -> TickReport:
        """End-of-turn upkeep: DOT/HOT ticks, then duration countdown.

        Order matters - a 1-turn poison must deal damage once before it
        expires, so ticking happens before the countdown.
        """
        report = TickReport()
        if not self.statuses:
            return report

        for status in list(self.statuses):
            hp_delta = status.tick_hp()
            if hp_delta < 0 and self.is_alive:
                outcome = self.take_raw_damage(
                    abs(hp_delta), damage_type=status.damage_type, ignore_shield=True
                )
                report.hp_delta -= outcome.damage
                report.messages.append(
                    f"{self.name} suffers {outcome.damage:.0f} damage from {status.name}."
                )
                if not self.is_alive:
                    report.died = True
            elif hp_delta > 0:
                healed = self.heal(hp_delta)
                if healed > 0:
                    report.hp_delta += healed
                    report.messages.append(f"{self.name} recovers {healed:.0f} HP from {status.name}.")

            mp_delta = status.tick_mp()
            if mp_delta:
                changed = self.change_mp(mp_delta)
                if changed:
                    report.mp_delta += changed
                    verb = "recovers" if changed > 0 else "loses"
                    report.messages.append(f"{self.name} {verb} {abs(changed):.0f} MP from {status.name}.")

        for status in self.statuses:
            status.duration -= 1

        expired = [s for s in self.statuses if s.expired]
        if expired:
            report.expired = [s.name for s in expired]
            report.messages.extend(f"{s.name} wears off {self.name}." for s in expired)
            self.statuses = [s for s in self.statuses if not s.expired]
            self.invalidate_stats()

        return report

    # ------------------------------------------------------------------
    # Presentation
    # ------------------------------------------------------------------
    def status_summaries(self) -> list[str]:
        return [status.summary() for status in self.statuses]

    def hp_text(self) -> str:
        return f"{int(self.current_hp)}/{self.max_hp}"

    def mp_text(self) -> str:
        return f"{int(self.current_mp)}/{self.max_mp}"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} {self.name} Lv{self.level} {self.hp_text()}>"

    # ------------------------------------------------------------------
    # Persistence helpers shared by subclasses
    # ------------------------------------------------------------------
    def _serialise_common(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "level": self.level,
            "base_stats": self.base_stats.to_dict(),
            "current_hp": self.current_hp,
            "current_mp": self.current_mp,
            "statuses": [status.to_dict() for status in self.statuses],
        }

    def _restore_common(self, payload: Mapping[str, Any]) -> None:
        self.statuses = [StatusEffect.from_dict(item) for item in payload.get("statuses", [])]
        self.invalidate_stats()
        self.current_hp = float(payload.get("current_hp", self.max_hp))
        self.current_mp = float(payload.get("current_mp", self.max_mp))
