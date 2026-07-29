"""World, areas and exploration - roadmap v0.0.7/v0.0.8.

Bible section 8 game loop:
``Town -> Explore -> Combat -> Rewards -> Town -> Sleep -> Morning Autosave``

Areas, encounter tables, shops and NPCs all come from ``data/world.json``; this
module holds only the rules that operate on them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

__all__ = ["Area", "EncounterEntry", "NPC", "Shop", "WorldState", "ExploreResult"]


@dataclass
class EncounterEntry:
    """One possible spawn in an area's encounter table."""

    enemy_ids: list[str]
    weight: float = 1.0
    level_min: int = 1
    level_max: int = 1
    is_boss: bool = False
    boss_id: str = ""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EncounterEntry":
        raw = payload.get("enemy_ids") or payload.get("enemies") or []
        if isinstance(raw, str):
            raw = [raw]
        low = int(payload.get("level_min", 1))
        enemy_ids = [str(e) for e in raw]
        is_boss = bool(payload.get("is_boss", False))
        return cls(
            enemy_ids=enemy_ids,
            weight=float(payload.get("weight", 1.0)),
            level_min=low,
            level_max=max(low, int(payload.get("level_max", low))),
            is_boss=is_boss,
            boss_id=str(payload.get("boss_id", "")),
        )


@dataclass
class NPC:
    """A townsperson: dialogue, affinity, and possibly marriage."""

    id: str
    name: str
    description: str = ""
    race_id: str = ""
    gender: str = ""
    dialogue: list[str] = field(default_factory=list)
    #: Affinity needed before marriage is offered (bible section 15).
    marriage_affinity: int = 80
    gift_item_ids: list[str] = field(default_factory=list)
    location_id: str = ""
    marriageable: bool = False

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "NPC":
        return cls(
            id=str(payload.get("id", "npc")),
            name=str(payload.get("name", "Stranger")),
            description=str(payload.get("description", "")),
            race_id=str(payload.get("race_id", "")),
            gender=str(payload.get("gender", "")).lower(),
            dialogue=[str(line) for line in payload.get("dialogue", [])],
            marriage_affinity=int(payload.get("marriage_affinity", 80)),
            gift_item_ids=[str(i) for i in payload.get("gift_item_ids", [])],
            location_id=str(payload.get("location_id", "")),
            marriageable=bool(payload.get("marriageable", False)),
        )


@dataclass
class Shop:
    """A vendor's stock list."""

    id: str
    name: str
    item_ids: list[str] = field(default_factory=list)
    buy_rate: float = 1.0
    sell_rate: float = 0.4
    faction_id: str = ""
    race_item_ids: dict[str, list[str]] = field(default_factory=dict)
    race_buy_rates: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Shop":
        return cls(
            id=str(payload.get("id", "shop")),
            name=str(payload.get("name", "Shop")),
            item_ids=[str(i) for i in payload.get("item_ids", [])],
            buy_rate=float(payload.get("buy_rate", 1.0)),
            sell_rate=float(payload.get("sell_rate", 0.4)),
            faction_id=str(payload.get("faction_id", "")),
            race_item_ids={str(k): [str(v) for v in values] for k, values in (payload.get("race_item_ids") or {}).items()},
            race_buy_rates={str(k): float(v) for k, v in (payload.get("race_buy_rates") or {}).items()},
        )


@dataclass
class Area:
    """One place on the map."""

    id: str
    name: str
    description: str = ""
    #: Safe areas have no encounters - towns, the inn.
    is_town: bool = False
    recommended_level: int = 1
    encounters: list[EncounterEntry] = field(default_factory=list)
    connections: list[str] = field(default_factory=list)
    shop_ids: list[str] = field(default_factory=list)
    npc_ids: list[str] = field(default_factory=list)
    #: Chance an exploration step finds nothing but flavour.
    quiet_chance: float = 0.25
    unlock_level: int = 1

    @property
    def is_safe(self) -> bool:
        return self.is_town or not self.encounters

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Area":
        return cls(
            id=str(payload.get("id", "area")),
            name=str(payload.get("name", "Unknown")),
            description=str(payload.get("description", "")),
            is_town=bool(payload.get("is_town", False)),
            recommended_level=int(payload.get("recommended_level", 1)),
            encounters=[EncounterEntry.from_dict(e) for e in payload.get("encounters", [])],
            connections=[str(c) for c in payload.get("connections", [])],
            shop_ids=[str(s) for s in payload.get("shop_ids", [])],
            npc_ids=[str(n) for n in payload.get("npc_ids", [])],
            quiet_chance=float(payload.get("quiet_chance", 0.25)),
            unlock_level=int(payload.get("unlock_level", 1)),
        )

    def detail_lines(self) -> list[str]:
        lines = [f"Area: {self.name}"]
        if self.description:
            lines.append(self.description)
        lines.append(f"Recommended level: {self.recommended_level}")
        lines.append("Type: " + ("Town (safe)" if self.is_town else "Wilderness"))
        return lines


@dataclass
class ExploreResult:
    """Outcome of one exploration step."""

    #: ``"encounter"``, ``"quiet"``, ``"blocked"``.
    kind: str
    message: str = ""
    #: ``(enemy_id, level)`` pairs for the caller to spawn.
    spawns: list[tuple[str, int]] = field(default_factory=list)

    @property
    def is_encounter(self) -> bool:
        return self.kind == "encounter"


class WorldState:
    """Where the player is, what day it is, and what the map contains."""

    def __init__(
        self,
        areas: Mapping[str, Area],
        npcs: Mapping[str, NPC] | None = None,
        shops: Mapping[str, Shop] | None = None,
        start_area_id: str = "",
        flavour: Sequence[str] = (),
    ) -> None:
        self.areas: dict[str, Area] = dict(areas)
        self.npcs: dict[str, NPC] = dict(npcs or {})
        self.shops: dict[str, Shop] = dict(shops or {})
        self.flavour: list[str] = list(flavour) or ["The path is quiet."]

        self.day: int = 1
        self.current_area_id: str = start_area_id or next(iter(self.areas), "")
        #: Areas the player has set foot in - used for the travel list.
        self.visited: set[str] = {self.current_area_id} if self.current_area_id else set()
        self.steps_today: int = 0
        #: One-time bosses already defeated in this save. Their encounter-table
        #: entries are filtered out while ordinary encounters remain repeatable.
        self.defeated_bosses: set[str] = set()

    # ------------------------------------------------------------------
    @property
    def current_area(self) -> Area | None:
        return self.areas.get(self.current_area_id)

    def area_name(self) -> str:
        area = self.current_area
        return area.name if area else "Nowhere"

    def is_in_town(self) -> bool:
        area = self.current_area
        return bool(area and area.is_town)

    def connected_areas(self, player_level: int = 1) -> list[Area]:
        """Neighbouring areas, hiding ones the player is too low-level for."""
        area = self.current_area
        if area is None:
            return []
        return [
            self.areas[area_id]
            for area_id in area.connections
            if area_id in self.areas and self.areas[area_id].unlock_level <= player_level
        ]

    def travel_to(self, area_id: str, player_level: int = 1) -> tuple[bool, str]:
        """Move to a connected area."""
        area = self.current_area
        if area is None:
            return False, "You are nowhere."
        if area_id == self.current_area_id:
            return False, f"You are already in {area.name}."
        if area_id not in area.connections:
            return False, "You cannot reach that place from here."
        destination = self.areas.get(area_id)
        if destination is None:
            return False, "That place does not exist."
        if destination.unlock_level > player_level:
            return False, f"{destination.name} requires level {destination.unlock_level}."

        self.current_area_id = area_id
        self.visited.add(area_id)
        return True, f"You travel to {destination.name}."

    # ------------------------------------------------------------------
    def explore(self, rng: Any, player_level: int) -> ExploreResult:
        """Take one step in the current area.

        Encounter levels are rolled inside the area's band and never scale to
        the player, so out-levelling an area genuinely makes it easy.
        """
        area = self.current_area
        if area is None:
            return ExploreResult(kind="blocked", message="There is nowhere to explore.")
        if area.is_safe:
            return ExploreResult(
                kind="blocked",
                message=f"{area.name} is peaceful. Travel somewhere wilder to find trouble.",
            )

        self.steps_today += 1

        if rng.chance(area.quiet_chance):
            return ExploreResult(kind="quiet", message=rng.choice(self.flavour))

        encounters = [
            entry
            for entry in area.encounters
            if not (entry.is_boss and entry.boss_id in self.defeated_bosses)
        ]
        if not encounters:
            return ExploreResult(kind="quiet", message=rng.choice(self.flavour))

        entry = rng.weighted_choice([(e, e.weight) for e in encounters])
        spawns = [(enemy_id, rng.randint(entry.level_min, entry.level_max)) for enemy_id in entry.enemy_ids]
        names = ", ".join(enemy_id.replace("_", " ").title() for enemy_id in entry.enemy_ids)
        return ExploreResult(kind="encounter", message=f"Ambushed by {names}!", spawns=spawns)

    # ------------------------------------------------------------------
    def advance_day(self) -> int:
        """Sleep: next day (bible section 8)."""
        self.day += 1
        self.steps_today = 0
        return self.day

    def npcs_here(self) -> list[NPC]:
        area = self.current_area
        if area is None:
            return []
        return [self.npcs[npc_id] for npc_id in area.npc_ids if npc_id in self.npcs]

    def shops_here(self) -> list[Shop]:
        area = self.current_area
        if area is None:
            return []
        return [self.shops[shop_id] for shop_id in area.shop_ids if shop_id in self.shops]

    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "current_area_id": self.current_area_id,
            "visited": sorted(self.visited),
            "steps_today": self.steps_today,
            "defeated_bosses": sorted(self.defeated_bosses),
        }

    def load_dict(self, payload: Mapping[str, Any] | None) -> None:
        if not payload:
            return
        self.day = int(payload.get("day", 1))
        area_id = str(payload.get("current_area_id", self.current_area_id))
        # Guard against a save pointing at an area that content removed.
        self.current_area_id = area_id if area_id in self.areas else self.current_area_id
        self.visited = set(payload.get("visited", [])) | {self.current_area_id}
        self.steps_today = int(payload.get("steps_today", 0))
        self.defeated_bosses = {str(boss_id) for boss_id in payload.get("defeated_bosses", [])}
