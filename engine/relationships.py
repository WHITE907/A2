"""Affinity and marriage - bible section 15.

*"Affinity with NPCs. Marriage possible regardless of gender using a special
item."*

Companions are romanceable on the same terms as townspeople, so the rules live
here once rather than being duplicated per entity type.  Both
:class:`~engine.world.world.NPC` and
:class:`~engine.entities.companion.CompanionDefinition` expose the same handful
of fields (``id``, ``name``, ``marriageable``, ``marriage_affinity``,
``gift_item_ids``), and this module is written against that shape - structural
typing, not a shared base class, because the two are otherwise unrelated: one
is scenery, the other is a combatant.

Affinity is stored on the Player keyed by id, which means a companion's
standing survives dismissal and re-recruitment.

Gender is never consulted anywhere in this module.  That is the bible's rule,
and the cleanest way to honour it is to have nothing to remove.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

__all__ = [
    "AFFINITY_MIN",
    "AFFINITY_MAX",
    "Suitor",
    "AffinityTier",
    "RelationshipRules",
    "MarriageCheck",
]

#: Affinity is clamped to this range for everyone.
AFFINITY_MIN = -100
AFFINITY_MAX = 100


@runtime_checkable
class Suitor(Protocol):
    """Anything the player can build a relationship with."""

    id: str
    name: str
    marriageable: bool
    marriage_affinity: int
    gift_item_ids: list[str]


@dataclass(frozen=True)
class AffinityTier:
    """A named band of affinity, for display."""

    threshold: int
    label: str


#: Descending, so the first match wins.
_DEFAULT_TIERS: tuple[AffinityTier, ...] = (
    AffinityTier(90, "Devoted"),
    AffinityTier(70, "Beloved"),
    AffinityTier(50, "Close"),
    AffinityTier(25, "Friendly"),
    AffinityTier(5, "Warm"),
    AffinityTier(-4, "Neutral"),
    AffinityTier(-40, "Cool"),
    AffinityTier(AFFINITY_MIN, "Hostile"),
)


@dataclass
class MarriageCheck:
    """Why a proposal is or isn't possible - a checklist, not a yes/no.

    Mirrors :class:`~engine.classes.PromotionCheck`: the GUI shows exactly
    what is still missing rather than a bare refusal.
    """

    eligible: bool
    target_id: str = ""
    target_name: str = ""
    met: list[str] = field(default_factory=list)
    unmet: list[str] = field(default_factory=list)
    reason: str = ""

    def summary_lines(self) -> list[str]:
        lines = [f"{'[ok]' if self.eligible else '[--]'} {self.target_name or self.target_id}"]
        lines.extend(f"  met   : {item}" for item in self.met)
        lines.extend(f"  needs : {item}" for item in self.unmet)
        if self.reason and not self.eligible:
            lines.append(f"  {self.reason}")
        return lines


class RelationshipRules:
    """Affinity gains, marriage eligibility, and the spouse bonus.

    Values come from ``data/config.json`` - no number here is hardcoded
    (bible section 5).
    """

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        config = config or {}
        self.per_talk = int(config.get("affinity_per_talk", 2))
        self.gift = int(config.get("affinity_gift", 5))
        self.gift_liked = int(config.get("affinity_gift_liked", 15))
        #: Affinity earned per battle a companion fights alongside the player.
        self.per_battle = int(config.get("affinity_per_battle", 3))
        #: Repeated chatter in one day is worth less - see :meth:`talk_gain`.
        self.talk_falloff_after = int(config.get("affinity_talk_falloff_after", 3))
        self.marriage_item_id = str(config.get("marriage_item_id", ""))
        #: Stat bonus a married companion fights with.
        self.spouse_bonus: dict[str, float] = {
            str(k): float(v) for k, v in (config.get("marriage_spouse_bonus") or {}).items()
        }
        self.tiers = _DEFAULT_TIERS

    # ------------------------------------------------------------------
    def tier_label(self, affinity: int) -> str:
        for tier in self.tiers:
            if affinity >= tier.threshold:
                return tier.label
        return self.tiers[-1].label

    def talk_gain(self, times_talked_today: int) -> int:
        """Affinity from one conversation.

        Falls off after a few chats in the same day so the optimal play isn't
        clicking "Talk" a hundred times in a row.  It never reaches zero -
        checking in daily should always be worth something.
        """
        if times_talked_today < self.talk_falloff_after:
            return self.per_talk
        return max(1, self.per_talk // 2)

    def gift_gain(self, suitor: Suitor, item_id: str) -> tuple[int, bool]:
        """``(affinity, was_a_favourite)`` for gifting ``item_id``."""
        liked = item_id in (suitor.gift_item_ids or [])
        return (self.gift_liked if liked else self.gift, liked)

    @staticmethod
    def clamp(value: int) -> int:
        return max(AFFINITY_MIN, min(AFFINITY_MAX, int(value)))

    # ------------------------------------------------------------------
    def check_marriage(
        self,
        suitor: Suitor,
        *,
        affinity: int,
        has_ring: bool,
        current_spouse_id: str | None,
        ring_name: str = "",
        recruited: bool = True,
    ) -> MarriageCheck:
        """Full eligibility check.  Gender is deliberately never consulted."""
        check = MarriageCheck(eligible=True, target_id=suitor.id, target_name=suitor.name)

        if current_spouse_id:
            if current_spouse_id == suitor.id:
                return MarriageCheck(
                    eligible=False,
                    target_id=suitor.id,
                    target_name=suitor.name,
                    reason=f"You are already married to {suitor.name}.",
                )
            return MarriageCheck(
                eligible=False,
                target_id=suitor.id,
                target_name=suitor.name,
                reason="You are already married.",
            )

        if not suitor.marriageable:
            return MarriageCheck(
                eligible=False,
                target_id=suitor.id,
                target_name=suitor.name,
                reason=f"{suitor.name} is not interested in marriage.",
            )

        # A companion who has left the party cannot be proposed to.
        if not recruited:
            check.unmet.append(f"{suitor.name} must be in your party")

        needed = int(suitor.marriage_affinity)
        (check.met if affinity >= needed else check.unmet).append(
            f"Affinity {needed} (have {affinity})"
        )

        if self.marriage_item_id:
            label = ring_name or self.marriage_item_id.replace("_", " ").title()
            (check.met if has_ring else check.unmet).append(label)

        check.eligible = not check.unmet
        if not check.eligible:
            check.reason = "Requirements not met."
        return check

    # ------------------------------------------------------------------
    def spouse_modifiers(self) -> dict[str, float]:
        """Flat stat bonus a married companion gains.

        Marrying a companion should be felt in play, not just recorded on the
        status screen - otherwise it is a checkbox rather than a system.
        """
        return dict(self.spouse_bonus)
