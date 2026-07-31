"""``WorldManager`` - factory for the world map from ``data/world.json``."""

from __future__ import annotations

from typing import Any

from engine.managers.data_loader import ContentError, DataLoader
from engine.world.world import NPC, Area, Shop, WorldState

__all__ = ["WorldManager"]


class WorldManager:
    """Loads areas, NPCs and shops, and builds :class:`WorldState`."""

    WORLD_FILE = "world.json"

    def __init__(self, loader: DataLoader) -> None:
        self._loader = loader
        self._areas: dict[str, Area] = {}
        self._npcs: dict[str, NPC] = {}
        self._shops: dict[str, Shop] = {}
        self._flavour: list[str] = []
        self._start_area_id: str = ""
        self._loaded = False

    # ------------------------------------------------------------------
    def load(self) -> None:
        if self._loaded:
            return
        payload = self._loader.load_mapping(self.WORLD_FILE, required=True)

        for entry in payload.get("areas", []):
            try:
                area = Area.from_dict(entry)
            except ValueError as exc:
                raise ContentError(f"{self.WORLD_FILE}: {exc}") from exc
            if area.id in self._areas:
                raise ContentError(f"duplicate area id {area.id!r} in {self.WORLD_FILE}")
            self._areas[area.id] = area
        if not self._areas:
            raise ContentError(f"{self.WORLD_FILE} defines no areas")

        for entry in payload.get("npcs", []):
            npc = NPC.from_dict(entry)
            self._npcs[npc.id] = npc
        for entry in payload.get("shops", []):
            shop = Shop.from_dict(entry)
            self._shops[shop.id] = shop

        self._flavour = [str(line) for line in payload.get("flavour", [])]
        self._start_area_id = str(payload.get("start_area_id", next(iter(self._areas))))
        if self._start_area_id not in self._areas:
            raise ContentError(f"{self.WORLD_FILE}: start_area_id {self._start_area_id!r} is not a known area")

        self._validate_connections()
        self._loaded = True

    def _validate_connections(self) -> None:
        """Reject one-way links caused by a missing reciprocal entry.

        A connection that points at a nonexistent area would silently vanish
        from the travel list, which reads as a bug in the GUI rather than a
        typo in content.
        """
        action_ids: set[str] = set()
        for area in self._areas.values():
            for action in area.ancestry_actions:
                if action.id in action_ids:
                    raise ContentError(f"duplicate ancestry action id {action.id!r} in {self.WORLD_FILE}")
                action_ids.add(action.id)
            for target in area.connections:
                if target not in self._areas:
                    raise ContentError(f"area {area.id!r} connects to unknown area {target!r}")
                if area.id not in self._areas[target].connections:
                    raise ContentError(
                        f"area connection {area.id!r} -> {target!r} is not reciprocal"
                    )
            for shop_id in area.shop_ids:
                if shop_id not in self._shops:
                    raise ContentError(f"area {area.id!r} references unknown shop {shop_id!r}")
            for npc_id in area.npc_ids:
                if npc_id not in self._npcs:
                    raise ContentError(f"area {area.id!r} references unknown npc {npc_id!r}")

    # ------------------------------------------------------------------
    def create_world(self) -> WorldState:
        """Build a fresh :class:`WorldState` at the starting area."""
        self.load()
        return WorldState(
            areas=self._areas,
            npcs=self._npcs,
            shops=self._shops,
            start_area_id=self._start_area_id,
            flavour=self._flavour,
        )

    def get_area(self, area_id: str) -> Area | None:
        self.load()
        return self._areas.get(area_id)

    def get_npc(self, npc_id: str) -> NPC | None:
        self.load()
        return self._npcs.get(npc_id)

    def get_shop(self, shop_id: str) -> Shop | None:
        self.load()
        return self._shops.get(shop_id)

    def all_areas(self) -> list[Area]:
        self.load()
        return sorted(self._areas.values(), key=lambda a: (a.recommended_level, a.name))

    def count(self) -> int:
        self.load()
        return len(self._areas)
