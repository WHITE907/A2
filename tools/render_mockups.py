#!/usr/bin/env python3
"""Render approximate screenshots of the GUI without a display.

docs/GUI_VERIFICATION.md's pipeline (Xvfb + openbox + ``import``) needs
``python3-tk``, ``xvfb`` and ``openbox``.  Where those cannot be installed,
this script gets as close as possible from pure Python:

1. build the real screens on the headless toolkit in :mod:`tests.tk_stub`
2. walk the resulting widget tree
3. run a simplified ``pack`` geometry manager over it
4. draw the result with Pillow

The output is a *layout* rendering, not a Tk rendering: real font metrics,
native button chrome and window-manager decoration will differ.  What it does
show faithfully is structure, ordering, sizing, colour and text - which is
enough to catch a panel packed on the wrong side, a stat block that renders
empty, or a colour that never reaches a widget.

Usage::

    python3 tools/render_mockups.py [--out-dir assets/mockups]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tests import tk_stub  # noqa: E402

tk_stub.install()

import tkinter as tk  # noqa: E402  - the stub

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from engine.game import Game  # noqa: E402
from gui import theme  # noqa: E402
from gui.app import AscensionApp  # noqa: E402

WINDOW_W, WINDOW_H = 1040, 700


# ----------------------------------------------------------------------
# Fonts
# ----------------------------------------------------------------------
def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def font_for(spec) -> ImageFont.FreeTypeFont:
    """Map a theme font tuple onto a real TTF at a comparable size."""
    if not isinstance(spec, tuple):
        return _load_font(13)
    size = int(spec[1]) if len(spec) > 1 else 10
    bold = len(spec) > 2 and "bold" in str(spec[2])
    # Tk point sizes render larger than the same number of pixels.
    return _load_font(max(9, int(size * 1.35)), bold)


# ----------------------------------------------------------------------
# Geometry
# ----------------------------------------------------------------------
class Box:
    """A laid-out widget rectangle."""

    __slots__ = ("widget", "x", "y", "w", "h")

    def __init__(self, widget, x: int, y: int, w: int, h: int) -> None:
        self.widget = widget
        self.x, self.y, self.w, self.h = x, y, w, h


def _wrap_lines(text: str, font, wrap_px: int) -> list[str]:
    """Split text to fit ``wrap_px``, mirroring Tk's ``wraplength``."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not wrap_px or font.getbbox(paragraph)[2] <= wrap_px:
            lines.append(paragraph)
            continue
        current = ""
        for word in paragraph.split(" "):
            candidate = f"{current} {word}".strip()
            if current and font.getbbox(candidate)[2] > wrap_px:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines


def _text_size(text: str, font, wrap_px: int = 0) -> tuple[int, int]:
    if not text:
        return (0, 0)
    lines = _wrap_lines(text, font, wrap_px)
    widths = [font.getbbox(line)[2] for line in lines if line] or [0]
    line_h = font.getbbox("Ag")[3] + 4
    return (max(widths), line_h * len(lines))


def natural_size(widget) -> tuple[int, int]:
    """Rough intrinsic size of a leaf widget before expansion."""
    options = widget.options
    if isinstance(widget, tk.Label):
        font = font_for(options.get("font", theme.FONT_BODY))
        wrap_px = int(options.get("wraplength", 0) or 0)
        tw, th = _text_size(str(options.get("text", "")), font, wrap_px)
        return (tw + 8, th + 4)
    if isinstance(widget, tk.Button):
        font = font_for(options.get("font", theme.FONT_BODY))
        tw, th = _text_size(str(options.get("text", "")), font)
        width_chars = options.get("width")
        if width_chars:
            tw = max(tw, int(width_chars) * 8)
        return (tw + 2 * int(options.get("padx", 10)), th + 2 * int(options.get("pady", 6)))
    if isinstance(widget, tk.Listbox):
        rows = int(options.get("height", 8) or 8)
        font = font_for(options.get("font", theme.FONT_BODY))
        line_h = font.getbbox("Ag")[3] + 6
        return (200, rows * line_h + 6)
    if isinstance(widget, tk.Text):
        rows = int(options.get("height", 10) or 10)
        font = font_for(options.get("font", theme.FONT_BODY))
        line_h = font.getbbox("Ag")[3] + 5
        return (260, rows * line_h + 10)
    if isinstance(widget, tk.Entry):
        return (160, 26)
    if isinstance(widget, tk.Radiobutton):
        font = font_for(options.get("font", theme.FONT_SMALL))
        tw, th = _text_size(str(options.get("text", "")), font)
        return (tw + 26, th + 6)
    if isinstance(widget, tk.Scrollbar):
        return (12, 12)
    if isinstance(widget, tk.Frame):
        w = int(options.get("width") or 0)
        h = int(options.get("height") or 0)
        return (w, h)
    return (0, 0)


def _pad_total(value) -> int:
    """Pack padding may be a scalar or a ``(before, after)`` pair."""
    if isinstance(value, (tuple, list)):
        return sum(int(part or 0) for part in value)
    return 2 * int(value or 0)


def _pad_pair(value) -> tuple[int, int]:
    """Split pack padding into ``(before, after)``."""
    if isinstance(value, (tuple, list)):
        first = int(value[0] or 0)
        second = int(value[1] or 0) if len(value) > 1 else first
        return (first, second)
    scalar = int(value or 0)
    return (scalar, scalar)


def _children_extent(widget) -> tuple[int, int]:
    """Total space children need, honouring pack side and padding."""
    width = height = 0
    row_w = row_h = 0
    for child in widget.children:
        if not child.winfo_ismapped():
            continue
        cw, ch = measure(child)
        options = child._pack_options
        cw += _pad_total(options.get("padx", 0))
        ch += _pad_total(options.get("pady", 0))
        side = options.get("side", tk.TOP)
        if side in (tk.LEFT, tk.RIGHT):
            row_w += cw
            row_h = max(row_h, ch)
        else:
            width = max(width, cw)
            height += ch
    return (max(width, row_w), height + row_h)


def measure(widget) -> tuple[int, int]:
    """Intrinsic size including children."""
    own_w, own_h = natural_size(widget)
    if widget.children:
        kid_w, kid_h = _children_extent(widget)
        pad_x = 2 * int(widget.options.get("padx", 0) or 0)
        pad_y = 2 * int(widget.options.get("pady", 0) or 0)
        # pack_propagate(False) means the explicit size wins over children.
        if widget.options.get("_pack_propagate") is False:
            return (own_w or kid_w + pad_x, own_h or kid_h + pad_y)
        return (max(own_w, kid_w + pad_x), max(own_h, kid_h + pad_y))
    return (own_w, own_h)


def layout(widget, x: int, y: int, w: int, h: int, out: list[Box]) -> None:
    """Simplified ``pack``: place children by side, fill and expand."""
    out.append(Box(widget, x, y, w, h))

    pad_x = int(widget.options.get("padx", 0) or 0)
    pad_y = int(widget.options.get("pady", 0) or 0)
    left, top = x + pad_x, y + pad_y
    right, bottom = x + w - pad_x, y + h - pad_y

    mapped = [c for c in widget.children if c.winfo_ismapped()]

    # Tk distributes only the space left over once *every* child has its
    # natural size - including the expanding ones.  Counting natural size for
    # non-expanding children alone over-allocates and pushes later siblings
    # off the edge (which is exactly what hid the combat action panel).
    natural_v = natural_h = 0
    expand_v = expand_h = 0
    for child in mapped:
        cw, ch = measure(child)
        options = child._pack_options
        horizontal = options.get("side") in (tk.LEFT, tk.RIGHT)
        if horizontal:
            natural_h += cw + _pad_total(options.get("padx", 0))
            expand_h += 1 if options.get("expand") else 0
        else:
            natural_v += ch + _pad_total(options.get("pady", 0))
            expand_v += 1 if options.get("expand") else 0

    spare_v = max(0, (bottom - top) - natural_v)
    spare_h = max(0, (right - left) - natural_h)
    share_v = spare_v // expand_v if expand_v else 0
    share_h = spare_h // expand_h if expand_h else 0

    for child in mapped:
        options = child._pack_options
        side = options.get("side", tk.TOP)
        fill = options.get("fill", tk.NONE)
        expand = bool(options.get("expand"))
        cw, ch = measure(child)

        px_l, px_r = _pad_pair(options.get("padx", 0))
        py_t, py_b = _pad_pair(options.get("pady", 0))

        if side in (tk.LEFT, tk.RIGHT):
            box_w = cw + (share_h if expand else 0)
            box_h = (bottom - top) if fill in (tk.Y, tk.BOTH) else ch
            cx = left + px_l if side == tk.LEFT else right - box_w - px_r
            cy = top + py_t
            layout(child, cx, cy, max(1, box_w), max(1, box_h), out)
            if side == tk.LEFT:
                left += box_w + px_l + px_r
            else:
                right -= box_w + px_l + px_r
        else:
            box_h = ch + (share_v if expand else 0)
            box_w = (right - left) if fill in (tk.X, tk.BOTH) else cw
            cx = left + px_l
            if fill not in (tk.X, tk.BOTH):
                # Honour pack(anchor=...): Tk centres by default, but "w"/"e"
                # pin the child to a side.  Section headings rely on this.
                anchor = str(options.get("anchor", "center"))
                if "w" in anchor:
                    cx = left + px_l
                elif "e" in anchor:
                    cx = right - box_w - px_r
                else:
                    cx = left + ((right - left) - box_w) // 2 + px_l
            cy = top + py_t if side == tk.TOP else bottom - box_h - py_b
            layout(child, cx, cy, max(1, box_w), max(1, box_h), out)
            if side == tk.TOP:
                top += box_h + py_t + py_b
            else:
                bottom -= box_h + py_t + py_b


# ----------------------------------------------------------------------
# Drawing
# ----------------------------------------------------------------------
def _colour(value, fallback: str) -> str:
    return value if isinstance(value, str) and value.startswith("#") else fallback


def draw_widget(draw: ImageDraw.ImageDraw, box: Box) -> None:
    widget, x, y, w, h = box.widget, box.x, box.y, box.w, box.h
    options = widget.options

    if isinstance(widget, tk.Button):
        bg = _colour(options.get("bg"), theme.BUTTON_BG)
        fg = _colour(options.get("fg"), theme.BUTTON_FG)
        if options.get("state") == tk.DISABLED:
            bg, fg = "#9d9d9d", "#6e6e6e"
        draw.rectangle([x, y, x + w, y + h], fill=bg, outline="#a8a8a8")
        font = font_for(options.get("font", theme.FONT_BODY))
        text = str(options.get("text", ""))
        tw, th = _text_size(text, font)
        draw.text((x + (w - tw) / 2, y + (h - th) / 2), text, font=font, fill=fg)
        return

    if isinstance(widget, tk.Label):
        bg = _colour(options.get("bg"), theme.BG)
        draw.rectangle([x, y, x + w, y + h], fill=bg)
        font = font_for(options.get("font", theme.FONT_BODY))
        fg = _colour(options.get("fg"), theme.FG)
        text = str(options.get("text", ""))
        if not text:
            return
        anchor = options.get("anchor", "w")
        line_h = font.getbbox("Ag")[3] + 4
        wrap_px = int(options.get("wraplength", 0) or 0)
        for index, line in enumerate(_wrap_lines(text, font, wrap_px)):
            tw, _ = _text_size(line, font)
            tx = x + 4 if anchor == "w" else x + (w - tw) / 2
            draw.text((tx, y + 2 + index * line_h), line, font=font, fill=fg)
        return

    if isinstance(widget, tk.Listbox):
        draw.rectangle([x, y, x + w, y + h], fill=_colour(options.get("bg"), theme.LISTBOX_BG), outline="#2c3242")
        font = font_for(options.get("font", theme.FONT_BODY))
        line_h = font.getbbox("Ag")[3] + 6
        for index, item in enumerate(widget.items):
            iy = y + 3 + index * line_h
            if iy + line_h > y + h:
                break
            if widget.selection_includes(index):
                draw.rectangle([x + 1, iy - 1, x + w - 1, iy + line_h - 2], fill=theme.LISTBOX_SELECT_BG)
            draw.text((x + 6, iy), str(item)[:60], font=font, fill=_colour(options.get("fg"), theme.FG))
        return

    if isinstance(widget, tk.Text):
        draw.rectangle([x, y, x + w, y + h], fill=_colour(options.get("bg"), theme.LISTBOX_BG), outline="#2c3242")
        font = font_for(options.get("font", theme.FONT_BODY))
        line_h = font.getbbox("Ag")[3] + 5
        lines = widget.content.rstrip("\n").split("\n") if widget.content else []
        max_lines = max(0, (h - 12) // line_h)
        for index, line in enumerate(lines[-max_lines:]):
            draw.text((x + 8, y + 6 + index * line_h), line[:70], font=font, fill=theme.FG)
        return

    if isinstance(widget, tk.Entry):
        draw.rectangle([x, y, x + w, y + h], fill=theme.LISTBOX_BG, outline="#2c3242")
        font = font_for(theme.FONT_BODY)
        draw.text((x + 6, y + 5), widget.get()[:40], font=font, fill=theme.FG)
        return

    if isinstance(widget, tk.Radiobutton):
        draw.rectangle([x, y, x + w, y + h], fill=_colour(options.get("bg"), theme.BG))
        cy = y + h / 2
        variable = options.get("variable")
        selected = variable is not None and variable.get() == options.get("value")
        draw.ellipse([x + 4, cy - 6, x + 16, cy + 6], outline=theme.FG, width=1)
        if selected:
            draw.ellipse([x + 7, cy - 3, x + 13, cy + 3], fill=theme.FG)
        font = font_for(options.get("font", theme.FONT_SMALL))
        draw.text((x + 22, cy - 8), str(options.get("text", "")), font=font, fill=theme.FG)
        return

    if isinstance(widget, tk.Scrollbar):
        draw.rectangle([x, y, x + w, y + h], fill="#262b38")
        return

    if isinstance(widget, (tk.Frame, tk.Tk, tk.Toplevel)):
        bg = options.get("bg")
        if isinstance(bg, str) and bg.startswith("#"):
            draw.rectangle([x, y, x + w, y + h], fill=bg)


def render(widget, width: int, height: int, title: str) -> Image.Image:
    """Lay out and draw one window."""
    boxes: list[Box] = []
    layout(widget, 0, 0, width, height, boxes)

    image = Image.new("RGB", (width, height + 26), theme.BG)
    draw = ImageDraw.Draw(image)

    # Title bar - stands in for window-manager decoration.
    draw.rectangle([0, 0, width, 26], fill="#11141d")
    draw.text((10, 5), title, font=_load_font(13, bold=True), fill=theme.FG_DIM)

    body = Image.new("RGB", (width, height), theme.BG)
    body_draw = ImageDraw.Draw(body)
    for box in boxes:
        draw_widget(body_draw, box)
    image.paste(body, (0, 26))
    return image


# ----------------------------------------------------------------------
def build_app(save_dir: Path) -> AscensionApp:
    game = Game(data_dir=PROJECT_ROOT / "data", save_dir=save_dir, seed=20240728)
    game.load_content()
    return AscensionApp(tk.Tk(), game)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "assets" / "mockups"))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        save_dir = Path(tmp)
        written: list[str] = []

        # -- launcher ---------------------------------------------------
        app = build_app(save_dir)
        render(app.root, WINDOW_W, WINDOW_H, "Project Ascension").save(out_dir / "01_launcher.png")
        written.append("01_launcher.png")

        # -- main menu with a character ---------------------------------
        app.game.create_character("Aria", "female", "maiden")
        app.game.player.gain_exp(260)
        app.game.player.inventory.add_gold(180)
        app.game.save_game("aria")
        app.show_main_menu()
        render(app.root, WINDOW_W, WINDOW_H, "Project Ascension").save(out_dir / "02_main_menu.png")
        written.append("02_main_menu.png")

        # -- character creation (Toplevel) ------------------------------
        fresh = build_app(save_dir)
        fresh.show_main_menu()
        creation = fresh.open_character_creation()
        creation.name_var.set("Roland")
        squire = creation.class_list.listbox.items.index("Squire")
        creation.class_list.select_index(squire)
        render(creation, 620, 600, "Project Ascension - New Game").save(out_dir / "03_character_creation.png")
        written.append("03_character_creation.png")

        # -- save browser (Toplevel) ------------------------------------
        browser = fresh.open_save_browser("load")
        browser.slot_list.select_index(0)
        render(browser, 480, 560, "Project Ascension - Load Game").save(out_dir / "04_load_game.png")
        written.append("04_load_game.png")

        # -- world ------------------------------------------------------
        app.show_world()
        world = app.current_screen
        world.log.append("You travel to The Greenfields.", "system")
        world.log.append("Wind moves through the grass and nothing follows it.", "info")
        app.game.travel_to("greenfields")
        world.refresh()
        render(app.root, WINDOW_W, WINDOW_H, "Project Ascension").save(out_dir / "05_world.png")
        written.append("05_world.png")

        # -- combat -----------------------------------------------------
        app.game.start_battle([("green_slime", 2), ("field_rat", 2)])
        combat = app.show_combat()
        battle = app.game.battle
        if battle.waiting_for_player:
            combat.action_list.select_index(0)
            if combat.target_list.count:
                combat.target_list.select_index(0)
            combat._use_selected()
        combat.refresh()
        render(app.root, WINDOW_W, WINDOW_H, "Project Ascension").save(out_dir / "06_combat.png")
        written.append("06_combat.png")

        # -- status / inventory / equipment / skills / shop --------------
        app.game.battle = None
        app.show_world()
        app.game.player.unspent_stat_points = 5
        app.game.player.unspent_skill_points = 2

        for name, opener, size in (
            ("07_status.png", app.open_status, (560, 620)),
            ("08_inventory.png", app.open_inventory, (660, 520)),
            ("09_equipment.png", app.open_equipment, (720, 520)),
            ("10_skills.png", app.open_skills, (760, 560)),
        ):
            window = opener()
            window.refresh()
            render(window, size[0], size[1], f"Project Ascension - {name[3:-4].title()}").save(out_dir / name)
            written.append(name)
            app.close_all_toplevels()

        app.game.travel_to("town_ashvale")
        shop = app.open_shop("ashvale_general")
        shop.stock_list.select_index(0)
        render(shop, 720, 520, "Project Ascension - Ashvale General Goods").save(out_dir / "11_shop.png")
        written.append("11_shop.png")

        talk = app.open_talk("innkeeper_mara")
        talk._talk()
        render(talk, 620, 520, "Project Ascension - Mara").save(out_dir / "12_talk.png")
        written.append("12_talk.png")

    print(f"Wrote {len(written)} mockups to {out_dir}:")
    for name in written:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
