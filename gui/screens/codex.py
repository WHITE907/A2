"""Codex - achievements and discovery tracking."""

from __future__ import annotations

import tkinter as tk

from gui import theme
from gui.widgets import StatPanel

__all__ = ["CodexWindow"]


class CodexWindow(tk.Toplevel):
    """Shows achievements and discovery stats."""

    def __init__(self, app) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app

        theme.style_window(self, "Project Ascension - Codex")
        theme.center_window(self, 640, 580)
        self.transient(app.root)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        theme.heading_label(body, text="Codex & Achievements").pack(anchor="w", pady=(0, 10))

        self.panel = StatPanel(body, title="", wrap=580)
        self.panel.pack(fill=tk.BOTH, expand=True)

        buttons = tk.Frame(body, bg=theme.BG)
        buttons.pack(fill=tk.X, pady=(16, 0))
        theme.flat_button(buttons, "Close", self._close, width=10).pack(side=tk.RIGHT)

        self.refresh()

    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self.panel.set_lines(["No character loaded."])
            return
        # Codex lines from player
        lines = game.player.codex.summary_lines()
        # Add extra stats
        lines.append("")
        lines.append("--- Race & Class ---")
        lines.append(f"Race: {game.player.race_def.name} ({game.player.sub_race_id or 'no sub-race'})")
        lines.append(f"Class: {game.player.class_def.name} Tier {game.player.class_def.tier}")
        lines.append(f"Level: {game.player.level}")
        # Show party composition for party bonus context
        if hasattr(game.player, "party_races") and game.player.party_races:
            lines.append(f"Party races: {', '.join(game.player.party_races)}")
        self.panel.set_lines(lines)

    def _close(self) -> None:
        self.app.close_toplevel("codex")
