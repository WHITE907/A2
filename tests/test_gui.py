"""GUI test-suite, run headlessly via :mod:`tests.tk_stub`.

These import and construct the *real* screen classes against the *real*
engine, then invoke the same handler methods a click would trigger - which is
exactly the technique docs/GUI_VERIFICATION.md prescribes for driving the app
without mouse automation ("simulating the result of user interaction, not the
interaction itself").

Run with::

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests import tk_stub

# The stub must be installed before `gui` (or anything importing tkinter) loads.
tk_stub.install()

import tkinter as tk  # noqa: E402  - resolves to the stub

from engine.game import Game  # noqa: E402
from gui import theme  # noqa: E402
from gui.app import AscensionApp  # noqa: E402
from gui.widgets import ButtonStack, LogPanel, ScrollableFrame, SelectList, StatPanel  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_app(save_dir: Path | str | None = None, seed: int = 4242) -> AscensionApp:
    """A fully wired app on the fake toolkit, with real content loaded."""
    game = Game(data_dir=PROJECT_ROOT / "data", save_dir=save_dir, seed=seed)
    game.load_content()
    return AscensionApp(tk.Tk(), game)


def make_app_with_character(save_dir: Path | str | None = None, seed: int = 4242) -> AscensionApp:
    app = make_app(save_dir, seed)
    app.game.create_character("Test Hero", "male", "squire")
    return app


def make_app_with_party(save_dir=None, seed: int = 4242) -> AscensionApp:
    """An app whose player has a companion recruited."""
    app = make_app_with_character(save_dir, seed)
    app.game.player.level = 10
    app.game.player._recalculate_base_stats()
    app.game.player.inventory.add_gold(3000)
    app.game.recruit("rook")
    return app


def buttons_in(widget) -> list:
    return [w for w in widget.walk() if isinstance(w, tk.Button)]


def button_labelled(widget, text: str):
    for button in buttons_in(widget):
        if button.options.get("text") == text:
            return button
    return None


def listboxes_in(widget) -> list:
    return [w for w in widget.walk() if isinstance(w, tk.Listbox)]


# ======================================================================
class TestThemeContract(unittest.TestCase):
    """The palette and widget factories must match GUI_STYLE_REFERENCE.md."""

    def test_background_is_dark_navy(self):
        self.assertEqual(theme.BG.lower(), "#1a1f2e")
        self.assertEqual(theme.BG_ALT.lower(), "#20242f")

    def test_accent_is_dark_red(self):
        red, green, blue = (int(theme.ACCENT[i : i + 2], 16) for i in (1, 3, 5))
        self.assertGreater(red, green)
        self.assertGreater(red, blue)

    def test_buttons_are_flat_light_gray_with_dark_text(self):
        button = theme.flat_button(tk.Tk(), "Go", lambda: None)
        self.assertEqual(button.options["relief"], tk.FLAT)
        self.assertEqual(button.options["bg"], theme.BUTTON_BG)
        self.assertEqual(button.options["fg"], theme.BUTTON_FG)
        # "subtle border" - present but thin.
        self.assertEqual(button.options["borderwidth"], 1)

    def test_title_font_is_large_and_bold(self):
        self.assertGreaterEqual(theme.FONT_TITLE[1], 24)
        self.assertEqual(theme.FONT_TITLE[2], "bold")

    def test_version_label_is_small_and_plain(self):
        self.assertLess(theme.FONT_SMALL[1], theme.FONT_TITLE[1])
        self.assertEqual(len(theme.FONT_SMALL), 2, "version font must not be bold")

    def test_body_label_is_left_aligned(self):
        label = theme.body_label(tk.Tk(), text="Name: Hero")
        self.assertEqual(label.options["anchor"], "w")
        self.assertEqual(label.options["justify"], tk.LEFT)

    def test_accent_strip_uses_accent_colour(self):
        self.assertEqual(theme.accent_strip(tk.Tk()).options["bg"], theme.ACCENT)

    def test_listbox_factory_defaults_to_no_exportselection(self):
        """The exact bug documented in GUI_VERIFICATION.md."""
        self.assertFalse(theme.stat_listbox(tk.Tk()).options["exportselection"])


# ======================================================================
class TestExportSelectionRegression(unittest.TestCase):
    """Two coexisting Listboxes must keep independent selections.

    GUI_VERIFICATION.md: with the Tk default (``exportselection=True``) the
    second listbox steals the X PRIMARY selection and ``curselection()`` on the
    first silently returns ``()``.  The stub reproduces that behaviour, so the
    first test below proves the harness can actually detect the bug and the
    second proves the shipped widgets avoid it.
    """

    def test_stub_reproduces_the_bug_with_tk_defaults(self):
        root = tk.Tk()
        first = tk.Listbox(root, exportselection=True)
        second = tk.Listbox(root, exportselection=True)
        for box in (first, second):
            box.insert(tk.END, "a", "b")

        first.selection_set(0)
        self.assertEqual(first.curselection(), (0,))
        second.selection_set(1)
        self.assertEqual(first.curselection(), (), "harness should model the PRIMARY conflict")

    def test_theme_listboxes_keep_independent_selections(self):
        root = tk.Tk()
        first = theme.stat_listbox(root)
        second = theme.stat_listbox(root)
        for box in (first, second):
            box.insert(tk.END, "a", "b")

        first.selection_set(0)
        second.selection_set(1)
        self.assertEqual(first.curselection(), (0,))
        self.assertEqual(second.curselection(), (1,))

    def test_every_listbox_in_the_app_disables_exportselection(self):
        """Sweeps every screen, including Toplevels, for a stray default."""
        app = make_app_with_character()
        offenders: list[str] = []

        screens = [app.show_world(), app.show_main_menu(), app.show_launcher()]
        app.game.start_battle([("green_slime", 1)])
        screens.append(app.show_combat())

        openers = [
            app.open_inventory,
            app.open_equipment,
            app.open_skills,
            app.open_quests,
            app.open_party,
            app.open_status,
            app.open_settings,
            lambda: app.open_save_browser("load"),
            app.open_character_creation,
            lambda: app.open_shop("ashvale_general"),
            lambda: app.open_talk("innkeeper_mara"),
        ]
        windows = [opener() for opener in openers]

        for widget in [*screens, *windows]:
            for box in listboxes_in(widget):
                if box.options.get("exportselection", True):
                    offenders.append(repr(widget))
        self.assertEqual(offenders, [])

    def test_combat_action_and_target_selections_coexist(self):
        """The concrete case GUI_VERIFICATION.md found the bug in."""
        app = make_app_with_character()
        app.game.start_battle([("green_slime", 1), ("field_rat", 1)])
        screen = app.show_combat()

        screen.action_list.select_index(0)
        screen.target_list.select_index(0)

        self.assertIsNotNone(screen.action_list.selected_value)
        self.assertIsNotNone(screen.target_list.selected_value)


# ======================================================================
class TestWidgets(unittest.TestCase):
    """The shared composite widgets."""

    def setUp(self):
        self.root = tk.Tk()

    def test_statpanel_renders_stacked_lines(self):
        panel = StatPanel(self.root, title="Character")
        panel.set_lines(["Name: Hero", "Level: 3"])
        self.assertIn("Name: Hero\nLevel: 3", panel._label.options["text"])

    def test_buttonstack_enable_disable(self):
        stack = ButtonStack(self.root)
        stack.add("go", "Go", lambda: None)
        stack.set_enabled("go", False)
        self.assertEqual(stack.buttons["go"].options["state"], tk.DISABLED)
        stack.set_all_enabled(True)
        self.assertEqual(stack.buttons["go"].options["state"], tk.NORMAL)

    def test_selectlist_maps_rows_to_values(self):
        picker = SelectList(self.root)
        picker.set_items([("One", 1), ("Two", 2)])
        picker.select_index(1)
        self.assertEqual(picker.selected_value, 2)

    def test_selectlist_autoselects_first_item(self):
        picker = SelectList(self.root)
        picker.set_items([("One", 1), ("Two", 2)])
        self.assertEqual(picker.selected_value, 1)

    def test_selectlist_preserves_selection_across_refresh(self):
        picker = SelectList(self.root)
        picker.set_items([("One", 1), ("Two", 2), ("Three", 3)])
        picker.select_index(2)
        picker.set_items([("One", 1), ("Two", 2), ("Three", 3)], keep_selection=True)
        self.assertEqual(picker.selected_value, 3)

    def test_selectlist_empty_returns_none(self):
        picker = SelectList(self.root)
        picker.set_items([])
        self.assertIsNone(picker.selected_value)

    def test_selectlist_fires_callback(self):
        seen: list[object] = []
        picker = SelectList(self.root, on_select=seen.append)
        picker.set_items([("One", 1), ("Two", 2)])
        picker.select_index(1)
        self.assertEqual(seen[-1], 2)

    def test_logpanel_appends_and_clears(self):
        log = LogPanel(self.root)
        log.append("hello", "damage")
        self.assertIn("hello", log.text.content)
        log.clear()
        self.assertEqual(log.text.content, "")

    def test_logpanel_registers_colour_tags(self):
        log = LogPanel(self.root)
        for kind in theme.LOG_COLORS:
            self.assertIn(kind, log.text.tags)

    def test_logpanel_is_read_only_after_write(self):
        log = LogPanel(self.root)
        log.append("x")
        self.assertEqual(log.text.options["state"], tk.DISABLED)


# ======================================================================
class TestScrollableLayout(unittest.TestCase):
    """Long pages remain usable on compact displays instead of clipping controls."""

    def setUp(self):
        self.root = tk.Tk()

    def test_scrollable_frame_owns_a_canvas_content_area_and_scrollbar(self):
        page = ScrollableFrame(self.root)
        page.pack(fill=tk.BOTH, expand=True)
        self.assertIsInstance(page.canvas, tk.Canvas)
        self.assertIsInstance(page.content, tk.Frame)
        self.assertIsInstance(page.scrollbar, tk.Scrollbar)

        page.content.event_generate("<MouseWheel>", delta=-120, num=None)
        self.assertEqual(page.canvas.yview_scroll_calls[-1], (1, "units"))

    def test_main_and_toplevel_screens_use_scrollable_viewports(self):
        app = make_app_with_character()
        self.assertIsInstance(app.show_world().viewport, ScrollableFrame)

        app.game.start_battle([("green_slime", 1)])
        self.assertIsInstance(app.show_combat().viewport, ScrollableFrame)

        windows = [
            app.open_inventory(),
            app.open_equipment(),
            app.open_skills(),
            app.open_quests(),
            app.open_party(),
            app.open_status(),
            app.open_settings(),
            app.open_save_browser("load"),
            app.open_character_creation(),
            app.open_shop("ashvale_general"),
            app.open_talk("innkeeper_mara"),
            app.open_codex(),
        ]
        self.assertTrue(all(isinstance(window.viewport, ScrollableFrame) for window in windows))

    def test_dialogue_and_tactics_popups_use_scrollable_viewports(self):
        app = make_app_with_party()
        tactics = app.open_tactics("rook")
        self.assertIsInstance(tactics.viewport, ScrollableFrame)

        stories = app.game.dialogues_for_speaker("mother_sable")
        self.assertTrue(stories)
        dialogue = app.open_dialogue(stories[0]["id"])
        self.assertIsInstance(dialogue.viewport, ScrollableFrame)


# ======================================================================
class TestAppShell(unittest.TestCase):
    """Screen swapping and Toplevel lifecycle."""

    def setUp(self):
        self.app = make_app()

    def test_starts_on_launcher(self):
        from gui.screens.launcher import LauncherScreen

        self.assertIsInstance(self.app.current_screen, LauncherScreen)

    def test_root_uses_theme_background_and_title(self):
        self.assertEqual(self.app.root.options["bg"], theme.BG)
        self.assertEqual(self.app.root.title(), "Project Ascension")

    def test_accent_strip_is_packed_at_the_bottom(self):
        strips = [
            w
            for w in self.app.root.walk()
            if isinstance(w, tk.Frame) and w.options.get("bg") == theme.ACCENT
        ]
        self.assertTrue(strips)
        self.assertEqual(strips[0]._pack_options.get("side"), tk.BOTTOM)

    def test_screen_swap_destroys_previous(self):
        first = self.app.show_main_menu()
        self.app.show_launcher()
        self.assertFalse(first.winfo_exists())

    def test_toplevel_is_reused_not_duplicated(self):
        self.app.game.create_character("Hero", "male", "squire")
        first = self.app.open_inventory()
        second = self.app.open_inventory()
        self.assertIs(first, second)

    def test_closing_toplevel_removes_it(self):
        self.app.game.create_character("Hero", "male", "squire")
        self.app.open_inventory()
        self.app.close_toplevel("inventory")
        self.assertNotIn("inventory", self.app._toplevels)

    def test_screen_swap_closes_open_toplevels(self):
        """Style reference: sub-screens layer over the *main menu*."""
        self.app.game.create_character("Hero", "male", "squire")
        self.app.show_world()
        self.app.open_inventory()
        self.app.show_main_menu()
        self.assertEqual(self.app._toplevels, {})

    def test_notify_writes_to_status_bar(self):
        self.app.notify("Saved.")
        self.assertEqual(self.app.status_bar._label.options["text"], "Saved.")

    def test_refresh_active_updates_open_windows(self):
        self.app.game.create_character("Hero", "male", "squire")
        self.app.show_world()
        window = self.app.open_status()
        self.app.game.player.inventory.add_gold(777)
        expected = self.app.game.player.inventory.gold  # starting gold + 777
        self.app.refresh_active()
        self.assertIn(f"Gold: {expected}", window.sheet._label.options["text"])


# ======================================================================
class TestLauncherAndMainMenu(unittest.TestCase):
    """The two screens the style reference describes directly."""

    def setUp(self):
        self.app = make_app()

    def test_launcher_shows_title_and_version(self):
        screen = self.app.current_screen
        texts = [w.options.get("text", "") for w in screen.walk() if isinstance(w, tk.Label)]
        self.assertTrue(any("ASCENSION" in t.upper() for t in texts))
        self.assertTrue(any(t.startswith("Version") for t in texts))

    def test_launcher_reports_content_counts(self):
        panels = [w for w in self.app.current_screen.walk() if isinstance(w, StatPanel)]
        self.assertTrue(any("Classes:" in p._label.options["text"] for p in panels))

    def test_main_menu_has_the_four_reference_buttons(self):
        screen = self.app.show_main_menu()
        labels = {b.options.get("text") for b in buttons_in(screen)}
        self.assertLessEqual({"New Game", "Load Game", "Delete Save", "Exit"}, labels)

    def test_main_menu_buttons_are_a_vertical_full_width_stack(self):
        screen = self.app.show_main_menu()
        for key in ("new", "load", "delete", "exit"):
            options = screen.stack.buttons[key]._pack_options
            self.assertEqual(options.get("fill"), tk.X)
            self.assertGreaterEqual(options.get("pady", 0), 5, "needs generous spacing")

    def test_main_menu_hides_continue_without_character(self):
        screen = self.app.show_main_menu()
        self.assertFalse(screen.continue_button.winfo_ismapped())

    def test_main_menu_shows_preview_with_character(self):
        self.app.game.create_character("Aria", "female", "maiden")
        screen = self.app.show_main_menu()
        text = screen.preview._label.options["text"]
        self.assertIn("Aria", text)
        self.assertIn("Maiden", text)
        self.assertTrue(screen.continue_button.winfo_ismapped())

    def test_new_game_button_opens_character_creation_toplevel(self):
        screen = self.app.show_main_menu()
        button_labelled(screen, "New Game").invoke()
        window = self.app._toplevels.get("character_creation")
        self.assertIsInstance(window, tk.Toplevel)

    def test_sub_screen_is_a_toplevel_not_a_swapped_frame(self):
        """Style reference: the main menu stays visible behind sub-screens."""
        screen = self.app.show_main_menu()
        self.app.open_save_browser("load")
        self.assertIs(self.app.current_screen, screen)
        self.assertTrue(screen.winfo_exists())


# ======================================================================
class TestCharacterCreation(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.window = self.app.open_character_creation()

    def test_lists_starting_classes(self):
        self.assertGreater(self.window.class_list.count, 0)

    def test_lists_playable_races(self):
        self.assertEqual(self.window.race_list.count, 15)

    def test_selecting_a_race_shows_traits(self):
        elf_index = next(
            index for index, race in enumerate(self.window.race_list._values) if race.id == "elf"
        )
        self.window.race_list.select_index(elf_index)
        self.assertIn("Keen Senses", self.window.preview._label.options["text"])

    def test_gender_switch_requeries_classes(self):
        """Bible section 10: starting classes are gender-restricted."""
        male = {label for label, _ in zip(self.window.class_list.listbox.items, range(99))}
        self.window.gender_var.set("female")
        self.window._reload_classes()
        female = set(self.window.class_list.listbox.items)
        self.assertIn("Squire", male)
        self.assertNotIn("Squire", female)
        self.assertIn("Maiden", female)

    def test_selecting_a_class_shows_details(self):
        self.window.class_list.select_index(0)
        self.assertIn("Base stats", self.window.preview._label.options["text"])

    def test_empty_name_is_rejected(self):
        self.window.name_var.set("")
        self.window._create()
        self.assertFalse(self.app.game.has_character)
        self.assertIn("name", self.app.status_bar._label.options["text"].lower())

    def test_creating_a_character_opens_the_world(self):
        from gui.screens.world_screen import WorldScreen

        elf_index = next(
            index for index, race in enumerate(self.window.race_list._values) if race.id == "elf"
        )
        self.window.name_var.set("Hero")
        self.window.race_list.select_index(elf_index)
        self.window.class_list.select_index(0)
        self.window._create()
        self.assertTrue(self.app.game.has_character)
        self.assertEqual(self.app.game.player.race_id, "elf")
        self.assertIsInstance(self.app.current_screen, WorldScreen)


# ======================================================================
class TestWorldScreen(unittest.TestCase):
    def setUp(self):
        self.app = make_app_with_character()
        self.screen = self.app.show_world()

    def test_shows_character_and_location(self):
        self.assertIn("Test Hero", self.screen.character_panel._label.options["text"])
        self.assertIn("Ashvale", self.screen.location_panel._label.options["text"])

    def test_town_disables_explore_and_enables_rest(self):
        self.assertEqual(self.screen.actions.buttons["explore"].options["state"], tk.DISABLED)
        self.assertEqual(self.screen.actions.buttons["rest"].options["state"], tk.NORMAL)

    def test_travelling_flips_those_buttons(self):
        self.screen.travel_list.set_items(
            [(a.name, a) for a in self.app.game.travel_options()], keep_selection=False
        )
        self.screen._travel()
        self.assertEqual(self.app.game.world.current_area_id, "greenfields")
        self.assertEqual(self.screen.actions.buttons["explore"].options["state"], tk.NORMAL)
        self.assertEqual(self.screen.actions.buttons["rest"].options["state"], tk.DISABLED)

    def test_explore_in_town_is_refused_gracefully(self):
        self.screen._explore()
        self.assertIn("peaceful", self.screen.log.text.content.lower())

    def test_explore_can_start_a_battle_and_switch_screens(self):
        from gui.screens.combat_screen import CombatScreen

        self.app.game.travel_to("greenfields")
        for _ in range(80):
            self.screen = self.app.show_world()
            self.screen._explore()
            if isinstance(self.app.current_screen, CombatScreen):
                self.assertIsNotNone(self.app.game.battle)
                return
        self.fail("exploration never produced a battle")

    def test_rest_advances_the_day_and_logs_autosave(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = make_app_with_character(save_dir=tmp)
            screen = app.show_world()
            app.game.player.inventory.add_gold(200)
            screen._rest()
            self.assertEqual(app.game.world.day, 2)
            self.assertIn("autosave", screen.log.text.content.lower())

    def test_action_buttons_open_the_right_windows(self):
        for label, key in (
            ("Status", "status"),
            ("Inventory", "inventory"),
            ("Equipment", "equipment"),
            ("Skills", "skills"),
        ):
            button_labelled(self.screen, label).invoke()
            self.assertIn(key, self.app._toplevels, label)


# ======================================================================
class TestCombatScreen(unittest.TestCase):
    def setUp(self):
        self.app = make_app_with_character()
        self.app.game.start_battle([("green_slime", 1)])
        self.screen = self.app.show_combat()

    def test_lists_actions_including_basic_attack(self):
        self.assertIn("Attack", self.screen.action_list.listbox.items)

    def test_lists_living_enemies_as_targets(self):
        self.assertEqual(self.screen.target_list.count, 1)
        self.assertIn("Green Slime", self.screen.target_list.listbox.items[0])

    def test_panels_show_hp(self):
        self.assertIn("HP:", self.screen.player_panel._label.options["text"])
        self.assertIn("HP", self.screen.enemy_panel._label.options["text"])

    def test_attacking_damages_the_enemy_and_logs_it(self):
        enemy = self.app.game.battle.enemies[0]
        before = enemy.current_hp
        self.screen.action_list.select_index(0)
        self.screen.target_list.select_index(0)
        self.screen._use_selected()
        self.assertTrue(enemy.current_hp < before or not enemy.is_alive or self.app.game.battle.is_over)
        self.assertTrue(self.screen.log.text.content.strip())

    def test_defend_applies_guard(self):
        """Guard must be active for the enemy turns it is meant to blunt.

        It is checked immediately after the button's handler and before the
        AI turns run, because Guard is a 1-round buff that correctly expires
        during end-of-round upkeep.
        """
        battle = self.app.game.battle
        before_armor = self.app.game.player.derived_stats().armor
        battle.player_defend()
        self.assertTrue(self.app.game.player.has_status("guard"))
        self.assertGreater(self.app.game.player.derived_stats().armor, before_armor)

    def test_battle_can_be_fought_to_a_conclusion_through_the_ui(self):
        for _ in range(80):
            battle = self.app.game.battle
            if battle is None or battle.is_over:
                break
            if battle.waiting_for_player:
                self.screen.action_list.select_index(0)
                if self.screen.target_list.count:
                    self.screen.target_list.select_index(0)
                self.screen._use_selected()
            else:
                battle.run_until_player_turn()
                self.screen.refresh()
        self.assertTrue(self.app.game.battle.is_over)

    def test_continue_button_appears_when_battle_ends(self):
        for _ in range(80):
            battle = self.app.game.battle
            if battle.is_over:
                break
            if battle.waiting_for_player:
                self.screen.action_list.select_index(0)
                self.screen._use_selected()
            else:
                battle.run_until_player_turn()
        self.screen.refresh()
        self.assertTrue(self.screen.continue_button.winfo_ismapped())

    def test_finishing_returns_to_the_world_screen(self):
        from gui.screens.world_screen import WorldScreen

        for _ in range(80):
            battle = self.app.game.battle
            if battle.is_over:
                break
            if battle.waiting_for_player:
                self.screen.action_list.select_index(0)
                self.screen._use_selected()
            else:
                battle.run_until_player_turn()
        self.screen.refresh()
        self.screen._finish()
        self.assertIsInstance(self.app.current_screen, WorldScreen)

    def test_action_buttons_disabled_when_not_player_turn(self):
        battle = self.app.game.battle
        battle._turn_index = len(battle.turn_order)  # nobody's turn -> not waiting
        self.screen.refresh()
        if not battle.waiting_for_player and not battle.is_over:
            self.assertEqual(self.screen.buttons.buttons["confirm"].options["state"], tk.DISABLED)

    def test_flee_disabled_against_a_boss(self):
        app = make_app_with_character()
        app.game.start_battle([("bandit_chief", 9)])
        screen = app.show_combat()
        self.assertEqual(screen.buttons.buttons["flee"].options["state"], tk.DISABLED)

    def test_log_does_not_duplicate_entries_on_refresh(self):
        self.screen.refresh()
        self.screen.refresh()
        content = self.screen.log.text.content
        self.assertEqual(content.count("Battle start"), 1)


# ======================================================================
class TestInventoryEquipmentSkillsStatus(unittest.TestCase):
    def setUp(self):
        self.app = make_app_with_character()
        self.app.show_world()

    def test_inventory_lists_items_and_gold(self):
        window = self.app.open_inventory()
        self.assertIn("Gold:", window.gold_label.options["text"])
        self.assertGreater(window.item_list.count, 0)

    def test_inventory_filter_narrows_the_list(self):
        window = self.app.open_inventory()
        window.filter_var.set("Consumables")
        window.refresh()
        self.assertTrue(all("Potion" in row for row in window.item_list.listbox.items))

    def test_using_a_potion_heals_and_decrements(self):
        self.app.game.player.current_hp = 5
        window = self.app.open_inventory()
        window.filter_var.set("Consumables")
        window.refresh()
        window.item_list.select_index(0)
        before = self.app.game.player.inventory.count("minor_potion")
        window._use()
        self.assertEqual(self.app.game.player.inventory.count("minor_potion"), before - 1)
        self.assertGreater(self.app.game.player.current_hp, 5)

    def test_equipment_lists_every_slot(self):
        from engine.items.item import EQUIPMENT_SLOTS

        window = self.app.open_equipment()
        self.assertEqual(window.slot_list.count, len(EQUIPMENT_SLOTS))

    def test_unequipping_through_the_ui_updates_the_engine(self):
        window = self.app.open_equipment()
        window.slot_list.select_index(0)  # weapon
        window._unequip()
        self.assertIsNone(self.app.game.player.equipment["weapon"])

    def test_equipping_through_the_ui_updates_the_engine(self):
        window = self.app.open_equipment()
        window.slot_list.select_index(0)
        window._unequip()
        window.refresh()
        window.slot_list.select_index(0)
        window._reload_candidates()
        if window.candidate_list.count:
            window.candidate_list.select_index(0)
            window._equip()
            self.assertIsNotNone(self.app.game.player.equipment["weapon"])

    def test_skills_window_lists_known_and_learnable(self):
        window = self.app.open_skills()
        self.assertGreater(window.known_list.count, 0)
        self.assertIn("Skill points:", window.points_label.options["text"])

    def test_learning_a_skill_spends_a_point(self):
        self.app.game.player.unspent_skill_points = 3
        window = self.app.open_skills()
        window.refresh()
        if window.learnable_list.count:
            window.learnable_list.select_index(0)
            before = self.app.game.player.unspent_skill_points
            window._learn()
            self.assertLess(self.app.game.player.unspent_skill_points, before)

    def test_status_window_shows_the_sheet(self):
        window = self.app.open_status()
        text = window.sheet._label.options["text"]
        for expected in ("Name:", "Level:", "HP:", "STR:"):
            self.assertIn(expected, text)

    def test_status_window_displays_mastery_track_objects_after_refresh(self):
        """Mastery tracks are objects, so opening and refreshing Status must not unpack them."""
        player = self.app.game.player
        player.mastery.gain("sword", 100)
        player.unspent_stat_points = 1

        window = self.app.open_status()
        self.assertIn("Sword: E (100 EXP)", window.mastery_label.options["text"])

        window.allocate_buttons["STR"].invoke()
        self.assertEqual(player.unspent_stat_points, 0)
        self.assertIn("Sword: E (100 EXP)", window.mastery_label.options["text"])

    def test_stat_allocation_buttons_follow_available_points(self):
        window = self.app.open_status()
        self.assertEqual(window.allocate_buttons["STR"].options["state"], tk.DISABLED)
        self.app.game.player.unspent_stat_points = 5
        window.refresh()
        self.assertEqual(window.allocate_buttons["STR"].options["state"], tk.NORMAL)

    def test_allocating_a_point_raises_the_stat(self):
        self.app.game.player.unspent_stat_points = 5
        window = self.app.open_status()
        window.refresh()
        before = self.app.game.player.base_stats["STR"]
        window.allocate_buttons["STR"].invoke()
        self.assertEqual(self.app.game.player.base_stats["STR"], before + 1)

    def test_settings_window_reports_paths_and_content(self):
        window = self.app.open_settings()
        text = window.info._label.options["text"]
        self.assertIn("Version:", text)
        self.assertIn("Save folder:", text)


# ======================================================================
class TestShopAndTalk(unittest.TestCase):
    def setUp(self):
        self.app = make_app_with_character()
        self.app.show_world()

    def test_shop_lists_stock_and_bag(self):
        window = self.app.open_shop("ashvale_general")
        self.assertGreater(window.stock_list.count, 0)
        self.assertGreater(window.bag_list.count, 0)

    def test_buying_moves_gold_and_item(self):
        self.app.game.player.inventory.gold = 5000
        window = self.app.open_shop("ashvale_general")
        window.stock_list.select_index(0)
        before_gold = self.app.game.player.inventory.gold
        window._buy()
        self.assertLess(self.app.game.player.inventory.gold, before_gold)

    def test_selling_adds_gold(self):
        window = self.app.open_shop("ashvale_general")
        window.bag_list.select_index(0)
        before = self.app.game.player.inventory.gold
        window._sell()
        self.assertGreater(self.app.game.player.inventory.gold, before)

    def test_talking_raises_affinity_and_logs(self):
        window = self.app.open_talk("innkeeper_mara")
        window._talk()
        self.assertGreater(self.app.game.player.affinity_with("innkeeper_mara"), 0)
        self.assertTrue(window.log.text.content.strip())

    def test_propose_disabled_until_requirements_met(self):
        window = self.app.open_talk("innkeeper_mara")
        self.assertEqual(window.marry_button.options["state"], tk.DISABLED)

        self.app.game.player.affinity["innkeeper_mara"] = 100
        self.app.game.items.grant(self.app.game.player.inventory, "eternal_band", 1)
        window.refresh()
        self.assertEqual(window.marry_button.options["state"], tk.NORMAL)

    def test_proposing_marries(self):
        self.app.game.player.affinity["innkeeper_mara"] = 100
        self.app.game.items.grant(self.app.game.player.inventory, "eternal_band", 1)
        window = self.app.open_talk("innkeeper_mara")
        window.refresh()
        window._propose()
        self.assertEqual(self.app.game.player.spouse_id, "innkeeper_mara")


# ======================================================================
class TestSaveBrowserUI(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.app = make_app_with_character(save_dir=self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_browser_reports_no_saves(self):
        window = self.app.open_save_browser("load")
        self.assertIn("No saved games", window.preview._label.options["text"])

    def test_save_then_list_shows_the_character_name(self):
        self.app.game.save_game("slot_a")
        window = self.app.open_save_browser("load")
        self.assertIn("Test Hero", window.slot_list.listbox.items[0])

    def test_preview_shows_stacked_key_value_detail(self):
        self.app.game.save_game("slot_a")
        window = self.app.open_save_browser("load")
        window.slot_list.select_index(0)
        text = window.preview._label.options["text"]
        for expected in ("Name:", "Class:", "Level:", "Day:", "Gold:"):
            self.assertIn(expected, text)

    def test_load_restores_and_opens_world(self):
        from gui.screens.world_screen import WorldScreen

        self.app.game.player.inventory.add_gold(999)
        self.app.game.save_game("slot_a")
        self.app.game.player.inventory.gold = 0

        window = self.app.open_save_browser("load")
        window.slot_list.select_index(0)
        window._primary()

        self.assertGreater(self.app.game.player.inventory.gold, 900)
        self.assertIsInstance(self.app.current_screen, WorldScreen)

    def test_save_mode_writes_the_named_slot(self):
        window = self.app.open_save_browser("save")
        window.name_var.set("my_slot")
        window._primary()
        self.assertTrue(self.app.game.saves.exists("my_slot"))

    def test_delete_asks_for_confirmation(self):
        self.app.game.save_game("slot_a")
        tk_stub.records.clear()
        tk_stub.records.answer_yes = True

        window = self.app.open_save_browser("delete")
        window.slot_list.select_index(0)
        window._primary()

        self.assertTrue(tk_stub.records.questions)
        self.assertFalse(self.app.game.saves.exists("slot_a"))

    def test_declining_confirmation_keeps_the_save(self):
        self.app.game.save_game("slot_a")
        tk_stub.records.clear()
        tk_stub.records.answer_yes = False

        window = self.app.open_save_browser("delete")
        window.slot_list.select_index(0)
        window._primary()

        self.assertTrue(self.app.game.saves.exists("slot_a"))

    def test_corrupt_save_is_listed_and_not_loadable(self):
        Path(self._tmp.name, "broken.json").write_text("{oh no", encoding="utf-8")
        window = self.app.open_save_browser("load")
        labels = window.slot_list.listbox.items
        self.assertTrue(any("corrupt" in label for label in labels))
        window.slot_list.select_index(labels.index(next(l for l in labels if "corrupt" in l)))
        self.assertEqual(window.primary_button.options["state"], tk.DISABLED)


# ======================================================================
class TestFullPlaythroughThroughTheUI(unittest.TestCase):
    """One long journey exercising the whole bible section 8 loop."""

    def test_create_fight_level_save_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = make_app(save_dir=tmp, seed=2024)

            # Create ----------------------------------------------------
            # Pick the Squire by name rather than by index: the list is
            # sorted alphabetically, so index 0 is Acolyte (a staff user),
            # which would make the sword-mastery assertion below meaningless.
            creation = app.open_character_creation()
            creation.name_var.set("Journey")
            squire_row = creation.class_list.listbox.items.index("Squire")
            creation.class_list.select_index(squire_row)
            creation._create()
            self.assertTrue(app.game.has_character)
            self.assertEqual(app.game.player.class_def.id, "squire")

            # Travel ----------------------------------------------------
            world = app.current_screen
            world.travel_list.set_items(
                [(a.name, a) for a in app.game.travel_options()], keep_selection=False
            )
            world._travel()

            # Fight a few battles ---------------------------------------
            battles_won = 0
            for _ in range(120):
                if battles_won >= 3:
                    break
                world = app.show_world()
                world._explore()
                battle = app.game.battle
                if battle is None:
                    continue
                combat = app.current_screen
                for _ in range(120):
                    battle = app.game.battle
                    if battle is None or battle.is_over:
                        break
                    if battle.waiting_for_player:
                        combat.action_list.select_index(0)
                        if combat.target_list.count:
                            combat.target_list.select_index(0)
                        combat._use_selected()
                    else:
                        battle.run_until_player_turn()
                        combat.refresh()
                combat.refresh()
                combat._finish()
                battles_won += 1

            self.assertGreater(app.game.player.mastery.exp_of("sword"), 0)

            # Save ------------------------------------------------------
            browser = app.open_save_browser("save")
            browser.name_var.set("journey")
            browser._primary()
            self.assertTrue(app.game.saves.exists("journey"))

            snapshot = (
                app.game.player.level,
                app.game.player.inventory.gold,
                app.game.world.current_area_id,
            )

            # Load into a fresh app -------------------------------------
            reloaded = make_app(save_dir=tmp, seed=5)
            loader = reloaded.open_save_browser("load")
            labels = loader.slot_list.listbox.items
            loader.slot_list.select_index(labels.index(next(l for l in labels if "Journey" in l)))
            loader._primary()

            self.assertEqual(
                (
                    reloaded.game.player.level,
                    reloaded.game.player.inventory.gold,
                    reloaded.game.world.current_area_id,
                ),
                snapshot,
            )


# ======================================================================
class TestPartyWindow(unittest.TestCase):
    """Companion roster UI (bible section 6)."""

    def setUp(self):
        self.app = make_app_with_party()
        self.app.show_world()

    def test_world_screen_has_a_party_button(self):
        screen = self.app.current_screen
        self.assertIsNotNone(button_labelled(screen, "Party"))

    def test_party_button_opens_the_window(self):
        button_labelled(self.app.current_screen, "Party").invoke()
        self.assertIn("party", self.app._toplevels)

    def test_lists_recruited_companions(self):
        window = self.app.open_party()
        self.assertTrue(any("Rook" in row for row in window.member_list.listbox.items))

    def test_lists_recruitable_locals(self):
        window = self.app.open_party()
        self.assertTrue(any("Elen" in row for row in window.recruit_list.listbox.items))

    def test_detail_pane_shows_affinity(self):
        window = self.app.open_party()
        window.member_list.select_index(0)
        self.assertIn("Affinity", window.detail._label.options["text"])

    def test_benching_through_the_ui_updates_the_engine(self):
        window = self.app.open_party()
        window.member_list.select_index(0)
        window._toggle_active()
        self.assertFalse(self.app.game.party.is_active("rook"))

    def test_recruiting_through_the_ui(self):
        self.app.game.player.affinity["sister_elen"] = 50
        self.app.game.items.grant(self.app.game.player.inventory, "minor_ether", 2)
        window = self.app.open_party()
        window.refresh()
        index = next(
            i for i, row in enumerate(window.recruit_list.listbox.items) if "Elen" in row
        )
        window.recruit_list.select_index(index)
        window._recruit()
        self.assertTrue(self.app.game.party.has("sister_elen"))

    def test_failed_recruit_shows_the_checklist(self):
        window = self.app.open_party()
        index = next(
            i for i, row in enumerate(window.recruit_list.listbox.items) if "Elen" in row
        )
        window.recruit_list.select_index(index)
        window._recruit()
        self.assertIn("Not yet", window.detail._label.options["text"])

    def test_dismiss_asks_for_confirmation(self):
        tk_stub.records.clear()
        tk_stub.records.answer_yes = True
        window = self.app.open_party()
        window.member_list.select_index(0)
        window._dismiss()
        self.assertTrue(tk_stub.records.questions)
        self.assertFalse(self.app.game.party.has("rook"))

    def test_declining_dismiss_keeps_the_companion(self):
        tk_stub.records.clear()
        tk_stub.records.answer_yes = False
        window = self.app.open_party()
        window.member_list.select_index(0)
        window._dismiss()
        self.assertTrue(self.app.game.party.has("rook"))

    def test_empty_party_shows_recruitable_locals(self):
        """With no companions the pane usefully previews who is available."""
        app = make_app_with_character()
        app.show_world()
        window = app.open_party()
        self.assertEqual(window.member_list.count, 0)
        self.assertGreater(window.recruit_list.count, 0)
        self.assertIn("To recruit", window.detail._label.options["text"])

    def test_empty_party_in_an_area_with_nobody(self):
        """Falls back to the guidance message when there is truly nobody."""
        app = make_app_with_character()
        app.game.travel_to("greenfields")
        app.show_world()
        window = app.open_party()
        self.assertIn("No companions", window.detail._label.options["text"])


# ======================================================================
class TestCompanionCombatUI(unittest.TestCase):
    def setUp(self):
        self.app = make_app_with_party()

    def test_ally_panel_shows_the_companion(self):
        self.app.game.start_battle([("green_slime", 1)])
        screen = self.app.show_combat()
        self.assertIn("Rook", screen.ally_panel._label.options["text"])

    def test_ally_panel_without_companions(self):
        app = make_app_with_character()
        app.game.start_battle([("green_slime", 1)])
        screen = app.show_combat()
        self.assertIn("none", screen.ally_panel._label.options["text"].lower())

    def test_battle_with_a_companion_resolves_through_the_ui(self):
        self.app.game.start_battle([("green_slime", 1)])
        screen = self.app.show_combat()
        for _ in range(120):
            battle = self.app.game.battle
            if battle is None or battle.is_over:
                break
            if battle.waiting_for_player:
                screen.action_list.select_index(0)
                if screen.target_list.count:
                    screen.target_list.select_index(0)
                screen._use_selected()
            else:
                battle.run_until_player_turn()
                screen.refresh()
        self.assertTrue(self.app.game.battle.is_over)


# ======================================================================
class TestCompanionMarriageUI(unittest.TestCase):
    """Bible section 15 through the Talk window."""

    def setUp(self):
        self.app = make_app_with_party()
        self.app.show_world()

    def test_talk_window_opens_for_a_companion(self):
        window = self.app.open_talk("rook")
        self.assertEqual(window.npc_name, "Rook")

    def test_talking_to_a_companion_raises_affinity(self):
        window = self.app.open_talk("rook")
        window._talk()
        self.assertGreater(self.app.game.player.affinity_with("rook"), 0)

    def test_propose_disabled_until_requirements_met(self):
        window = self.app.open_talk("rook")
        self.assertEqual(window.marry_button.options["state"], tk.DISABLED)

    def test_requirements_panel_lists_what_is_missing(self):
        window = self.app.open_talk("rook")
        self.assertIn("Affinity", window.requirements._label.options["text"])

    def test_propose_enables_once_eligible(self):
        self.app.game.player.affinity["rook"] = 100
        self.app.game.items.grant(self.app.game.player.inventory, "eternal_band", 1)
        window = self.app.open_talk("rook")
        window.refresh()
        self.assertEqual(window.marry_button.options["state"], tk.NORMAL)

    def test_marrying_a_companion_through_the_ui(self):
        self.app.game.player.affinity["rook"] = 100
        self.app.game.items.grant(self.app.game.player.inventory, "eternal_band", 1)
        window = self.app.open_talk("rook")
        window.refresh()
        window._propose()
        self.assertEqual(self.app.game.player.spouse_id, "rook")

    def test_married_state_is_shown(self):
        self.app.game.player.affinity["rook"] = 100
        self.app.game.items.grant(self.app.game.player.inventory, "eternal_band", 1)
        window = self.app.open_talk("rook")
        window.refresh()
        window._propose()
        window.refresh()
        self.assertIn("Married", window.info._label.options["text"])

    def test_talk_window_still_works_for_npcs(self):
        window = self.app.open_talk("innkeeper_mara")
        window._talk()
        self.assertGreater(self.app.game.player.affinity_with("innkeeper_mara"), 0)

    def test_story_button_opens_branching_dialogue(self):
        app = make_app_with_character()
        window = app.open_talk("mother_sable")
        self.assertEqual(window.story_button.options["state"], tk.NORMAL)
        window._story()
        self.assertIn("dialogue", app._toplevels)

    def test_companion_tactics_window_updates_policy(self):
        app = make_app_with_party()
        window = app.open_tactics("rook")
        before = app.game.party.get("rook").tactics["preserve_mp"]
        window.toggle_mp()
        self.assertNotEqual(app.game.party.get("rook").tactics["preserve_mp"], before)


# ======================================================================
class TestQuestUI(unittest.TestCase):
    def setUp(self):
        self.app = make_app_with_character()
        self.app.game.player.class_def = self.app.game.classes.require("paladin")
        self.app.game.player.level = 35
        self.app.game.player._recalculate_base_stats()
        quest = self.app.game.quests.require("trial_of_the_dawn")
        self.app.game.world.current_area_id = quest.start_area_id
        self.app.show_world()

    def _select_trial(self, window) -> None:
        index = next(
            index
            for index, quest in enumerate(window.available_list._values)
            if quest.id == "trial_of_the_dawn"
        )
        window.available_list.select_index(index)

    def test_world_screen_has_quest_button(self):
        screen = self.app.show_world()
        self.assertIsNotNone(button_labelled(screen, "Quests"))

    def test_quest_window_lists_available_quest(self):
        window = self.app.open_quests()
        self.assertGreaterEqual(window.available_list.count, 1)
        self._select_trial(window)
        self.assertIn("Trial of the Dawn", window.details._label.options["text"])
        self.assertIn("Reeve Marta", window.details._label.options["text"])

    def test_quest_giver_talk_window_links_to_quest_log(self):
        window = self.app.open_talk("reeve_marta")
        self.assertIn("Trial of the Dawn", window.quest_info._label.options["text"])
        self.assertEqual(window.quest_button.options["state"], tk.NORMAL)

    def test_accept_quest_through_window(self):
        window = self.app.open_quests()
        self._select_trial(window)
        window._accept()
        self.assertIn("trial_of_the_dawn", self.app.game.player.active_quests)
        self.assertEqual(window.active_list.count, 1)

    def test_complete_button_enables_when_ready(self):
        window = self.app.open_quests()
        self._select_trial(window)
        window._accept()
        objective = self.app.game.quests.require("trial_of_the_dawn").objectives[0]
        self.app.game.quests.record_defeats(self.app.game.player, [objective.target_id])
        window._show_active(window.active_list.selected_value)
        self.assertEqual(window.complete_button.options["state"], tk.NORMAL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
