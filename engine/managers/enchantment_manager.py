"""Data-driven equipment enchantments."""

from __future__ import annotations

from dataclasses import dataclass

from engine.managers.data_loader import ContentError, DataLoader
from engine.stats import ModifierSet


@dataclass(frozen=True)
class EnchantmentDefinition:
    id: str
    name: str
    modifiers: ModifierSet
    gold_cost: int = 0


class EnchantmentManager:
    def __init__(self, loader: DataLoader) -> None:
        self.loader = loader
        self.definitions: dict[str, EnchantmentDefinition] = {}
        self.loaded = False

    def load(self) -> None:
        if self.loaded:
            return
        for entry in self.loader.load_entries("enchantments.json", "enchantments"):
            enchantment_id = str(entry.get("id", ""))
            if not enchantment_id or enchantment_id in self.definitions:
                raise ContentError(f"invalid/duplicate enchantment {enchantment_id!r}")
            self.definitions[enchantment_id] = EnchantmentDefinition(
                id=enchantment_id,
                name=str(entry.get("name", enchantment_id)),
                modifiers=ModifierSet.from_dict(entry.get("modifiers")),
                gold_cost=int(entry.get("gold_cost", 0)),
            )
        self.loaded = True

    def get(self, enchantment_id: str) -> EnchantmentDefinition | None:
        self.load()
        return self.definitions.get(enchantment_id)

    def all_definitions(self) -> list[EnchantmentDefinition]:
        self.load()
        return list(self.definitions.values())
