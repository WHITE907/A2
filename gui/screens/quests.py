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
        theme.center_window(self, 820, 620)
        self.transient(app.root)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)
        header = tk.Frame(body, bg=theme.BG)
        header.pack(fill=tk.X)
        theme.heading_label(header, text="Quest Log").pack(side=tk.LEFT)
        # Search
        theme.body_label(header, text="Search:", font=theme.FONT_SMALL).pack(side=tk.LEFT, padx=(12, 4))
        self.search_var = tk.StringVar(value="")
        search_entry = tk.Entry(header, textvariable=self.search_var, width=20, bg=theme.LISTBOX_BG, fg=theme.FG, insertbackground=theme.FG, font=theme.FONT_SMALL)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind("<KeyRelease>", lambda _e: self.refresh())

        columns = tk.Frame(body, bg=theme.BG)
        columns.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        left = tk.Frame(columns, bg=theme.BG, width=260)
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
        self.details = StatPanel(right, title="Quest", wrap=500)
        self.details.pack(fill=tk.BOTH, expand=True)

        self.accept_button = theme.flat_button(right, "Accept Quest", self._accept)
        self.accept_button.pack(fill=tk.X, pady=(12, 0))
        self.complete_button = theme.flat_button(right, "Complete Quest", self._complete)
        self.complete_button.pack(fill=tk.X, pady=(6, 0))

        self.completed_label = theme.body_label(right, text="", fg=theme.FG_DIM, wraplength=500)
        self.completed_label.pack(fill=tk.X, pady=(12, 0))
        theme.flat_button(right, "Close", self._close, width=10).pack(anchor="e", pady=(12, 0))

        self._selected_id: str | None = None
        self._selected_source: str = ""
        self.refresh()

    def _filter_quests(self, quests: list[QuestDefinition]) -> list[QuestDefinition]:
        search = self.search_var.get().strip().lower()
        if not search:
            return quests
        return [q for q in quests if search in q.name.lower() or search in q.description.lower() or search in q.id.lower()]

    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self._close()
            return

        active = self._filter_quests(game.active_quests())
        available = self._filter_quests(game.available_quests())
        self.active_list.set_items([(f"{q.name} (Lv {q.min_level})", q) for q in active])
        self.available_list.set_items([(f"{q.name} (Lv {q.min_level})", q) for q in available])

        completed = game.completed_quests()
        # Also filter completed by search for label
        search = self.search_var.get().strip().lower()
        if search:
            completed_filtered = [q for q in completed if search in q.name.lower()]
        else:
            completed_filtered = completed
        names = ", ".join(q.name for q in completed_filtered) if completed_filtered else "None"
        self.completed_label.configure(text=f"Completed ({len(completed_filtered)}/{len(completed)} shown): {names}")

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
            lines = game.quest_detail_lines(selected.id)
            # Add progress bar for objectives
            ready, unmet = game.quest_completion_check(selected.id)
            if ready:
                lines.append("")
                lines.append("READY TO TURN IN")
            elif unmet:
                lines.append("")
                lines.append("Unmet: " + "; ".join(unmet[:3]))
            self.details.set_lines(lines)

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
        # Refresh will set details and button states correctly
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
