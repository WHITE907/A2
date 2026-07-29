"""Companion combat policy controls; the engine owns all decision rules."""

from __future__ import annotations

import tkinter as tk

from gui import theme
from gui.widgets import ButtonStack, StatPanel, SelectList


class TacticsWindow(tk.Toplevel):
    def __init__(self, app, companion_id: str) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app
        self.companion_id = companion_id
        theme.style_window(self, "Companion Tactics")
        theme.center_window(self, 560, 680)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)
        self.info = StatPanel(body, title="Policy")
        self.info.pack(fill=tk.X)

        # Skill priority list
        self.skill_list: SelectList[str] = SelectList(body, title="Skills (priority)", height=6, on_select=self._on_skill_select)
        self.skill_list.pack(fill=tk.X, pady=(12, 0))

        buttons = ButtonStack(body, spacing=4)
        buttons.add("stance", "Cycle Stance", self.cycle_stance)
        buttons.add("mp", "Toggle Preserve MP", self.toggle_mp)
        buttons.add("sp", "Toggle Preserve SP", self.toggle_sp)
        buttons.add("ultimate", "Cycle Ultimate Policy", self.cycle_ultimate)
        buttons.add("heal", "Cycle Healing Threshold", self.cycle_heal)
        buttons.add("heal_prio", "Cycle Heal Priority", self.cycle_heal_prio)
        buttons.add("protect_prio", "Cycle Protect Priority", self.cycle_protect_prio)
        buttons.add("cleanse", "Toggle Cleanse", self.toggle_cleanse)
        buttons.add("revive", "Toggle Revive", self.toggle_revive)
        buttons.add("boss", "Toggle Boss Focus", self.toggle_boss)
        buttons.add("racial", "Toggle Racial Skills", self.toggle_racial)
        buttons.add("racial_bonus", "Toggle Racial Bonus", self.toggle_racial_bonus)
        buttons.add("skill_up", "Increase Skill Priority", self.increase_skill_prio)
        buttons.add("skill_down", "Decrease Skill Priority", self.decrease_skill_prio)
        buttons.pack(fill=tk.X, pady=(12, 0))

        # Target selection
        target_frame = tk.Frame(body, bg=theme.BG)
        target_frame.pack(fill=tk.X, pady=(8, 0))
        theme.body_label(target_frame, text="Preferred Target (enemy id or empty):").pack(anchor="w")
        self.target_var = tk.StringVar(value="")
        tk.Entry(target_frame, textvariable=self.target_var, bg=theme.LISTBOX_BG, fg=theme.FG, insertbackground=theme.FG).pack(fill=tk.X, pady=(4, 0))
        theme.body_label(target_frame, text="Protect Target (ally id or name):").pack(anchor="w", pady=(6, 0))
        self.protect_var = tk.StringVar(value="")
        tk.Entry(target_frame, textvariable=self.protect_var, bg=theme.LISTBOX_BG, fg=theme.FG, insertbackground=theme.FG).pack(fill=tk.X, pady=(4, 0))
        theme.flat_button(target_frame, "Apply Targets", self.apply_targets).pack(anchor="e", pady=(6, 0))

        theme.flat_button(body, "Close", self.destroy).pack(anchor="e", pady=(16, 0))
        self.refresh()

    def member(self):
        return self.app.game.party.get(self.companion_id)

    def update(self, values: dict) -> None:
        self.app.game.set_companion_tactics(self.companion_id, values)
        self.refresh()

    def cycle_stance(self) -> None:
        values = ["aggressive", "tactical", "defensive", "opportunist", "berserk"]
        current = self.member().tactics.get("stance", "tactical")
        if current not in values:
            current = values[0]
        self.update({"stance": values[(values.index(current) + 1) % len(values)]})

    def toggle_mp(self) -> None:
        self.update({"preserve_mp": not self.member().tactics.get("preserve_mp", False)})

    def toggle_sp(self) -> None:
        self.update({"preserve_sp": not self.member().tactics.get("preserve_sp", False)})

    def cycle_ultimate(self) -> None:
        values = ["smart", "always", "never"]
        current = self.member().tactics.get("ultimate_policy", "smart")
        self.update({"ultimate_policy": values[(values.index(current) + 1) % len(values)]})

    def cycle_heal(self) -> None:
        values = [0.2, 0.3, 0.5, 0.7, 0.9]
        current = float(self.member().tactics.get("healing_threshold", 0.5))
        if current not in values:
            current = values[1]
        self.update({"healing_threshold": values[(values.index(current) + 1) % len(values)]})

    def cycle_heal_prio(self) -> None:
        values = [0.5, 1.0, 1.5, 2.0]
        current = float(self.member().tactics.get("heal_priority", 1.0))
        if current not in values:
            current = 1.0
        self.update({"heal_priority": values[(values.index(current) + 1) % len(values)]})

    def cycle_protect_prio(self) -> None:
        values = [1.0, 1.5, 2.0, 2.5]
        current = float(self.member().tactics.get("protect_priority", 1.5))
        if current not in values:
            current = 1.5
        self.update({"protect_priority": values[(values.index(current) + 1) % len(values)]})

    def toggle_cleanse(self) -> None:
        self.update({"allow_cleanse": not self.member().tactics.get("allow_cleanse", True)})

    def toggle_revive(self) -> None:
        self.update({"allow_revive": not self.member().tactics.get("allow_revive", True)})

    def toggle_boss(self) -> None:
        self.update({"boss_focus": not self.member().tactics.get("boss_focus", False)})

    def toggle_racial(self) -> None:
        self.update({"allow_racial_skills": not self.member().tactics.get("allow_racial_skills", True)})

    def toggle_racial_bonus(self) -> None:
        self.update({"racial_skill_bonus": not self.member().tactics.get("racial_skill_bonus", False)})

    def _on_skill_select(self, skill_id: str | None) -> None:
        self._selected_skill = skill_id

    def increase_skill_prio(self) -> None:
        skill_id = getattr(self, "_selected_skill", None) or (self.skill_list.selected_value)
        if not skill_id:
            return
        current = self.member().tactics.get("skill_priorities", {}).get(skill_id, 1.0)
        new = min(3.0, current + 0.5)
        prios = dict(self.member().tactics.get("skill_priorities", {}))
        prios[skill_id] = new
        self.update({"skill_priorities": prios})

    def decrease_skill_prio(self) -> None:
        skill_id = getattr(self, "_selected_skill", None) or (self.skill_list.selected_value)
        if not skill_id:
            return
        current = self.member().tactics.get("skill_priorities", {}).get(skill_id, 1.0)
        new = max(0.0, current - 0.5)
        prios = dict(self.member().tactics.get("skill_priorities", {}))
        prios[skill_id] = new
        self.update({"skill_priorities": prios})

    def apply_targets(self) -> None:
        self.update({
            "preferred_target": self.target_var.get().strip(),
            "protect_target": self.protect_var.get().strip(),
        })

    def refresh(self) -> None:
        companion = self.member()
        if companion is None:
            return
        tactics = companion.tactics
        # Sync target entries
        if not hasattr(self, "_targets_initialized"):
            self.target_var.set(str(tactics.get("preferred_target", "")))
            self.protect_var.set(str(tactics.get("protect_target", "")))
            self._targets_initialized = True

        # Skills list with priorities
        skills = companion.skills
        prios = tactics.get("skill_priorities") or {}
        items = []
        for s in skills:
            p = prios.get(s.id, 1.0)
            items.append((f"[{p:.1f}] {s.name} ({s.id})", s.id))
        self.skill_list.set_items(sorted(items))

        self.info.set_lines(
            [
                f"Companion: {companion.name} ({companion.definition.role})",
                f"Stance: {str(tactics.get('stance')).title()}",
                f"Preserve MP: {tactics.get('preserve_mp')} | Preserve SP: {tactics.get('preserve_sp')}",
                f"Ultimate: {str(tactics.get('ultimate_policy')).title()}",
                f"Heal below: {float(tactics.get('healing_threshold', 0.5)) * 100:.0f}% (prio {float(tactics.get('heal_priority',1.0)):.1f}x)",
                f"Protect: {tactics.get('protect_target') or 'Auto'} (prio {float(tactics.get('protect_priority',1.5)):.1f}x)",
                f"Cleanse: {tactics.get('allow_cleanse')} (prio {float(tactics.get('cleanse_priority',0.7)):.1f}) | Revive: {tactics.get('allow_revive')} (prio {float(tactics.get('revive_priority',1.0)):.1f})",
                f"Boss Focus: {tactics.get('boss_focus')} | Racial: {tactics.get('allow_racial_skills')} (bonus {tactics.get('racial_skill_bonus')})",
                f"Preferred target: {tactics.get('preferred_target') or 'Automatic'}",
                f"Resource preservation threshold: {float(tactics.get('resource_preservation',0.4))*100:.0f}%",
            ]
        )
