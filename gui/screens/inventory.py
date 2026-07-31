"""Inventory - browse the bag, inspect items, use consumables."""

from __future__ import annotations

import tkinter as tk

from gui import theme
from engine.items.item import Item
from gui.widgets import ScrollableFrame, SelectList, StatPanel

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
        theme.center_window(self, 820, 600)
        self.transient(app.root)

        self.viewport = ScrollableFrame(self, bg=theme.BG, padx=18, pady=16)
        self.viewport.pack(fill=tk.BOTH, expand=True)
        body = self.viewport.content

        header = tk.Frame(body, bg=theme.BG)
        header.pack(fill=tk.X)
        theme.heading_label(header, text="Inventory").pack(side=tk.LEFT)
        self.gold_label = theme.body_label(header, text="", fg=theme.FG_DIM)
        self.gold_label.pack(side=tk.RIGHT)

        # -- search + filter row --------------------------------------------------
        search_row = tk.Frame(body, bg=theme.BG)
        search_row.pack(fill=tk.X, pady=(10, 0))
        theme.body_label(search_row, text="Search:", font=theme.FONT_SMALL).pack(side=tk.LEFT)
        self.search_var = tk.StringVar(value="")
        search_entry = theme.field_entry(search_row, textvariable=self.search_var, width=22, bg=theme.LISTBOX_BG, fg=theme.FG, insertbackground=theme.FG, font=theme.FONT_SMALL)
        search_entry.pack(side=tk.LEFT, padx=(6, 10))
        search_entry.bind("<KeyRelease>", lambda _e: self.refresh())
        theme.body_label(search_row, text="Total value:").pack(side=tk.LEFT, padx=(10, 4))
        self.value_label = theme.body_label(search_row, text="", fg=theme.FG_DIM, font=theme.FONT_SMALL)
        self.value_label.pack(side=tk.LEFT)

        filters = tk.Frame(body, bg=theme.BG)
        filters.pack(fill=tk.X, pady=(8, 0))
        self.filter_var = tk.StringVar(value="All")
        for label, _kind in _FILTERS:
            theme.choice_button(
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
            theme.choice_button(
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
            theme.choice_button(
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

        self.detail = StatPanel(columns, title="Details", wrap=320)
        self.detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))

        # -- actions ------------------------------------------------------
        buttons = tk.Frame(body, bg=theme.BG)
        buttons.pack(fill=tk.X, pady=(16, 0))
        self.use_button = theme.flat_button(buttons, "Use", self._use, width=10)
        self.use_button.pack(side=tk.LEFT)
        self.equip_button = theme.flat_button(buttons, "Equip", self._equip, width=10)
        self.equip_button.pack(side=tk.LEFT, padx=8)
        self.enchant_button = theme.flat_button(buttons, "Enchant Info", self._enchant_info, width=12)
        self.enchant_button.pack(side=tk.LEFT, padx=8)
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
        search = self.search_var.get().strip().lower()

        entries = game.inventory_entries(kind)
        if rarity:
            entries = [e for e in entries if e.item.rarity.lower() == rarity.lower()]
        if search:
            entries = [e for e in entries if search in e.item.name.lower() or search in e.item.description.lower() or search in e.item.rarity.lower()]

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

        # Total value
        total_value = sum(e.item.value * e.quantity for e in entries)
        self.value_label.configure(text=f"{total_value} gold value in view, {len(entries)} stacks")

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
            self.enchant_button.configure(state=tk.DISABLED)
        else:
            self._on_select(self.item_list.selected_value)

    def _enriched_detail(self, item: Item) -> list[str]:
        game = self.app.game
        rarity_cfg = game.config.get("rarities") or {}
        lines = item.detail_lines(rarity_cfg)
        # Enchantments
        ench_ids = game.player.item_enchantments.get(item.id, [])
        if ench_ids:
            lines.append("")
            lines.append(f"Enchantments ({len(ench_ids)}/{item.effective_enchant_slots(rarity_cfg)}):")
            for eid in ench_ids:
                ench = game.enchantments.get(eid)
                if ench:
                    lines.append(f"  {ench.name}: " + ", ".join(ench.modifiers.describe()))
                else:
                    lines.append(f"  {eid}")
        else:
            if item.is_equipment:
                lines.append(f"Enchant slots: {item.effective_enchant_slots(rarity_cfg)} (empty)")
        # Upgrades with preview
        up_lvl = game.player.item_upgrades.get(item.id, 0)
        cfg = game.config.get("equipment_upgrade", {})
        rate = float(cfg.get("modifier_rate", 0.08))
        max_lvl = int(cfg.get("max_level", 5))
        if up_lvl:
            lines.append(f"Upgrade: +{up_lvl}/{max_lvl}")
        if item.is_equipment and up_lvl < max_lvl:
            next_lvl = up_lvl + 1
            cost = int(cfg.get('base_gold',500)*(next_lvl))
            rarity_scale = float(game.config.get("rarities", {}).get(item.rarity.lower(), {}).get("modifier_rate", 1.0))
            curr_scale = (1.0 + rate * up_lvl) * rarity_scale
            next_scale = (1.0 + rate * next_lvl) * rarity_scale
            lines.append(f"Next upgrade +{next_lvl} cost: {cost}g")
            for k, v in item.modifiers.flat.items():
                curr_val = v * curr_scale
                next_val = v * next_scale
                diff = next_val - curr_val
                if abs(diff) >= 0.1:
                    lines.append(f"  {k} +{diff:.1f} ({curr_val:.0f}->{next_val:.0f})")
        elif up_lvl >= max_lvl and item.is_equipment:
            lines.append(f"Upgrade: MAX (+{max_lvl})")
        # Comparison vs equipped
        if item.is_equipment:
            equipped = game.player.equipment.get(item.slot)
            if equipped and equipped.id != item.id:
                lines.append("")
                lines.append(f"Compared to equipped {equipped.name}:")
                # Simple comparison of key stats
                for key in ["physical_power", "magic_power", "armor", "magic_resist", "max_hp", "max_mp", "crit_chance", "accuracy", "evasion", "speed"]:
                    old = equipped.modifiers.flat.get(key, 0) + equipped.modifiers.pct.get(key, 0)*100
                    new = item.modifiers.flat.get(key, 0) + item.modifiers.pct.get(key, 0)*100
                    # Include rarity scaling
                    old_r = game.config.get("rarities", {}).get(equipped.rarity.lower(), {}).get("modifier_rate", 1.0)
                    new_r = rarity_cfg.get(item.rarity.lower(), {}).get("modifier_rate", 1.0)
                    # Approximate diff
                    diff = (item.modifiers.flat.get(key,0)*new_r) - (equipped.modifiers.flat.get(key,0)*old_r)
                    if abs(diff) >= 0.5 or key in item.modifiers.flat or key in equipped.modifiers.flat:
                        sign = "+" if diff>0 else ""
                        lines.append(f"  {key}: {sign}{diff:.1f}")
        return lines

    def _on_select(self, item: Item | None) -> None:
        if item is None:
            self.detail.set_lines([])
            return
        self.detail.set_lines(self._enriched_detail(item))
        self.use_button.configure(state=tk.NORMAL if item.is_consumable else tk.DISABLED)
        self.equip_button.configure(state=tk.NORMAL if item.is_equipment else tk.DISABLED)
        self.enchant_button.configure(state=tk.NORMAL if item.is_equipment else tk.DISABLED)

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

    def _enchant_info(self) -> None:
        item = self.item_list.selected_value
        if not item:
            return
        game = self.app.game
        ench_ids = game.player.item_enchantments.get(item.id, [])
        rarity_cfg = game.config.get("rarities") or {}
        slots = item.effective_enchant_slots(rarity_cfg)
        lines = [f"{item.name} - {len(ench_ids)}/{slots} slots used"]
        if ench_ids:
            for eid in ench_ids:
                ench = game.enchantments.get(eid)
                lines.append(f"  {eid}: {ench.name if ench else 'Unknown'}")
        else:
            lines.append("No enchantments")
        lines.append("")
        lines.append("Available enchantments:")
        for ench in game.enchantments.all_definitions():
            lines.append(f"  {ench.id}: {ench.name} ({ench.gold_cost}g) - " + ", ".join(ench.modifiers.describe()))
        # Show as notify popup via info window
        self.app.show_info("Enchantments", "\n".join(lines))

    def _close(self) -> None:
        self.app.close_toplevel("inventory")
