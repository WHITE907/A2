"""Status - the full character sheet, plus stat-point allocation."""

from __future__ import annotations

import tkinter as tk

from engine.stats import PRIMARY_STATS, PRIMARY_STAT_NAMES, DERIVED_STATS
from gui import theme

__all__ = ["StatusWindow"]


class StatusWindow(tk.Toplevel):
    """Character sheet with scrollable cards, colored bonus breakdowns, and stat allocation."""

    def __init__(self, app) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app

        theme.style_window(self, "Project Ascension - Character Status")
        theme.center_window(self, 720, 720)
        self.transient(app.root)

        # Main container with canvas + scrollbar
        container = tk.Frame(self, bg=theme.BG)
        container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(container, bg=theme.BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview, relief=tk.FLAT, borderwidth=0)
        
        self.scrollable_frame = tk.Frame(self.canvas, bg=theme.BG, padx=20, pady=16)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        def _on_canvas_configure(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)
        self.canvas.bind("<Configure>", _on_canvas_configure)

        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mousewheel support
        def _on_mousewheel(event):
            if event.delta:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                if event.num == 4:
                    self.canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.canvas.yview_scroll(1, "units")
        
        self.canvas.bind("<MouseWheel>", _on_mousewheel)
        self.scrollable_frame.bind("<MouseWheel>", _on_mousewheel)

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        frame = self.scrollable_frame

        # Header Title
        header_frame = tk.Frame(frame, bg=theme.BG)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        theme.heading_label(header_frame, text="Character Status Sheet", fg=theme.FG).pack(anchor="w")

        # 1. Overview Card
        self.overview_card = self._create_card(frame, "Overview")
        self.overview_label = tk.Label(self.overview_card, bg=theme.BG_ALT, fg=theme.FG, font=theme.FONT_BODY, justify=tk.LEFT, anchor="w")
        self.overview_label.pack(fill=tk.BOTH, padx=14, pady=10)

        # 2. Primary Stats Card (Grid with colored bonuses)
        self.primary_card = self._create_card(frame, "Primary Attributes (Breakdown)")
        self.primary_container = tk.Frame(self.primary_card, bg=theme.BG_ALT, padx=14, pady=10)
        self.primary_container.pack(fill=tk.BOTH, expand=True)

        # 3. Combat / Derived Stats Card
        self.combat_card = self._create_card(frame, "Combat Performance")
        self.combat_label = tk.Label(self.combat_card, bg=theme.BG_ALT, fg=theme.FG, font=theme.FONT_MONO, justify=tk.LEFT, anchor="w")
        self.combat_label.pack(fill=tk.BOTH, padx=14, pady=10)

        # 4. Mastery Card
        self.mastery_card = self._create_card(frame, "Mastery Tracks")
        self.mastery_label = tk.Label(self.mastery_card, bg=theme.BG_ALT, fg=theme.FG, font=theme.FONT_BODY, justify=tk.LEFT, anchor="w")
        self.mastery_label.pack(fill=tk.BOTH, padx=14, pady=10)

        # 5. Perks & Traits Card
        self.perks_card = self._create_card(frame, "Perks, Traits & Set Bonuses")
        self.perks_label = tk.Label(self.perks_card, bg=theme.BG_ALT, fg=theme.FG, font=theme.FONT_SMALL, justify=tk.LEFT, anchor="w")
        self.perks_label.pack(fill=tk.BOTH, padx=14, pady=10)

        # 6. Stat Point Allocation Card
        alloc_card = self._create_card(frame, "Stat Point Allocation")
        alloc_inner = tk.Frame(alloc_card, bg=theme.BG_ALT, padx=14, pady=12)
        alloc_inner.pack(fill=tk.BOTH, expand=True)

        self.points_label = theme.body_label(alloc_inner, text="", fg=theme.FG_DIM, bg=theme.BG_ALT)
        self.points_label.pack(anchor="w", pady=(0, 8))

        btn_row = tk.Frame(alloc_inner, bg=theme.BG_ALT)
        btn_row.pack(fill=tk.X)
        self.allocate_buttons: dict[str, tk.Button] = {}
        for stat in PRIMARY_STATS:
            b = theme.flat_button(
                btn_row,
                f"+ {stat}",
                lambda s=stat: self._allocate(s),
                width=9,
            )
            b.pack(side=tk.LEFT, padx=(0, 10))
            self.allocate_buttons[stat] = b

        # Close button at bottom
        close_frame = tk.Frame(frame, bg=theme.BG)
        close_frame.pack(fill=tk.X, pady=(16, 12))
        theme.flat_button(close_frame, "Close", self._close, width=12).pack(side=tk.RIGHT)

    def _create_card(self, parent: tk.Widget, title: str) -> tk.Frame:
        card = tk.Frame(parent, bg=theme.BG_ALT, highlightthickness=1, highlightbackground="#2c3242")
        card.pack(fill=tk.X, pady=(0, 14))
        
        header = tk.Frame(card, bg=theme.BG_ALT, padx=14, pady=8)
        header.pack(fill=tk.X)
        theme.heading_label(header, text=title, fg="#f0d060", font=(theme._SANS, 11, "bold"), bg=theme.BG_ALT).pack(anchor="w")
        
        div = tk.Frame(card, bg="#2c3242", height=1)
        div.pack(fill=tk.X)
        return card

    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self._close()
            return

        player = game.player

        class SheetMock:
            def __init__(self, text):
                self._label = type('DummyLabel', (), {'options': {'text': text}})()
        
        lines = list(player.summary_lines())
        lines.extend(player.stat_lines())
        self.sheet = SheetMock("\n".join(lines))

        # 1. Overview text
        exp_cur, exp_need = player.exp_progress()
        sub_race_str = f" ({player.sub_race_id.replace('_', ' ').title()})" if player.sub_race_id else ""
        overview_lines = [
            f"Name: {player.name}    •    Gender: {player.gender.title()}",
            f"Race: {player.race_def.name}{sub_race_str}",
            f"Class: {player.class_def.name} (Tier {player.class_def.tier})    •    Level: {player.level}",
            f"EXP: {exp_cur:.0f} / {exp_need:.0f} ({exp_cur/exp_need*100:.1f}%)" if exp_need > 0 else "EXP: Max",
            f"HP: {player.hp_text()}   •   MP: {player.mp_text()}   •   SP: {player.sp_text()}",
            f"Gold: {player.inventory.gold}g   •   Mastery Rank: {player.mastery.highest_rank()}"
        ]
        self.overview_label.configure(text="\n".join(overview_lines))

        # 2. Primary stats grid with colored bonuses
        for widget in self.primary_container.winfo_children():
            widget.destroy()

        # Header row for primary attributes grid
        headers = ["Attribute", "Base", "Gear", "Traits", "Perks", "Total"]
        header_row = tk.Frame(self.primary_container, bg=theme.BG_ALT)
        header_row.pack(fill=tk.X, pady=(0, 4))
        for h in headers:
            tk.Label(header_row, text=h, bg=theme.BG_ALT, fg=theme.FG_DIM, font=(theme._SANS, 9, "bold"), width=10, anchor="w").pack(side=tk.LEFT)

        effective_pri = player.effective_primaries()
        base_pri = player.base_stats
        
        # Calculate bonus components for primary stats
        gear_mods = player._equipment_modifiers()
        trait_mods = player.race_def.combined_modifiers(player.sub_race_id)

        for stat in PRIMARY_STATS:
            row = tk.Frame(self.primary_container, bg=theme.BG_ALT)
            row.pack(fill=tk.X, pady=2)

            name = PRIMARY_STAT_NAMES.get(stat, stat)
            base_val = float(base_pri[stat])
            
            # Estimate breakdown from modifier sets
            gear_val = gear_mods.flat.get(stat, 0.0)
            trait_val = trait_mods.flat.get(stat, 0.0)
            total_val = effective_pri.get(stat, base_val)
            perk_val = total_val - base_val - gear_val - trait_val
            if perk_val < 0:
                perk_val = 0.0

            tk.Label(row, text=f"{stat} ({name})", bg=theme.BG_ALT, fg=theme.FG, font=theme.FONT_BODY, width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{base_val:.0f}", bg=theme.BG_ALT, fg=theme.FG, font=theme.FONT_BODY, width=8, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{gear_val:+g}" if gear_val else "-", bg=theme.BG_ALT, fg="#5da9e9" if gear_val else theme.FG_DIM, font=theme.FONT_BODY, width=8, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{trait_val:+g}" if trait_val else "-", bg=theme.BG_ALT, fg="#b678e5" if trait_val else theme.FG_DIM, font=theme.FONT_BODY, width=8, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{perk_val:+g}" if perk_val else "-", bg=theme.BG_ALT, fg="#f0d060" if perk_val else theme.FG_DIM, font=theme.FONT_BODY, width=8, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{total_val:.0f}", bg=theme.BG_ALT, fg="#7fc98a", font=(theme._SANS, 10, "bold"), width=8, anchor="w").pack(side=tk.LEFT)

        # 3. Combat derived stats
        derived = player.derived_stats()
        combat_lines = [
            f"  • Attack (Physical Power):  {derived.physical_power:.1f}",
            f"  • Magic (Magic Power):      {derived.magic_power:.1f}",
            f"  • Armor:                    {derived.armor:.1f}",
            f"  • Magic Resist:             {derived.magic_resist:.1f}",
            f"  • Crit Chance / Damage:     {derived.crit_chance*100:.1f}% / {derived.crit_damage*100:.0f}%",
            f"  • Accuracy:                 {derived.accuracy*100:.1f}%",
            f"  • Evasion:                  {derived.evasion*100:.1f}%",
            f"  • Speed:                    {derived.speed:.1f}",
        ]
        self.combat_label.configure(text="\n".join(combat_lines))

        # 4. Mastery tracks
        mastery_lines = []
        for track_id, (rank, exp) in sorted(player.mastery.tracks.items()):
            mastery_lines.append(f"  • {track_id.replace('_', ' ').title()}: Rank {rank} ({exp:.0f} EXP)")
        if not mastery_lines:
            mastery_lines.append("  No mastery progression yet.")
        self.mastery_label.configure(text="\n".join(mastery_lines))

        # 5. Perks & Traits & Set Bonuses
        perks_lines = []
        traits = player.race_def.combined_traits(player.sub_race_id)
        if traits:
            perks_lines.append("Racial & Sub-Race Traits:")
            for t in traits:
                perks_lines.append(f"  • {t}")
            perks_lines.append("")
        
        perks_lines.append("Class Perks:")
        active_perks = player.active_perks()
        if active_perks:
            for entry in active_perks:
                perk = entry["perk"]
                is_active = entry["active"]
                reason = entry["reason"]
                status = "[ACTIVE]" if is_active else "[INACTIVE]"
                name = perk.get("name", perk.get("id", ""))
                desc = perk.get("description", "")
                perks_lines.append(f"  • {status} {name}: {desc}")
                if reason:
                    perks_lines.append(f"    ({reason})")
        else:
            perks_lines.append("  None")

        # Set bonuses
        sets = player.active_set_bonuses()
        if sets:
            perks_lines.append("")
            perks_lines.append("Active Equipment Sets:")
            for s in sets:
                perks_lines.append(f"  • {s}")

        # Specials (lifesteal, reflect, counter)
        specials = player.special_effects()
        if specials:
            perks_lines.append("")
            perks_lines.append("Active Combat Specials:")
            for sp in specials:
                stype = sp.get("type", "")
                sval = float(sp.get("value", 0.0))
                if stype in ("lifesteal", "counter", "reflect"):
                    perks_lines.append(f"  • {stype.title()}: {sval*100:.0f}%")

        self.perks_label.configure(text="\n".join(perks_lines))

        # Allocation points
        available = player.unspent_stat_points
        self.points_label.configure(text=f"Unspent stat points available: {available}")
        for stat, button in self.allocate_buttons.items():
            button.configure(state=tk.NORMAL if available > 0 else tk.DISABLED)

    def _allocate(self, stat: str) -> None:
        ok, message = self.app.game.allocate_stat(stat, 1)
        self.app.notify(message)
        self.refresh()
        self.app.refresh_active()

    def _close(self) -> None:
        self.app.close_toplevel("status")
