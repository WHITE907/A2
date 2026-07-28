"""Companion combat policy controls; the engine owns all decision rules."""

from __future__ import annotations

import tkinter as tk

from gui import theme
from gui.widgets import ButtonStack, StatPanel


class TacticsWindow(tk.Toplevel):
    def __init__(self, app, companion_id: str) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app
        self.companion_id = companion_id
        theme.style_window(self, "Companion Tactics")
        theme.center_window(self, 440, 520)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)
        self.info = StatPanel(body, title="Policy")
        self.info.pack(fill=tk.X)
        buttons = ButtonStack(body, spacing=6)
        buttons.add("stance", "Cycle Stance", self.cycle_stance)
        buttons.add("mp", "Toggle Preserve MP", self.toggle_mp)
        buttons.add("ultimate", "Cycle Ultimate Policy", self.cycle_ultimate)
        buttons.add("heal", "Cycle Healing Threshold", self.cycle_heal)
        buttons.pack(fill=tk.X, pady=(12, 0))
        theme.flat_button(body, "Close", self.destroy).pack(anchor="e", pady=(16, 0))
        self.refresh()

    def member(self):
        return self.app.game.party.get(self.companion_id)

    def update(self, values: dict) -> None:
        self.app.game.set_companion_tactics(self.companion_id, values)
        self.refresh()

    def cycle_stance(self) -> None:
        values = ["aggressive", "tactical", "defensive"]
        current = self.member().tactics.get("stance", "tactical")
        self.update({"stance": values[(values.index(current) + 1) % len(values)]})

    def toggle_mp(self) -> None:
        self.update({"preserve_mp": not self.member().tactics.get("preserve_mp", False)})

    def cycle_ultimate(self) -> None:
        values = ["smart", "always", "never"]
        current = self.member().tactics.get("ultimate_policy", "smart")
        self.update({"ultimate_policy": values[(values.index(current) + 1) % len(values)]})

    def cycle_heal(self) -> None:
        values = [0.3, 0.5, 0.7, 0.9]
        current = float(self.member().tactics.get("healing_threshold", 0.5))
        self.update({"healing_threshold": values[(values.index(current) + 1) % len(values)]})

    def refresh(self) -> None:
        companion = self.member()
        if companion is None:
            return
        tactics = companion.tactics
        self.info.set_lines(
            [
                f"Companion: {companion.name}",
                f"Stance: {str(tactics.get('stance')).title()}",
                f"Preserve MP: {tactics.get('preserve_mp')}",
                f"Ultimate: {str(tactics.get('ultimate_policy')).title()}",
                f"Heal below: {float(tactics.get('healing_threshold', 0.5)) * 100:.0f}%",
                f"Preferred target: {tactics.get('preferred_target') or 'Automatic'}",
                f"Protect: {tactics.get('protect_target') or 'Automatic'}",
            ]
        )
