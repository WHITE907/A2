"""Party - recruit, bench and inspect companions.

Two Listboxes hold simultaneous selections here (party roster and recruitable
locals), so this is another screen covered by the ``exportselection=False``
note in docs/GUI_VERIFICATION.md - handled by :func:`gui.theme.stat_listbox`.

Like every screen, this holds no rules: it asks the engine what is possible
(``check_recruit``, ``party_lines``) and displays the answer.
"""

from __future__ import annotations

import tkinter as tk

from gui import theme
from gui.widgets import ScrollableFrame, SelectList, StatPanel

__all__ = ["PartyWindow"]


class PartyWindow(tk.Toplevel):
    """Roster management and recruitment."""

    def __init__(self, app) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app

        theme.style_window(self, "Project Ascension - Party")
        theme.center_window(self, 760, 560)
        self.transient(app.root)

        self.viewport = ScrollableFrame(self, bg=theme.BG, padx=18, pady=16)
        self.viewport.pack(fill=tk.BOTH, expand=True)
        body = self.viewport.content

        header = tk.Frame(body, bg=theme.BG)
        header.pack(fill=tk.X)
        theme.heading_label(header, text="Party").pack(side=tk.LEFT)
        self.count_label = theme.body_label(header, text="", fg=theme.FG_DIM)
        self.count_label.pack(side=tk.RIGHT)

        columns = tk.Frame(body, bg=theme.BG)
        columns.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        # Listbox #1: who is already with you.
        self.member_list: SelectList[str] = SelectList(
            columns, title="Companions", height=13, on_select=self._on_member
        )
        self.member_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Listbox #2: who can be recruited in this area.
        self.recruit_list: SelectList[str] = SelectList(
            columns,
            title="Available Here",
            height=13,
            on_select=self._on_recruit_target,
            on_activate=lambda _v: self._recruit(),
        )
        self.recruit_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))

        self.detail = StatPanel(columns, title="Details", wrap=230)
        self.detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))

        buttons = tk.Frame(body, bg=theme.BG)
        buttons.pack(fill=tk.X, pady=(16, 0))
        self.toggle_button = theme.flat_button(buttons, "Bench", self._toggle_active, width=10)
        self.toggle_button.pack(side=tk.LEFT)
        theme.flat_button(buttons, "Talk", self._talk, width=10).pack(side=tk.LEFT, padx=8)
        theme.flat_button(buttons, "Tactics", self._tactics, width=10).pack(side=tk.LEFT)
        theme.flat_button(buttons, "Dismiss", self._dismiss, width=10).pack(side=tk.LEFT, padx=8)
        self.recruit_button = theme.flat_button(buttons, "Recruit", self._recruit, width=10)
        self.recruit_button.pack(side=tk.LEFT, padx=8)
        theme.flat_button(buttons, "Close", self._close, width=10).pack(side=tk.RIGHT)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self._close()
            return

        party = game.party
        self.count_label.configure(text=f"Active {len(party.active)}/{party.max_active}")

        rows: list[tuple[str, str]] = []
        for companion in party.active:
            tag = " (spouse)" if game.player.spouse_id == companion.id else ""
            rows.append((f"{companion.name} - Lv {companion.level}{tag}", companion.id))
        for companion in party.reserve:
            tag = " (spouse)" if game.player.spouse_id == companion.id else ""
            rows.append((f"{companion.name} [reserve]{tag}", companion.id))
        self.member_list.set_items(rows, keep_selection=True)

        available = game.recruitable_here()
        self.recruit_list.set_items([(d.name, d.id) for d in available], keep_selection=True)
        self.recruit_button.configure(state=tk.NORMAL if available else tk.DISABLED)

        if rows:
            self._on_member(self.member_list.selected_value)
        elif available:
            self._on_recruit_target(self.recruit_list.selected_value)
        else:
            self.detail.set_lines(["No companions yet.", "Look for allies in towns and on the road."])
            self.toggle_button.configure(state=tk.DISABLED)

    def _on_member(self, companion_id: str | None) -> None:
        if companion_id is None:
            return
        self.detail.set_lines(self.app.game.companion_detail_lines(companion_id))
        active = self.app.game.party.is_active(companion_id)
        self.toggle_button.configure(text="Bench" if active else "Activate", state=tk.NORMAL)

    def _on_recruit_target(self, companion_id: str | None) -> None:
        if companion_id is None:
            return
        lines = self.app.game.companion_detail_lines(companion_id)
        ok, unmet = self.app.game.check_recruit(companion_id)
        if not ok and unmet:
            lines.append("")
            lines.append("Not yet:")
            lines.extend(f"  {item}" for item in unmet)
        self.detail.set_lines(lines)

    # ------------------------------------------------------------------
    def _toggle_active(self) -> None:
        companion_id = self.member_list.selected_value
        if companion_id is None:
            return
        active = self.app.game.party.is_active(companion_id)
        ok, message = self.app.game.set_companion_active(companion_id, not active)
        self.app.notify(message)
        self.app.refresh_active()

    def _dismiss(self) -> None:
        companion_id = self.member_list.selected_value
        if companion_id is None:
            return
        companion = self.app.game.party.get(companion_id)
        name = companion.name if companion else "them"
        if not self.app.confirm("Dismiss", f"Send {name} away?"):
            return
        ok, message = self.app.game.dismiss_companion(companion_id)
        self.app.notify(message)
        self.app.refresh_active()

    def _recruit(self) -> None:
        companion_id = self.recruit_list.selected_value
        if companion_id is None:
            self.app.notify("Nobody to recruit here.")
            return
        ok, messages = self.app.game.recruit(companion_id)
        self.app.notify(messages[0] if messages else "")
        self.app.refresh_active()
        # Redraw the checklist *after* the global refresh, which would
        # otherwise immediately overwrite it with the plain detail view.
        if not ok:
            self._on_recruit_target(companion_id)

    def _tactics(self) -> None:
        companion_id = self.member_list.selected_value
        if companion_id:
            self.app.open_tactics(companion_id)

    def _talk(self) -> None:
        """Open the shared Talk window - companions use the same one as NPCs."""
        companion_id = self.member_list.selected_value or self.recruit_list.selected_value
        if companion_id is None:
            return
        self.app.open_talk(companion_id)

    def _close(self) -> None:
        self.app.close_toplevel("party")
