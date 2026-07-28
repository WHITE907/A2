"""The combat turn loop - roadmap v0.0.5.

Per docs/ENGINE_DESIGN.md this layer *"calls skill.use(caster, targets) and
entity.tick_status_effects(); it doesn't need to know what any specific skill
does"* - and it doesn't.  There is no ``if skill.id == "fireball"`` anywhere.

Turn order is speed-based and recomputed each round, so a haste buff or a slow
debuff changes the order mid-battle rather than only at the start.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Sequence

from engine.combat.ai import AIRegistry, default_registry
from engine.skills.skill import Skill, SkillUseResult

__all__ = ["CombatState", "CombatLogEntry", "CombatRewards", "Battle"]


class CombatState(Enum):
    """Where a battle currently is."""

    ONGOING = "ongoing"
    VICTORY = "victory"
    DEFEAT = "defeat"
    FLED = "fled"


@dataclass
class CombatLogEntry:
    """One line in the combat log, tagged so the GUI can style it."""

    text: str
    #: ``"info"``, ``"damage"``, ``"heal"``, ``"status"``, ``"system"``.
    kind: str = "info"

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.text


@dataclass
class CombatRewards:
    """What the player walked away with."""

    exp: float = 0.0
    gold: int = 0
    items: list[tuple[str, int]] = field(default_factory=list)
    mastery_gains: dict[str, float] = field(default_factory=dict)
    level_up_messages: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [f"EXP: {self.exp:.0f}", f"Gold: {self.gold}"]
        lines.extend(f"Item: {item_id.replace('_', ' ').title()} x{qty}" for item_id, qty in self.items)
        lines.extend(f"Mastery: {track.title()} +{amount:.0f}" for track, amount in self.mastery_gains.items())
        lines.extend(self.level_up_messages)
        return lines


class Battle:
    """One encounter: the player (plus allies) versus a group of enemies."""

    def __init__(
        self,
        player: Any,
        enemies: Sequence[Any],
        ctx: Any,
        rng: Any,
        *,
        allies: Sequence[Any] = (),
        ai_registry: AIRegistry | None = None,
        flee_base_chance: float = 0.45,
        mastery_per_action: float = 6.0,
    ) -> None:
        self.player = player
        self.enemies: list[Any] = list(enemies)
        self.allies: list[Any] = [player, *allies]
        self.ctx = ctx
        self.rng = rng
        self.ai = ai_registry or default_registry()
        self.flee_base_chance = flee_base_chance
        self.mastery_per_action = mastery_per_action

        self.state = CombatState.ONGOING
        self.round = 0
        self.log: list[CombatLogEntry] = []
        self.rewards = CombatRewards()
        #: Recomputed each round in :meth:`begin_round`.
        self.turn_order: list[Any] = []
        self._turn_index = 0

        self._say(
            "Battle start: " + ", ".join(e.name for e in self.enemies) + "!",
            kind="system",
        )
        self.begin_round()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _say(self, text: str, kind: str = "info") -> None:
        if text:
            self.log.append(CombatLogEntry(text, kind))

    def recent_log(self, count: int = 12) -> list[str]:
        return [entry.text for entry in self.log[-count:]]

    # ------------------------------------------------------------------
    # Round / turn management
    # ------------------------------------------------------------------
    @property
    def living_enemies(self) -> list[Any]:
        return [e for e in self.enemies if e.is_alive]

    @property
    def living_allies(self) -> list[Any]:
        return [a for a in self.allies if a.is_alive]

    @property
    def is_over(self) -> bool:
        return self.state is not CombatState.ONGOING

    def begin_round(self) -> None:
        """Start a new round and rebuild the speed-ordered turn queue."""
        if self.is_over:
            return
        self.round += 1
        combatants = self.living_allies + self.living_enemies
        # Small random jitter breaks speed ties without making order feel
        # arbitrary - a much faster unit still always goes first.
        self.turn_order = sorted(
            combatants,
            key=lambda c: (-(c.derived_stats().speed + self.rng.uniform(0.0, 0.5)), c.name),
        )
        self._turn_index = 0
        self._say(f"-- Round {self.round} --", kind="system")

    @property
    def current_actor(self) -> Any | None:
        """Whose turn it is, skipping anyone who died earlier this round."""
        while self._turn_index < len(self.turn_order):
            actor = self.turn_order[self._turn_index]
            if actor.is_alive:
                return actor
            self._turn_index += 1
        return None

    @property
    def waiting_for_player(self) -> bool:
        """``True`` when the GUI should enable the action buttons."""
        return not self.is_over and self.current_actor is self.player

    def _advance(self) -> None:
        """Finish the current turn; roll into the next round when exhausted."""
        self._turn_index += 1
        if self.current_actor is None and not self.is_over:
            self.end_round()

    # ------------------------------------------------------------------
    # Player actions
    # ------------------------------------------------------------------
    def player_attack(self, target: Any | None = None) -> bool:
        """Basic attack - the free action always available.

        Implemented as the player's core skill when they have one, so the
        "basic attack" is itself just data.
        """
        core_id = self.player.class_def.core_skill_id
        skill = self.player.known_skills.get(core_id)
        if skill is None:
            usable = self.player.usable_skills()
            skill = next((s for s in usable if s.mp_cost == 0), None)
        if skill is None:
            self._say("You have no attack available.", kind="system")
            return False
        return self.player_use_skill(skill, [target] if target else [])

    def player_use_skill(self, skill: Skill, targets: Sequence[Any] | None = None) -> bool:
        """Resolve the player's chosen skill.  Returns ``False`` if rejected."""
        if not self.waiting_for_player:
            return False

        chosen = list(targets or [])
        if not chosen and skill.needs_target_pick:
            living = self.living_enemies
            if not living:
                return False
            chosen = [living[0]]

        result = skill.use(self.player, chosen, self.ctx, allies=self.living_allies, enemies=self.living_enemies)
        if not result.success:
            self._say(result.failure_reason, kind="system")
            return False

        self._record(result)
        self._train_mastery(skill)
        self._after_action()
        return True

    def player_use_item(self, item_manager: Any, item_id: str, target: Any | None = None) -> bool:
        """Use a consumable.  Costs the player's turn, like any other action."""
        if not self.waiting_for_player:
            return False
        ok, messages = item_manager.use_consumable(
            self.player, item_id, self.ctx, [target] if target else [self.player]
        )
        for message in messages:
            self._say(message, kind="heal" if ok else "system")
        if not ok:
            return False
        self._after_action()
        return True

    def player_defend(self) -> bool:
        """Skip the turn to halve incoming damage until the next one."""
        if not self.waiting_for_player:
            return False
        from engine.skills.status import StatusEffect

        guard = StatusEffect(
            id="guard",
            name="Guard",
            duration=1,
            category="buff",
            source_name=self.player.name,
            description="Reduces incoming damage.",
        )
        guard.modifiers.add_pct("armor", 1.0)
        guard.modifiers.add_pct("magic_resist", 1.0)
        self.player.apply_status(guard)
        self._say(f"{self.player.name} braces for impact.", kind="status")
        self._after_action()
        return True

    def player_flee(self) -> bool:
        """Attempt to escape; failure still costs the turn.

        Chance scales with the speed difference so fleeing a much faster
        monster is genuinely risky.
        """
        if not self.waiting_for_player:
            return False
        if any(e.is_boss for e in self.living_enemies):
            self._say("You cannot flee from this battle!", kind="system")
            return False

        player_speed = self.player.derived_stats().speed
        enemy_speed = max((e.derived_stats().speed for e in self.living_enemies), default=0.0)
        chance = max(0.1, min(0.9, self.flee_base_chance + (player_speed - enemy_speed) * 0.02))

        if self.rng.chance(chance):
            self.state = CombatState.FLED
            self._say(f"{self.player.name} escaped!", kind="system")
            return True

        self._say("Escape failed!", kind="system")
        self._after_action()
        return False

    # ------------------------------------------------------------------
    # Enemy turns
    # ------------------------------------------------------------------
    def run_until_player_turn(self, max_iterations: int = 200) -> list[str]:
        """Advance the battle until the player must act (or it ends).

        The GUI calls this after every player action.  ``max_iterations`` is a
        safety net against a content bug where nobody can damage anybody.
        """
        produced: list[int] = [len(self.log)]
        iterations = 0
        while not self.is_over and not self.waiting_for_player and iterations < max_iterations:
            actor = self.current_actor
            if actor is None:
                self.end_round()
                iterations += 1
                continue
            self._take_ai_turn(actor)
            iterations += 1
        return [entry.text for entry in self.log[produced[0]:]]

    def _take_ai_turn(self, actor: Any) -> None:
        behavior = self.ai.get(getattr(actor, "ai_behavior_id", "aggressive"))
        foes = self.living_allies if actor in self.enemies else self.living_enemies
        friends = self.living_enemies if actor in self.enemies else self.living_allies

        decision = behavior.decide(actor, friends, foes, self.rng)
        if decision.pass_turn or decision.skill is None:
            if decision.note == "stunned":
                self._say(f"{actor.name} is stunned and cannot act.", kind="status")
            else:
                self._say(f"{actor.name} hesitates.", kind="info")
        else:
            result = decision.skill.use(actor, decision.targets, self.ctx, allies=friends, enemies=foes)
            if result.success:
                self._record(result)
            else:
                self._say(f"{actor.name} hesitates.", kind="info")

        self._after_action(actor)

    # ------------------------------------------------------------------
    # Shared turn plumbing
    # ------------------------------------------------------------------
    def _record(self, result: SkillUseResult) -> None:
        """Push a skill's results into the log with sensible tags."""
        self._say(f"{result.caster_name} uses {result.skill_name}.", kind="info")
        for effect_result in result.results:
            kind = {
                "damage": "damage",
                "miss": "info",
                "heal": "heal",
                "shield": "status",
                "status": "status",
                "resist": "status",
                "resource": "info",
            }.get(effect_result.kind, "info")
            self._say(effect_result.message, kind=kind)

    def _train_mastery(self, skill: Skill) -> None:
        """Mastery grows through use (bible section 14).

        The skill's own track wins; otherwise the equipped weapon's type is
        trained, so plain attacks still build weapon mastery.
        """
        track = skill.mastery_track or self.player.equipped_weapon_type()
        if not track or track == "unarmed":
            return
        promoted = self.player.train_mastery(track, self.mastery_per_action)
        self.rewards.mastery_gains[track] = self.rewards.mastery_gains.get(track, 0.0) + self.mastery_per_action
        if promoted:
            self._say(f"{track.title()} mastery increased to {promoted}!", kind="system")

    def _after_action(self, actor: Any | None = None) -> None:
        """Post-action upkeep: deaths, win/loss check, then next turn."""
        actor = actor or self.player
        self._collect_deaths()
        if self._check_end():
            return
        self._advance()

    def _collect_deaths(self) -> None:
        for entity in [*self.enemies, *self.allies]:
            if not entity.is_alive and not getattr(entity, "_death_logged", False):
                entity._death_logged = True
                self._say(f"{entity.name} is defeated!", kind="system")

    def _check_end(self) -> bool:
        if not self.living_enemies:
            self.state = CombatState.VICTORY
            self._finish_victory()
            return True
        if not self.player.is_alive:
            self.state = CombatState.DEFEAT
            self._say(f"{self.player.name} has fallen...", kind="system")
            return True
        return False

    def end_round(self) -> None:
        """End-of-round upkeep: DOT/HOT ticks and cooldown countdowns."""
        if self.is_over:
            return
        for entity in [*self.living_allies, *self.living_enemies]:
            report = entity.tick_status_effects()
            for message in report.messages:
                self._say(message, kind="status")
            if hasattr(entity, "tick_cooldowns"):
                entity.tick_cooldowns()

        self._collect_deaths()
        if self._check_end():
            return
        self.begin_round()

    # ------------------------------------------------------------------
    # Rewards
    # ------------------------------------------------------------------
    def _finish_victory(self) -> None:
        """Tally EXP, gold and loot, then apply them to the player."""
        total_exp = 0.0
        total_gold = 0
        drops: list[tuple[str, int]] = []

        for enemy in self.enemies:
            exp, gold = enemy.rewards()
            total_exp += exp
            total_gold += gold
            drops.extend(enemy.roll_loot(self.rng))

        self.rewards.exp = total_exp
        self.rewards.gold = total_gold
        self.rewards.items = drops

        self.player.inventory.add_gold(total_gold)
        level_report = self.player.gain_exp(total_exp)
        self.rewards.level_up_messages = level_report.messages

        self._say("Victory!", kind="system")
        self._say(f"Gained {total_exp:.0f} EXP and {total_gold} gold.", kind="system")
        for message in level_report.messages:
            self._say(message, kind="system")

    def grant_loot(self, item_manager: Any) -> list[str]:
        """Move rolled drops into the bag.

        Kept separate from ``_finish_victory`` so the engine core has no hard
        dependency on ItemManager - the caller decides when loot is collected.
        """
        if not self.rewards.items:
            return []
        lines = item_manager.grant_many(self.player.inventory, self.rewards.items)
        for line in lines:
            self._say(f"Obtained {line}.", kind="system")
        return lines

    # ------------------------------------------------------------------
    # Presentation
    # ------------------------------------------------------------------
    def enemy_lines(self) -> list[str]:
        """``Slime A: 12/30 HP`` rows for the combat screen's target list."""
        lines = []
        for enemy in self.enemies:
            if enemy.is_alive:
                status = f" [{', '.join(enemy.status_summaries())}]" if enemy.statuses else ""
                lines.append(f"{enemy.name}: {enemy.hp_text()} HP{status}")
            else:
                lines.append(f"{enemy.name}: defeated")
        return lines

    def player_lines(self) -> list[str]:
        lines = [
            f"HP: {self.player.hp_text()}",
            f"MP: {self.player.mp_text()}",
            f"Round: {self.round}",
        ]
        if self.player.statuses:
            lines.append("Status: " + ", ".join(self.player.status_summaries()))
        return lines
