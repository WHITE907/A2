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
        theme.center_window(self, 820, 560)
        self.transient(app.root)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        theme.heading_label(body, text="Equipment").pack(anchor="w", pady=(0, 10))

        # Active set bonuses
        self.set_bonus_label = theme.body_label(body, text="", fg=theme.FG_DIM, font=theme.FONT_SMALL)
        self.set_bonus_label.pack(anchor="w", pady=(0, 8))

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

        self.detail = StatPanel(columns, title="Details", wrap=280)
        self.detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))

        buttons = tk.Frame(body, bg=theme.BG)
        buttons.pack(fill=tk.X, pady=(16, 0))
        theme.flat_button(buttons, "Equip", self._equip, width=10).pack(side=tk.LEFT)
        theme.flat_button(buttons, "Unequip", self._unequip, width=10).pack(side=tk.LEFT, padx=8)
        theme.flat_button(buttons, "Enchant", self._enchant, width=10).pack(side=tk.LEFT, padx=8)
        theme.flat_button(buttons, "Upgrade", self._upgrade, width=10).pack(side=tk.LEFT, padx=8)
        theme.flat_button(buttons, "Best", self._equip_best, width=8).pack(side=tk.LEFT, padx=8)
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
        colors = []
        rarity_cfg = game.config.get("rarities") or {}
        for slot in EQUIPMENT_SLOTS:
            item = player.equipment.get(slot)
            label = f"{SLOT_LABELS[slot]}: {item.name if item else '(empty)'}"
            if item:
                label = f"[{item.rarity_label}] {label}"
                colors.append(rarity_cfg.get(item.rarity.lower(), {}).get("color", theme.FG))
            else:
                colors.append(theme.FG)
            rows.append((label, slot))
        self.slot_list.set_items(rows, keep_selection=True)
        self.slot_list.set_row_colors(colors)

        # Set bonuses with next tier preview
        counts = {}
        for it in player.equipment.values():
            if it and it.set_id:
                counts[it.set_id] = counts.get(it.set_id, 0) + 1
        active = player.active_set_bonuses()
        lines = []
        if active:
            lines.append("Active: " + ", ".join(active))
        # Next thresholds
        for set_id, count in counts.items():
            defn = game.config.get("equipment_sets", {}).get(set_id, {})
            thresholds = sorted(int(k) for k in (defn.get("bonuses") or {}).keys())
            for thr in thresholds:
                if count < thr:
                    lines.append(f"Next {defn.get('name', set_id)}: {count}/{thr} pieces")
                    break
        if not lines:
            lines.append("No set bonuses active")
        self.set_bonus_label.configure(text=" | ".join(lines))

        self._reload_candidates()

    def _reload_candidates(self) -> None:
        slot = self.slot_list.selected_value
        if slot is None:
            self.candidate_list.clear()
            return
        items = self.app.game.equippable_for_slot(slot)
        rarity_cfg = self.app.game.config.get("rarities") or {}
        # Sort by rarity then power estimate
        rarity_order = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4}
        def power_est(it: Item):
            return sum(it.modifiers.flat.values())
        items = sorted(items, key=lambda i: (rarity_order.get(i.rarity.lower(), 0), power_est(i)), reverse=True)
        self.candidate_list.set_items([(f"[{item.rarity_label}] {item.name}", item) for item in items], keep_selection=False)
        self.candidate_list.set_row_colors([rarity_cfg.get(item.rarity.lower(), {}).get("color", theme.FG) for item in items])
        if items:
            self._on_candidate(self.candidate_list.selected_value)
        else:
            equipped = self.app.game.player.equipment.get(slot)
            if equipped:
                self.detail.set_lines(self._enriched_detail(equipped))
            else:
                self.detail.set_lines(["Nothing available for this slot."])

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
            if item.is_equipment:
                lines.append(f"Enchant slots: {item.effective_enchant_slots(rarity_cfg)} (empty)")
        up_lvl = game.player.item_upgrades.get(item.id, 0)
        cfg = game.config.get("equipment_upgrade", {})
        rate = float(cfg.get("modifier_rate", 0.08))
        max_lvl = int(cfg.get("max_level", 5))
        if up_lvl:
            lines.append(f"Upgrade: +{up_lvl}/{max_lvl}")
        if up_lvl < max_lvl:
            next_lvl = up_lvl + 1
            cost = int(cfg.get('base_gold',500)*(next_lvl))
            lines.append(f"Next upgrade +{next_lvl} cost: {cost}g (room: {item.effective_enchant_slots(rarity_cfg)-len(game.player.item_enchantments.get(item.id, []))} free slots)")
            # Preview stat increase
            rarity_scale = float(rarity_cfg.get(item.rarity.lower(), {}).get("modifier_rate", 1.0))
            curr_scale = (1.0 + rate * up_lvl) * rarity_scale
            next_scale = (1.0 + rate * next_lvl) * rarity_scale
            for k, v in item.modifiers.flat.items():
                curr_val = v * curr_scale
                next_val = v * next_scale
                diff = next_val - curr_val
                if abs(diff) >= 0.1:
                    lines.append(f"  Upgrade {k}: +{diff:.1f} ({curr_val:.0f} -> {next_val:.0f})")
        else:
            if item.is_equipment:
                lines.append(f"Upgrade: MAX (+{max_lvl})")
        # Comparison
        equipped = game.player.equipment.get(item.slot)
        if equipped and equipped.id != item.id:
            lines.append("")
            lines.append(f"vs {equipped.name} [{equipped.rarity_label}]:")
            for key in ["physical_power", "magic_power", "armor", "magic_resist", "max_hp", "max_mp", "crit_chance", "accuracy", "evasion", "speed"]:
                old_flat = equipped.modifiers.flat.get(key, 0)
                new_flat = item.modifiers.flat.get(key, 0)
                old_r = rarity_cfg.get(equipped.rarity.lower(), {}).get("modifier_rate", 1.0)
                new_r = rarity_cfg.get(item.rarity.lower(), {}).get("modifier_rate", 1.0)
                # Apply rarity scaling for fair compare
                old_val = old_flat * old_r
                new_val = new_flat * new_r
                diff = new_val - old_val
                if abs(diff) >= 0.1 or key in item.modifiers.flat or key in equipped.modifiers.flat:
                    sign = "+" if diff>0 else ""
                    lines.append(f"  {key}: {sign}{diff:.1f} ({new_val:.0f} vs {old_val:.0f})")
        return lines

    def _on_candidate(self, item: Item | None) -> None:
        if item is None:
            return
        self.detail.set_lines(self._enriched_detail(item))

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

    def _enchant(self) -> None:
        # Determine which item: prefer candidate if selected, else equipped in slot
        item = self.candidate_list.selected_value
        if item is None:
            slot = self.slot_list.selected_value
            if slot:
                item = self.app.game.player.equipment.get(slot)
        if not item:
            self.app.notify("Select an item to enchant.")
            return
        # Open enchant chooser
        self._open_enchant_window(item)

    def _upgrade(self) -> None:
        item = self.candidate_list.selected_value
        if item is None:
            slot = self.slot_list.selected_value
            if slot:
                item = self.app.game.player.equipment.get(slot)
        if not item:
            self.app.notify("Select an item to upgrade.")
            return
        ok, msg = self.app.game.upgrade_item(item.id)
        self.app.notify(msg)
        self.app.refresh_active()

    def _equip_best(self) -> None:
        # Simple heuristic: best by effective power (flat mods * rarity scale)
        game = self.app.game
        rarity_cfg = game.config.get("rarities") or {}
        best_for_slot = {}
        for entry in game.player.inventory.equipment_entries():
            it = entry.item
            score = sum(it.modifiers.flat.values()) * float(rarity_cfg.get(it.rarity.lower(), {}).get("modifier_rate", 1.0))
            score += sum(it.modifiers.pct.values()) * 100  # weight pct
            # Prefer higher rarity
            score += {"common":0, "uncommon":5, "rare":15, "epic":30, "legendary":50}.get(it.rarity.lower(),0)
            if it.slot not in best_for_slot or score > best_for_slot[it.slot][0]:
                best_for_slot[it.slot] = (score, it)
        equipped_count = 0
        for slot, (score, it) in best_for_slot.items():
            current = game.player.equipment.get(slot)
            # Only equip if better than current (or empty)
            curr_score = 0
            if current:
                curr_score = sum(current.modifiers.flat.values()) * float(rarity_cfg.get(current.rarity.lower(), {}).get("modifier_rate",1.0))
                curr_score += sum(current.modifiers.pct.values())*100
                curr_score += {"common":0,"uncommon":5,"rare":15,"epic":30,"legendary":50}.get(current.rarity.lower(),0)
            if not current or score > curr_score:
                ok, msg = game.equip_item(it.id)
                if ok:
                    equipped_count += 1
        game.player.invalidate_stats()
        self.app.notify(f"Equipped {equipped_count} best items.")
        self.app.refresh_active()

    def _open_enchant_window(self, item: Item) -> None:
        game = self.app.game
        window = tk.Toplevel(self.app.root, bg=theme.BG)
        theme.style_window(window, f"Enchant {item.name}")
        theme.center_window(window, 420, 400)
        window.transient(self.app.root)
        frame = tk.Frame(window, bg=theme.BG, padx=16, pady=14)
        frame.pack(fill=tk.BOTH, expand=True)
        theme.heading_label(frame, text=f"Enchant {item.name}").pack(anchor="w")
        rarity_cfg = game.config.get("rarities") or {}
        slots = item.effective_enchant_slots(rarity_cfg)
        used = len(game.player.item_enchantments.get(item.id, []))
        theme.body_label(frame, text=f"Slots: {used}/{slots}", fg=theme.FG_DIM).pack(anchor="w", pady=(4, 8))

        current = game.player.item_enchantments.get(item.id, [])
        if current:
            theme.body_label(frame, text="Current:").pack(anchor="w")
            for eid in current:
                ench = game.enchantments.get(eid)
                theme.body_label(frame, text=f"  {eid}: {ench.name if ench else eid}", font=theme.FONT_SMALL).pack(anchor="w")
                theme.flat_button(frame, f"Remove {eid}", lambda e=eid: (game.disenchant_item(item.id, e), self.app.refresh_active(), window.destroy())).pack(fill=tk.X, pady=2)
        else:
            theme.body_label(frame, text="No enchantments", fg=theme.FG_DIM).pack(anchor="w")

        theme.body_label(frame, text="Available:", font=theme.FONT_SMALL).pack(anchor="w", pady=(12, 4))
        picker: SelectList[str] = SelectList(frame, height=6)
        options = [(f"{ench.name} - {ench.gold_cost}g: " + ", ".join(ench.modifiers.describe()), ench.id) for ench in game.enchantments.all_definitions()]
        picker.set_items(options)
        picker.pack(fill=tk.BOTH, expand=True)

        def apply_enchant():
            eid = picker.selected_value
            if not eid:
                return
            ok, msg = game.enchant_item(item.id, eid)
            self.app.notify(msg)
            self.app.refresh_active()
            window.destroy()

        theme.flat_button(frame, "Enchant", apply_enchant).pack(fill=tk.X, pady=(12, 0))
        theme.flat_button(frame, "Close", window.destroy).pack(fill=tk.X, pady=(6, 0))

    def _close(self) -> None:
        self.app.close_toplevel("equipment")
