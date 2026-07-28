"""Visual constants, captured from docs/GUI_STYLE_REFERENCE.md.

Every colour, font and spacing value the GUI uses lives here, so the look can
be adjusted in one place.  Straight from the style reference:

- Background: dark navy/charcoal (``#1a1f2e`` - ``#20242f``)
- Primary text: off-white / light gray
- Buttons: flat light-gray rectangles, dark text, subtle border, no gradients,
  no rounded corners - native flat Tk rather than a themed overlay
- A single thin dark-red accent line along the very bottom of the main window
- Large bold sans-serif title, small plain version label beneath it
- Stat text as small, plain, left-aligned ``key: value`` lines

**A note on the ``**options`` factories below.**  Each one builds a defaults
dict, lets the caller override entries, and splats the result into a Tk
widget.  Type-checkers flag every such call, because Tk widget constructors
declare each option as its own narrowly-typed keyword (``relief`` is a
``Literal``, ``padx`` a ``float | str``, and so on) and a ``dict[str, object]``
cannot be proven to satisfy them.  The pattern is correct at runtime - Tk
validates option names and values itself - and the alternative (spelling out
every option as an explicit parameter on all five helpers) would be far more
code for no behavioural gain.  These are the only type-check findings in the
project, and they are confined to this file.
"""

from __future__ import annotations

import tkinter as tk

__all__ = [
    "BG",
    "BG_ALT",
    "FG",
    "FG_DIM",
    "ACCENT",
    "BUTTON_BG",
    "BUTTON_FG",
    "BUTTON_ACTIVE_BG",
    "BUTTON_DISABLED_FG",
    "LISTBOX_BG",
    "LISTBOX_SELECT_BG",
    "FONT_TITLE",
    "FONT_HEADING",
    "FONT_BODY",
    "FONT_SMALL",
    "FONT_MONO",
    "LOG_COLORS",
    "flat_button",
    "body_label",
    "heading_label",
    "title_label",
    "stat_listbox",
    "text_panel",
    "accent_strip",
    "style_window",
    "center_window",
]

# ----------------------------------------------------------------------
# Palette
# ----------------------------------------------------------------------
BG = "#1a1f2e"
BG_ALT = "#20242f"
FG = "#e8e8ea"
FG_DIM = "#9aa0ac"
ACCENT = "#7a1f28"

BUTTON_BG = "#d6d6d6"
BUTTON_FG = "#1a1a1a"
BUTTON_ACTIVE_BG = "#bfbfbf"
BUTTON_DISABLED_FG = "#8a8a8a"

LISTBOX_BG = "#20242f"
LISTBOX_SELECT_BG = "#3c4354"

# ----------------------------------------------------------------------
# Typography
# ----------------------------------------------------------------------
#: Segoe UI may not exist on Linux (noted in docs/GUI_VERIFICATION.md);
#: Tk silently falls back to a default sans, which is acceptable.
_SANS = "Segoe UI"

FONT_TITLE = (_SANS, 30, "bold")
FONT_HEADING = (_SANS, 14, "bold")
FONT_BODY = (_SANS, 10)
FONT_SMALL = (_SANS, 9)
FONT_MONO = ("Consolas", 10)

#: Combat-log tag colours, keyed by CombatLogEntry.kind.
LOG_COLORS = {
    "info": FG,
    "damage": "#e0736b",
    "heal": "#7fc98a",
    "status": "#d8c07a",
    "system": FG_DIM,
}


# ----------------------------------------------------------------------
# Widget factories
# ----------------------------------------------------------------------
def flat_button(parent: tk.Misc, text: str, command, **kwargs) -> tk.Button:
    """A flat light-gray button - the style reference's core control."""
    options = {
        "text": text,
        "command": command,
        "bg": BUTTON_BG,
        "fg": BUTTON_FG,
        "activebackground": BUTTON_ACTIVE_BG,
        "activeforeground": BUTTON_FG,
        "disabledforeground": BUTTON_DISABLED_FG,
        "relief": tk.FLAT,
        "borderwidth": 1,
        "highlightthickness": 0,
        "font": FONT_BODY,
        "cursor": "hand2",
        "padx": 10,
        "pady": 6,
    }
    options.update(kwargs)
    return tk.Button(parent, **options)


def body_label(parent: tk.Misc, text: str = "", **kwargs) -> tk.Label:
    """Small plain left-aligned text - the ``key: value`` line style."""
    options = {
        "text": text,
        "bg": BG,
        "fg": FG,
        "font": FONT_BODY,
        "anchor": "w",
        "justify": tk.LEFT,
    }
    options.update(kwargs)
    return tk.Label(parent, **options)


def heading_label(parent: tk.Misc, text: str = "", **kwargs) -> tk.Label:
    options = {"text": text, "bg": BG, "fg": FG, "font": FONT_HEADING, "anchor": "w"}
    options.update(kwargs)
    return tk.Label(parent, **options)


def title_label(parent: tk.Misc, text: str = "", **kwargs) -> tk.Label:
    options = {"text": text, "bg": BG, "fg": FG, "font": FONT_TITLE}
    options.update(kwargs)
    return tk.Label(parent, **options)


def stat_listbox(parent: tk.Misc, **kwargs) -> tk.Listbox:
    """A Listbox configured for this UI.

    ``exportselection=False`` is set by default and deliberately: per
    docs/GUI_VERIFICATION.md, two Listboxes that both need a live selection
    (Combat's Action + Target lists) silently steal it from one another
    otherwise, because Tk ties selection to the X PRIMARY clipboard.
    """
    options = {
        "bg": LISTBOX_BG,
        "fg": FG,
        "selectbackground": LISTBOX_SELECT_BG,
        "selectforeground": FG,
        "relief": tk.FLAT,
        "borderwidth": 0,
        "highlightthickness": 1,
        "highlightbackground": "#2c3242",
        "highlightcolor": "#2c3242",
        "font": FONT_BODY,
        "activestyle": "none",
        "exportselection": False,
    }
    options.update(kwargs)
    return tk.Listbox(parent, **options)


def text_panel(parent: tk.Misc, **kwargs) -> tk.Text:
    """A read-only text area used for logs and long descriptions."""
    options = {
        "bg": LISTBOX_BG,
        "fg": FG,
        "relief": tk.FLAT,
        "borderwidth": 0,
        "highlightthickness": 1,
        "highlightbackground": "#2c3242",
        "font": FONT_BODY,
        "wrap": tk.WORD,
        "state": tk.DISABLED,
        "padx": 8,
        "pady": 6,
    }
    options.update(kwargs)
    return tk.Text(parent, **options)


def accent_strip(parent: tk.Misc, height: int = 3) -> tk.Frame:
    """The single thin maroon line along the bottom edge."""
    return tk.Frame(parent, bg=ACCENT, height=height)


def style_window(window: "tk.Tk | tk.Toplevel", title: str = "", geometry: str = "") -> None:
    """Apply the base background/title/size to a Tk or Toplevel.

    Typed against ``Tk | Toplevel`` rather than ``Misc`` because ``title()``
    and ``geometry()`` are window-manager methods that only those two have.
    """
    window.configure(bg=BG)
    if title:
        window.title(title)
    if geometry:
        window.geometry(geometry)


def center_window(window: "tk.Tk | tk.Toplevel", width: int, height: int) -> None:
    """Centre a window on screen.

    ``update_idletasks`` first so screen metrics are correct before the
    geometry string is applied.
    """
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 3)
    window.geometry(f"{width}x{height}+{x}+{y}")
