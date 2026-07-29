"""Items, equipment and the inventory container.

Same pattern as skills: ONE :class:`Item` class, thousands of JSON entries.
Behaviour differences come from ``kind`` + composed data, not subclasses.

Bible section 4 lists ``items`` as a top-level folder; this module holds the
runtime model, ``data/items.json`` holds the content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from engine.stats import ModifierSet

__all__ = [
    "EQUIPMENT_SLOTS",
    "SLOT_LABELS",
    "ItemKind",
    "Item",
    "InventoryEntry",
    "Inventory",
]

#: Canonical equipment slots, in display order.
EQUIPMENT_SLOTS: tuple[str, ...] = (
    "weapon",
    "offhand",
    "head",
    "body",
    "hands",
    "feet",
    "accessory1",
    "accessory2",
)

#: GUI-facing slot names.
SLOT_LABELS: dict[str, str] = {
    "weapon": "Weapon",
    "offhand": "Off-hand",
    "head": "Head",
    "body": "Body",
    "hands": "Hands",
    "feet": "Feet",
    "accessory1": "Accessory I",
    "accessory2": "Accessory II",
}


class ItemKind:
    """What an item fundamentally does."""

    EQUIPMENT = "equipment"
    CONSUMABLE = "consumable"
    MATERIAL = "material"
    KEY = "key"
    SPECIAL = "special"

    ALL = (EQUIPMENT, CONSUMABLE, MATERIAL, KEY, SPECIAL)


@dataclass
class Item:
    """A single item definition, shared immutably across all stacks of it."""

    id: str
    name: str
    kind: str = ItemKind.MATERIAL
    description: str = ""
    value: int = 0
    #: Which slot it occupies (equipment only).
    slot: str = ""
    #: ``sword`` / ``staff`` / ... - drives weapon-skill and mastery gating.
    weapon_type: str = ""
    modifiers: ModifierSet = field(default_factory=ModifierSet)
    #: Extra equipment modifiers keyed by race id. Base modifiers still apply to everyone.
    race_modifiers: dict[str, ModifierSet] = field(default_factory=dict)
    #: Effect payloads run on use (consumables); built lazily to avoid a cycle.
    use_effects: list[dict[str, Any]] = field(default_factory=list)
    stack_size: int = 99
    required_level: int = 1
    required_stats: dict[str, int] = field(default_factory=dict)
    #: Marks the marriage item from bible section 15.
    tags: list[str] = field(default_factory=list)
    rarity: str = "common"
    set_id: str = ""
    enchant_slots: int = 0
    bound_skill_id: str = ""
    conditional_modifiers: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_equipment(self) -> bool:
        return self.kind == ItemKind.EQUIPMENT and self.slot in EQUIPMENT_SLOTS

    @property
    def is_consumable(self) -> bool:
        return self.kind == ItemKind.CONSUMABLE and bool(self.use_effects)

    @property
    def stackable(self) -> bool:
        # Equipment never stacks - two swords can be enchanted differently
        # later, and merging them would erase that distinction.
        return self.stack_size > 1 and not self.is_equipment

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def sell_price(self, rate: float = 0.4) -> int:
        return max(1, int(self.value * rate))

    @property
    def rarity_label(self) -> str:
        """Human-readable rarity, while preserving the JSON id."""
        return self.rarity.replace("_", " ").title()

    def detail_lines(self) -> list[str]:
        """Stacked ``key: value`` text for the Inventory/Equipment panes."""
        lines = [f"{self.name} [{self.rarity_label}]"]
        if self.description:
            lines.append(self.description)
        if self.is_equipment:
            lines.append(f"Slot: {SLOT_LABELS.get(self.slot, self.slot.title())}")
        if self.weapon_type:
            lines.append(f"Type: {self.weapon_type.title()}")
        lines.extend(self.modifiers.describe())
        for race_id, modifiers in sorted(self.race_modifiers.items()):
            label = race_id.replace("_", " ").title()
            lines.append(f"{label} racial bonus:")
            lines.extend(f"  {line}" for line in modifiers.describe())
        if self.required_level > 1:
            lines.append(f"Requires level {self.required_level}")
        for stat, amount in self.required_stats.items():
            lines.append(f"Requires {stat} {amount}")
        lines.append(f"Value: {self.value} gold")
        return lines

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Item":
        item_id = str(payload.get("id", "")).strip()
        if not item_id:
            raise ValueError("item entry is missing an 'id'")
        kind = str(payload.get("kind", ItemKind.MATERIAL)).lower()
        if kind not in ItemKind.ALL:
            raise ValueError(f"item {item_id!r} has unknown kind {kind!r}")
        slot = str(payload.get("slot", "")).lower()
        if kind == ItemKind.EQUIPMENT and slot not in EQUIPMENT_SLOTS:
            raise ValueError(f"equipment {item_id!r} has invalid slot {slot!r}")
        return cls(
            id=item_id,
            name=str(payload.get("name", item_id)),
            kind=kind,
            description=str(payload.get("description", "")),
            value=int(payload.get("value", 0)),
            slot=slot,
            weapon_type=str(payload.get("weapon_type", "")).lower(),
            modifiers=ModifierSet.from_dict(payload.get("modifiers")),
            race_modifiers={
                str(race_id): ModifierSet.from_dict(modifiers)
                for race_id, modifiers in (payload.get("race_modifiers") or {}).items()
            },
            use_effects=[dict(e) for e in payload.get("use_effects", [])],
            stack_size=int(payload.get("stack_size", 99)),
            required_level=int(payload.get("required_level", 1)),
            required_stats={str(k).upper(): int(v) for k, v in (payload.get("required_stats") or {}).items()},
            tags=[str(t) for t in payload.get("tags", [])],
            rarity=str(payload.get("rarity", "common")),
            set_id=str(payload.get("set_id", "")),
            enchant_slots=int(payload.get("enchant_slots", 1 if kind == ItemKind.EQUIPMENT else 0)),
            bound_skill_id=str(payload.get("bound_skill_id", "")),
            conditional_modifiers=[dict(value) for value in payload.get("conditional_modifiers", [])],
        )


@dataclass
class InventoryEntry:
    """One stack in the bag."""

    item: Item
    quantity: int = 1

    def label(self) -> str:
        return f"{self.item.name} x{self.quantity}" if self.quantity > 1 else self.item.name


class Inventory:
    """The player's bag: stacks, gold, and equip/unequip bookkeeping."""

    def __init__(self, capacity: int = 60) -> None:
        self.capacity = capacity
        self.entries: list[InventoryEntry] = []
        self.gold: int = 0

    # ------------------------------------------------------------------
    @property
    def is_full(self) -> bool:
        return len(self.entries) >= self.capacity

    def find(self, item_id: str) -> InventoryEntry | None:
        return next((e for e in self.entries if e.item.id == item_id), None)

    def count(self, item_id: str) -> int:
        entry = self.find(item_id)
        return entry.quantity if entry else 0

    def has(self, item_id: str, quantity: int = 1) -> bool:
        return self.count(item_id) >= quantity

    def has_all(self, requirements: Mapping[str, int] | Iterable[str] | None) -> bool:
        """Accepts ``{"id": qty}`` or a plain list of ids."""
        if not requirements:
            return True
        if isinstance(requirements, Mapping):
            return all(self.has(item_id, int(qty)) for item_id, qty in requirements.items())
        return all(self.has(str(item_id)) for item_id in requirements)

    # ------------------------------------------------------------------
    def add(self, item: Item, quantity: int = 1) -> int:
        """Add items, merging into an existing stack when possible.

        Returns how many were actually added - the remainder was refused
        because the bag is full, and the caller should tell the player.
        """
        if quantity <= 0:
            return 0
        added = 0
        remaining = quantity

        if item.stackable:
            entry = self.find(item.id)
            if entry is not None:
                room = max(0, item.stack_size - entry.quantity)
                moved = min(room, remaining)
                entry.quantity += moved
                added += moved
                remaining -= moved

        while remaining > 0 and not self.is_full:
            chunk = min(remaining, item.stack_size if item.stackable else 1)
            self.entries.append(InventoryEntry(item=item, quantity=chunk))
            added += chunk
            remaining -= chunk

        return added

    def remove(self, item_id: str, quantity: int = 1) -> bool:
        """Remove ``quantity``; all-or-nothing so callers can't half-pay."""
        if quantity <= 0:
            return True
        if self.count(item_id) < quantity:
            return False
        remaining = quantity
        for entry in [e for e in self.entries if e.item.id == item_id]:
            take = min(entry.quantity, remaining)
            entry.quantity -= take
            remaining -= take
            if remaining <= 0:
                break
        self.entries = [e for e in self.entries if e.quantity > 0]
        return True

    def add_gold(self, amount: int) -> None:
        self.gold = max(0, self.gold + int(amount))

    def spend_gold(self, amount: int) -> bool:
        if amount <= 0:
            return True
        if self.gold < amount:
            return False
        self.gold -= int(amount)
        return True

    # ------------------------------------------------------------------
    def sorted_entries(self, kind: str | None = None) -> list[InventoryEntry]:
        """Entries filtered by kind, ordered for stable GUI listing."""
        entries = [e for e in self.entries if kind is None or e.item.kind == kind]
        return sorted(entries, key=lambda e: (e.item.kind, e.item.name))

    def equipment_entries(self, slot: str | None = None) -> list[InventoryEntry]:
        return [
            e
            for e in self.sorted_entries()
            if e.item.is_equipment and (slot is None or e.item.slot == slot)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gold": self.gold,
            "capacity": self.capacity,
            "entries": [{"id": e.item.id, "quantity": e.quantity} for e in self.entries],
        }
