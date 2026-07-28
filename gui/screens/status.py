"""Status - the full character sheet, plus stat-point allocation."""

from __future__ import annotations

import tkinter as tk

from engine.stats import PRIMARY_STATS, PRIMARY_STAT_NAMES
from gui import theme
from gui.widgets import StatPanel

__all__ = ["StatusWindow"]


class StatusWindow(tk.Toplevel):
    """Character sheet with ``+`` buttons for unspent stat points."""

    def __init__(self, app) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app

        theme.style_window(self, "Project Ascension - Status")
        theme.center_window(self, 560, 620)
        self.transient(app.root)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        theme.heading_label(body, text="Status").pack(anchor="w", pady=(0, 10))

        self.sheet = StatPanel(body, title="")
        self.sheet.pack(fill=tk.BOTH, expand=True)

        # -- allocation ---------------------------------------------------
        theme.heading_label(body, text="Allocate Points").pack(anchor="w", pady=(14, 6))
        self.points_label = theme.body_label(body, text="", fg=theme.FG_DIM)
        self.points_label.pack(anchor="w", pady=(0, 6))

        allocate = tk.Frame(body, bg=theme.BG)
        allocate.pack(fill=tk.X)
        self.allocate_buttons: dict[str, tk.Button] = {}
        for stat in PRIMARY_STATS:
            button = theme.flat_button(
                allocate,
                f"+ {stat}",
                lambda s=stat: self._allocate(s),
                width=7,
            )
            button.pack(side=tk.LEFT, padx=(0, 6))
            self.allocate_buttons[stat] = button

        theme.flat_button(body, "Close", self._close, width=10).pack(anchor="e", pady=(16, 0))

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self._close()
            return

        self.sheet.set_lines(game.status_lines())

        available = game.player.unspent_stat_points
        self.points_label.configure(text=f"Unspent stat points: {available}")
        for button in self.allocate_buttons.values():
            button.configure(state=tk.NORMAL if available > 0 else tk.DISABLED)

    def _allocate(self, stat: str) -> None:
        ok, message = self.app.game.allocate_stat(stat, 1)
        self.app.notify(message)
        self.app.refresh_active()

    def _close(self) -> None:
        self.app.close_toplevel("status")
