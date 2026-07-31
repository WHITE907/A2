"""Shop - buy from stock, sell from the bag.

Two Listboxes (stock and bag) again hold independent selections; see
docs/GUI_VERIFICATION.md and :func:`gui.theme.stat_listbox`.
"""

from __future__ import annotations

import tkinter as tk

from gui import theme
from engine.items.item import Item
from gui.widgets import ScrollableFrame, SelectList, StatPanel

__all__ = ["ShopWindow"]


class ShopWindow(tk.Toplevel):
    """Vendor stock and the player's sellable items, side by side."""

    def __init__(self, app, shop_id: str) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app
        self.shop_id = shop_id
        shop = app.game.world_manager.get_shop(shop_id)
        self.shop_name = shop.name if shop else "Shop"
        self.buy_rate = shop.buy_rate if shop else 1.0
        self.sell_rate = shop.sell_rate if shop else 0.4

        theme.style_window(self, f"Project Ascension - {self.shop_name}")
        theme.center_window(self, 820, 560)
        self.transient(app.root)

        self.viewport = ScrollableFrame(self, bg=theme.BG, padx=18, pady=16)
        self.viewport.pack(fill=tk.BOTH, expand=True)
        body = self.viewport.content

        header = tk.Frame(body, bg=theme.BG)
        header.pack(fill=tk.X)
        theme.heading_label(header, text=self.shop_name).pack(side=tk.LEFT)
        self.gold_label = theme.body_label(header, text="", fg=theme.FG_DIM)
        self.gold_label.pack(side=tk.RIGHT)

        columns = tk.Frame(body, bg=theme.BG)
        columns.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        self.stock_list: SelectList[Item] = SelectList(
            columns, title="For Sale", height=13, on_select=self._on_stock, on_activate=lambda _v: self._buy()
        )
        self.stock_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.bag_list: SelectList[Item] = SelectList(
            columns, title="Your Items", height=13, on_select=self._on_bag, on_activate=lambda _v: self._sell()
        )
        self.bag_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))

        self.detail = StatPanel(columns, title="Details", wrap=260)
        self.detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))

        buttons = tk.Frame(body, bg=theme.BG)
        buttons.pack(fill=tk.X, pady=(16, 0))
        theme.flat_button(buttons, "Buy", self._buy, width=10).pack(side=tk.LEFT)
        theme.flat_button(buttons, "Sell", self._sell, width=10).pack(side=tk.LEFT, padx=8)
        theme.flat_button(buttons, "Compare", self._compare, width=10).pack(side=tk.LEFT, padx=8)
        theme.flat_button(buttons, "Close", self._close, width=10).pack(side=tk.RIGHT)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self._close()
            return

        self.gold_label.configure(text=f"Gold: {game.player.inventory.gold}")

        stock = game.shop_stock(self.shop_id)
        self.stock_list.set_items(
            [(f"[{item.rarity_label}] {item.name} - {game.shop_price(self.shop_id, item.id)}g", item) for item in stock]
        )
        rarity_colors = game.config.get("rarities") or {}
        self.stock_list.set_row_colors([rarity_colors.get(item.rarity.lower(), {}).get("color", theme.FG) for item in stock])

        entries = game.inventory_entries()
        self.bag_list.set_items(
            [(f"[{entry.item.rarity_label}] {entry.label()} - {int(entry.item.sell_price(self.sell_rate) * float((game.config.get('rarities') or {}).get(entry.item.rarity.lower(), {}).get('value_rate', 1.0)))}g", entry.item) for entry in entries],
            keep_selection=False,
        )
        self.bag_list.set_row_colors([rarity_colors.get(entry.item.rarity.lower(), {}).get("color", theme.FG) for entry in entries])

    def _enriched_detail(self, item: Item, compare: bool = True) -> list[str]:
        game = self.app.game
        rarity_cfg = game.config.get("rarities") or {}
        lines = item.detail_lines(rarity_cfg)
        # Enchant slots
        if item.is_equipment:
            lines.append(f"Enchant slots: {item.effective_enchant_slots(rarity_cfg)}")
        # Comparison
        if compare and item.is_equipment:
            equipped = game.player.equipment.get(item.slot)
            if equipped and equipped.id != item.id:
                lines.append("")
                lines.append(f"vs equipped {equipped.name} [{equipped.rarity_label}]:")
                for key in ["physical_power", "magic_power", "armor", "magic_resist", "max_hp", "crit_chance", "accuracy", "evasion", "speed"]:
                    old = equipped.modifiers.flat.get(key, 0) * rarity_cfg.get(equipped.rarity.lower(), {}).get("modifier_rate", 1.0)
                    new = item.modifiers.flat.get(key, 0) * rarity_cfg.get(item.rarity.lower(), {}).get("modifier_rate", 1.0)
                    diff = new - old
                    if abs(diff) >= 0.1 or key in item.modifiers.flat or key in equipped.modifiers.flat:
                        sign = "+" if diff>0 else ""
                        marker = "↑" if diff>0 else "↓" if diff<0 else "="
                        lines.append(f"  {marker} {key}: {sign}{diff:.1f} ({new:.0f} vs {old:.0f})")
                # Overall verdict
                old_power = sum(equipped.modifiers.flat.values())
                new_power = sum(item.modifiers.flat.values())
                if new_power > old_power:
                    lines.append("  Overall: UPGRADE")
                elif new_power < old_power:
                    lines.append("  Overall: downgrade")
        # Sell/buy price
        if item.id in [it.id for it in game.shop_stock(self.shop_id)]:
            price = game.shop_price(self.shop_id, item.id)
            lines.append(f"Buy price: {price}g")
        else:
            sell_rate = self.sell_rate
            rarity = rarity_cfg.get(item.rarity.lower(), {})
            price = max(1, int(item.sell_price(sell_rate) * float(rarity.get("value_rate", 1.0))))
            lines.append(f"Sell price: {price}g")
        return lines

    def _on_stock(self, item: Item | None) -> None:
        if item is not None:
            self.detail.set_lines(self._enriched_detail(item, compare=True))

    def _on_bag(self, item: Item | None) -> None:
        if item is not None:
            self.detail.set_lines(self._enriched_detail(item, compare=False))

    def _compare(self) -> None:
        item = self.stock_list.selected_value or self.bag_list.selected_value
        if not item:
            self.app.notify("Select an item to compare.")
            return
        # Show detailed comparison in info window
        lines = self._enriched_detail(item, compare=True)
        self.app.show_info(f"Compare {item.name}", "\n".join(lines))

    # ------------------------------------------------------------------
    def _buy(self) -> None:
        item = self.stock_list.selected_value
        if item is None:
            self.app.notify("Select something to buy.")
            return
        ok, message = self.app.game.buy_item(self.shop_id, item.id)
        self.app.notify(message)
        self.app.refresh_active()

    def _sell(self) -> None:
        item = self.bag_list.selected_value
        if item is None:
            self.app.notify("Select something to sell.")
            return
        ok, message = self.app.game.sell_item(self.shop_id, item.id)
        self.app.notify(message)
        self.app.refresh_active()

    def _close(self) -> None:
        self.app.close_toplevel("shop")
