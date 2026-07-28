"""The Tkinter application shell.

Screen model, following docs/GUI_STYLE_REFERENCE.md:

- The **main window** hosts the primary screens (Launcher, Main Menu, World,
  Combat) by swapping one frame for another.
- **Sub-screens** (Save Browser, Character Creation, Inventory, Equipment,
  Skills, Status, Settings, Shop, Talk) open as separate ``Toplevel`` windows
  layered over the main window, which stays visible behind them.

Bible section 5/18: nothing in this package computes gameplay values.  Screens
call :class:`engine.game.Game` and display what it returns.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable

from engine.game import GAME_VERSION, Game
from gui import theme
from gui.widgets import StatusBar

__all__ = ["AscensionApp", "run"]

WINDOW_WIDTH = 1040
WINDOW_HEIGHT = 700


class AscensionApp:
    """Owns the root window, the active screen, and the shared Game."""

    def __init__(self, root: tk.Tk, game: Game) -> None:
        self.root = root
        self.game = game
        #: Open Toplevel sub-screens, keyed by name so one instance is reused
        #: rather than stacking duplicates when a button is pressed twice.
        self._toplevels: dict[str, tk.Toplevel] = {}
        self._current_screen: Any = None

        theme.style_window(root, "Project Ascension")
        theme.center_window(root, WINDOW_WIDTH, WINDOW_HEIGHT)
        root.minsize(900, 620)
        root.protocol("WM_DELETE_WINDOW", self.quit)

        # Layout: content area, then status bar, then the accent line last so
        # it sits flush against the very bottom edge.
        self.container = tk.Frame(root, bg=theme.BG)
        self.container.pack(fill=tk.BOTH, expand=True)

        self.status_bar = StatusBar(root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        theme.accent_strip(root).pack(fill=tk.X, side=tk.BOTTOM)

        self.show_launcher()

    # ------------------------------------------------------------------
    # Screen management
    # ------------------------------------------------------------------
    def _swap(self, screen_factory: Callable[[tk.Misc, "AscensionApp"], Any]) -> Any:
        """Replace the main-window screen."""
        self.close_all_toplevels()
        if self._current_screen is not None:
            self._current_screen.destroy()
        self._current_screen = screen_factory(self.container, self)
        self._current_screen.pack(fill=tk.BOTH, expand=True)
        return self._current_screen

    @property
    def current_screen(self) -> Any:
        return self._current_screen

    def show_launcher(self) -> Any:
        from gui.screens.launcher import LauncherScreen

        return self._swap(LauncherScreen)

    def show_main_menu(self) -> Any:
        from gui.screens.main_menu import MainMenuScreen

        return self._swap(MainMenuScreen)

    def show_world(self) -> Any:
        from gui.screens.world_screen import WorldScreen

        return self._swap(WorldScreen)

    def show_combat(self) -> Any:
        from gui.screens.combat_screen import CombatScreen

        return self._swap(CombatScreen)

    # ------------------------------------------------------------------
    # Toplevel sub-screens
    # ------------------------------------------------------------------
    def open_toplevel(self, name: str, factory: Callable[["AscensionApp"], tk.Toplevel]) -> tk.Toplevel:
        """Open (or refocus) a named sub-window.

        Reusing an existing window rather than opening a second copy is what
        keeps repeated button presses from burying the main menu under a stack
        of identical dialogs.
        """
        existing = self._toplevels.get(name)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_set()
            return existing

        window = factory(self)
        self._toplevels[name] = window
        window.protocol("WM_DELETE_WINDOW", lambda: self.close_toplevel(name))
        return window

    def close_toplevel(self, name: str) -> None:
        window = self._toplevels.pop(name, None)
        if window is not None and window.winfo_exists():
            window.destroy()

    def close_all_toplevels(self) -> None:
        for name in list(self._toplevels):
            self.close_toplevel(name)

    def open_save_browser(self, mode: str = "load") -> tk.Toplevel:
        """``mode`` is ``"load"``, ``"save"`` or ``"delete"``."""
        from gui.screens.save_browser import SaveBrowserWindow

        self.close_toplevel("save_browser")
        return self.open_toplevel("save_browser", lambda app: SaveBrowserWindow(app, mode=mode))

    def open_character_creation(self) -> tk.Toplevel:
        from gui.screens.character_creation import CharacterCreationWindow

        return self.open_toplevel("character_creation", CharacterCreationWindow)

    def open_inventory(self) -> tk.Toplevel:
        from gui.screens.inventory import InventoryWindow

        return self.open_toplevel("inventory", InventoryWindow)

    def open_equipment(self) -> tk.Toplevel:
        from gui.screens.equipment import EquipmentWindow

        return self.open_toplevel("equipment", EquipmentWindow)

    def open_skills(self) -> tk.Toplevel:
        from gui.screens.skills import SkillsWindow

        return self.open_toplevel("skills", SkillsWindow)

    def open_status(self) -> tk.Toplevel:
        from gui.screens.status import StatusWindow

        return self.open_toplevel("status", StatusWindow)

    def open_quests(self) -> tk.Toplevel:
        from gui.screens.quests import QuestWindow

        return self.open_toplevel("quests", QuestWindow)

    def open_party(self) -> tk.Toplevel:
        from gui.screens.party import PartyWindow

        return self.open_toplevel("party", PartyWindow)

    def open_settings(self) -> tk.Toplevel:
        from gui.screens.settings import SettingsWindow

        return self.open_toplevel("settings", SettingsWindow)

    def open_shop(self, shop_id: str) -> tk.Toplevel:
        from gui.screens.shop import ShopWindow

        self.close_toplevel("shop")
        return self.open_toplevel("shop", lambda app: ShopWindow(app, shop_id))

    def open_talk(self, npc_id: str) -> tk.Toplevel:
        from gui.screens.talk import TalkWindow

        self.close_toplevel("talk")
        return self.open_toplevel("talk", lambda app: TalkWindow(app, npc_id))

    # ------------------------------------------------------------------
    # Shared helpers used by screens
    # ------------------------------------------------------------------
    def notify(self, message: str) -> None:
        """Show a transient one-line notice in the status bar."""
        self.status_bar.show(message)

    def report(self, ok: bool, message: str) -> bool:
        """Display the ``(ok, message)`` tuple engine calls return."""
        self.notify(message)
        return ok

    def refresh_active(self) -> None:
        """Ask the current screen and every open sub-window to redraw.

        Called after any action that changes player state, so an open Status
        window updates the moment gear is equipped in another window.
        """
        if self._current_screen is not None and hasattr(self._current_screen, "refresh"):
            self._current_screen.refresh()
        for window in list(self._toplevels.values()):
            if window.winfo_exists() and hasattr(window, "refresh"):
                window.refresh()

    def confirm(self, title: str, question: str) -> bool:
        return messagebox.askyesno(title, question, parent=self.root)

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message, parent=self.root)

    def show_info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message, parent=self.root)

    # ------------------------------------------------------------------
    def quit(self) -> None:
        self.close_all_toplevels()
        self.root.destroy()


def run(data_dir: str | None = None, save_dir: str | None = None, seed: int | None = None) -> None:
    """Entry point used by ``main.py``.

    Content is loaded *before* the window appears so a broken JSON file
    produces a clear error dialog instead of a half-built UI.
    """
    game = Game(data_dir=data_dir, save_dir=save_dir, seed=seed)

    root = tk.Tk()
    try:
        game.load_content()
    except Exception as exc:  # noqa: BLE001 - surfaced to the player verbatim
        root.withdraw()
        messagebox.showerror("Project Ascension - Content Error", str(exc))
        root.destroy()
        return

    AscensionApp(root, game)
    root.mainloop()
