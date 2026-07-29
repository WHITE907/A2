"""Reusable composite widgets built from the theme primitives.

These exist to keep the screens declarative.  None of them contain gameplay
logic - they take already-computed strings from the engine and display them
(bible section 5).
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Generic, Iterable, Sequence, TypeVar

from gui import theme

__all__ = ["StatPanel", "ButtonStack", "SelectList", "LogPanel", "StatusBar"]

#: Type of the engine object a SelectList row maps back to.
T = TypeVar("T")


class StatPanel(tk.Frame):
    """Stacked ``key: value`` text - the style reference's stat display.

    Uses a single Label with embedded newlines rather than one Label per line;
    with a dozen+ rows updated every action, repacking child widgets flickers
    visibly while re-rendering one string does not.

    ``wrap`` sets a wrap width in pixels.  Panels that show authored prose
    (area descriptions, item flavour) need it so a long sentence wraps inside
    its column instead of running past the panel edge; pure ``key: value``
    panels leave it at 0 because their lines are naturally short and wrapping
    them would only make the alignment harder to read.
    """

    def __init__(self, parent: tk.Misc, title: str = "", wrap: int = 0, **kwargs) -> None:
        super().__init__(parent, bg=theme.BG, **kwargs)
        self._title = title
        if title:
            theme.heading_label(self, text=title).pack(anchor="w", pady=(0, 4))
        self._label = theme.body_label(self, text="", font=theme.FONT_SMALL)
        if wrap:
            self._label.configure(wraplength=wrap)
        self._label.pack(anchor="w", fill=tk.X)

    def set_lines(self, lines: Iterable[str]) -> None:
        self._label.configure(text="\n".join(lines))

    def set_text(self, text: str) -> None:
        self._label.configure(text=text)


class ButtonStack(tk.Frame):
    """A vertical stack of full-width flat buttons, generously spaced."""

    def __init__(self, parent: tk.Misc, spacing: int = 6, width: int | None = None, **kwargs) -> None:
        super().__init__(parent, bg=theme.BG, **kwargs)
        self._spacing = spacing
        self._width = width
        self.buttons: dict[str, tk.Button] = {}

    def add(self, key: str, text: str, command: Callable[[], None], **kwargs) -> tk.Button:
        options = {"width": self._width} if self._width else {}
        options.update(kwargs)
        button = theme.flat_button(self, text, command, **options)
        button.pack(fill=tk.X, pady=self._spacing)
        self.buttons[key] = button
        return button

    def set_enabled(self, key: str, enabled: bool) -> None:
        button = self.buttons.get(key)
        if button is not None:
            button.configure(state=tk.NORMAL if enabled else tk.DISABLED)

    def set_all_enabled(self, enabled: bool) -> None:
        for key in self.buttons:
            self.set_enabled(key, enabled)


class SelectList(tk.Frame, Generic[T]):
    """A labelled Listbox that maps rows back to engine objects.

    The caller supplies ``(label, value)`` pairs and reads ``selected_value``,
    so no screen ever has to translate a row index into a game object itself.
    """

    def __init__(
        self,
        parent: tk.Misc,
        title: str = "",
        height: int = 8,
        on_select: Callable[[T], None] | None = None,
        on_activate: Callable[[T], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, bg=theme.BG, **kwargs)
        if title:
            theme.heading_label(self, text=title).pack(anchor="w", pady=(0, 4))

        holder = tk.Frame(self, bg=theme.BG)
        holder.pack(fill=tk.BOTH, expand=True)

        self.listbox = theme.stat_listbox(holder, height=height)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(holder, command=self.listbox.yview, relief=tk.FLAT, borderwidth=0)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._values: list[T] = []
        self._on_select = on_select
        self._on_activate = on_activate
        self.listbox.bind("<<ListboxSelect>>", self._handle_select)
        self.listbox.bind("<Double-Button-1>", self._handle_activate)

    # ------------------------------------------------------------------
    def set_items(self, items: Sequence[tuple[str, T]], keep_selection: bool = True) -> None:
        """Replace the contents, optionally preserving the selected index."""
        previous = self.selected_index if keep_selection else None
        self.listbox.delete(0, tk.END)
        self._values = []
        for label, value in items:
            self.listbox.insert(tk.END, label)
            self._values.append(value)
        if previous is not None and 0 <= previous < len(self._values):
            self.select_index(previous, notify=False)
        elif self._values:
            self.select_index(0, notify=False)

    def set_row_colors(self, colors: Sequence[str]) -> None:
        """Apply per-row foreground colors without changing engine data."""
        for index, color in enumerate(colors):
            try:
                self.listbox.itemconfigure(index, foreground=color)
            except (AttributeError, tk.TclError):
                # Headless test widgets and older Tk builds may not expose it.
                pass

    def set_labels(self: "SelectList[str]", labels: Sequence[str]) -> None:
        """Convenience for display-only lists where the label *is* the value."""
        self.set_items([(label, label) for label in labels])

    # ------------------------------------------------------------------
    @property
    def selected_index(self) -> int | None:
        selection = self.listbox.curselection()
        return int(selection[0]) if selection else None

    @property
    def selected_value(self) -> T | None:
        index = self.selected_index
        if index is None or index >= len(self._values):
            return None
        return self._values[index]

    def select_index(self, index: int, notify: bool = True) -> None:
        if not (0 <= index < len(self._values)):
            return
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(index)
        self.listbox.activate(index)
        self.listbox.see(index)
        if notify and self._on_select is not None:
            self._on_select(self._values[index])

    def clear(self) -> None:
        self.listbox.delete(0, tk.END)
        self._values = []

    @property
    def count(self) -> int:
        return len(self._values)

    # ------------------------------------------------------------------
    def _handle_select(self, _event: object = None) -> None:
        if self._on_select is not None:
            value = self.selected_value
            if value is not None:
                self._on_select(value)

    def _handle_activate(self, _event: object = None) -> None:
        if self._on_activate is not None:
            value = self.selected_value
            if value is not None:
                self._on_activate(value)


class LogPanel(tk.Frame):
    """Scrolling, colour-tagged message log."""

    def __init__(self, parent: tk.Misc, title: str = "", height: int = 12, **kwargs) -> None:
        super().__init__(parent, bg=theme.BG, **kwargs)
        if title:
            theme.heading_label(self, text=title).pack(anchor="w", pady=(0, 4))

        holder = tk.Frame(self, bg=theme.BG)
        holder.pack(fill=tk.BOTH, expand=True)

        self.text = theme.text_panel(holder, height=height)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(holder, command=self.text.yview, relief=tk.FLAT, borderwidth=0)
        self.text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for kind, colour in theme.LOG_COLORS.items():
            self.text.tag_configure(kind, foreground=colour)

    def append(self, message: str, kind: str = "info") -> None:
        # The widget is disabled so the player cannot type into it; writing
        # requires flipping it back to NORMAL around the insert.
        self.text.configure(state=tk.NORMAL)
        self.text.insert(tk.END, message + "\n", kind)
        self.text.see(tk.END)
        self.text.configure(state=tk.DISABLED)

    def append_many(self, messages: Iterable[str], kind: str = "info") -> None:
        for message in messages:
            self.append(message, kind)

    def set_content(self, messages: Iterable[str]) -> None:
        self.clear()
        self.append_many(messages)

    def clear(self) -> None:
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.configure(state=tk.DISABLED)


class StatusBar(tk.Frame):
    """One-line notice strip above the accent line."""

    def __init__(self, parent: tk.Misc, **kwargs) -> None:
        super().__init__(parent, bg=theme.BG_ALT, **kwargs)
        self._label = theme.body_label(
            self, text="", bg=theme.BG_ALT, fg=theme.FG_DIM, font=theme.FONT_SMALL
        )
        self._label.pack(side=tk.LEFT, padx=10, pady=4)

    def show(self, message: str) -> None:
        self._label.configure(text=message)

    def clear(self) -> None:
        self._label.configure(text="")
