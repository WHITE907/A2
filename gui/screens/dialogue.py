"""Data-driven branching dialogue window."""

from __future__ import annotations

import tkinter as tk

from gui import theme
from gui.widgets import ButtonStack, ScrollableFrame, StatPanel


class DialogueWindow(tk.Toplevel):
    def __init__(self, app, tree_id: str) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app
        self.tree_id = tree_id
        theme.style_window(self, "Project Ascension - Story")
        theme.center_window(self, 620, 480)
        self.transient(app.root)

        self.viewport = ScrollableFrame(self, bg=theme.BG, padx=18, pady=16)
        self.viewport.pack(fill=tk.BOTH, expand=True)
        self.body = self.viewport.content
        self.text = StatPanel(self.body, title="Conversation", wrap=560)
        self.text.pack(fill=tk.BOTH, expand=True)
        self.options = ButtonStack(self.body, spacing=6)
        self.options.pack(fill=tk.X, pady=(12, 0))
        self.show(app.game.start_dialogue(tree_id))

    def show(self, view: dict) -> None:
        self.text.set_lines([view.get("text", "")])
        self.options.destroy()
        self.options = ButtonStack(self.body, spacing=6)
        self.options.pack(fill=tk.X, pady=(12, 0))
        for option in view.get("options", []):
            self.options.add(
                option["id"],
                option["text"],
                lambda option_id=option["id"]: self.show(
                    self.app.game.choose_dialogue(self.tree_id, option_id)
                ),
            )
        if not view.get("options"):
            self.options.add("close", "Close", lambda: self.app.close_toplevel("dialogue"))
