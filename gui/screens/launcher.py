"""Launcher - the first screen (bible section 7).

Title block, version string, content diagnostics, and a way in.  Kept
deliberately sparse: the style reference calls for a large title, a small
version label, and a flat button stack with generous spacing.
"""

from __future__ import annotations

import tkinter as tk

from engine.game import GAME_VERSION
from gui import theme
from gui.widgets import ButtonStack, StatPanel

__all__ = ["LauncherScreen"]


class LauncherScreen(tk.Frame):
    """Startup screen with content diagnostics."""

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=theme.BG)
        self.app = app

        body = tk.Frame(self, bg=theme.BG)
        body.pack(expand=True)

        theme.title_label(body, text="PROJECT ASCENSION").pack(pady=(0, 6))
        theme.body_label(
            body, text=f"Version {GAME_VERSION}", fg=theme.FG_DIM, anchor="center"
        ).pack()

        diagnostics = StatPanel(body, title="")
        diagnostics.set_lines(["Content loaded:", *self.app.game.content_summary()])
        diagnostics.pack(pady=(30, 24))

        stack = ButtonStack(body, spacing=8, width=26)
        stack.add("continue", "Continue", self._continue)
        stack.add("exit", "Exit", self.app.quit)
        stack.pack()

        self.app.notify("Ready.")

    def _continue(self) -> None:
        self.app.show_main_menu()

    def refresh(self) -> None:
        """Nothing here changes at runtime, but the app calls it uniformly."""
