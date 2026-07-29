"""AI behaviours - the registry ENGINE_DESIGN.md said should exist.

That document notes ``ai_behavior_id`` was stored on Enemy with no registry
behind it yet, and that *\"the same composition pattern should apply when it's
built\"*.  This is that registry: behaviours are instances of one class
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
    # Companion resource preservation
    tactics = getattr(actor, "tactics", {}) or {}
    usable = list(actor.usable_skills())
    # Filter by MP/SP preservation
    if tactics.get("preserve_mp") and hasattr(actor, "mp_fraction") and actor.mp_fraction < 0.4:
        # Keep only low-cost skills
        low = [s for s in usable if getattr(s, "mp_cost", 0) <= 2]
        if low:
            usable = low
    if tactics.get("preserve_sp") and hasattr(actor, "sp_fraction") and actor.sp_fraction < 0.4:
        low = [s for s in usable if getattr(s, "sp_cost", 0) <= 2]
        if low:
            usable = low
    offensive = [s for s in usable if any(getattr(e, "type_id", "") == "damage" for e in s.effects)]
    if offensive:
        # Apply per-skill priorities
        priorities = tactics.get("skill_priorities") or {}
        if priorities:
            def prio_score(s):
                return float(priorities.get(getattr(s, "id", ""), 1.0))
            # Prefer higher priority
            offensive = sorted(offensive, key=lambda s: (-prio_score(s), -getattr(s, "mp_cost", 0)))
            return offensive[0]
        # Racial skill bonus
        if tactics.get("allow_racial_skills", True) and tactics.get("racial_skill_bonus"):
            racial = [s for s in offensive if str(getattr(s, "id", "")).startswith("racial_")]
            if racial and rng.chance(0.6):
                return rng.choice(racial)
        # Boss focus
        if tactics.get("boss_focus"):
            # Prefer highest cost for boss
            offensive = sorted(offensive, key=lambda s: -getattr(s, "mp_cost", 0))
            return offensive[0]
        return rng.choice(offensive)
    return usable[0] if usable else None


def _find_protected_ally(actor: Any, allies: Sequence[Any]) -> Any | None:
    tactics = getattr(actor, "tactics", {}) or {}
    protect_id = str(tactics.get("protect_target", "")).strip()
    if not protect_id:
        return None
    for ally in _living(allies):
        if getattr(ally, "id", "") == protect_id or getattr(ally, "name", "") == protect_id:
            return ally
    return None


def _aggressive(actor: Any, allies: Sequence[Any], foes: Sequence[Any], rng: Any) -> AIDecision:
    """Straight ahead: strongest available attack on a random living foe."""
    tactics = getattr(actor, "tactics", {}) or {}
    # Boss focus override
    if tactics.get("boss_focus"):
        bosses = [f for f in _living(foes) if getattr(f, "is_boss", False)]
        if bosses:
            skill = _pick_attack_skill(actor, rng)
            if skill is None:
                return AIDecision(pass_turn=True, note="no usable skill")
            return AIDecision(skill=skill, targets=[rng.choice(bosses)], note="aggressive boss focus")
    skill = _pick_attack_skill(actor, rng)
    if skill is None:
        return AIDecision(pass_turn=True, note="no usable skill")
    # Preferred target override
    preferred = str(tactics.get("preferred_target", "")).strip()
    if preferred:
        match = next((f for f in _living(foes) if getattr(getattr(f, "template", None), "id", "") == preferred or getattr(f, "id", "") == preferred), None)
        if match:
            return AIDecision(skill=skill, targets=[match], note="aggressive preferred")
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
    """Heals badly-hurt allies, cleanses, revives, otherwise attacks biggest threat.

    Companion tactics expanded:
    - heal_priority, protect_priority, cleanse_priority, revive_priority
    - allow_cleanse, allow_revive, allow_racial_skills
    - boss_focus, racial_skill_bonus, skill_priorities
    - preserve_mp, preserve_sp
    """
    tactics = getattr(actor, "tactics", {}) or {}
    usable = list(actor.usable_skills())

    # ---- Revive ----
    if tactics.get("allow_revive", True):
        revive_priority = float(tactics.get("revive_priority", 1.0))
        if revive_priority > 0 and rng.chance(0.3 + 0.2 * revive_priority):
            revives = [s for s in usable if any(getattr(e, "type_id", "") == "revive" for e in s.effects)]
            if revives:
                downed = [a for a in allies if not a.is_alive]
                if downed:
                    target = rng.choice(downed)
                    skill = max(revives, key=lambda s: float(tactics.get("skill_priorities", {}).get(getattr(s, "id", ""), 1.0)))
                    return AIDecision(skill=skill, targets=[target], note="tactical revive")

    # ---- Cleanse ----
    if tactics.get("allow_cleanse", True):
        cleanse_priority = float(tactics.get("cleanse_priority", 0.7))
        if cleanse_priority > 0:
            cleanses = [s for s in usable if any(getattr(e, "type_id", "") in ("cleanse", "status_transfer") for e in s.effects)]
            if cleanses:
                # Find ally with debuffs
                debuffed = [a for a in _living(allies) if any(st.is_debuff for st in getattr(a, "statuses", []))]
                if debuffed and rng.chance(0.2 + 0.3 * cleanse_priority):
                    target = min(debuffed, key=lambda a: a.hp_fraction)
                    skill = rng.choice(cleanses)
                    return AIDecision(skill=skill, targets=[target], note="tactical cleanse")

    # ---- Healing ----
    healing = [s for s in usable if any(getattr(e, "type_id", "") == "heal" for e in s.effects)]
    if healing:
        protect_target = _find_protected_ally(actor, allies)
        heal_thresh = float(tactics.get("healing_threshold", 0.5))
        heal_prio = float(tactics.get("heal_priority", 1.0))
        # Protection priority: if protect target is hurt, heal them even above threshold
        if protect_target and protect_target.is_alive:
            prot_prio = float(tactics.get("protect_priority", 1.5))
            effective_thresh = min(1.0, heal_thresh * prot_prio)
            if protect_target.hp_fraction < effective_thresh:
                # Apply per-skill priorities
                priorities = tactics.get("skill_priorities") or {}
                if priorities:
                    healing = sorted(healing, key=lambda s: -float(priorities.get(getattr(s, "id", ""), 1.0)))
                skill = healing[0] if healing else rng.choice(healing)
                return AIDecision(skill=skill, targets=[protect_target], note="tactical heal protect")

        wounded = protect_target if protect_target and protect_target.hp_fraction < 1 else _lowest_hp_fraction(allies)
        if wounded is not None and wounded.hp_fraction < heal_thresh * heal_prio:
            # Prioritize strongest heal that is affordable
            priorities = tactics.get("skill_priorities") or {}
            if priorities:
                healing = sorted(healing, key=lambda s: -float(priorities.get(getattr(s, "id", ""), 1.0)))
            skill = healing[0] if healing else rng.choice(healing)
            return AIDecision(skill=skill, targets=[wounded], note="tactical heal")

    # ---- Support (shields, buffs) ----
    support = [
        s
        for s in usable
        if any(getattr(e, "type_id", "") in ("shield", "apply_status") for e in s.effects)
        and not any(getattr(e, "type_id", "") == "damage" for e in s.effects)
    ]
    # Protective shield on protect target
    if support and tactics.get("protect_target"):
        protected = _find_protected_ally(actor, allies)
        if protected and protected.hp_fraction < 0.8:
            # Prefer shield skills
            shields = [s for s in support if any(getattr(e, "type_id", "") == "shield" for e in s.effects)]
            if shields:
                return AIDecision(skill=rng.choice(shields), targets=[protected], note="tactical protect")

    # Occasionally buff
    if support and rng.chance(0.35):
        # Racial skill bonus for support too
        if tactics.get("allow_racial_skills", True) and tactics.get("racial_skill_bonus"):
            racial_support = [s for s in support if str(getattr(s, "id", "")).startswith("racial_")]
            if racial_support and rng.chance(0.5):
                return AIDecision(skill=rng.choice(racial_support), targets=[actor], note="tactical racial support")
        return AIDecision(skill=rng.choice(support), targets=[actor], note="tactical support")

    skill = _pick_attack_skill(actor, rng)
    if skill is None:
        return AIDecision(pass_turn=True, note="no usable skill")

    # Preferred target or boss focus
    preferred = str(tactics.get("preferred_target", "")).strip()
    if preferred:
        match = next((foe for foe in _living(foes) if getattr(getattr(foe, "template", None), "id", "") == preferred or getattr(foe, "id", "") == preferred), None)
        if match:
            return AIDecision(skill=skill, targets=[match], note="tactical preferred")

    if tactics.get("boss_focus"):
        bosses = [f for f in _living(foes) if getattr(f, "is_boss", False)]
        if bosses:
            return AIDecision(skill=skill, targets=[rng.choice(bosses)], note="tactical boss focus")

    target = _highest_threat(foes)
    return AIDecision(skill=skill, targets=[target] if target else [], note="tactical attack")


def _defensive(actor: Any, allies: Sequence[Any], foes: Sequence[Any], rng: Any) -> AIDecision:
    """Shields up when hurt, then attacks whoever is weakest."""
    tactics = getattr(actor, "tactics", {}) or {}
    usable = list(actor.usable_skills())
    if actor.hp_fraction < 0.4:
        defensive = [
            s for s in usable if any(getattr(e, "type_id", "") in ("shield", "heal") for e in s.effects)
        ]
        if defensive:
            # Prefer higher priority
            priorities = tactics.get("skill_priorities") or {}
            if priorities:
                defensive = sorted(defensive, key=lambda s: -float(priorities.get(getattr(s, "id", ""), 1.0)))
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
    # Per-skill priorities still apply even in berserk
    tactics = getattr(actor, "tactics", {}) or {}
    priorities = tactics.get("skill_priorities") or {}
    if priorities:
        offensive = sorted(offensive, key=lambda s: (-float(priorities.get(getattr(s, "id", ""), 1.0)), -getattr(s, "mp_cost", 0)))
        skill = offensive[0]
    else:
        skill = max(offensive, key=lambda s: getattr(s, "mp_cost", 0))
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
