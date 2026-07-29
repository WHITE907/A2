"""Skills - known skills, the learnable tree, and promotion.

Promotion lives here rather than in its own screen because the requirement
checklist is a skill-tree concern: promoting is how the tree expands
(bible section 10).
"""

from __future__ import annotations

import tkinter as tk

from gui import theme
from engine.classes import PromotionCheck
from engine.skills.skill import Skill
from gui.widgets import SelectList, StatPanel

__all__ = ["SkillsWindow"]


class SkillsWindow(tk.Toplevel):
    """Learn skills and promote class."""

    def __init__(self, app) -> None:
        super().__init__(app.root, bg=theme.BG)
        self.app = app

        theme.style_window(self, "Project Ascension - Skills")
        theme.center_window(self, 760, 560)
        self.transient(app.root)

        body = tk.Frame(self, bg=theme.BG, padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(body, bg=theme.BG)
        header.pack(fill=tk.X)
        theme.heading_label(header, text="Skills").pack(side=tk.LEFT)
        self.points_label = theme.body_label(header, text="", fg=theme.FG_DIM)
        self.points_label.pack(side=tk.RIGHT)

        filters = tk.Frame(body, bg=theme.BG)
        filters.pack(fill=tk.X, pady=(10, 0))
        theme.body_label(filters, text="Filter:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar(value="")
        search = tk.Entry(filters, textvariable=self.search_var, width=18, bg=theme.BG_ALT, fg=theme.FG, insertbackground=theme.FG)
        search.pack(side=tk.LEFT, padx=(6, 10))
        search.bind("<KeyRelease>", lambda _event: self.refresh())
        self.category_var = tk.StringVar(value="all")
        self.category_options = ["all", "core", "active", "passive", "weapon", "shared", "ultimate"]
        self.sort_options = ["name", "category", "cost"]
        theme.flat_button(filters, "Category", self._cycle_category, width=11).pack(side=tk.LEFT)
        self.category_label = theme.body_label(filters, text="all", fg=theme.FG_DIM)
        self.category_label.pack(side=tk.LEFT, padx=(4, 8))
        self.sort_var = tk.StringVar(value="name")
        theme.flat_button(filters, "Sort", self._cycle_sort, width=8).pack(side=tk.LEFT)
        self.sort_label = theme.body_label(filters, text="name", fg=theme.FG_DIM)
        self.sort_label.pack(side=tk.LEFT, padx=(4, 0))

        columns = tk.Frame(body, bg=theme.BG)
        columns.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        self.known_list: SelectList[Skill] = SelectList(
            columns, title="Known", height=13, on_select=self._on_known
        )
        self.known_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.learnable_list: SelectList[Skill] = SelectList(
            columns,
            title="Learnable",
            height=13,
            on_select=self._on_learnable,
            on_activate=lambda _v: self._learn(),
        )
        self.learnable_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))

        self.detail = StatPanel(columns, title="Details", wrap=220)
        self.detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 0))

        buttons = tk.Frame(body, bg=theme.BG)
        buttons.pack(fill=tk.X, pady=(16, 0))
        theme.flat_button(buttons, "Learn", self._learn, width=10).pack(side=tk.LEFT)
        theme.flat_button(buttons, "Promotion", self._open_promotion, width=12).pack(side=tk.LEFT, padx=8)
        theme.flat_button(buttons, "Close", self._close, width=10).pack(side=tk.RIGHT)

        self.refresh()

    def _cycle_category(self) -> None:
        value = self.category_options[(self.category_options.index(self.category_var.get()) + 1) % len(self.category_options)]
        self.category_var.set(value)
        self.category_label.configure(text=value)
        self.refresh()

    def _cycle_sort(self) -> None:
        value = self.sort_options[(self.sort_options.index(self.sort_var.get()) + 1) % len(self.sort_options)]
        self.sort_var.set(value)
        self.sort_label.configure(text=value)
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        game = self.app.game
        if not game.has_character:
            self._close()
            return

        player = game.player
        self.points_label.configure(text=f"Skill points: {player.unspent_skill_points}")

        query = self.search_var.get().strip().lower()
        category = self.category_var.get()

        def visible(skills: list[Skill]) -> list[Skill]:
            result = [s for s in skills if (category == "all" or s.category == category) and (not query or query in s.name.lower() or query in s.description.lower() or any(query in tag.lower() for tag in s.tags))]
            mode = self.sort_var.get()
            return sorted(result, key=lambda s: (s.category, s.name) if mode == "category" else (s.skill_point_cost, s.name) if mode == "cost" else s.name.lower())

        known = visible(list(player.usable_skills()) + list(player.passive_skills()))
        self.known_list.set_items([(f"{s.name}  [{s.category}]" + ("  [racial gift]" if s.id.startswith("racial_") else ""), s) for s in known])

        learnable = visible(game.learnable_skills())
        self.learnable_list.set_items(
            [(f"{s.name}  ({s.skill_point_cost} pt)", s) for s in learnable], keep_selection=False
        )

        if not learnable and not known:
            self.detail.set_lines(["No skills available."])

    def _on_known(self, skill: Skill | None) -> None:
        if skill is not None:
            self.detail.set_lines(skill.detail_lines())

    def _on_learnable(self, skill: Skill | None) -> None:
        if skill is None:
            return
        lines = list(skill.detail_lines())
        lines.append("")
        lines.append(f"Cost: {skill.skill_point_cost} skill point(s)")
        if skill.required_level > 1:
            lines.append(f"Requires level {skill.required_level}")
        for track, rank in skill.required_mastery.items():
            lines.append(f"Requires {track.title()} mastery {rank}")
        self.detail.set_lines(lines)

    # ------------------------------------------------------------------
    def _learn(self) -> None:
        skill = self.learnable_list.selected_value
        if skill is None:
            self.app.notify("Select a skill to learn.")
            return
        ok, message = self.app.game.learn_skill(skill.id)
        self.app.notify(message)
        self.app.refresh_active()

    def _open_promotion(self) -> None:
        """Promotion checklist as its own small Toplevel."""
        options = self.app.game.promotion_options()
        window = tk.Toplevel(self.app.root, bg=theme.BG)
        theme.style_window(window, "Promotion")
        theme.center_window(window, 460, 420)
        window.transient(self.app.root)

        frame = tk.Frame(window, bg=theme.BG, padx=18, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        player = self.app.game.player
        theme.heading_label(frame, text=f"Promotion - {player.class_def.name}").pack(anchor="w")
        theme.body_label(
            frame, text=f"Tier {player.class_def.tier}", fg=theme.FG_DIM
        ).pack(anchor="w", pady=(2, 10))

        if not options:
            theme.body_label(
                frame, text="This class has no further promotions.", fg=theme.FG_DIM
            ).pack(anchor="w")
            theme.flat_button(frame, "Close", window.destroy).pack(fill=tk.X, pady=(16, 0))
            return

        picker: SelectList[PromotionCheck] = SelectList(frame, title="Available paths", height=4)
        picker.pack(fill=tk.X)

        detail = StatPanel(frame, title="")
        detail.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        def show(check: PromotionCheck | None) -> None:
            if check is not None:
                detail.set_lines(check.summary_lines())

        picker._on_select = show
        picker.set_items(
            [(f"{'[ok] ' if c.eligible else ''}{c.target_class_name}", c) for c in options]
        )
        show(picker.selected_value)

        def promote() -> None:
            check = picker.selected_value
            if check is None:
                return
            ok, messages = self.app.game.promote(check.target_class_id)
            self.app.notify(messages[0] if messages else "")
            if ok:
                self.app.show_info("Promotion", "\n".join(messages))
                window.destroy()
                self.app.refresh_active()
            else:
                detail.set_lines(messages)

        row = tk.Frame(frame, bg=theme.BG)
        row.pack(fill=tk.X, pady=(14, 0))
        theme.flat_button(row, "Promote", promote, width=12).pack(side=tk.LEFT)
        theme.flat_button(row, "Close", window.destroy, width=12).pack(side=tk.RIGHT)

    def _close(self) -> None:
        self.app.close_toplevel("skills")
