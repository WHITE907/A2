"""``ItemManager`` - factory for :class:`Item` definitions.

Bible section 6 lists ItemManager as planned; it is real now.  Items are
immutable definitions shared between all stacks, so the manager hands out the
same object rather than copying - nothing mutates an ``Item``.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from engine.items.item import EQUIPMENT_SLOTS, Inventory, Item, ItemKind
from engine.managers.data_loader import ContentError, DataLoader

__all__ = ["ItemManager"]


class ItemManager:
    """Loads item content and applies consumables."""

    ITEM_FILE = "items.json"

    def __init__(self, loader: DataLoader) -> None:
        self._loader = loader
        self._items: dict[str, Item] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    def load(self) -> None:
        if self._loaded:
            return
        for entry in self._loader.load_entries(self.ITEM_FILE, "items", required=False):
            try:
                item = Item.from_dict(entry)
            except ValueError as exc:
                raise ContentError(f"{self.ITEM_FILE}: {exc}") from exc
            if item.id in self._items:
                raise ContentError(f"duplicate item id {item.id!r} in {self.ITEM_FILE}")
            self._items[item.id] = item
        self._loaded = True

    # ------------------------------------------------------------------
    def get(self, item_id: str) -> Item | None:
        self.load()
        return self._items.get(item_id)

    def require(self, item_id: str) -> Item:
        item = self.get(item_id)
        if item is None:
            raise ContentError(f"unknown item id {item_id!r}")
        return item

    def all_items(self) -> list[Item]:
        self.load()
        return sorted(self._items.values(), key=lambda i: (i.kind, i.name))

    def by_kind(self, kind: str) -> list[Item]:
        self.load()
        return sorted((i for i in self._items.values() if i.kind == kind), key=lambda i: i.name)

    def by_slot(self, slot: str) -> list[Item]:
        self.load()
        return sorted((i for i in self._items.values() if i.slot == slot), key=lambda i: i.name)

    def find_by_tag(self, tag: str) -> list[Item]:
        """Used for e.g. the marriage item (bible section 15)."""
        self.load()
        return sorted((i for i in self._items.values() if i.has_tag(tag)), key=lambda i: i.name)

    # ------------------------------------------------------------------
    def grant(self, inventory: Inventory, item_id: str, quantity: int = 1) -> int:
        """Add items to a bag by id; returns how many fit."""
        item = self.get(item_id)
        if item is None:
            return 0
        return inventory.add(item, quantity)

    def grant_many(self, inventory: Inventory, grants: Mapping[str, int] | Iterable[tuple[str, int]]) -> list[str]:
        """Bulk-grant; returns human-readable lines for the reward log."""
        pairs = grants.items() if isinstance(grants, Mapping) else grants
        lines: list[str] = []
        for item_id, quantity in pairs:
            added = self.grant(inventory, item_id, int(quantity))
            if added > 0:
                item = self.require(item_id)
                lines.append(f"{item.name} x{added}" if added > 1 else item.name)
        return lines

    # ------------------------------------------------------------------
    def use_consumable(self, user: Any, item_id: str, ctx: Any, targets: Sequence[Any] | None = None) -> tuple[bool, list[str]]:
        """Consume one item and apply its effects.

        The item is removed only after the effects resolve successfully, so a
        failed use never destroys the item.
        """
        item = self.get(item_id)
        if item is None:
            return False, [f"Unknown item {item_id!r}."]
        if not item.is_consumable:
            return False, [f"{item.name} cannot be used."]
        if not user.inventory.has(item_id):
            return False, [f"You have no {item.name}."]

        from engine.skills.effects import build_effects  # local: avoids a cycle

        try:
            effects = build_effects(item.use_effects)
        except ValueError as exc:
            return False, [f"{item.name} is misconfigured: {exc}"]

        recipients = list(targets) if targets else [user]
        messages: list[str] = []
        for effect in effects:
            for target in recipients if effect.target_override != "self" else [user]:
                result = effect.apply(user, target, ctx)
                if result is not None and result.message:
                    messages.append(result.message)

        user.inventory.remove(item_id, 1)
        if not messages:
            messages.append(f"{user.name} uses {item.name}.")
        return True, messages

    def count(self) -> int:
        self.load()
        return len(self._items)
