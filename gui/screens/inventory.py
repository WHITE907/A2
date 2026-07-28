"""Inventory - browse the bag, inspect items, use consumables."""

from __future__ import annotations

import tkinter as tk

from gui import theme
from engine.items.item import Item
from gui.widgets import SelectList, StatPanel

__all__ = ["InventoryWindow"]

_FILTERS: tuple[tuple[str, str | None], ...] = (
    ("All", None),
    ("Equipment", "equipment"),
    ("Consumables", "consumable"),
    ("Materials", "material"),
    ("Key Items", "key"),
)


class InventoryWindow(tk.Toplevel):
    """Bag contents with a detail preview."""

    def __init__(self, app) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app

        theme.style_window(self, "Project Ascension - Inventory")
        theme.center_window(self, 660, 520)
        self.transient(app.root)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(body, bg=theme.BG)
        header.pack(fill=tk.X)
        theme.heading_label(header, text="Inventory").pack(side=tk.LEFT)
        self.gold_label = theme.body_label(header, text="", fg=theme.FG_DIM)
        self.gold_label.pack(side=tk.RIGHT)

        # -- filter row --------------------------------------------------
        filters = tk.Frame(body, bg=theme.BG)
        filters.pack(fill=tk.X, pady=(10, 0))
        self.filter_var = tk.StringVar(value="All")
        for label, _kind in _FILTERS:
            tk.Radiobutton(
                filters,
                text=label,
                value=label,
                variable=self.filter_var,
                command=self.refresh,
                bg=theme.BG,
                fg=theme.FG,
                selectcolor=theme.BG_ALT,
                activebackground=theme.BG,
                activeforeground=theme.FG,
                font=theme.FONT_SMALL,
                highlightthickness=0,
                borderwidth=0,
            ).pack(side=tk.LEFT, padx=(0, 10))

        # -- list + detail -----------------------------------------------
        columns = tk.Frame(body, bg=theme.BG)
        columns.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        self.item_list: SelectList[Item] = SelectList(
            columns, title="", height=14, on_select=self._on_select, on_activate=lambda _v: self._use()
        )
        self.item_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.detail = StatPanel(columns, title="Details", wrap=290)
        self.detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))

        # -- actions ------------------------------------------------------
        buttons = tk.Frame(body, bg=theme.BG)
        buttons.pack(fill=tk.X, pady=(16, 0))
        self.use_button = theme.flat_button(buttons, "Use", self._use, width=10)
        self.use_button.pack(side=tk.LEFT)
        self.equip_button = theme.flat_button(buttons, "Equip", self._equip, width=10)
        self.equip_button.pack(side=tk.LEFT, padx=8)
        theme.flat_button(buttons, "Close", self._close, width=10).pack(side=tk.RIGHT)

        self.refresh()

    # ------------------------------------------------------------------
    def _selected_kind(self) -> str | None:
        return dict(_FILTERS).get(self.filter_var.get())

    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self._close()
            return

        self.gold_label.configure(text=f"Gold: {game.player.inventory.gold}")
        entries = game.inventory_entries(self._selected_kind())
        self.item_list.set_items([(entry.label(), entry.item) for entry in entries])

        if not entries:
            self.detail.set_lines(["Nothing here."])
            self.use_button.configure(state=tk.DISABLED)
            self.equip_button.configure(state=tk.DISABLED)
        else:
            self._on_select(self.item_list.selected_value)

    def _on_select(self, item: Item | None) -> None:
        if item is None:
            self.detail.set_lines([])
            return
        self.detail.set_lines(item.detail_lines())
        # Buttons follow what the item actually supports.
        self.use_button.configure(state=tk.NORMAL if item.is_consumable else tk.DISABLED)
        self.equip_button.configure(state=tk.NORMAL if item.is_equipment else tk.DISABLED)

    # ------------------------------------------------------------------
    def _use(self) -> None:
        item = self.item_list.selected_value
        if item is None or not item.is_consumable:
            return
        ok, messages = self.app.game.use_item(item.id)
        self.app.notify(messages[0] if messages else "")
        self.app.refresh_active()

    def _equip(self) -> None:
        item = self.item_list.selected_value
        if item is None or not item.is_equipment:
            return
        ok, message = self.app.game.equip_item(item.id)
        self.app.notify(message)
        self.app.refresh_active()

    def _close(self) -> None:
        self.app.close_toplevel("inventory")
