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
from gui.widgets import ScrollableFrame, ButtonStack, LogPanel, SelectList, StatPanel

__all__ = ["WorldScreen"]


class WorldScreen(tk.Frame):
    """Travel, explore, rest, shop and talk."""

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=theme.BG)
        self.app = app

        # The hub can be taller than a small laptop viewport once every action
        # is available, so the full page has a vertical fallback scrollbar.
        self.viewport = ScrollableFrame(self, bg=theme.BG, padx=16, pady=14)
        self.viewport.pack(fill=tk.BOTH, expand=True)
        outer = self.viewport.content

        # ---------------- left: character + location -------------------
        # Both side columns must keep pack propagation on so their requested
        # height grows with their panels.  With pack_propagate(False) a
        # column collapses to its minimum height and the panels stacked
        # inside it are clipped - they never contribute to the page
        # ScrollableFrame's region, so the hub cannot scroll down to them
        # either.  (The combat screen's left column was rescued from the same
        # trap; the width option still holds as the minimum column width.)
        self.left_column = left = tk.Frame(outer, bg=theme.BG, width=230)
        left.pack(side=tk.LEFT, fill=tk.Y)

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
        self.right_column = right = tk.Frame(outer, bg=theme.BG, width=190)
        right.pack(side=tk.LEFT, fill=tk.Y)

        theme.heading_label(right, text="Actions").pack(anchor="w", pady=(0, 6))

        self.actions = ButtonStack(right, spacing=5)
        self.actions.add("explore", "Explore", self._explore)
        self.actions.add("rest", "Rest at Inn", self._rest)
        self.actions.add("shop", "Shops", self._shops)
        self.actions.add("talk", "People", self._people)
        self.actions.add("heritage", "Heritage", self._heritage)
        self.actions.pack(fill=tk.X)

        theme.body_label(right, text="").pack(pady=4)

        self.menus = ButtonStack(right, spacing=5)
        self.menus.add("status", "Status", self.app.open_status)
        self.menus.add("inventory", "Inventory", self.app.open_inventory)
        self.menus.add("equipment", "Equipment", self.app.open_equipment)
        self.menus.add("skills", "Skills", self.app.open_skills)
        self.menus.add("quests", "Quests", self.app.open_quests)
        self.menus.add("party", "Party", self.app.open_party)
        self.menus.add("codex", "Codex", self.app.open_codex)
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
        player_level = game.player.level if game.player else 1
        rows = []
        colors = []
        for a in areas:
            diff = a.recommended_level - player_level
            # Color coding: green easy, yellow equal, orange hard, red very hard
            if diff <= -5:
                color = "#7fbf7f"  # green easy
                tag = "Easy"
            elif diff <= -1:
                color = "#a3d977"  # light green
                tag = "Easy"
            elif diff <= 2:
                color = "#e8e8a0"  # yellow ~ even
                tag = "Even"
            elif diff <= 5:
                color = "#e8b860"  # orange hard
                tag = "Hard"
            else:
                color = "#e0736b"  # red very hard
                tag = "Deadly"
            label = f"{a.name}  (Lv {a.recommended_level}) [{tag}]"
            if a.is_town:
                label = f"{label} [Town]"
            rows.append((label, a))
            colors.append(color)
        self.travel_list.set_items(rows, keep_selection=False)
        self.travel_list.set_row_colors(colors)

        # The engine decides what is possible; the UI only reflects it.
        in_town = game.world.is_in_town()
        self.actions.set_enabled("explore", not in_town)
        self.actions.set_enabled("rest", in_town)
        self.actions.set_enabled("shop", bool(game.world.shops_here()))
        self.actions.set_enabled("talk", bool(game.npcs_here()))
        self.actions.set_enabled("heritage", bool(game.ancestry_actions()))

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

    def _heritage(self) -> None:
        actions = self.app.game.ancestry_actions()
        if not actions:
            self.app.notify("No heritage interaction is available here.")
            return
        if len(actions) == 1:
            self._perform_heritage(actions[0].id)
            return
        self._choose(
            "Heritage Choice",
            [(f"{action.name} — {action.description}", action.id) for action in actions],
            self._perform_heritage,
        )

    def _perform_heritage(self, action_id: str) -> None:
        ok, message = self.app.game.perform_ancestry_action(action_id)
        self.log.append(message, "quest" if ok else "info")
        self.app.notify(message.split("\n", 1)[0])
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

        viewport = ScrollableFrame(window, bg=theme.BG, padx=16, pady=14)
        viewport.pack(fill=tk.BOTH, expand=True)
        frame = viewport.content
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
