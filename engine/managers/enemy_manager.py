"""``EnemyManager`` - spawns live :class:`Enemy` objects from JSON templates.

``spawn(template_id, level)`` is the exact API docs/ENGINE_DESIGN.md specifies.
Every monster in the game comes from here; there is no per-monster subclass.
"""

from __future__ import annotations

import string
from typing import Any, Sequence

from engine.entities.enemy import Enemy, EnemyTemplate
from engine.managers.data_loader import ContentError, DataLoader
from engine.managers.skill_manager import SkillManager
from engine.stats import Formulas

__all__ = ["EnemyManager"]


class EnemyManager:
    """Loads enemy templates and instantiates them at a requested level."""

    ENEMY_FILE = "enemies.json"

    def __init__(self, loader: DataLoader, skill_manager: SkillManager, formulas: Formulas) -> None:
        self._loader = loader
        self._skills = skill_manager
        self._formulas = formulas
        self._templates: dict[str, EnemyTemplate] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    def load(self) -> None:
        if self._loaded:
            return
        for entry in self._loader.load_entries(self.ENEMY_FILE, "enemies"):
            try:
                template = EnemyTemplate.from_dict(entry)
            except ValueError as exc:
                raise ContentError(f"{self.ENEMY_FILE}: {exc}") from exc
            if template.id in self._templates:
                raise ContentError(f"duplicate enemy id {template.id!r} in {self.ENEMY_FILE}")
            self._templates[template.id] = template
        self._loaded = True

    # ------------------------------------------------------------------
    def get_template(self, template_id: str) -> EnemyTemplate | None:
        self.load()
        return self._templates.get(template_id)

    def all_templates(self) -> list[EnemyTemplate]:
        self.load()
        return sorted(self._templates.values(), key=lambda t: (t.base_level, t.name))

    def templates_for_level(self, level: int, tolerance: int = 3) -> list[EnemyTemplate]:
        """Templates appropriate for a given player level.

        Bosses are excluded from the normal pool so they only appear where an
        area explicitly places them.
        """
        self.load()
        return [
            t
            for t in self._templates.values()
            if not t.is_boss and (t.base_level - tolerance) <= level <= (t.base_level + tolerance * 2)
        ]

    # ------------------------------------------------------------------
    def spawn(self, template_id: str, level: int | None = None, name_suffix: str = "") -> Enemy:
        """Create one live enemy.  The core API from ENGINE_DESIGN.md."""
        self.load()
        template = self._templates.get(template_id)
        if template is None:
            raise ContentError(f"unknown enemy template {template_id!r}")
        actual_level = max(1, int(level if level is not None else template.base_level))
        return Enemy(
            template=template,
            level=actual_level,
            formulas=self._formulas,
            skills=self._skills.get_many(template.skill_ids),
            name_suffix=name_suffix,
        )

    def spawn_group(self, spec: Sequence[tuple[str, int]] | Sequence[str], level: int | None = None) -> list[Enemy]:
        """Spawn several enemies, labelling duplicates A/B/C.

        Without the suffix a party of three slimes gives the player three
        identically-named entries in the target list and no way to tell which
        one is nearly dead.
        """
        self.load()
        requests: list[tuple[str, int]] = []
        for entry in spec:
            if isinstance(entry, str):
                requests.append((entry, level if level is not None else 0))
            else:
                requests.append((entry[0], entry[1]))

        counts: dict[str, int] = {}
        for template_id, _ in requests:
            counts[template_id] = counts.get(template_id, 0) + 1

        seen: dict[str, int] = {}
        enemies: list[Enemy] = []
        for template_id, enemy_level in requests:
            suffix = ""
            if counts[template_id] > 1:
                index = seen.get(template_id, 0)
                suffix = string.ascii_uppercase[index % 26]
                seen[template_id] = index + 1
            resolved = enemy_level if enemy_level > 0 else None
            enemies.append(self.spawn(template_id, resolved, name_suffix=suffix))
        return enemies

    def count(self) -> int:
        self.load()
        return len(self._templates)
