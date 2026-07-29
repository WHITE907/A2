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
        self.taunted_by: Entity | None = None
        self.taunt_turns: int = 0

        # Derived stats are recomputed only when something that feeds them
        # changes.  Combat asks for them constantly (every hit reads accuracy,
        # evasion, armour), so recomputing per call would be wasteful.
        self._cached: DerivedStats | None = None
        self._cache_token: int = 0

        derived = self.derived_stats()
        self.current_hp: float = float(derived.max_hp)
        self.current_mp: float = float(derived.max_mp)
        self.current_sp: float = float(derived.max_sp)

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

        Called by anything that changes stats, level, gear or statuses.  HP/MP/SP
        are clamped to the new maximums but *not* refilled - losing a +max-HP
        buff should not heal you.
        """
        self._cached = None
        self._cache_token += 1
        if self._cached is None and hasattr(self, "current_hp"):
            derived = self.derived_stats()
            self.current_hp = min(self.current_hp, float(derived.max_hp))
            self.current_mp = min(self.current_mp, float(derived.max_mp))
            self.current_sp = min(self.current_sp, float(derived.max_sp))

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
    def max_sp(self) -> int:
        return self.derived_stats().max_sp

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def hp_fraction(self) -> float:
        return 0.0 if self.max_hp <= 0 else max(0.0, min(1.0, self.current_hp / self.max_hp))

    @property
    def mp_fraction(self) -> float:
        return 0.0 if self.max_mp <= 0 else max(0.0, min(1.0, self.current_mp / self.max_mp))

    @property
    def sp_fraction(self) -> float:
        return 0.0 if self.max_sp <= 0 else max(0.0, min(1.0, self.current_sp / self.max_sp))

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

        for status in self.statuses:
            protector = getattr(status, "redirect_target", None)
            if remaining > 0 and status.redirect_pct > 0 and protector is not None and protector.is_alive:
                redirected = remaining * min(1.0, status.redirect_pct)
                protector.take_raw_damage(
                    redirected, damage_type=damage_type, ignore_shield=False,
                    attacker=attacker, allow_reflect=False,
                )
                remaining -= redirected

        reflected = 0.0
        if allow_reflect and attacker is not None and remaining > 0:
            reflect_pct = sum(status.reflect_pct for status in self.statuses)
            reflect_pct += sum(float(s.get("value", 0)) for s in getattr(self, "special_effects", lambda: [])() if s.get("type") == "reflect")
            if reflect_pct > 0:
                reflected = remaining * reflect_pct

        self.current_hp = max(0.0, self.current_hp - remaining)
        # Counter is a passive data-defined special. It is resolved here so
        # every incoming damage source (skills, hazards, and direct attacks)
        # behaves consistently, while the re-entry guard prevents chains.
        if attacker is not None and remaining > 0 and allow_reflect:
            for special in getattr(self, "special_effects", lambda: [])():
                if special.get("type") == "counter" and float(special.get("value", 0)) > 0:
                    attacker.take_raw_damage(remaining * float(special["value"]), damage_type="true", attacker=None, allow_reflect=False)
        self._cached = None
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
        self._cached = None
        return self.current_hp - before

    def change_mp(self, amount: float) -> float:
        """Add (or subtract) MP; returns the actual delta after clamping."""
        before = self.current_mp
        self.current_mp = max(0.0, min(float(self.max_mp), self.current_mp + float(amount)))
        return self.current_mp - before

    def change_sp(self, amount: float) -> float:
        """Add (or subtract) SP; returns the actual delta after clamping."""
        before = self.current_sp
        self.current_sp = max(0.0, min(float(self.max_sp), self.current_sp + float(amount)))
        return self.current_sp - before

    def can_afford(self, cost: float) -> bool:
        return self.current_mp >= cost

    def spend_mp(self, cost: float) -> bool:
        """Pay an MP cost.  Returns ``False`` and spends nothing if too poor."""
        if not self.can_afford(cost):
            return False
        self.current_mp -= float(cost)
        return True

    def can_afford_sp(self, cost: float) -> bool:
        return self.current_sp >= cost

    def spend_sp(self, cost: float) -> bool:
        """Pay an SP cost.  Returns ``False`` and spends nothing if too poor."""
        if not self.can_afford_sp(cost):
            return False
        self.current_sp -= float(cost)
        return True

    def restore_fully(self) -> None:
        """Full heal and clear all statuses - inn rest, respawn, new battle."""
        self.statuses.clear()
        self.invalidate_stats()
        self.current_hp = float(self.max_hp)
        self.current_mp = float(self.max_mp)
        self.current_sp = float(self.max_sp)

    def regenerate_resources(self) -> tuple[float, float]:
        """Per-turn MP and SP regeneration, scaling off INT and END respectively.
        
        Returns (mp_gained, sp_gained) for combat log messages.
        """
        primaries = self.effective_primaries()
        # MP regen: base 2 + 5% of INT
        mp_regen = 2.0 + primaries.get("INT", 0.0) * 0.05
        # SP regen: base 3 + 5% of END
        sp_regen = 3.0 + primaries.get("END", 0.0) * 0.05
        
        mp_gained = self.change_mp(mp_regen)
        sp_gained = self.change_sp(sp_regen)
        return mp_gained, sp_gained

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
        if self.taunt_turns > 0:
            self.taunt_turns -= 1
            if self.taunt_turns <= 0:
                self.taunted_by = None

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

    def sp_text(self) -> str:
        return f"{int(self.current_sp)}/{self.max_sp}"

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
            "current_sp": self.current_sp,
            "statuses": [status.to_dict() for status in self.statuses],
        }

    def _restore_common(self, payload: Mapping[str, Any]) -> None:
        self.statuses = [StatusEffect.from_dict(item) for item in payload.get("statuses", [])]
        self.invalidate_stats()
        self.current_hp = float(payload.get("current_hp", self.max_hp))
        self.current_mp = float(payload.get("current_mp", self.max_mp))
        self.current_sp = float(payload.get("current_sp", self.max_sp))
