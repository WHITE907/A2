"""Visual constants and widget factories for Project Ascension.

The GUI deliberately stays within the restrained visual direction in
``docs/GUI_STYLE_REFERENCE.md``: deep navy surfaces, off-white text, flat
light-gray controls, and one maroon accent.  Keeping these values and factories
in one module means screens share the same spacing, fields, cards, and focus
states instead of gradually becoming a collection of one-off Tk widgets.
"""

from __future__ import annotations

import tkinter as tk

__all__ = [
    "BG",
    "BG_ALT",
    "PANEL_BG",
    "INPUT_BG",
    "BORDER",
    "FG",
    "FG_DIM",
    "ACCENT",
    "ACCENT_TEXT",
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
    "field_entry",
    "choice_button",
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
#: Raised-but-subtle surface used by reusable cards.
PANEL_BG = "#242a38"
#: Recessed background for editable controls.
INPUT_BG = "#171b27"
BORDER = "#343d50"
FG = "#e8e8ea"
FG_DIM = "#9aa0ac"
ACCENT = "#7a1f28"
ACCENT_TEXT = "#f0d060"

BUTTON_BG = "#d6d6d6"
BUTTON_FG = "#1a1a1a"
BUTTON_ACTIVE_BG = "#bfbfbf"
BUTTON_DISABLED_FG = "#8a8a8a"

LISTBOX_BG = "#20242f"
LISTBOX_SELECT_BG = "#3c4354"

# ----------------------------------------------------------------------
# Typography
# ----------------------------------------------------------------------
# Segoe UI may not exist on Linux; Tk falls back to the platform default.
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
    "common": "#d8d8d8",
    "uncommon": "#65c466",
    "rare": "#5da9e9",
    "epic": "#b678e5",
    "legendary": "#e5a83f",
    "quest": "#7fb5e0",
    "achievement": ACCENT_TEXT,
}


# ----------------------------------------------------------------------
# Widget factories
# ----------------------------------------------------------------------
def flat_button(parent: tk.Misc, text: str, command, **kwargs) -> tk.Button:
    """Create the app's compact, flat, high-contrast action button."""
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
    """Small plain left-aligned text, ideal for ``key: value`` lines."""
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


def field_entry(parent: tk.Misc, **kwargs) -> tk.Entry:
    """A consistent dark entry field with a visible but quiet focus boundary."""
    options = {
        "bg": INPUT_BG,
        "fg": FG,
        "insertbackground": FG,
        "relief": tk.FLAT,
        "borderwidth": 0,
        "highlightthickness": 1,
        "highlightbackground": BORDER,
        "highlightcolor": ACCENT_TEXT,
        "font": FONT_BODY,
    }
    options.update(kwargs)
    return tk.Entry(parent, **options)


def choice_button(parent: tk.Misc, **kwargs) -> tk.Radiobutton:
    """A themed radio button for filters and character-creation choices."""
    options = {
        "bg": BG,
        "fg": FG,
        "selectcolor": PANEL_BG,
        "activebackground": BG,
        "activeforeground": FG,
        "font": FONT_SMALL,
        "highlightthickness": 0,
        "borderwidth": 0,
    }
    options.update(kwargs)
    return tk.Radiobutton(parent, **options)


def stat_listbox(parent: tk.Misc, **kwargs) -> tk.Listbox:
    """A listbox with the app palette and independent selection ownership."""
    options = {
        "bg": LISTBOX_BG,
        "fg": FG,
        "selectbackground": LISTBOX_SELECT_BG,
        "selectforeground": FG,
        "relief": tk.FLAT,
        "borderwidth": 0,
        "highlightthickness": 1,
        "highlightbackground": BORDER,
        "highlightcolor": ACCENT_TEXT,
        "font": FONT_BODY,
        "activestyle": "none",
        # Multiple simultaneous lists (Combat, Party, Equipment) must retain
        # their selections rather than fighting over X PRIMARY.
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
        "highlightbackground": BORDER,
        "highlightcolor": ACCENT_TEXT,
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
    """Apply the shared window background, title, and optional size."""
    window.configure(bg=BG)
    if title:
        window.title(title)
    if geometry:
        window.geometry(geometry)


def center_window(window: "tk.Tk | tk.Toplevel", width: int, height: int) -> None:
    """Centre a window while keeping its initial bounds on-screen."""
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    # Leave enough room for desktop chrome; the content itself remains
    # scrollable when the viewport is shorter than the preferred height.
    width = min(width, max(320, screen_w - 32))
    height = min(height, max(260, screen_h - 80))
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 3)
    window.geometry(f"{width}x{height}+{x}+{y}")
