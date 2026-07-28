"""Settings - version info, content diagnostics, and save-file location.

Deliberately read-mostly.  Any true gameplay option belongs in
``data/config.json`` where the engine reads it, not in UI state.
"""

from __future__ import annotations

import tkinter as tk

from engine.game import GAME_VERSION
from gui import theme
from gui.widgets import StatPanel

__all__ = ["SettingsWindow"]


class SettingsWindow(tk.Toplevel):
    """Diagnostics and paths."""

    def __init__(self, app) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app

        theme.style_window(self, "Project Ascension - Settings")
        theme.center_window(self, 520, 460)
        self.transient(app.root)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        theme.heading_label(body, text="Settings").pack(anchor="w", pady=(0, 12))

        self.info = StatPanel(body, title="")
        self.info.pack(fill=tk.BOTH, expand=True)

        theme.body_label(
            body,
            text="Gameplay values are defined in data/config.json.",
            fg=theme.FG_DIM,
            font=theme.FONT_SMALL,
        ).pack(anchor="w", pady=(12, 0))

        buttons = tk.Frame(body, bg=theme.BG)
        buttons.pack(fill=tk.X, pady=(16, 0))
        theme.flat_button(buttons, "Close", self._close, width=10).pack(side=tk.RIGHT)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        game = self.app.game
        lines = [
            f"Version: {GAME_VERSION}",
            "",
            "Content:",
            *[f"  {line}" for line in game.content_summary()],
            "",
            f"Data folder: {game.loader.data_dir}",
            f"Save folder: {game.saves.save_dir}",
            f"Saves on disk: {len(game.save_slots())}",
        ]
        if game.current_slot:
            lines.append(f"Current slot: {game.current_slot}")
        self.info.set_lines(lines)

    def _close(self) -> None:
        self.app.close_toplevel("settings")
