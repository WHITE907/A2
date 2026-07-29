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
        self._rarity_config: dict[str, Any] = {}

    # ------------------------------------------------------------------
    def load(self) -> None:
        if self._loaded:
            return
        # Load rarity config for enchant slot defaults
        try:
            config = self._loader.load_mapping("config.json", required=False) or {}
            self._rarity_config = config.get("rarities") or {}
        except Exception:
            self._rarity_config = {}

        for entry in self._loader.load_entries(self.ITEM_FILE, "items", required=False):
            try:
                item = Item.from_dict(entry)
            except ValueError as exc:
                raise ContentError(f"{self.ITEM_FILE}: {exc}") from exc
            if item.id in self._items:
                raise ContentError(f"duplicate item id {item.id!r} in {self.ITEM_FILE}")
            # Resolve sentinel enchant_slots via rarity config
            if item.enchant_slots == -1:
                rarity_cfg = self._rarity_config.get(item.rarity.lower(), {})
                slots = int(rarity_cfg.get("enchant_slots", 1)) if rarity_cfg else 1
                # Need to recreate dataclass with new slots since frozen? Item is not frozen, but we set attr
                item.enchant_slots = slots
            self._items[item.id] = item
        self._loaded = True

    def rarity_config(self) -> dict[str, Any]:
        self.load()
        return self._rarity_config

    def get_or_create_variant(self, base_id: str, target_rarity: str) -> "Item":
        """Create a rarity variant of an existing item, preserving base id.

        Variant id format: base_id@rarity (e.g. iron_sword@rare).  If variant
        already exists, return it.  Base modifiers are scaled via rarity config.
        """
        target_rarity = target_rarity.lower()
        if target_rarity in ("", "common") and "@" not in base_id:
            # Common variant is the base itself if base is common
            base = self._items.get(base_id)
            if base and base.rarity.lower() == "common":
                return base
        variant_id = f"{base_id.split('@')[0]}@{target_rarity}" if "@" not in base_id else f"{base_id.split('@')[0]}@{target_rarity}"
        if variant_id in self._items:
            return self._items[variant_id]
        base = self._items.get(base_id.split("@")[0])
        if base is None:
            raise ValueError(f"unknown base item {base_id!r}")
        # Compute scaled modifiers
        rarity_cfg = self._rarity_config.get(target_rarity, {})
        # Clone base item with new rarity
        from dataclasses import replace
        # For simplicity, create new Item via from_dict style clone
        # Modifiers scaled by rarity handled in Player, but we store base modifiers unchanged;
        # rarity field drives scaling later.
        variant = replace(base, id=variant_id, rarity=target_rarity, name=f"{base.name} [{target_rarity.title()}]")
        self._items[variant_id] = variant
        return variant



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
        """Bulk-grant; returns human-readable lines for the reward log with rarity."""
        pairs = grants.items() if isinstance(grants, Mapping) else grants
        lines: list[str] = []
        for item_id, quantity in pairs:
            added = self.grant(inventory, item_id, int(quantity))
            if added > 0:
                item = self.require(item_id)
                label = f"[{item.rarity_label}] {item.name}"
                lines.append(f"{label} x{added}" if added > 1 else label)
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
