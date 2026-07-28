"""Effect strategies - the composable verbs every skill is built from.

Per docs/ENGINE_DESIGN.md, class count scales with *behaviour types*, not
content volume.  A skill is a list of these objects; "Fireball" is not a
Python class, it is a JSON entry whose ``effects`` array contains one
:class:`DamageEffect` and maybe one :class:`ApplyStatusEffect`.

The five shipped behaviours:

===================  ==========================================================
``damage``           Physical / magic / true damage, with hit + crit rolls.
``heal``             Restore HP, optionally scaling off a caster stat.
``resource``         Restore or drain MP.
``shield``           Attach an absorb pool.
``apply_status``     Attach any buff/debuff/DOT/HOT from ``data/statuses.json``.
===================  ==========================================================

Adding a genuinely new *behaviour* means adding one class here and one
``@register_effect`` line.  Adding new *content* means editing JSON only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Mapping

from engine.stats import DAMAGE_TYPES, PRIMARY_STATS

if TYPE_CHECKING:  # pragma: no cover - typing only
    from engine.entities.entity import Entity
    from engine.skills.status import StatusEffect

__all__ = [
    "Effect",
    "EffectContext",
    "EffectResult",
    "DamageEffect",
    "HealEffect",
    "ResourceEffect",
    "ShieldEffect",
    "ApplyStatusEffect",
    "register_effect",
    "build_effect",
    "build_effects",
    "known_effect_types",
]


# ----------------------------------------------------------------------
# Context / result
# ----------------------------------------------------------------------
@dataclass
class EffectContext:
    """Everything an effect needs from the outside world.

    Passing this instead of reaching for globals is what keeps effects pure
    enough to unit-test: give it a seeded RNG and the same inputs always
    produce the same output.
    """

    rng: Any
    formulas: Any
    #: Resolves a status id to a template instance; injected by SkillManager
    #: so effects never read JSON themselves.
    status_factory: Callable[[str], "StatusEffect | None"] | None = None


@dataclass
class EffectResult:
    """What one effect did to one target - the atom of the combat log."""

    target_name: str
    kind: str
    amount: float = 0.0
    crit: bool = False
    missed: bool = False
    absorbed: float = 0.0
    reflected: float = 0.0
    status_name: str = ""
    message: str = ""
    lethal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target_name,
            "kind": self.kind,
            "amount": self.amount,
            "crit": self.crit,
            "missed": self.missed,
            "absorbed": self.absorbed,
            "reflected": self.reflected,
            "status": self.status_name,
            "message": self.message,
            "lethal": self.lethal,
        }


# ----------------------------------------------------------------------
# Base
# ----------------------------------------------------------------------
class Effect(ABC):
    """Strategy interface: one thing a skill does to one target."""

    #: JSON discriminator, set by ``@register_effect``.
    type_id: str = "effect"

    def __init__(self, payload: Mapping[str, Any] | None = None) -> None:
        payload = payload or {}
        #: ``"enemy"``, ``"ally"``, or ``"self"`` - lets one skill both damage
        #: a foe and buff its caster without needing two skills.
        self.target_override: str = str(payload.get("target", "")).lower()
        #: Probability the effect fires at all (e.g. 30% chance to poison).
        self.chance: float = float(payload.get("chance", 1.0))

    @abstractmethod
    def apply(self, caster: "Entity", target: "Entity", ctx: EffectContext) -> EffectResult | None:
        """Resolve against one target.  ``None`` means "nothing happened"."""

    @abstractmethod
    def describe(self) -> str:
        """One-line human summary for skill tooltips."""

    def roll_fires(self, ctx: EffectContext) -> bool:
        return self.chance >= 1.0 or ctx.rng.chance(self.chance)

    def _suffix(self) -> str:
        return "" if self.chance >= 1.0 else f" ({self.chance * 100:.0f}% chance)"


#: Discriminator -> class, populated by the decorator below.
_EFFECT_REGISTRY: dict[str, type[Effect]] = {}


def register_effect(type_id: str) -> Callable[[type[Effect]], type[Effect]]:
    """Class decorator registering an effect under its JSON ``type``."""

    def decorator(cls: type[Effect]) -> type[Effect]:
        cls.type_id = type_id
        _EFFECT_REGISTRY[type_id] = cls
        return cls

    return decorator


def known_effect_types() -> tuple[str, ...]:
    """All registered discriminators - used by the content validator."""
    return tuple(sorted(_EFFECT_REGISTRY))


def build_effect(payload: Mapping[str, Any]) -> Effect:
    """Instantiate one effect from its JSON payload."""
    type_id = str(payload.get("type", "")).lower()
    cls = _EFFECT_REGISTRY.get(type_id)
    if cls is None:
        raise ValueError(f"unknown effect type {type_id!r}; known: {', '.join(known_effect_types())}")
    return cls(payload)


def build_effects(payloads: Any) -> list[Effect]:
    """Instantiate a whole ``effects`` array."""
    if not payloads:
        return []
    return [build_effect(item) for item in payloads]


def _scaling_amount(
    caster: "Entity",
    ctx: EffectContext,
    base: float,
    scaling: Mapping[str, float] | None,
    default_stat_value: float,
    default_ratio: float,
) -> float:
    """Shared ``base + ratio * stat`` maths for damage/heal/shield.

    If the JSON gives an explicit ``scaling`` map it is used verbatim (keys may
    be primary stats or derived stats).  Otherwise the effect falls back to its
    natural stat - physical power for a physical hit, magic power for a spell.
    """
    total = float(base)
    if scaling:
        derived = caster.derived_stats()
        primaries = caster.effective_primaries()
        for key, ratio in scaling.items():
            upper = key.upper()
            if upper in PRIMARY_STATS:
                total += float(ratio) * float(primaries.get(upper, 0.0))
            else:
                total += float(ratio) * float(getattr(derived, key, 0.0))
    elif default_ratio:
        total += default_ratio * default_stat_value
    return max(0.0, total)


# ----------------------------------------------------------------------
# 1. Damage
# ----------------------------------------------------------------------
@register_effect("damage")
class DamageEffect(Effect):
    """Deal damage, running the full hit -> crit -> mitigate -> shield chain.

    Bible section 12 lists physical/magic/true damage, crits, armour, magic
    resist, penetration, accuracy, evasion, shields and reflect.  All of that
    resolves here, in one place, so a rule change touches one file.
    """

    def __init__(self, payload: Mapping[str, Any] | None = None) -> None:
        super().__init__(payload)
        payload = payload or {}
        self.damage_type: str = str(payload.get("damage_type", "physical")).lower()
        if self.damage_type not in DAMAGE_TYPES:
            raise ValueError(f"unknown damage_type {self.damage_type!r}")
        self.base: float = float(payload.get("base", 0.0))
        self.scaling: dict[str, float] = {k: float(v) for k, v in (payload.get("scaling") or {}).items()}
        #: Multiplier on the *final* number - the usual "120% weapon damage" dial.
        self.multiplier: float = float(payload.get("multiplier", 1.0))
        self.penetration_pct: float = float(payload.get("penetration_pct", 0.0))
        self.penetration_flat: float = float(payload.get("penetration_flat", 0.0))
        self.hits: int = max(1, int(payload.get("hits", 1)))
        self.can_crit: bool = bool(payload.get("can_crit", True))
        self.can_miss: bool = bool(payload.get("can_miss", True))
        #: Extra accuracy for this specific strike.
        self.accuracy_bonus: float = float(payload.get("accuracy_bonus", 0.0))
        self.ignores_shield: bool = bool(payload.get("ignores_shield", False))
        self.default_ratio: float = float(payload.get("power_ratio", 1.0))

    def apply(self, caster: "Entity", target: "Entity", ctx: EffectContext) -> EffectResult | None:
        if not target.is_alive:
            return None
        if not self.roll_fires(ctx):
            return None

        caster_stats = caster.derived_stats()
        target_stats = target.derived_stats()

        # --- accuracy ---------------------------------------------------
        if self.can_miss:
            chance = ctx.formulas.hit_chance(caster_stats.accuracy + self.accuracy_bonus, target_stats.evasion)
            if not ctx.rng.chance(chance):
                return EffectResult(
                    target_name=target.name,
                    kind="miss",
                    missed=True,
                    message=f"{caster.name}'s attack misses {target.name}.",
                )

        total_dealt = 0.0
        total_absorbed = 0.0
        total_reflected = 0.0
        any_crit = False

        for _ in range(self.hits):
            raw = _scaling_amount(
                caster,
                ctx,
                self.base,
                self.scaling,
                caster_stats.scaling_for(self.damage_type),
                self.default_ratio,
            ) * self.multiplier

            is_crit = self.can_crit and ctx.rng.chance(caster_stats.crit_chance)
            if is_crit:
                raw *= caster_stats.crit_damage
                any_crit = True

            mitigated = ctx.formulas.apply_mitigation(
                raw,
                target_stats.defence_for(self.damage_type),
                self.penetration_pct,
                self.penetration_flat,
            )

            outcome = target.take_raw_damage(
                mitigated,
                damage_type=self.damage_type,
                ignore_shield=self.ignores_shield,
                attacker=caster,
            )
            total_dealt += outcome.damage
            total_absorbed += outcome.absorbed
            total_reflected += outcome.reflected
            if not target.is_alive:
                break

        # Reflect is resolved by the *target*, but the damage lands on the
        # caster, so it is applied here rather than inside take_raw_damage to
        # avoid a re-entrant loop between two reflecting entities.
        if total_reflected > 0:
            caster.take_raw_damage(total_reflected, damage_type="true", ignore_shield=True, allow_reflect=False)

        hit_note = f" x{self.hits}" if self.hits > 1 else ""
        crit_note = " Critical hit!" if any_crit else ""
        parts = [f"{caster.name} hits {target.name} for {total_dealt:.0f} {self.damage_type} damage{hit_note}.{crit_note}"]
        if total_absorbed > 0:
            parts.append(f"({total_absorbed:.0f} absorbed)")
        if total_reflected > 0:
            parts.append(f"({total_reflected:.0f} reflected)")

        return EffectResult(
            target_name=target.name,
            kind="damage",
            amount=total_dealt,
            crit=any_crit,
            absorbed=total_absorbed,
            reflected=total_reflected,
            message=" ".join(parts),
            lethal=not target.is_alive,
        )

    def describe(self) -> str:
        bits = [f"{self.base:.0f}" if self.base else ""]
        if self.scaling:
            bits.extend(f"{ratio:g}x{key.upper()}" for key, ratio in self.scaling.items())
        elif self.default_ratio:
            stat = "MAG" if self.damage_type == "magic" else "ATK"
            bits.append(f"{self.default_ratio:g}x{stat}")
        formula = " + ".join(part for part in bits if part) or "0"
        text = f"Deals {formula} {self.damage_type} damage"
        if self.hits > 1:
            text += f" ({self.hits} hits)"
        if self.penetration_pct:
            text += f", {self.penetration_pct * 100:.0f}% penetration"
        return text + self._suffix()


# ----------------------------------------------------------------------
# 2. Heal
# ----------------------------------------------------------------------
@register_effect("heal")
class HealEffect(Effect):
    """Restore HP, flat and/or as a percentage of the target's maximum."""

    def __init__(self, payload: Mapping[str, Any] | None = None) -> None:
        super().__init__(payload)
        payload = payload or {}
        self.base: float = float(payload.get("base", 0.0))
        self.scaling: dict[str, float] = {k: float(v) for k, v in (payload.get("scaling") or {}).items()}
        self.percent_max_hp: float = float(payload.get("percent_max_hp", 0.0))
        self.default_ratio: float = float(payload.get("power_ratio", 0.0))
        if not self.target_override:
            self.target_override = "self"

    def apply(self, caster: "Entity", target: "Entity", ctx: EffectContext) -> EffectResult | None:
        if not target.is_alive or not self.roll_fires(ctx):
            return None
        amount = _scaling_amount(
            caster,
            ctx,
            self.base,
            self.scaling,
            caster.derived_stats().magic_power,
            self.default_ratio,
        )
        if self.percent_max_hp:
            amount += target.max_hp * self.percent_max_hp
        healed = target.heal(amount)
        if healed <= 0:
            return EffectResult(
                target_name=target.name,
                kind="heal",
                amount=0.0,
                message=f"{target.name} is already at full health.",
            )
        return EffectResult(
            target_name=target.name,
            kind="heal",
            amount=healed,
            message=f"{target.name} recovers {healed:.0f} HP.",
        )

    def describe(self) -> str:
        bits = []
        if self.base:
            bits.append(f"{self.base:.0f}")
        for key, ratio in self.scaling.items():
            bits.append(f"{ratio:g}x{key.upper()}")
        if self.percent_max_hp:
            bits.append(f"{self.percent_max_hp * 100:.0f}% max HP")
        return f"Restores {' + '.join(bits) or '0'} HP" + self._suffix()


# ----------------------------------------------------------------------
# 3. Resource (MP)
# ----------------------------------------------------------------------
@register_effect("resource")
class ResourceEffect(Effect):
    """Restore or drain MP.  Negative ``amount`` drains."""

    def __init__(self, payload: Mapping[str, Any] | None = None) -> None:
        super().__init__(payload)
        payload = payload or {}
        self.amount: float = float(payload.get("amount", 0.0))
        self.percent_max_mp: float = float(payload.get("percent_max_mp", 0.0))
        if not self.target_override:
            self.target_override = "self"

    def apply(self, caster: "Entity", target: "Entity", ctx: EffectContext) -> EffectResult | None:
        if not target.is_alive or not self.roll_fires(ctx):
            return None
        amount = self.amount + target.max_mp * self.percent_max_mp
        changed = target.change_mp(amount)
        if not changed:
            return None
        if changed > 0:
            message = f"{target.name} recovers {changed:.0f} MP."
        else:
            message = f"{target.name} loses {abs(changed):.0f} MP."
        return EffectResult(target_name=target.name, kind="resource", amount=changed, message=message)

    def describe(self) -> str:
        bits = []
        if self.amount:
            bits.append(f"{abs(self.amount):.0f}")
        if self.percent_max_mp:
            bits.append(f"{abs(self.percent_max_mp) * 100:.0f}% max MP")
        verb = "Restores" if (self.amount + self.percent_max_mp) >= 0 else "Drains"
        return f"{verb} {' + '.join(bits) or '0'} MP" + self._suffix()


# ----------------------------------------------------------------------
# 4. Shield
# ----------------------------------------------------------------------
@register_effect("shield")
class ShieldEffect(Effect):
    """Attach a damage-absorbing pool as a ``shield`` status."""

    def __init__(self, payload: Mapping[str, Any] | None = None) -> None:
        super().__init__(payload)
        payload = payload or {}
        self.base: float = float(payload.get("base", 0.0))
        self.scaling: dict[str, float] = {k: float(v) for k, v in (payload.get("scaling") or {}).items()}
        self.percent_max_hp: float = float(payload.get("percent_max_hp", 0.0))
        self.duration: int = max(1, int(payload.get("duration", 3)))
        self.reflect_pct: float = float(payload.get("reflect_pct", 0.0))
        self.name: str = str(payload.get("name", "Shield"))
        self.default_ratio: float = float(payload.get("power_ratio", 0.0))
        if not self.target_override:
            self.target_override = "self"

    def apply(self, caster: "Entity", target: "Entity", ctx: EffectContext) -> EffectResult | None:
        if not target.is_alive or not self.roll_fires(ctx):
            return None
        from engine.skills.status import StatusEffect as _Status  # local: avoids cycle

        amount = _scaling_amount(
            caster,
            ctx,
            self.base,
            self.scaling,
            caster.derived_stats().magic_power,
            self.default_ratio,
        )
        if self.percent_max_hp:
            amount += target.max_hp * self.percent_max_hp
        if amount <= 0 and not self.reflect_pct:
            return None

        status = _Status(
            id=f"shield_{self.name.lower().replace(' ', '_')}",
            name=self.name,
            duration=self.duration,
            category="shield",
            shield_hp=amount,
            reflect_pct=self.reflect_pct,
            source_name=caster.name,
        )
        target.apply_status(status)
        note = f" and reflects {self.reflect_pct * 100:.0f}% damage" if self.reflect_pct else ""
        return EffectResult(
            target_name=target.name,
            kind="shield",
            amount=amount,
            status_name=self.name,
            message=f"{target.name} gains a {amount:.0f} HP shield{note}.",
        )

    def describe(self) -> str:
        bits = []
        if self.base:
            bits.append(f"{self.base:.0f}")
        for key, ratio in self.scaling.items():
            bits.append(f"{ratio:g}x{key.upper()}")
        if self.percent_max_hp:
            bits.append(f"{self.percent_max_hp * 100:.0f}% max HP")
        text = f"Grants a {' + '.join(bits) or '0'} HP shield for {self.duration} turns"
        if self.reflect_pct:
            text += f", reflecting {self.reflect_pct * 100:.0f}% of damage taken"
        return text + self._suffix()


# ----------------------------------------------------------------------
# 5. Apply status
# ----------------------------------------------------------------------
@register_effect("apply_status")
class ApplyStatusEffect(Effect):
    """Attach any status from ``data/statuses.json`` to the target.

    This one effect covers every buff, debuff, DOT, HOT and stun in the game -
    the behaviour lives in :class:`~engine.skills.status.StatusEffect`, and the
    specific numbers live in JSON.
    """

    def __init__(self, payload: Mapping[str, Any] | None = None) -> None:
        super().__init__(payload)
        payload = payload or {}
        self.status_id: str = str(payload.get("status_id", payload.get("status", "")))
        if not self.status_id:
            raise ValueError("apply_status effect requires a 'status_id'")
        #: Optional overrides so one status template can be reused at
        #: different strengths without duplicating the JSON entry.
        self.duration_override: int | None = (
            int(payload["duration"]) if payload.get("duration") is not None else None
        )
        self.stacks: int = max(1, int(payload.get("stacks", 1)))
        #: Debuffs can be resisted; buffs on allies should not be.
        self.resistible: bool = bool(payload.get("resistible", True))

    def apply(self, caster: "Entity", target: "Entity", ctx: EffectContext) -> EffectResult | None:
        if not target.is_alive or not self.roll_fires(ctx):
            return None
        if ctx.status_factory is None:
            return None
        template = ctx.status_factory(self.status_id)
        if template is None:
            return None

        status = template.clone()
        if self.duration_override is not None:
            status.duration = self.duration_override
        status.stacks = min(self.stacks, max(1, status.max_stacks))
        status.source_name = caster.name

        if status.is_debuff and self.resistible and target is not caster:
            resist = target.status_resistance()
            if resist > 0 and ctx.rng.chance(resist):
                return EffectResult(
                    target_name=target.name,
                    kind="resist",
                    status_name=status.name,
                    message=f"{target.name} resists {status.name}.",
                )

        target.apply_status(status)
        return EffectResult(
            target_name=target.name,
            kind="status",
            status_name=status.name,
            message=f"{target.name} is afflicted by {status.name}."
            if status.is_debuff
            else f"{target.name} gains {status.name}.",
        )

    def describe(self) -> str:
        text = f"Applies {self.status_id.replace('_', ' ').title()}"
        if self.duration_override:
            text += f" for {self.duration_override} turns"
        return text + self._suffix()
