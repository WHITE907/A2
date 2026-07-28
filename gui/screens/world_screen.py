"""World screen - the hub of the game loop.

Bible section 8:
``Town -> Explore -> Combat -> Rewards -> Town -> Sleep -> Morning Autosave``

Left column: character summary and location.
Middle: travel destinations and the event log.
Right: the action button stack (Explore, Rest, Shops, People, Save, Menu).

Town-only actions are disabled outside town by asking the engine, never by the
UI deciding what a town is.
"""

from __future__ import annotations

import tkinter as tk

from gui import theme
from engine.world.world import Area
from gui.widgets import ButtonStack, LogPanel, SelectList, StatPanel

__all__ = ["WorldScreen"]


class WorldScreen(tk.Frame):
    """Travel, explore, rest, shop and talk."""

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=theme.BG)
        self.app = app

        outer = tk.Frame(self, bg=theme.BG, padx=16, pady=14)
        outer.pack(fill=tk.BOTH, expand=True)

        # ---------------- left: character + location -------------------
        left = tk.Frame(outer, bg=theme.BG, width=230)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        self.character_panel = StatPanel(left, title="Character")
        self.character_panel.pack(fill=tk.X, anchor="n")

        self.location_panel = StatPanel(left, title="Location", wrap=210)
        self.location_panel.pack(fill=tk.X, anchor="n", pady=(18, 0))

        # ---------------- middle: travel + log -------------------------
        middle = tk.Frame(outer, bg=theme.BG)
        middle.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=18)

        self.travel_list: SelectList[Area] = SelectList(
            middle, title="Travel", height=6, on_activate=lambda _v: self._travel()
        )
        self.travel_list.pack(fill=tk.X)

        theme.flat_button(middle, "Travel To Selected", self._travel).pack(fill=tk.X, pady=(8, 0))

        self.log = LogPanel(middle, title="Journal", height=14)
        self.log.pack(fill=tk.BOTH, expand=True, pady=(16, 0))

        # ---------------- right: actions -------------------------------
        right = tk.Frame(outer, bg=theme.BG, width=190)
        right.pack(side=tk.LEFT, fill=tk.Y)
        right.pack_propagate(False)

        theme.heading_label(right, text="Actions").pack(anchor="w", pady=(0, 6))

        self.actions = ButtonStack(right, spacing=5)
        self.actions.add("explore", "Explore", self._explore)
        self.actions.add("rest", "Rest at Inn", self._rest)
        self.actions.add("shop", "Shops", self._shops)
        self.actions.add("talk", "People", self._people)
        self.actions.pack(fill=tk.X)

        theme.body_label(right, text="").pack(pady=4)

        self.menus = ButtonStack(right, spacing=5)
        self.menus.add("status", "Status", self.app.open_status)
        self.menus.add("inventory", "Inventory", self.app.open_inventory)
        self.menus.add("equipment", "Equipment", self.app.open_equipment)
        self.menus.add("skills", "Skills", self.app.open_skills)
        self.menus.add("party", "Party", self.app.open_party)
        self.menus.add("save", "Save Game", lambda: self.app.open_save_browser("save"))
        self.menus.add("menu", "Main Menu", self._main_menu)
        self.menus.pack(fill=tk.X)

        self.log.append("Welcome to Project Ascension.", "system")
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self.app.show_main_menu()
            return

        self.character_panel.set_lines(game.player_summary())
        self.location_panel.set_lines(game.world_lines())

        areas = game.travel_options()
        self.travel_list.set_items(
            [(f"{a.name}  (Lv {a.recommended_level})", a) for a in areas], keep_selection=False
        )

        # The engine decides what is possible; the UI only reflects it.
        in_town = game.world.is_in_town()
        self.actions.set_enabled("explore", not in_town)
        self.actions.set_enabled("rest", in_town)
        self.actions.set_enabled("shop", bool(game.world.shops_here()))
        self.actions.set_enabled("talk", bool(game.npcs_here()))

    # ------------------------------------------------------------------
    def _travel(self) -> None:
        area = self.travel_list.selected_value
        if area is None:
            self.app.notify("Choose a destination.")
            return
        ok, message = self.app.game.travel_to(area.id)
        self.log.append(message, "system" if ok else "info")
        self.app.notify(message)
        self.refresh()

    def _explore(self) -> None:
        message, battle = self.app.game.explore()
        self.log.append(message, "damage" if battle else "info")
        self.app.notify(message)
        if battle is not None:
            self.app.show_combat()
        else:
            self.refresh()

    def _rest(self) -> None:
        ok, lines = self.app.game.rest_at_inn()
        for line in lines:
            self.log.append(line, "system" if ok else "info")
        self.app.notify(lines[0] if lines else "")
        self.refresh()

    def _shops(self) -> None:
        shops = self.app.game.world.shops_here()
        if not shops:
            self.app.notify("No shops here.")
            return
        # One shop opens directly; several need a chooser.
        if len(shops) == 1:
            self.app.open_shop(shops[0].id)
        else:
            self._choose(
                "Shops", [(shop.name, shop.id) for shop in shops], self.app.open_shop
            )

    def _people(self) -> None:
        npcs = self.app.game.npcs_here()
        if not npcs:
            self.app.notify("Nobody here.")
            return
        if len(npcs) == 1:
            self.app.open_talk(npcs[0].id)
        else:
            self._choose("People", [(npc.name, npc.id) for npc in npcs], self.app.open_talk)

    def _choose(self, title: str, options: list[tuple[str, str]], on_pick) -> None:
        """Tiny picker Toplevel for when more than one target is available."""
        window = tk.Toplevel(self.app.root, bg=theme.BG)
        theme.style_window(window, title)
        theme.center_window(window, 300, 260)
        window.transient(self.app.root)

        frame = tk.Frame(window, bg=theme.BG, padx=16, pady=14)
        frame.pack(fill=tk.BOTH, expand=True)
        theme.heading_label(frame, text=title).pack(anchor="w", pady=(0, 8))

        picker: SelectList[str] = SelectList(frame, height=6)
        picker.set_items(options)
        picker.pack(fill=tk.BOTH, expand=True)

        def confirm() -> None:
            value = picker.selected_value
            window.destroy()
            if value is not None:
                on_pick(value)

        theme.flat_button(frame, "Open", confirm).pack(fill=tk.X, pady=(12, 0))

    def _main_menu(self) -> None:
        self.app.show_main_menu()
