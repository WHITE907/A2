"""Main Menu - the screen the style reference was captured from.

Layout, verbatim from docs/GUI_STYLE_REFERENCE.md:

- Large bold title with a small version label beneath it
- A large gap, then a vertical stack of full-width flat buttons
  (New Game, Load Game, Delete Save, Exit) with generous spacing
- A small stacked ``key: value`` preview of the loaded character
- Sub-screens open as Toplevel windows over this one, which stays visible
"""

from __future__ import annotations

import tkinter as tk

from engine.game import GAME_VERSION
from gui import theme
from gui.widgets import ButtonStack, StatPanel

__all__ = ["MainMenuScreen"]


class MainMenuScreen(tk.Frame):
    """New Game / Load Game / Delete Save / Exit."""

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=theme.BG)
        self.app = app

        body = tk.Frame(self, bg=theme.BG)
        body.pack(expand=True)

        theme.title_label(body, text="Project Ascension").pack(pady=(0, 4))
        theme.body_label(
            body, text=f"Version {GAME_VERSION}", fg=theme.FG_DIM, anchor="center"
        ).pack()

        # The style reference calls for a large gap here, not a crowded stack.
        self.stack = ButtonStack(body, spacing=7, width=24)
        self.stack.add("new", "New Game", self.app.open_character_creation)
        self.stack.add("load", "Load Game", lambda: self.app.open_save_browser("load"))
        self.stack.add("delete", "Delete Save", lambda: self.app.open_save_browser("delete"))
        self.stack.add("settings", "Settings", self.app.open_settings)
        self.stack.add("exit", "Exit", self.app.quit)
        self.stack.pack(pady=(46, 0))

        self.preview = StatPanel(body, title="")
        self.preview.pack(pady=(28, 0))

        self.continue_button = theme.flat_button(body, "Continue Adventure", self._continue, width=24)

        self.refresh()

    # ------------------------------------------------------------------
    def _continue(self) -> None:
        if self.app.game.has_character:
            self.app.show_world()

    def refresh(self) -> None:
        """Show the active character, or a hint when there is none."""
        game = self.app.game
        if game.has_character:
            self.preview.set_lines(game.player_summary())
            if not self.continue_button.winfo_ismapped():
                self.continue_button.pack(pady=(22, 0))
        else:
            self.preview.set_lines(["No character loaded.", "Start a new game or load a save."])
            if self.continue_button.winfo_ismapped():
                self.continue_button.pack_forget()

        self.stack.set_enabled("delete", bool(game.save_slots()))
        self.stack.set_enabled("load", bool(game.save_slots()))
