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

_RARITY_FILTERS: tuple[tuple[str, str | None], ...] = (
    ("All Rarities", None),
    ("Common", "common"),
    ("Uncommon", "uncommon"),
    ("Rare", "rare"),
    ("Epic", "epic"),
    ("Legendary", "legendary"),
)

_SORTS: tuple[str, ...] = ("name", "rarity", "value", "type")


class InventoryWindow(tk.Toplevel):
    """Bag contents with a detail preview."""

    def __init__(self, app) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app

        theme.style_window(self, "Project Ascension - Inventory")
        theme.center_window(self, 760, 560)
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

        # -- rarity filter + sort row -----------------------------------
        rarity_row = tk.Frame(body, bg=theme.BG)
        rarity_row.pack(fill=tk.X, pady=(6, 0))
        theme.body_label(rarity_row, text="Rarity:", font=theme.FONT_SMALL).pack(side=tk.LEFT)
        self.rarity_var = tk.StringVar(value="All Rarities")
        for label, _rar in _RARITY_FILTERS:
            tk.Radiobutton(
                rarity_row,
                text=label,
                value=label,
                variable=self.rarity_var,
                command=self.refresh,
                bg=theme.BG,
                fg=theme.FG,
                selectcolor=theme.BG_ALT,
                activebackground=theme.BG,
                activeforeground=theme.FG,
                font=theme.FONT_SMALL,
                highlightthickness=0,
                borderwidth=0,
            ).pack(side=tk.LEFT, padx=(0, 6))

        sort_row = tk.Frame(body, bg=theme.BG)
        sort_row.pack(fill=tk.X, pady=(6, 0))
        theme.body_label(sort_row, text="Sort:", font=theme.FONT_SMALL).pack(side=tk.LEFT)
        self.sort_var = tk.StringVar(value="name")
        for s in _SORTS:
            tk.Radiobutton(
                sort_row,
                text=s.title(),
                value=s,
                variable=self.sort_var,
                command=self.refresh,
                bg=theme.BG,
                fg=theme.FG,
                selectcolor=theme.BG_ALT,
                activebackground=theme.BG,
                activeforeground=theme.FG,
                font=theme.FONT_SMALL,
                highlightthickness=0,
                borderwidth=0,
            ).pack(side=tk.LEFT, padx=(0, 8))

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

    def _selected_rarity(self) -> str | None:
        return dict(_RARITY_FILTERS).get(self.rarity_var.get())

    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self._close()
            return

        self.gold_label.configure(text=f"Gold: {game.player.inventory.gold}")
        kind = self._selected_kind()
        rarity = self._selected_rarity()
        sort_mode = self.sort_var.get()

        entries = game.inventory_entries(kind)
        if rarity:
            entries = [e for e in entries if e.item.rarity.lower() == rarity.lower()]

        # Sorting
        rarity_order = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4}
        if sort_mode == "rarity":
            entries = sorted(entries, key=lambda e: (rarity_order.get(e.item.rarity.lower(), 0), e.item.name))
        elif sort_mode == "value":
            entries = sorted(entries, key=lambda e: (e.item.value, e.item.name), reverse=True)
        elif sort_mode == "type":
            entries = sorted(entries, key=lambda e: (e.item.kind, e.item.name))
        else:
            entries = sorted(entries, key=lambda e: e.item.name.lower())

        # Labels with rarity
        labels = [(f"[{e.item.rarity_label}] {e.label()}", e.item) for e in entries]
        self.item_list.set_items(labels)

        # Rarity colors
        rarity_colors = game.config.get("rarities") or {}
        colors = [rarity_colors.get(e.item.rarity.lower(), {}).get("color", theme.FG) for e in entries]
        self.item_list.set_row_colors(colors)

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
        rarity_cfg = self.app.game.config.get("rarities") or {}
        self.detail.set_lines(item.detail_lines(rarity_cfg))
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
