"""Talk - conversation, gifts, and marriage (bible section 15).

Serves NPCs and companions alike: both satisfy the ``Suitor`` shape that
:mod:`engine.relationships` is written against, so this screen resolves a
target through ``Game`` and never branches on which kind it got.
"""

from __future__ import annotations

import tkinter as tk

from gui import theme
from gui.widgets import LogPanel, SelectList, StatPanel

__all__ = ["TalkWindow"]


class TalkWindow(tk.Toplevel):
    """Conversation window for one NPC."""

    def __init__(self, app, npc_id: str) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app
        self.npc_id = npc_id
        npc = app.game._find_suitor(npc_id)
        self.npc_name = npc.name if npc else "Stranger"

        theme.style_window(self, f"Project Ascension - {self.npc_name}")
        theme.center_window(self, 720, 600)
        self.transient(app.root)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        theme.heading_label(body, text=self.npc_name).pack(anchor="w")
        if npc and npc.description:
            theme.body_label(body, text=npc.description, fg=theme.FG_DIM).pack(anchor="w", pady=(2, 0))

        self.info = StatPanel(body, title="")
        self.info.pack(fill=tk.X, pady=(10, 0))

        self.requirements = StatPanel(body, title="", wrap=560)
        self.requirements.pack(fill=tk.X, pady=(6, 0))

        self.quest_info = StatPanel(body, title="", wrap=560)
        self.quest_info.pack(fill=tk.X, pady=(6, 0))

        self.log = LogPanel(body, title="Conversation", height=8)
        self.log.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        buttons = tk.Frame(body, bg=theme.BG)
        buttons.pack(fill=tk.X, pady=(14, 0))
        theme.flat_button(buttons, "Talk", self._talk, width=10).pack(side=tk.LEFT)
        theme.flat_button(buttons, "Give Gift", self._gift, width=10).pack(side=tk.LEFT, padx=8)
        self.marry_button = theme.flat_button(buttons, "Propose", self._propose, width=10)
        self.marry_button.pack(side=tk.LEFT)
        self.quest_button = theme.flat_button(buttons, "Quests", self.app.open_quests, width=10)
        self.quest_button.pack(side=tk.LEFT, padx=(8, 0))
        self.story_button = theme.flat_button(buttons, "Story", self._story, width=8)
        self.story_button.pack(side=tk.LEFT, padx=(8, 0))
        theme.flat_button(buttons, "Close", self._close, width=10).pack(side=tk.RIGHT)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self._close()
            return

        npc = game._find_suitor(self.npc_id)
        affinity = game.player.affinity_with(self.npc_id)
        lines = [f"Affinity: {affinity} ({game.relationships.tier_label(affinity)})"]
        if npc and getattr(npc, "race_id", ""):
            lines.append(f"Race: {game.race_name(npc.race_id)}")
        if npc and getattr(npc, "marriageable", False):
            lines.append(f"Marriage at: {npc.marriage_affinity}")
        if game.player.spouse_id == self.npc_id:
            lines.append("Married to you")
        if game.party.has(self.npc_id):
            lines.append("Travelling with you")
        self.info.set_lines(lines)

        # The engine decides whether a proposal is possible; the UI just asks,
        # and shows the checklist rather than a bare disabled button.
        check = game.marriage_check(self.npc_id)
        self.marry_button.configure(state=tk.NORMAL if check.eligible else tk.DISABLED)
        if not check.eligible and check.unmet:
            self.requirements.set_lines(["To propose:", *[f"  {item}" for item in check.unmet]])
        else:
            self.requirements.set_lines([])

        quest_lines = game.quest_giver_lines(self.npc_id)
        self.quest_info.set_lines(["Quests:", *quest_lines] if quest_lines else [])
        self.quest_button.configure(state=tk.NORMAL if quest_lines else tk.DISABLED)
        stories = game.dialogues_for_speaker(self.npc_id)
        self.story_button.configure(state=tk.NORMAL if stories else tk.DISABLED)

    # ------------------------------------------------------------------
    def _story(self) -> None:
        stories = self.app.game.dialogues_for_speaker(self.npc_id)
        if stories:
            self.app.open_dialogue(stories[0]["id"])

    def _talk(self) -> None:
        ok, lines = self.app.game.talk_to(self.npc_id)
        for line in lines:
            self.log.append(line, "info" if ok else "system")
        self.refresh()

    def _gift(self) -> None:
        entries = self.app.game.inventory_entries()
        if not entries:
            self.app.notify("You have nothing to give.")
            return

        window = tk.Toplevel(self.app.root, bg=theme.BG)
        theme.style_window(window, "Give Gift")
        theme.center_window(window, 320, 320)
        window.transient(self.app.root)

        frame = tk.Frame(window, bg=theme.BG, padx=16, pady=14)
        frame.pack(fill=tk.BOTH, expand=True)
        theme.heading_label(frame, text="Give Gift").pack(anchor="w", pady=(0, 8))

        picker: SelectList[str] = SelectList(frame, height=8)
        picker.set_items([(entry.label(), entry.item.id) for entry in entries])
        picker.pack(fill=tk.BOTH, expand=True)

        def confirm() -> None:
            item_id = picker.selected_value
            window.destroy()
            if item_id is None:
                return
            ok, lines = self.app.game.give_gift(self.npc_id, item_id)
            for line in lines:
                self.log.append(line, "heal" if ok else "system")
            self.app.refresh_active()

        theme.flat_button(frame, "Give", confirm).pack(fill=tk.X, pady=(12, 0))

    def _propose(self) -> None:
        ok, message = self.app.game.marry(self.npc_id)
        self.log.append(message, "heal" if ok else "system")
        self.app.notify(message)
        if ok:
            self.app.show_info("Marriage", message)
        self.app.refresh_active()

    def _close(self) -> None:
        self.app.close_toplevel("talk")
