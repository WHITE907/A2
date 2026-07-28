"""Load dialogue, faction, and contextual banter content."""

from __future__ import annotations

from engine.managers.data_loader import ContentError, DataLoader
from engine.story import BanterDefinition, DialogueTree, FactionDefinition


class StoryManager:
    def __init__(self, loader: DataLoader) -> None:
        self.loader = loader
        self.dialogues: dict[str, DialogueTree] = {}
        self.factions: dict[str, FactionDefinition] = {}
        self.banter: list[BanterDefinition] = []
        self.loaded = False

    def load(self) -> None:
        if self.loaded:
            return
        for entry in self.loader.load_entries("dialogues.json", "dialogues"):
            definition = DialogueTree.from_dict(entry)
            if not definition.id or definition.id in self.dialogues:
                raise ContentError(f"invalid/duplicate dialogue {definition.id!r}")
            self.dialogues[definition.id] = definition
        for entry in self.loader.load_entries("factions.json", "factions"):
            definition = FactionDefinition.from_dict(entry)
            if not definition.id or definition.id in self.factions:
                raise ContentError(f"invalid/duplicate faction {definition.id!r}")
            self.factions[definition.id] = definition
        self.banter = [
            BanterDefinition.from_dict(entry)
            for entry in self.loader.load_entries("banter.json", "banter")
        ]
        self.loaded = True

    def dialogue(self, dialogue_id: str) -> DialogueTree | None:
        self.load()
        return self.dialogues.get(dialogue_id)

    def faction(self, faction_id: str) -> FactionDefinition | None:
        self.load()
        return self.factions.get(faction_id)

    def count_dialogues(self) -> int:
        self.load()
        return len(self.dialogues)
