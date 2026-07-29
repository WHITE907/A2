"""Character Creation - name, gender, race/sub-race, and a gender-restricted class list.

Bible section 10: starting classes are gender-restricted, so changing the
gender re-queries the engine for the available classes rather than filtering a
cached list in the UI.
"""

from __future__ import annotations

import tkinter as tk

from gui import theme
from engine.classes import ClassDefinition
from engine.game import RaceDefinition
from engine.races import SubRace
from gui.widgets import SelectList, StatPanel

__all__ = ["CharacterCreationWindow"]


class CharacterCreationWindow(tk.Toplevel):
    """New-character setup."""

    def __init__(self, app) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app

        theme.style_window(self, "Project Ascension - New Game")
        theme.center_window(self, 820, 640)
        self.transient(app.root)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        theme.heading_label(body, text="Create Character").pack(anchor="w", pady=(0, 12))

        # -- name --------------------------------------------------------
        name_row = tk.Frame(body, bg=theme.BG)
        name_row.pack(fill=tk.X)
        theme.body_label(name_row, text="Name:", width=8).pack(side=tk.LEFT)
        self.name_var = tk.StringVar(value="")
        entry = tk.Entry(
            name_row,
            textvariable=self.name_var,
            bg=theme.LISTBOX_BG,
            fg=theme.FG,
            insertbackground=theme.FG,
            relief=tk.FLAT,
            font=theme.FONT_BODY,
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        entry.focus_set()

        # -- gender ------------------------------------------------------
        gender_row = tk.Frame(body, bg=theme.BG)
        gender_row.pack(fill=tk.X, pady=(12, 0))
        theme.body_label(gender_row, text="Gender:", width=8).pack(side=tk.LEFT)

        genders = self.app.game.genders()
        self.gender_var = tk.StringVar(value=genders[0] if genders else "male")
        for gender in genders:
            tk.Radiobutton(
                gender_row,
                text=gender.title(),
                value=gender,
                variable=self.gender_var,
                command=self._reload_classes,
                bg=theme.BG,
                fg=theme.FG,
                selectcolor=theme.BG_ALT,
                activebackground=theme.BG,
                activeforeground=theme.FG,
                font=theme.FONT_BODY,
                highlightthickness=0,
                borderwidth=0,
            ).pack(side=tk.LEFT, padx=(0, 14))

        # -- class list + preview ---------------------------------------
        columns = tk.Frame(body, bg=theme.BG)
        columns.pack(fill=tk.BOTH, expand=True, pady=(16, 0))

        self.race_list: SelectList[RaceDefinition] = SelectList(
            columns, title="Race", height=9, on_select=self._on_race_selected
        )
        races = self.app.game.race_options()
        self.race_list.set_items([(race.name, race) for race in races], keep_selection=False)
        default_id = self.app.game.default_race_id()
        default_index = next((i for i, race in enumerate(races) if race.id == default_id), 0)
        self.race_list.select_index(default_index, notify=False)
        self.race_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.sub_race_list: SelectList[SubRace] = SelectList(
            columns, title="Sub-Race", height=9, on_select=lambda _sub: self._refresh_preview()
        )
        self.sub_race_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(14, 0))

        self.class_list: SelectList[ClassDefinition] = SelectList(
            columns, title="Starting Class", height=9, on_select=self._on_class_selected
        )
        self.class_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(14, 0))

        self.preview = StatPanel(columns, title="Details", wrap=300)
        self.preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(14, 0))

        # Initialize sub-race list after all widgets are created
        self._on_race_selected(self.race_list.selected_value)

        # -- actions -----------------------------------------------------
        buttons = tk.Frame(body, bg=theme.BG)
        buttons.pack(fill=tk.X, pady=(18, 0))
        theme.flat_button(buttons, "Begin", self._create, width=12).pack(side=tk.LEFT)
        theme.flat_button(buttons, "Cancel", self._close, width=12).pack(side=tk.RIGHT)

        self._reload_classes()

    # ------------------------------------------------------------------
    def _reload_classes(self) -> None:
        """Re-query the engine whenever gender changes (bible section 10)."""
        classes = self.app.game.starting_classes(self.gender_var.get())
        self.class_list.set_items([(c.name, c) for c in classes], keep_selection=False)
        self._on_class_selected(self.class_list.selected_value)

    def _on_race_selected(self, race: RaceDefinition | None) -> None:
        """Update sub-race list when race changes."""
        if race is None or not race.sub_races:
            self.sub_race_list.set_items([], keep_selection=False)
        else:
            self.sub_race_list.set_items([(sub.name, sub) for sub in race.sub_races], keep_selection=False)
        self._refresh_preview()

    def _on_class_selected(self, definition: ClassDefinition | None) -> None:
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        definition = self.class_list.selected_value
        race = self.race_list.selected_value
        sub_race = self.sub_race_list.selected_value
        lines: list[str] = []
        if race is not None:
            lines.extend(self.app.game.race_detail_lines(race.id))
        if race is not None and sub_race is not None:
            lines.append("")
            lines.extend(sub_race.detail_lines())
        if (race is not None or sub_race is not None) and definition is not None:
            lines.append("")
        if definition is not None:
            lines.extend(definition.detail_lines())
        self.preview.set_lines(lines or ["Choose a race, sub-race, and class."])

    # ------------------------------------------------------------------
    def _create(self) -> None:
        definition = self.class_list.selected_value
        race = self.race_list.selected_value
        sub_race = self.sub_race_list.selected_value
        if definition is None:
            self.app.notify("Choose a class.")
            return
        if race is None:
            self.app.notify("Choose a race.")
            return
        if race.sub_races and sub_race is None:
            self.app.notify("Choose a sub-race.")
            return

        sub_race_id = sub_race.id if sub_race else None
        ok, message = self.app.game.create_character(
            self.name_var.get(), self.gender_var.get(), definition.id, race.id, sub_race_id
        )
        self.app.notify(message)
        if ok:
            self._close()
            self.app.show_world()

    def _close(self) -> None:
        self.app.close_toplevel("character_creation")

    def refresh(self) -> None:
        """No engine state to track while creating a character."""
