"""Equipment - slot list on the left, valid candidates for it on the right.

Two Listboxes coexist with live selections (slots and candidates), so this is
another screen covered by the ``exportselection=False`` note in
docs/GUI_VERIFICATION.md - handled by :func:`gui.theme.stat_listbox`.
"""

from __future__ import annotations

import tkinter as tk

from engine.items.item import EQUIPMENT_SLOTS, SLOT_LABELS, Item
from gui import theme
from gui.widgets import SelectList, StatPanel

__all__ = ["EquipmentWindow"]


class EquipmentWindow(tk.Toplevel):
    """Equip and unequip gear per slot."""

    def __init__(self, app) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app

        theme.style_window(self, "Project Ascension - Equipment")
        theme.center_window(self, 720, 520)
        self.transient(app.root)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        theme.heading_label(body, text="Equipment").pack(anchor="w", pady=(0, 10))

        columns = tk.Frame(body, bg=theme.BG)
        columns.pack(fill=tk.BOTH, expand=True)

        # Listbox #1: equipped slots.
        self.slot_list: SelectList[str] = SelectList(
            columns, title="Slots", height=10, on_select=lambda _v: self._reload_candidates()
        )
        self.slot_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Listbox #2: what can go in the selected slot.
        self.candidate_list: SelectList[Item] = SelectList(
            columns,
            title="Available",
            height=10,
            on_select=self._on_candidate,
            on_activate=lambda _v: self._equip(),
        )
        self.candidate_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))

        self.detail = StatPanel(columns, title="Details", wrap=210)
        self.detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))

        buttons = tk.Frame(body, bg=theme.BG)
        buttons.pack(fill=tk.X, pady=(16, 0))
        theme.flat_button(buttons, "Equip", self._equip, width=10).pack(side=tk.LEFT)
        theme.flat_button(buttons, "Unequip", self._unequip, width=10).pack(side=tk.LEFT, padx=8)
        theme.flat_button(buttons, "Close", self._close, width=10).pack(side=tk.RIGHT)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self._close()
            return

        player = game.player
        rows = []
        for slot in EQUIPMENT_SLOTS:
            item = player.equipment.get(slot)
            rows.append((f"{SLOT_LABELS[slot]}: {item.name if item else '(empty)'}", slot))
        self.slot_list.set_items(rows, keep_selection=True)
        self._reload_candidates()

    def _reload_candidates(self) -> None:
        slot = self.slot_list.selected_value
        if slot is None:
            self.candidate_list.clear()
            return
        items = self.app.game.equippable_for_slot(slot)
        self.candidate_list.set_items([(item.name, item) for item in items], keep_selection=False)
        if items:
            self._on_candidate(self.candidate_list.selected_value)
        else:
            equipped = self.app.game.player.equipment.get(slot)
            self.detail.set_lines(
                equipped.detail_lines() if equipped else ["Nothing available for this slot."]
            )

    def _on_candidate(self, item: Item | None) -> None:
        if item is None:
            return
        self.detail.set_lines(item.detail_lines())

    # ------------------------------------------------------------------
    def _equip(self) -> None:
        item = self.candidate_list.selected_value
        if item is None:
            self.app.notify("Select an item to equip.")
            return
        ok, message = self.app.game.equip_item(item.id)
        self.app.notify(message)
        self.app.refresh_active()

    def _unequip(self) -> None:
        slot = self.slot_list.selected_value
        if slot is None:
            return
        ok, message = self.app.game.unequip_slot(slot)
        self.app.notify(message)
        self.app.refresh_active()

    def _close(self) -> None:
        self.app.close_toplevel("equipment")
