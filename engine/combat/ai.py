"""AI behaviours - the registry ENGINE_DESIGN.md said should exist.

That document notes ``ai_behavior_id`` was stored on Enemy with no registry
behind it yet, and that *"the same composition pattern should apply when it's
built"*.  This is that registry: behaviours are instances of one class
configured by data, selected by id, never a subclass per monster.

A behaviour is a small decision function over (actor, allies, enemies) that
returns an :class:`AIDecision`.  It never mutates anything - CombatManager
executes the decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

__all__ = ["AIDecision", "AIBehavior", "AIRegistry", "default_registry"]


@dataclass
class AIDecision:
    """What an AI-controlled entity intends to do this turn."""

    skill: Any = None
    targets: list[Any] = field(default_factory=list)
    #: Set when the actor can do nothing useful (stunned, no valid target).
    pass_turn: bool = False
    note: str = ""


def _living(entities: Sequence[Any]) -> list[Any]:
    return [e for e in entities if e.is_alive]


def _lowest_hp(entities: Sequence[Any]) -> Any | None:
    candidates = _living(entities)
    return min(candidates, key=lambda e: e.current_hp) if candidates else None


def _lowest_hp_fraction(entities: Sequence[Any]) -> Any | None:
    candidates = _living(entities)
    return min(candidates, key=lambda e: e.hp_fraction) if candidates else None


def _highest_threat(entities: Sequence[Any]) -> Any | None:
    """Target whoever hits hardest - used by 'tactical' enemies."""
    candidates = _living(entities)
    if not candidates:
        return None
    return max(candidates, key=lambda e: e.derived_stats().physical_power + e.derived_stats().magic_power)


class AIBehavior:
    """One named decision strategy.

    ``chooser`` receives ``(actor, allies, foes, rng)`` and returns an
    :class:`AIDecision`.  New behaviours are added by registering another
    function, not by subclassing.
    """

    def __init__(
        self,
        behavior_id: str,
        description: str,
        chooser: Callable[[Any, Sequence[Any], Sequence[Any], Any], AIDecision],
    ) -> None:
        self.id = behavior_id
        self.description = description
        self._chooser = chooser

    def decide(self, actor: Any, allies: Sequence[Any], foes: Sequence[Any], rng: Any) -> AIDecision:
        if not actor.is_alive:
            return AIDecision(pass_turn=True, note="dead")
        if actor.is_stunned:
            return AIDecision(pass_turn=True, note="stunned")
        if not _living(foes):
            return AIDecision(pass_turn=True, note="no targets")
        return self._chooser(actor, allies, foes, rng)


# ----------------------------------------------------------------------
# Shipped behaviours
# ----------------------------------------------------------------------
def _pick_attack_skill(actor: Any, rng: Any) -> Any:
    """Prefer a real skill when affordable, else fall back to basic attack."""
    usable = [s for s in actor.usable_skills() if s.mp_cost <= actor.current_mp]
    offensive = [s for s in usable if any(getattr(e, "type_id", "") == "damage" for e in s.effects)]
    if offensive:
        return rng.choice(offensive)
    return usable[0] if usable else None


def _aggressive(actor: Any, allies: Sequence[Any], foes: Sequence[Any], rng: Any) -> AIDecision:
    """Straight ahead: strongest available attack on a random living foe."""
    skill = _pick_attack_skill(actor, rng)
    if skill is None:
        return AIDecision(pass_turn=True, note="no usable skill")
    target = rng.choice(_living(foes))
    return AIDecision(skill=skill, targets=[target], note="aggressive")


def _opportunist(actor: Any, allies: Sequence[Any], foes: Sequence[Any], rng: Any) -> AIDecision:
    """Finishes wounded targets - goes for the lowest absolute HP."""
    skill = _pick_attack_skill(actor, rng)
    if skill is None:
        return AIDecision(pass_turn=True, note="no usable skill")
    target = _lowest_hp(foes)
    return AIDecision(skill=skill, targets=[target] if target else [], note="opportunist")


def _tactical(actor: Any, allies: Sequence[Any], foes: Sequence[Any], rng: Any) -> AIDecision:
    """Heals badly-hurt allies, otherwise attacks the biggest threat."""
    usable = [s for s in actor.usable_skills() if s.mp_cost <= actor.current_mp]

    healing = [s for s in usable if any(getattr(e, "type_id", "") == "heal" for e in s.effects)]
    if healing:
        wounded = _lowest_hp_fraction(allies)
        if wounded is not None and wounded.hp_fraction < 0.5:
            return AIDecision(skill=rng.choice(healing), targets=[wounded], note="tactical heal")

    support = [
        s
        for s in usable
        if any(getattr(e, "type_id", "") in ("shield", "apply_status") for e in s.effects)
        and not any(getattr(e, "type_id", "") == "damage" for e in s.effects)
    ]
    # Only sometimes - an enemy that buffs every single turn never threatens.
    if support and rng.chance(0.35):
        return AIDecision(skill=rng.choice(support), targets=[actor], note="tactical support")

    skill = _pick_attack_skill(actor, rng)
    if skill is None:
        return AIDecision(pass_turn=True, note="no usable skill")
    target = _highest_threat(foes)
    return AIDecision(skill=skill, targets=[target] if target else [], note="tactical attack")


def _defensive(actor: Any, allies: Sequence[Any], foes: Sequence[Any], rng: Any) -> AIDecision:
    """Shields up when hurt, then attacks whoever is weakest."""
    usable = [s for s in actor.usable_skills() if s.mp_cost <= actor.current_mp]
    if actor.hp_fraction < 0.4:
        defensive = [
            s for s in usable if any(getattr(e, "type_id", "") in ("shield", "heal") for e in s.effects)
        ]
        if defensive:
            return AIDecision(skill=rng.choice(defensive), targets=[actor], note="defensive")
    skill = _pick_attack_skill(actor, rng)
    if skill is None:
        return AIDecision(pass_turn=True, note="no usable skill")
    target = _lowest_hp(foes)
    return AIDecision(skill=skill, targets=[target] if target else [], note="defensive attack")


def _berserk(actor: Any, allies: Sequence[Any], foes: Sequence[Any], rng: Any) -> AIDecision:
    """Always the most expensive attack it can pay for - no self-preservation."""
    usable = [s for s in actor.usable_skills() if s.mp_cost <= actor.current_mp]
    offensive = [s for s in usable if any(getattr(e, "type_id", "") == "damage" for e in s.effects)]
    if not offensive:
        return AIDecision(pass_turn=True, note="no usable skill")
    skill = max(offensive, key=lambda s: s.mp_cost)
    return AIDecision(skill=skill, targets=[rng.choice(_living(foes))], note="berserk")


class AIRegistry:
    """Maps ``ai_behavior_id`` from JSON to a behaviour instance."""

    def __init__(self) -> None:
        self._behaviors: dict[str, AIBehavior] = {}

    def register(self, behavior: AIBehavior) -> None:
        self._behaviors[behavior.id] = behavior

    def get(self, behavior_id: str) -> AIBehavior:
        """Never fails - an unknown id falls back to ``aggressive``.

        A typo in one monster's JSON should not crash a battle; it should make
        that monster behave plainly.
        """
        return self._behaviors.get(behavior_id) or self._behaviors["aggressive"]

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._behaviors))


def default_registry() -> AIRegistry:
    """The registry the engine uses unless a test injects its own."""
    registry = AIRegistry()
    registry.register(AIBehavior("aggressive", "Attacks a random foe with its best skill.", _aggressive))
    registry.register(AIBehavior("opportunist", "Targets the most wounded foe.", _opportunist))
    registry.register(AIBehavior("tactical", "Heals allies and focuses dangerous foes.", _tactical))
    registry.register(AIBehavior("defensive", "Protects itself when badly hurt.", _defensive))
    registry.register(AIBehavior("berserk", "Uses its costliest attack every turn.", _berserk))
    return registry
