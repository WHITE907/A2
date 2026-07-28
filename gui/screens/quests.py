"""Quest log: accept available quests, inspect progress, and claim rewards."""

from __future__ import annotations

import tkinter as tk

from engine.game import QuestDefinition
from gui import theme
from gui.widgets import SelectList, StatPanel

__all__ = ["QuestWindow"]


class QuestWindow(tk.Toplevel):
    """Displays the quest state calculated by :class:`engine.game.Game`."""

    def __init__(self, app) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app

        theme.style_window(self, "Project Ascension - Quests")
        theme.center_window(self, 780, 600)
        self.transient(app.root)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)
        theme.heading_label(body, text="Quest Log").pack(anchor="w", pady=(0, 10))

        columns = tk.Frame(body, bg=theme.BG)
        columns.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(columns, bg=theme.BG, width=240)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        self.active_list: SelectList[QuestDefinition] = SelectList(
            left, title="Active", height=9, on_select=self._show_active
        )
        self.active_list.pack(fill=tk.BOTH, expand=True)
        self.available_list: SelectList[QuestDefinition] = SelectList(
            left, title="Available", height=7, on_select=self._show_available
        )
        self.available_list.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        right = tk.Frame(columns, bg=theme.BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))
        self.details = StatPanel(right, title="Quest", wrap=470)
        self.details.pack(fill=tk.BOTH, expand=True)

        self.accept_button = theme.flat_button(right, "Accept Quest", self._accept)
        self.accept_button.pack(fill=tk.X, pady=(12, 0))
        self.complete_button = theme.flat_button(right, "Complete Quest", self._complete)
        self.complete_button.pack(fill=tk.X, pady=(6, 0))

        self.completed_label = theme.body_label(right, text="", fg=theme.FG_DIM, wraplength=470)
        self.completed_label.pack(fill=tk.X, pady=(12, 0))
        theme.flat_button(right, "Close", self._close, width=10).pack(anchor="e", pady=(12, 0))

        self._selected_id: str | None = None
        self._selected_source: str = ""
        self.refresh()

    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self._close()
            return

        active = game.active_quests()
        available = game.available_quests()
        self.active_list.set_items([(quest.name, quest) for quest in active])
        self.available_list.set_items([(quest.name, quest) for quest in available])

        completed = game.completed_quests()
        names = ", ".join(quest.name for quest in completed) if completed else "None"
        self.completed_label.configure(text=f"Completed: {names}")

        selected = next(
            (quest for quest in [*active, *available] if quest.id == self._selected_id),
            None,
        )
        if selected is None and active:
            selected = active[0]
            self._selected_id = selected.id
            self._selected_source = "active"
        elif selected is None and available:
            selected = available[0]
            self._selected_id = selected.id
            self._selected_source = "available"

        if selected is None:
            self._selected_id = None
            self._selected_source = ""
            self.details.set_lines(["No active or available quests."])
        else:
            self.details.set_lines(game.quest_detail_lines(selected.id))

        self.accept_button.configure(
            state=tk.NORMAL if self._selected_source == "available" and selected else tk.DISABLED
        )
        ready = False
        if self._selected_source == "active" and selected:
            ready, _ = game.quest_completion_check(selected.id)
        self.complete_button.configure(state=tk.NORMAL if ready else tk.DISABLED)

    def _show_active(self, quest: QuestDefinition | None) -> None:
        self._select(quest, "active")

    def _show_available(self, quest: QuestDefinition | None) -> None:
        self._select(quest, "available")

    def _select(self, quest: QuestDefinition | None, source: str) -> None:
        self._selected_id = quest.id if quest else None
        self._selected_source = source if quest else ""
        self.details.set_lines(
            self.app.game.quest_detail_lines(quest.id)
            if quest
            else ["Select a quest to view its details."]
        )
        self.refresh()

    def _accept(self) -> None:
        if not self._selected_id:
            return
        ok, message = self.app.game.accept_quest(self._selected_id)
        self.app.notify(message)
        if ok:
            self._selected_source = "active"
        self.app.refresh_active()

    def _complete(self) -> None:
        if not self._selected_id:
            return
        ok, lines = self.app.game.complete_quest(self._selected_id)
        self.app.notify(lines[0] if lines else "")
        if ok:
            self._selected_id = None
            self._selected_source = ""
        self.app.refresh_active()

    def _close(self) -> None:
        self.app.close_toplevel("quests")
