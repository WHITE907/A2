"""Reusable, consistently styled Tk widgets.

These components centralise the presentation layer's repeated patterns: cards,
selection lists, logs, action stacks, and vertically scrollable pages.  They
contain no game rules; screens provide display text and callbacks only.
"""

from __future__ import annotations

import tkinter as tk
import weakref
from typing import Callable, Generic, Iterable, Sequence, TypeVar

from gui import theme

__all__ = [
    "ScrollableFrame",
    "StatPanel",
    "ButtonStack",
    "SelectList",
    "LogPanel",
    "StatusBar",
    "ToolTip",
    "ProgressBar",
]

T = TypeVar("T")


class ScrollableFrame(tk.Frame):
    """A reusable vertical viewport for long dialog content.

    The visible ``canvas`` is deliberately kept private to the component's
    layout, while screens populate :attr:`content` like an ordinary ``Frame``.
    A scrollbar is always available, so a screen remains usable when dynamic
    content (perks, quests, dialogue, small displays, etc.) grows beyond the
    available desktop height.

    Nested Listboxes and Text widgets retain their own wheel behaviour; wheel
    events over the rest of a page scroll this outer viewport.
    """

    #: One app-wide wheel dispatcher per Tk root avoids leaving a callback
    #: bound to every Toplevel that has since been closed.
    _viewports: weakref.WeakSet = weakref.WeakSet()
    _wheel_roots: weakref.WeakSet = weakref.WeakSet()

    def __init__(
        self,
        parent: tk.Misc,
        *,
        bg: str = theme.BG,
        padx: int = 18,
        pady: int = 16,
        **kwargs,
    ) -> None:
        super().__init__(parent, bg=bg, **kwargs)
        row = tk.Frame(self, bg=bg)
        row.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(row, bg=bg, highlightthickness=0, borderwidth=0)
        self.scrollbar = tk.Scrollbar(
            row,
            orient="vertical",
            command=self.canvas.yview,
            relief=tk.FLAT,
            borderwidth=0,
        )
        # Wide pages used to disappear off the right edge on compact displays:
        # Tk happily clips a side-packed row that is wider than its canvas, and
        # our original viewport only exposed vertical scrolling.  Keep a quiet
        # horizontal scrollbar available and size the embedded page to at least
        # its requested width so every panel remains reachable.
        self.xscrollbar = tk.Scrollbar(
            self,
            orient="horizontal",
            command=self.canvas.xview,
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.content = tk.Frame(self.canvas, bg=bg, padx=padx, pady=pady)
        self._content_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set, xscrollcommand=self.xscrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.xscrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Descendant widgets do not bubble wheel events to a Frame in Tk.  A
        # single scoped app binding keeps page scrolling natural over
        # labels/cards while avoiding stale callbacks for closed Toplevels.
        type(self)._viewports.add(self)
        root = self.winfo_toplevel()
        if root not in type(self)._wheel_roots:
            type(self)._wheel_roots.add(root)
            root.bind_all("<MouseWheel>", type(self)._dispatch_mousewheel, add="+")
            root.bind_all("<Button-4>", type(self)._dispatch_mousewheel, add="+")
            root.bind_all("<Button-5>", type(self)._dispatch_mousewheel, add="+")

    @classmethod
    def _dispatch_mousewheel(cls, event: object) -> None:
        """Route the shared wheel event to the viewport under the cursor."""
        widget = getattr(event, "widget", None)
        for viewport in list(cls._viewports):
            try:
                alive = bool(viewport.winfo_exists())
            except tk.TclError:
                alive = False
            if alive and widget is not None and viewport._contains(widget) and not viewport._has_own_scroll(widget):
                viewport._on_mousewheel(event)
                return

    def _on_content_configure(self, _event: object = None) -> None:
        self._sync_content_window_width()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: object) -> None:
        self._sync_content_window_width(getattr(event, "width", None))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_content_window_width(self, canvas_width: int | None = None) -> None:
        """Stretch narrow pages, but preserve wide requested layouts.

        Without this guard, a content frame whose requested width is wider than
        the viewport is forcibly narrowed to the canvas width.  Side-packed
        children can then be clipped with no way to pan to them.  Keeping the
        embedded window at ``max(canvas width, requested width)`` gives compact
        displays a horizontal fallback while retaining the normal full-width
        look for pages that already fit.
        """
        if canvas_width is None:
            try:
                canvas_width = self.canvas.winfo_width()
            except tk.TclError:
                canvas_width = 0
        try:
            requested_width = self.content.winfo_reqwidth()
        except (AttributeError, tk.TclError):
            requested_width = 0
        width = max(int(canvas_width or 0), int(requested_width or 0))
        if width:
            self.canvas.itemconfig(self._content_window, width=width)

    def _contains(self, widget: object) -> bool:
        node = widget
        while node is not None:
            if node is self.content or node is self.canvas:
                return True
            node = getattr(node, "master", None)
        return False

    @staticmethod
    def _has_own_scroll(widget: object) -> bool:
        return isinstance(widget, (tk.Listbox, tk.Text, tk.Scrollbar))

    def _on_mousewheel(self, event: object) -> str | None:
        num = getattr(event, "num", None)
        if num == 4:
            direction = -1
        elif num == 5:
            direction = 1
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return None
            # Windows emits 120-step deltas; macOS commonly emits smaller
            # deltas.  At least one unit keeps a trackpad responsive.
            direction = -max(1, abs(int(delta)) // 120) if delta > 0 else max(1, abs(int(delta)) // 120)
        if getattr(event, "state", 0) & 0x0001:  # Shift + wheel pans wide pages.
            self.canvas.xview_scroll(direction, "units")
        else:
            self.canvas.yview_scroll(direction, "units")
        return "break"


class ToolTip:
    """Hover tooltip helper for widgets."""

    def __init__(self, widget: tk.Widget, text_func: Callable[[], str] | str) -> None:
        self.widget = widget
        self.text_func = text_func
        self.tip_window: tk.Toplevel | None = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, _event: object = None) -> None:
        if self.tip_window or not self.widget.winfo_exists():
            return
        text = self.text_func() if callable(self.text_func) else self.text_func
        if not text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=text,
            background=theme.PANEL_BG,
            foreground=theme.FG,
            relief=tk.SOLID,
            borderwidth=1,
            font=theme.FONT_SMALL,
            padx=6,
            pady=4,
            justify=tk.LEFT,
        )
        label.pack(ipadx=1)

    def hide_tip(self, _event: object = None) -> None:
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()


class ProgressBar(tk.Canvas):
    """Clean, styled progress bar for EXP and Mastery."""

    def __init__(
        self,
        parent: tk.Misc,
        width: int = 180,
        height: int = 14,
        fg: str = "#5da9e9",
        bg: str = theme.BG_ALT,
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=bg,
            highlightthickness=1,
            highlightbackground=theme.BORDER,
            **kwargs,
        )
        self.fg_color = fg
        self.bg_color = bg
        self._fraction = 0.0
        self._text = ""

    def set_progress(self, current: float, maximum: float, text: str = "") -> None:
        self._fraction = 0.0 if maximum <= 0 else max(0.0, min(1.0, current / maximum))
        self._text = text
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        fill_w = int(w * self._fraction)
        if fill_w > 0:
            self.create_rectangle(0, 0, fill_w, h, fill=self.fg_color, outline="")
        if self._text:
            self.create_text(w / 2, h / 2, text=self._text, fill=theme.FG, font=("Segoe UI", 8, "bold"))


class StatPanel(tk.Frame):
    """A quiet bordered card containing stacked ``key: value`` text."""

    def __init__(self, parent: tk.Misc, title: str = "", wrap: int = 0, **kwargs) -> None:
        options = {
            "bg": theme.PANEL_BG,
            "padx": 12,
            "pady": 10,
            "highlightthickness": 1,
            "highlightbackground": theme.BORDER,
        }
        options.update(kwargs)
        super().__init__(parent, **options)
        self._title = title
        bg = options["bg"]
        if title:
            theme.heading_label(self, text=title, bg=bg, fg=theme.ACCENT_TEXT).pack(anchor="w")
            tk.Frame(self, bg=theme.BORDER, height=1).pack(fill=tk.X, pady=(6, 8))
        self._label = theme.body_label(self, text="", bg=bg, font=theme.FONT_SMALL)
        if wrap:
            self._label.configure(wraplength=wrap)
        self._label.pack(anchor="w", fill=tk.X)

    def set_lines(self, lines: Iterable[str]) -> None:
        self._label.configure(text="\n".join(lines))

    def set_text(self, text: str) -> None:
        self._label.configure(text=text)


class ButtonStack(tk.Frame):
    """A vertical stack of generously spaced flat action buttons."""

    def __init__(self, parent: tk.Misc, spacing: int = 6, width: int | None = None, **kwargs) -> None:
        options = {"bg": theme.PANEL_BG, "padx": 8, "pady": 6, "highlightthickness": 1, "highlightbackground": theme.BORDER}
        options.update(kwargs)
        super().__init__(parent, **options)
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
    """A labelled, independently scrolling Listbox rendered as a card."""

    def __init__(
        self,
        parent: tk.Misc,
        title: str = "",
        height: int = 8,
        on_select: Callable[[T], None] | None = None,
        on_activate: Callable[[T], None] | None = None,
        **kwargs,
    ) -> None:
        options = {"bg": theme.PANEL_BG, "padx": 10, "pady": 8, "highlightthickness": 1, "highlightbackground": theme.BORDER}
        options.update(kwargs)
        super().__init__(parent, **options)
        bg = options["bg"]
        if title:
            theme.heading_label(self, title, bg=bg, fg=theme.ACCENT_TEXT).pack(anchor="w", pady=(0, 6))

        holder = tk.Frame(self, bg=bg)
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

    def set_items(self, items: Sequence[tuple[str, T]], keep_selection: bool = True) -> None:
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
        for index, color in enumerate(colors):
            try:
                self.listbox.itemconfigure(index, foreground=color)
            except (AttributeError, tk.TclError):
                pass

    def set_labels(self: "SelectList[str]", labels: Sequence[str]) -> None:
        self.set_items([(label, label) for label in labels])

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
    """A bordered, independently scrolling, colour-tagged message log."""

    def __init__(self, parent: tk.Misc, title: str = "", height: int = 12, **kwargs) -> None:
        options = {"bg": theme.PANEL_BG, "padx": 10, "pady": 8, "highlightthickness": 1, "highlightbackground": theme.BORDER}
        options.update(kwargs)
        super().__init__(parent, **options)
        bg = options["bg"]
        if title:
            theme.heading_label(self, title, bg=bg, fg=theme.ACCENT_TEXT).pack(anchor="w", pady=(0, 6))

        holder = tk.Frame(self, bg=bg)
        holder.pack(fill=tk.BOTH, expand=True)

        self.text = theme.text_panel(holder, height=height)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(holder, command=self.text.yview, relief=tk.FLAT, borderwidth=0)
        self.text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for kind, colour in theme.LOG_COLORS.items():
            self.text.tag_configure(kind, foreground=colour)

    def append(self, message: str, kind: str = "info") -> None:
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
    """One-line notice strip above the root window's accent line."""

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
