"""``SkillManager`` - factory turning ``skills.json`` into live :class:`Skill`s.

Also owns the status-effect catalog, because statuses are only ever created by
skills and keeping them together means one injection point
(:class:`~engine.skills.effects.EffectContext`) instead of two.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from engine.managers.data_loader import ContentError, DataLoader
from engine.skills.effects import EffectContext
from engine.skills.skill import Skill, SkillCategory
from engine.skills.status import StatusEffect

__all__ = ["SkillManager"]


class SkillManager:
    """Loads, caches and hands out skill definitions."""

    SKILL_FILE = "skills.json"
    STATUS_FILE = "statuses.json"

    def __init__(self, loader: DataLoader) -> None:
        self._loader = loader
        self._skills: dict[str, Skill] = {}
        self._statuses: dict[str, StatusEffect] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    def load(self) -> None:
        """Parse both content files.  Idempotent."""
        if self._loaded:
            return

        for entry in self._loader.load_entries(self.STATUS_FILE, "statuses", required=False):
            status = StatusEffect.from_dict(entry)
            if status.id in self._statuses:
                raise ContentError(f"duplicate status id {status.id!r} in {self.STATUS_FILE}")
            self._statuses[status.id] = status

        for entry in self._loader.load_entries(self.SKILL_FILE, "skills"):
            try:
                skill = Skill.from_dict(entry)
            except ValueError as exc:
                raise ContentError(f"{self.SKILL_FILE}: {exc}") from exc
            if skill.id in self._skills:
                raise ContentError(f"duplicate skill id {skill.id!r} in {self.SKILL_FILE}")
            self._skills[skill.id] = skill

        self._validate_status_references()
        self._loaded = True

    def _validate_status_references(self) -> None:
        """Fail loudly if a skill applies a status that does not exist.

        Catching this at load time turns a silent no-op in combat (the effect
        would just return ``None``) into an actionable content error.
        """
        from engine.skills.effects import ApplyStatusEffect

        for skill in self._skills.values():
            for effect in skill.effects:
                if isinstance(effect, ApplyStatusEffect) and effect.status_id not in self._statuses:
                    raise ContentError(
                        f"skill {skill.id!r} references unknown status {effect.status_id!r}"
                    )

    # ------------------------------------------------------------------
    def get(self, skill_id: str) -> Skill | None:
        self.load()
        return self._skills.get(skill_id)

    def require(self, skill_id: str) -> Skill:
        """Like :meth:`get`, but raises rather than returning ``None``."""
        skill = self.get(skill_id)
        if skill is None:
            raise ContentError(f"unknown skill id {skill_id!r}")
        return skill

    def get_many(self, skill_ids: Iterable[str]) -> list[Skill]:
        """Resolve several ids, silently skipping unknown ones.

        Used for enemy/class skill lists where one bad id should degrade that
        entity, not abort the whole game.
        """
        self.load()
        return [self._skills[sid] for sid in skill_ids if sid in self._skills]

    def all_skills(self) -> list[Skill]:
        self.load()
        return sorted(self._skills.values(), key=lambda s: (s.category, s.name))

    def by_category(self, category: str) -> list[Skill]:
        self.load()
        return sorted((s for s in self._skills.values() if s.category == category), key=lambda s: s.name)

    def weapon_skills(self, weapon_type: str) -> list[Skill]:
        """Shared weapon skills for a weapon type (bible section 11)."""
        self.load()
        return sorted(
            (
                s
                for s in self._skills.values()
                if s.category in (SkillCategory.WEAPON, SkillCategory.SHARED)
                and (not s.required_weapon_types or weapon_type in s.required_weapon_types)
            ),
            key=lambda s: s.name,
        )

    # ------------------------------------------------------------------
    def get_status(self, status_id: str) -> StatusEffect | None:
        self.load()
        return self._statuses.get(status_id)

    def all_statuses(self) -> list[StatusEffect]:
        self.load()
        return sorted(self._statuses.values(), key=lambda s: s.name)

    def make_context(self, rng: Any, formulas: Any) -> EffectContext:
        """Build the context effects need, wired to this manager's catalog.

        This is the injection point that keeps ``effects.py`` free of any
        knowledge of files or managers.
        """
        self.load()
        return EffectContext(rng=rng, formulas=formulas, status_factory=self.get_status)

    def count(self) -> int:
        self.load()
        return len(self._skills)
