"""Save Browser - Load / Save / Delete, as a Toplevel over the main menu.

Layout from docs/GUI_STYLE_REFERENCE.md's Load Game window:

- Save-slot list (Tk Listbox, single column, character names only) on top
- Selected-save detail preview as plain stacked text below it
- A row of flat action buttons (Load, Refresh, Close) at the bottom
"""

from __future__ import annotations

import tkinter as tk

from gui import theme
from engine.game import SaveSlotInfo
from gui.widgets import SelectList, StatPanel

__all__ = ["SaveBrowserWindow"]

_TITLES = {"load": "Load Game", "save": "Save Game", "delete": "Delete Save"}
_ACTIONS = {"load": "Load", "save": "Overwrite", "delete": "Delete"}


class SaveBrowserWindow(tk.Toplevel):
    """Slot list plus preview, in one of three modes."""

    def __init__(self, app, mode: str = "load") -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app
        self.mode = mode if mode in _TITLES else "load"

        theme.style_window(self, f"Project Ascension - {_TITLES[self.mode]}")
        theme.center_window(self, 480, 560)
        self.transient(app.root)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        theme.heading_label(body, text=_TITLES[self.mode]).pack(anchor="w", pady=(0, 10))

        self.slot_list: SelectList[SaveSlotInfo] = SelectList(
            body, title="", height=10, on_select=self._on_select, on_activate=lambda _v: self._primary()
        )
        self.slot_list.pack(fill=tk.BOTH, expand=True)

        self.preview = StatPanel(body, title="")
        self.preview.pack(fill=tk.X, pady=(14, 0))

        # "Save" mode needs somewhere to type a new slot name; the other modes
        # only ever act on an existing slot.
        self.name_var = tk.StringVar()
        if self.mode == "save":
            row = tk.Frame(body, bg=theme.BG)
            row.pack(fill=tk.X, pady=(14, 0))
            theme.body_label(row, text="Slot name:").pack(side=tk.LEFT)
            entry = tk.Entry(
                row,
                textvariable=self.name_var,
                bg=theme.LISTBOX_BG,
                fg=theme.FG,
                insertbackground=theme.FG,
                relief=tk.FLAT,
                font=theme.FONT_BODY,
            )
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0), ipady=3)
            if app.game.player:
                self.name_var.set(app.game.current_slot or app.game.saves.suggest_slot(app.game.player.name))

        buttons = tk.Frame(body, bg=theme.BG)
        buttons.pack(fill=tk.X, pady=(16, 0))
        self.primary_button = theme.flat_button(buttons, _ACTIONS[self.mode], self._primary, width=10)
        self.primary_button.pack(side=tk.LEFT)
        theme.flat_button(buttons, "Refresh", self.refresh, width=10).pack(side=tk.LEFT, padx=8)
        theme.flat_button(buttons, "Close", self._close, width=10).pack(side=tk.RIGHT)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        slots = self.app.game.save_slots()
        self.slot_list.set_items([(info.display_name, info) for info in slots])
        if not slots:
            self.preview.set_lines(["No saved games found."])
            self.primary_button.configure(state=tk.DISABLED)
        else:
            self.primary_button.configure(state=tk.NORMAL)
            self._on_select(self.slot_list.selected_value)

    def _on_select(self, info: SaveSlotInfo | None) -> None:
        if info is None:
            self.preview.set_lines([])
            return
        self.preview.set_lines(info.detail_lines())
        # A corrupt slot can still be deleted - that is the only useful action.
        if getattr(info, "corrupt", False) and self.mode == "load":
            self.primary_button.configure(state=tk.DISABLED)
        else:
            self.primary_button.configure(state=tk.NORMAL)

    # ------------------------------------------------------------------
    def _primary(self) -> None:
        if self.mode == "save":
            self._do_save()
            return
        info = self.slot_list.selected_value
        if info is None:
            self.app.notify("Select a save first.")
            return
        if self.mode == "load":
            self._do_load(info.slot)
        else:
            self._do_delete(info.slot, info.display_name)

    def _do_load(self, slot: str) -> None:
        ok, message = self.app.game.load_game(slot)
        self.app.notify(message)
        if ok:
            self._close()
            self.app.show_world()

    def _do_save(self) -> None:
        slot = self.name_var.get().strip()
        if not slot:
            self.app.notify("Enter a slot name.")
            return
        ok, message = self.app.game.save_game(slot)
        self.app.notify(message)
        if ok:
            self.refresh()

    def _do_delete(self, slot: str, label: str) -> None:
        if not self.app.confirm("Delete Save", f"Permanently delete '{label}'?"):
            return
        ok, message = self.app.game.delete_save(slot)
        self.app.notify(message)
        self.refresh()
        self.app.refresh_active()

    def _close(self) -> None:
        self.app.close_toplevel("save_browser")
