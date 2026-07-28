"""Character Creation - name, gender, and a gender-restricted class list.

Bible section 10: starting classes are gender-restricted, so changing the
gender re-queries the engine for the available classes rather than filtering a
cached list in the UI.
"""

from __future__ import annotations

import tkinter as tk

from gui import theme
from engine.classes import ClassDefinition
from gui.widgets import SelectList, StatPanel

__all__ = ["CharacterCreationWindow"]


class CharacterCreationWindow(tk.Toplevel):
    """New-character setup."""

    def __init__(self, app) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app

        theme.style_window(self, "Project Ascension - New Game")
        theme.center_window(self, 620, 600)
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

        self.class_list: SelectList[ClassDefinition] = SelectList(
            columns, title="Starting Class", height=9, on_select=self._on_class_selected
        )
        self.class_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.preview = StatPanel(columns, title="Details", wrap=280)
        self.preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))

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

    def _on_class_selected(self, definition: ClassDefinition | None) -> None:
        if definition is None:
            self.preview.set_lines(["No classes available."])
            return
        self.preview.set_lines(definition.detail_lines())

    # ------------------------------------------------------------------
    def _create(self) -> None:
        definition = self.class_list.selected_value
        if definition is None:
            self.app.notify("Choose a class.")
            return

        ok, message = self.app.game.create_character(
            self.name_var.get(), self.gender_var.get(), definition.id
        )
        self.app.notify(message)
        if ok:
            self._close()
            self.app.show_world()

    def _close(self) -> None:
        self.app.close_toplevel("character_creation")

    def refresh(self) -> None:
        """No engine state to track while creating a character."""
