"""``SaveManager`` - JSON save slots (bible section 16).

- Multiple save slots
- Morning autosave
- Respawn at the Inn after death
- JSON serialisation

Bible section 5 also demands backwards compatibility.  Every save carries a
``save_version``; :meth:`SaveManager._migrate` upgrades older payloads in place
so a save written by an earlier build keeps loading after new fields appear.

Writes go to a temporary file and are then atomically replaced, so a crash
mid-write can never leave a half-written save that fails to parse.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from engine.managers.data_loader import PROJECT_ROOT

__all__ = ["SaveManager", "SaveSlotInfo", "SAVE_VERSION"]

#: Bump when the payload shape changes; add a matching step in ``_migrate``.
SAVE_VERSION: int = 6

_AUTOSAVE_PREFIX = "autosave"


@dataclass
class SaveSlotInfo:
    """Header data for the Save Browser, read without loading the full save."""

    slot: str
    character_name: str = "Unknown"
    class_name: str = "Unknown"
    level: int = 1
    day: int = 1
    gold: int = 0
    mastery: str = "F"
    area_name: str = ""
    saved_at: float = 0.0
    is_autosave: bool = False
    corrupt: bool = False

    @property
    def display_name(self) -> str:
        """Listbox label - character names only, per the style reference."""
        if self.corrupt:
            return f"{self.slot} (corrupt)"
        tag = " [auto]" if self.is_autosave else ""
        return f"{self.character_name}{tag}"

    def timestamp_text(self) -> str:
        if not self.saved_at:
            return "Unknown"
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.saved_at))

    def detail_lines(self) -> list[str]:
        """Stacked ``key: value`` preview block for the Load Game window."""
        if self.corrupt:
            return [f"Slot: {self.slot}", "This save file is damaged and cannot be loaded."]
        return [
            f"Name: {self.character_name}",
            f"Class: {self.class_name}",
            f"Level: {self.level}",
            f"Day: {self.day}",
            f"Gold: {self.gold}",
            f"Mastery: {self.mastery}",
            f"Location: {self.area_name or 'Unknown'}",
            f"Saved: {self.timestamp_text()}",
        ]


class SaveManager:
    """Reads and writes save slots as JSON files."""

    def __init__(self, save_dir: Path | str | None = None) -> None:
        self.save_dir = Path(save_dir) if save_dir else PROJECT_ROOT / "saves"
        self.save_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def slot_path(self, slot: str) -> Path:
        """Resolve a slot name to a file path, rejecting path traversal."""
        safe = "".join(ch for ch in slot if ch.isalnum() or ch in ("_", "-")).strip()
        if not safe:
            safe = "slot"
        return self.save_dir / f"{safe}.json"

    def exists(self, slot: str) -> bool:
        return self.slot_path(slot).is_file()

    # ------------------------------------------------------------------
    def write(self, slot: str, payload: Mapping[str, Any]) -> Path:
        """Atomically write one save slot."""
        path = self.slot_path(slot)
        document = dict(payload)
        document["save_version"] = SAVE_VERSION
        document["saved_at"] = time.time()
        document["slot"] = slot

        temp_path = path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        return path

    def read(self, slot: str) -> dict[str, Any] | None:
        """Read and migrate one save.  ``None`` when missing or unreadable."""
        path = self.slot_path(slot)
        if not path.is_file():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(payload, dict):
            return None
        return self._migrate(payload)

    def delete(self, slot: str) -> bool:
        path = self.slot_path(slot)
        if not path.is_file():
            return False
        try:
            path.unlink()
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    def list_slots(self) -> list[SaveSlotInfo]:
        """Header info for every save on disk, newest first.

        A corrupt file is reported as a corrupt slot rather than being hidden -
        silently vanishing saves are far more alarming to a player than a slot
        that says it is damaged.
        """
        infos: list[SaveSlotInfo] = []
        for path in sorted(self.save_dir.glob("*.json")):
            slot = path.stem
            try:
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except (json.JSONDecodeError, OSError):
                infos.append(SaveSlotInfo(slot=slot, corrupt=True))
                continue
            if not isinstance(payload, dict):
                infos.append(SaveSlotInfo(slot=slot, corrupt=True))
                continue
            infos.append(self._header(slot, self._migrate(payload)))
        infos.sort(key=lambda info: info.saved_at, reverse=True)
        return infos

    def get_info(self, slot: str) -> SaveSlotInfo | None:
        payload = self.read(slot)
        if payload is None:
            return SaveSlotInfo(slot=slot, corrupt=True) if self.exists(slot) else None
        return self._header(slot, payload)

    @staticmethod
    def _header(slot: str, payload: Mapping[str, Any]) -> SaveSlotInfo:
        meta = payload.get("meta") or {}
        return SaveSlotInfo(
            slot=slot,
            character_name=str(meta.get("character_name", "Unknown")),
            class_name=str(meta.get("class_name", "Unknown")),
            level=int(meta.get("level", 1)),
            day=int(meta.get("day", 1)),
            gold=int(meta.get("gold", 0)),
            mastery=str(meta.get("mastery", "F")),
            area_name=str(meta.get("area_name", "")),
            saved_at=float(payload.get("saved_at", 0.0)),
            is_autosave=slot.startswith(_AUTOSAVE_PREFIX),
        )

    # ------------------------------------------------------------------
    def next_autosave_slot(self, character_name: str) -> str:
        """Deterministic autosave slot name, one per character."""
        safe = "".join(ch for ch in character_name.lower() if ch.isalnum()) or "hero"
        return f"{_AUTOSAVE_PREFIX}_{safe}"

    def suggest_slot(self, character_name: str) -> str:
        """First free manual slot for a character, ``name``, ``name_2``, ...

        Never silently overwrites an unrelated character's file.
        """
        safe = "".join(ch for ch in character_name.lower() if ch.isalnum()) or "hero"
        if not self.exists(safe):
            return safe
        index = 2
        while self.exists(f"{safe}_{index}"):
            index += 1
        return f"{safe}_{index}"

    # ------------------------------------------------------------------
    @staticmethod
    def _migrate(payload: dict[str, Any]) -> dict[str, Any]:
        """Bring an older save up to the current schema.

        Each step is additive and idempotent, so a v1 save loads exactly like a
        v2 one - bible section 5's backwards-compatibility rule.
        """
        version = int(payload.get("save_version", 1))

        if version < 2:
            # v1 stored no RNG state and no world block.
            payload.setdefault("rng", None)
            payload.setdefault("world", {"day": payload.get("day", 1)})
            player = payload.get("player")
            if isinstance(player, dict):
                player.setdefault("completed_quests", [])
                player.setdefault("affinity", {})
                player.setdefault("spouse_id", None)
                player.setdefault("flags", {})
                player.setdefault("class_history", [player.get("class_id", "")])
            version = 2

        if version < 3:
            player = payload.get("player")
            if isinstance(player, dict):
                player.setdefault("active_quests", [])
                player.setdefault("quest_progress", {})
            version = 3

        if version < 4:
            world = payload.setdefault("world", {})
            if isinstance(world, dict):
                world.setdefault("defeated_bosses", [])
            version = 4

        if version < 5:
            player = payload.get("player")
            if isinstance(player, dict):
                # The runtime resolves an empty id through config.default_race_id.
                player.setdefault("race_id", "")
            version = 5

        if version < 6:
            player = payload.get("player")
            if isinstance(player, dict):
                for key in (
                    "faction_reputation", "companion_loyalty",
                    "companion_unavailable_until", "item_enchantments", "item_upgrades",
                ):
                    player.setdefault(key, {})
            version = 6

        payload["save_version"] = max(version, SAVE_VERSION)
        return payload
