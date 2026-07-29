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
from gui.widgets import ButtonStack, LogPanel, SelectList, StatPanel

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

        outer = tk.Frame(self, bg=theme.BG, padx=16, pady=14)
        outer.pack(fill=tk.BOTH, expand=True)

        # ---------------- left: player + enemies -----------------------
        left = tk.Frame(outer, bg=theme.BG, width=240)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        self.player_panel = StatPanel(left, title="You", wrap=215)
        self.player_panel.pack(fill=tk.X, anchor="n")

        self.ally_panel = StatPanel(left, title="Allies", wrap=215)
        self.ally_panel.pack(fill=tk.X, anchor="n", pady=(16, 0))

        self.enemy_panel = StatPanel(left, title="Enemies", wrap=215)
        self.enemy_panel.pack(fill=tk.X, anchor="n", pady=(16, 0))

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
        self._sync_log()

        if battle.is_over:
            self._show_end_state()
            return

        # Actions: the player's usable skills, plus a free basic attack.
        actions: list[tuple[str, "Skill | str"]] = [("Attack", ATTACK)]
        for skill in self.app.game.player.usable_skills():
            ok, _ = skill.can_use(self.app.game.player)
            suffix = "" if ok else "  (unavailable)"
            actions.append((f"{skill.name} - {skill.cost_text()}{suffix}", skill))
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
        self.target_list.set_items([(target.name, target) for target in targets], keep_selection=keep_selection)

    def _on_action_selected(self, value: "Skill | str") -> None:
        """Show what the highlighted skill does and update valid targets."""
        self._refresh_target_list(keep_selection=False)
        if isinstance(value, str):  # the ATTACK sentinel
            self.app.notify("Basic attack with your equipped weapon.")
            return
        self.app.notify(" | ".join(value.effect_lines()))

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
        theme.center_window(window, 320, 300)
        window.transient(self.app.root)

        frame = tk.Frame(window, bg=theme.BG, padx=16, pady=14)
        frame.pack(fill=tk.BOTH, expand=True)
        theme.heading_label(frame, text="Use Item").pack(anchor="w", pady=(0, 8))

        picker: SelectList[str] = SelectList(frame, height=7)
        picker.set_items([(entry.label(), entry.item.id) for entry in entries])
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
