"""Combat screen.

Two Listboxes hold an independent selection at the same time here - the Action
list and the Target list.  docs/GUI_VERIFICATION.md documents exactly this
case: ``tk.Listbox`` defaults to ``exportselection=True``, which ties selection
to the X PRIMARY clipboard, so the second list silently steals it from the
first and ``curselection()`` on the first returns ``()``.  Both lists are built
through :func:`gui.theme.stat_listbox`, which sets ``exportselection=False`` by
default, so the conflict cannot occur.

The screen holds no combat rules.  It reads ``battle.waiting_for_player`` to
decide whether buttons are live and calls engine methods for everything else.
"""

from __future__ import annotations

import tkinter as tk

from engine.entities.enemy import Enemy
from engine.skills.skill import Skill, SkillTargeting
from gui import theme
from gui.widgets import ScrollableFrame, ButtonStack, LogPanel, SelectList, StatPanel

__all__ = ["CombatScreen"]

#: Sentinel row for the always-available basic attack.
ATTACK = "__attack__"

#: An action row is either the basic-attack sentinel or a real Skill.
Action = "Skill | str"


class CombatScreen(tk.Frame):
    """Turn-based battle UI."""

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self.battle = app.game.battle
        self._logged_entries = 0

        # Long party/enemy rosters can exceed a compact display, so combat
        # keeps its complete control layout reachable through the page scroll.
        self.viewport = ScrollableFrame(self, bg=theme.BG, padx=16, pady=14)
        self.viewport.pack(fill=tk.BOTH, expand=True)
        outer = self.viewport.content

        # ---------------- left: player + enemies -----------------------
        left = tk.Frame(outer, bg=theme.BG, width=250)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        self.player_panel = StatPanel(left, title="You", wrap=225)
        self.player_panel.pack(fill=tk.X, anchor="n")

        self.ally_panel = StatPanel(left, title="Allies", wrap=225)
        self.ally_panel.pack(fill=tk.X, anchor="n", pady=(12, 0))

        self.enemy_panel = StatPanel(left, title="Enemies", wrap=225)
        self.enemy_panel.pack(fill=tk.X, anchor="n", pady=(12, 0))

        self.turn_panel = StatPanel(left, title="Turn Order", wrap=225)
        self.turn_panel.pack(fill=tk.X, anchor="n", pady=(12, 0))

        self.boss_panel = StatPanel(left, title="Boss", wrap=225)
        # boss panel packed only when needed

        # ---------------- middle: log ----------------------------------
        middle = tk.Frame(outer, bg=theme.BG)
        middle.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=18)

        self.log = LogPanel(middle, title="Battle Log", height=20)
        self.log.pack(fill=tk.BOTH, expand=True)

        # ---------------- right: actions + targets ---------------------
        right = tk.Frame(outer, bg=theme.BG, width=250)
        right.pack(side=tk.LEFT, fill=tk.Y)
        right.pack_propagate(False)

        # Listbox #1 of 2 that hold simultaneous selections.
        self.action_list: SelectList["Skill | str"] = SelectList(
            right, title="Actions", height=8, on_select=self._on_action_selected
        )
        self.action_list.pack(fill=tk.X)

        # Listbox #2 - see the module docstring on exportselection.
        self.target_list: SelectList[Enemy] = SelectList(right, title="Target", height=5)
        self.target_list.pack(fill=tk.X, pady=(12, 0))

        self.buttons = ButtonStack(right, spacing=5)
        self.buttons.add("confirm", "Use Selected", self._use_selected)
        self.buttons.add("defend", "Defend", self._defend)
        self.buttons.add("item", "Use Item", self._use_item)
        self.buttons.add("flee", "Flee", self._flee)
        self.buttons.pack(fill=tk.X, pady=(12, 0))

        self.continue_button = theme.flat_button(right, "Continue", self._finish)

        self._sync_log()
        self.refresh()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        battle = self.app.game.battle
        if battle is None:
            self.app.show_world()
            return
        self.battle = battle

        self.player_panel.set_lines(battle.player_lines())
        self.ally_panel.set_lines(battle.ally_lines())
        self.enemy_panel.set_lines(battle.enemy_lines())

        # Turn order
        try:
            order = getattr(battle, "turn_order", [])
            current = getattr(battle, "current_actor", None)
            lines = ["Turn Order:"]
            for idx, actor in enumerate(order[:8]):  # show first 8
                marker = ">> " if actor is current else "   "
                name = getattr(actor, "name", str(actor))
                # Show speed for clarity
                try:
                    spd = actor.derived_stats().speed
                    lines.append(f"{marker}{name} (Spd {spd:.0f})")
                except Exception:
                    lines.append(f"{marker}{name}")
            # Next round indicator
            if len(order) > 8:
                lines.append(f"  ... +{len(order)-8} more this round")
            self.turn_panel.set_lines(lines)
        except Exception:
            self.turn_panel.set_lines(["Turn Order: (unavailable)"])

        # Boss info
        bosses = [e for e in battle.living_enemies if getattr(e, "is_boss", False)]
        if bosses:
            boss = bosses[0]
            try:
                phase = getattr(boss, "boss_phase", 0)
                template = getattr(boss, "template", None)
                phases = getattr(template, "boss_phases", []) if template else []
                phase_name = phases[phase].get("name", f"Phase {phase+1}") if phase < len(phases) else f"Phase {phase+1}"
                lines = [f"{boss.name}", f"Phase {phase+1}: {phase_name}", f"HP: {boss.hp_text()}"]
                # Enrage?
                if getattr(boss, "_enraged", False):
                    lines.append("ENRAGED!")
                # Telegraph pending?
                pending = getattr(battle, "_telegraph_pending", {}).get(boss)
                if pending:
                    lines.append(f"Telegraph: {pending.get('warning','Incoming!')[:40]}")
                self.boss_panel.set_lines(lines)
                if not self.boss_panel.winfo_ismapped():
                    self.boss_panel.pack(fill=tk.X, anchor="n", pady=(12, 0))
            except Exception:
                self.boss_panel.set_lines([f"{bosses[0].name}"])
                if not self.boss_panel.winfo_ismapped():
                    self.boss_panel.pack(fill=tk.X, anchor="n", pady=(12, 0))
        else:
            if self.boss_panel.winfo_ismapped():
                self.boss_panel.pack_forget()

        self._sync_log()

        if battle.is_over:
            self._show_end_state()
            return

        # Actions: the player's usable skills, plus a free basic attack.
        actions: list[tuple[str, "Skill | str"]] = [("Attack", ATTACK)]
        for skill in self.app.game.player.usable_skills():
            ok, reason = skill.can_use(self.app.game.player)
            suffix = "" if ok else f"  (unavailable: {reason})"
            # Clearly mark ancestry techniques without reducing their names to
            # generic "Race Gift" labels.
            racial_tag = " [ancestry]" if skill.id.startswith("racial_") else ""
            actions.append((f"{skill.name}{racial_tag} - {skill.cost_text()}{suffix}", skill))
        self.action_list.set_items(actions)

        self._refresh_target_list(keep_selection=True)

        living = battle.living_enemies
        waiting = battle.waiting_for_player
        self.buttons.set_all_enabled(waiting)
        self.buttons.set_enabled("flee", waiting and not any(e.is_boss for e in living))
        if self.continue_button.winfo_ismapped():
            self.continue_button.pack_forget()

    def _show_end_state(self) -> None:
        """Battle finished: swap the action buttons for a Continue button."""
        self.buttons.set_all_enabled(False)
        self.target_list.clear()
        if not self.continue_button.winfo_ismapped():
            self.continue_button.pack(fill=tk.X, pady=(12, 0))

    def _sync_log(self) -> None:
        """Append only entries the panel has not shown yet.

        Re-rendering the whole log every refresh would reset the scroll
        position on every action.
        """
        battle = self.app.game.battle
        if battle is None:
            return
        for entry in battle.log[self._logged_entries:]:
            self.log.append(entry.text, entry.kind)
        self._logged_entries = len(battle.log)

    def _refresh_target_list(self, keep_selection: bool = False) -> None:
        """Display targets valid for the currently selected action.

        Previously this list always contained enemies, which made ally-targeted
        skills appear unusable even though the engine already supported them.
        Keeping this decision in the presentation layer also preserves the
        engine/UI boundary: the engine remains authoritative when the action
        is resolved.
        """
        battle = self.app.game.battle
        if battle is None:
            return
        action = self.action_list.selected_value
        if isinstance(action, Skill):
            if action.targeting == SkillTargeting.ALLY:
                targets = battle.living_allies
            elif action.targeting == SkillTargeting.SELF:
                targets = [battle.player]
            elif action.targeting == SkillTargeting.ALL_ALLIES:
                targets = battle.living_allies
            else:
                targets = battle.living_enemies
        else:
            targets = battle.living_enemies
        # Add HP% for target selection clarity
        rows = []
        for target in targets:
            try:
                hp_pct = f"{target.hp_fraction*100:.0f}%"
                rows.append((f"{target.name} [{hp_pct}] {target.hp_text()}", target))
            except Exception:
                rows.append((target.name, target))
        self.target_list.set_items(rows, keep_selection=keep_selection)

    def _on_action_selected(self, value: "Skill | str") -> None:
        """Show what the highlighted skill does and update valid targets."""
        self._refresh_target_list(keep_selection=False)
        if isinstance(value, str):  # the ATTACK sentinel
            self.app.notify("Basic attack with your equipped weapon.")
            return
        # Show detailed effect lines including tags
        lines = value.effect_lines()
        if getattr(value, "tags", None):
            lines.append(f"Tags: {', '.join(value.tags)}")
        self.app.notify(" | ".join(lines))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _after_player_action(self, acted: bool) -> None:
        """Let the AI take its turns, then redraw."""
        if acted:
            self.app.game.battle.run_until_player_turn()
        self.refresh()

    def _use_selected(self) -> None:
        battle = self.app.game.battle
        if battle is None or not battle.waiting_for_player:
            return

        action = self.action_list.selected_value
        target = self.target_list.selected_value

        if action is None:
            self.app.notify("Choose an action.")
            return
        if isinstance(action, str):  # the ATTACK sentinel
            acted = battle.player_attack(target)
        else:
            targets = [target] if (target is not None and action.needs_target_pick) else []
            acted = battle.player_use_skill(action, targets)

        self._after_player_action(acted)

    def _defend(self) -> None:
        battle = self.app.game.battle
        if battle and battle.waiting_for_player:
            self._after_player_action(battle.player_defend())

    def _flee(self) -> None:
        battle = self.app.game.battle
        if battle is None or not battle.waiting_for_player:
            return
        fled = battle.player_flee()
        if fled:
            self.refresh()
        else:
            self._after_player_action(True)

    def _use_item(self) -> None:
        """Pick a consumable from the bag and use it as this turn's action."""
        battle = self.app.game.battle
        if battle is None or not battle.waiting_for_player:
            return

        entries = self.app.game.inventory_entries("consumable")
        if not entries:
            self.app.notify("No usable items.")
            return

        window = tk.Toplevel(self.app.root, bg=theme.BG)
        theme.style_window(window, "Use Item")
        theme.center_window(window, 360, 340)
        window.transient(self.app.root)

        viewport = ScrollableFrame(window, bg=theme.BG, padx=16, pady=14)
        viewport.pack(fill=tk.BOTH, expand=True)
        frame = viewport.content
        theme.heading_label(frame, text="Use Item").pack(anchor="w", pady=(0, 8))

        # Show rarity colors for consumables too
        picker: SelectList[str] = SelectList(frame, height=8)
        rarity_cfg = self.app.game.config.get("rarities") or {}
        rows = [(f"[{e.item.rarity_label}] {e.label()}", e.item.id) for e in entries]
        colors = [rarity_cfg.get(e.item.rarity.lower(), {}).get("color", theme.FG) for e in entries]
        picker.set_items(rows)
        picker.set_row_colors(colors)
        picker.pack(fill=tk.BOTH, expand=True)

        def confirm() -> None:
            item_id = picker.selected_value
            window.destroy()
            if item_id is None:
                return
            acted = self.app.game.battle.player_use_item(self.app.game.items, item_id)
            self._after_player_action(acted)

        theme.flat_button(frame, "Use", confirm).pack(fill=tk.X, pady=(12, 0))

    # ------------------------------------------------------------------
    def _finish(self) -> None:
        """Collect rewards and return to the world."""
        lines = self.app.game.finish_battle()
        for line in lines:
            self.log.append(line, "system")
        if lines:
            self.app.notify(lines[0])
        self.app.show_world()
