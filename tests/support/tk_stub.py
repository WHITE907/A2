"""A headless stand-in for ``tkinter``, used to test the GUI without a display.

docs/GUI_VERIFICATION.md describes verifying Tkinter output with Xvfb +
openbox + screenshots.  That pipeline needs ``python3-tk``, ``xvfb`` and
``openbox`` installed; where those are unavailable (no display, no root) this
module provides the next best thing: a faithful-enough fake ``tkinter`` that
records every widget, option and geometry call.

What this *does* verify:

- every screen constructs without error against the real engine
- the widget tree has the expected structure and options
  (including ``exportselection=False``, the bug from GUI_VERIFICATION.md)
- theme colours/fonts actually reach the widgets
- button commands are wired to real handlers, and invoking them drives the
  engine correctly and updates the widgets

What it does *not* verify: pixel rendering, font fallback, real event
dispatch, or window-manager behaviour.  Those still need the Xvfb pipeline or
a real desktop, exactly as GUI_VERIFICATION.md's closing section says.

Install with :func:`install`, which registers the fake modules in
``sys.modules`` *before* ``gui`` is imported.
"""

from __future__ import annotations

import sys
import types
from typing import Any, Callable

__all__ = ["install", "uninstall", "Widget", "records"]

# ----------------------------------------------------------------------
# Constants mirroring tkinter's
# ----------------------------------------------------------------------
END = "end"
LEFT = "left"
RIGHT = "right"
TOP = "top"
BOTTOM = "bottom"
BOTH = "both"
X = "x"
Y = "y"
NONE = "none"
FLAT = "flat"
RAISED = "raised"
SUNKEN = "sunken"
NORMAL = "normal"
DISABLED = "disabled"
ACTIVE = "active"
WORD = "word"
CHAR = "char"
VERTICAL = "vertical"
HORIZONTAL = "horizontal"
SINGLE = "single"
BROWSE = "browse"


class TclError(Exception):
    """Mirrors ``tkinter.TclError``."""


# ----------------------------------------------------------------------
# Recording
# ----------------------------------------------------------------------
class _Records:
    """Global capture of dialogs raised during a test run."""

    def __init__(self) -> None:
        self.info: list[tuple[str, str]] = []
        self.errors: list[tuple[str, str]] = []
        self.questions: list[tuple[str, str]] = []
        #: Scripted answer for the next ``askyesno``.
        self.answer_yes: bool = True

    def clear(self) -> None:
        self.info.clear()
        self.errors.clear()
        self.questions.clear()
        self.answer_yes = True


records = _Records()


# ----------------------------------------------------------------------
# Variables
# ----------------------------------------------------------------------
class Variable:
    def __init__(self, master: Any = None, value: Any = None, name: str | None = None) -> None:
        self._value = value if value is not None else self._default()
        self._callbacks: list[Callable[[], None]] = []

    @staticmethod
    def _default() -> Any:
        return ""

    def get(self) -> Any:
        return self._value

    def set(self, value: Any) -> None:
        self._value = value
        for callback in list(self._callbacks):
            callback()

    def trace_add(self, mode: str, callback: Callable[..., None]) -> str:
        self._callbacks.append(lambda: callback("", "", mode))
        return "trace0"


class StringVar(Variable):
    @staticmethod
    def _default() -> Any:
        return ""


class IntVar(Variable):
    @staticmethod
    def _default() -> Any:
        return 0


class DoubleVar(Variable):
    @staticmethod
    def _default() -> Any:
        return 0.0


class BooleanVar(Variable):
    @staticmethod
    def _default() -> Any:
        return False


# ----------------------------------------------------------------------
# Widgets
# ----------------------------------------------------------------------
class Widget:
    """Base fake widget: stores options, children and geometry calls."""

    def __init__(self, master: Any = None, **options: Any) -> None:
        self.master = master
        self.options: dict[str, Any] = dict(options)
        self.children: list["Widget"] = []
        self.bindings: dict[str, Callable[..., Any]] = {}
        self._mapped = False
        self._exists = True
        self._pack_options: dict[str, Any] = {}
        if isinstance(master, Widget):
            master.children.append(self)

    # -- options ---------------------------------------------------------
    def configure(self, **options: Any) -> None:
        self.options.update(options)

    config = configure

    def cget(self, key: str) -> Any:
        return self.options.get(key)

    def __getitem__(self, key: str) -> Any:
        return self.options.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.options[key] = value

    def keys(self) -> list[str]:
        return list(self.options)

    # -- geometry --------------------------------------------------------
    def pack(self, **options: Any) -> None:
        self._mapped = True
        self._pack_options = dict(options)

    def pack_forget(self) -> None:
        self._mapped = False

    def pack_propagate(self, flag: bool) -> None:
        self.options["_pack_propagate"] = flag

    def grid(self, **options: Any) -> None:
        self._mapped = True
        self._pack_options = dict(options)

    def grid_forget(self) -> None:
        self._mapped = False

    def place(self, **options: Any) -> None:
        self._mapped = True

    def place_forget(self) -> None:
        self._mapped = False

    # -- info ------------------------------------------------------------
    def winfo_ismapped(self) -> bool:
        return self._mapped

    def winfo_exists(self) -> bool:
        return self._exists

    def winfo_children(self) -> list["Widget"]:
        return list(self.children)

    def winfo_screenwidth(self) -> int:
        return 1920

    def winfo_screenheight(self) -> int:
        return 1080

    def winfo_width(self) -> int:
        return int(self.options.get("width", 100) or 100)

    def winfo_height(self) -> int:
        return int(self.options.get("height", 100) or 100)

    def winfo_reqwidth(self) -> int:
        return int(self.options.get("width", self.winfo_width()) or self.winfo_width())

    def winfo_reqheight(self) -> int:
        return int(self.options.get("height", self.winfo_height()) or self.winfo_height())

    def winfo_toplevel(self) -> "Widget":
        node: Widget = self
        while isinstance(node.master, Widget):
            node = node.master
        return node

    # -- events ----------------------------------------------------------
    def bind(self, sequence: str, func: Callable[..., Any], add: str | None = None) -> str:
        self.bindings[sequence] = func
        return "bind0"

    def bind_all(self, sequence: str, func: Callable[..., Any], add: str | None = None) -> str:
        """Small model of Tk's root-scoped bindings for scroll tests."""
        root = self.winfo_toplevel()
        if not hasattr(root, "_global_bindings"):
            root._global_bindings = {}
        if add in ("+", True):
            root._global_bindings.setdefault(sequence, []).append(func)
        else:
            root._global_bindings[sequence] = [func]
        return "bindall0"

    def unbind(self, sequence: str, funcid: str | None = None) -> None:
        self.bindings.pop(sequence, None)

    def event_generate(self, sequence: str, **kwargs: Any) -> None:
        """Fire local and global handlers directly - the stub has no event loop."""
        event = types.SimpleNamespace(widget=self, **kwargs)
        handler = self.bindings.get(sequence)
        if handler is not None:
            handler(event)
        root = self.winfo_toplevel()
        for global_handler in list(getattr(root, "_global_bindings", {}).get(sequence, [])):
            global_handler(event)

    def focus_set(self) -> None:
        pass

    focus = focus_set

    def update(self) -> None:
        pass

    def update_idletasks(self) -> None:
        pass

    def after(self, delay: int, func: Callable[..., Any] | None = None, *args: Any) -> str:
        # Run immediately: tests want deterministic ordering, not real delays.
        if func is not None:
            func(*args)
        return "after0"

    def after_cancel(self, identifier: str) -> None:
        pass

    def destroy(self) -> None:
        self._exists = False
        self._mapped = False
        for child in list(self.children):
            child.destroy()
        if isinstance(self.master, Widget) and self in self.master.children:
            self.master.children.remove(self)

    # -- introspection helpers used by tests -----------------------------
    def walk(self):
        """Yield this widget and every descendant."""
        yield self
        for child in list(self.children):
            yield from child.walk()

    def find_all(self, cls: type) -> list["Widget"]:
        return [w for w in self.walk() if isinstance(w, cls)]

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        text = self.options.get("text")
        return f"<{type(self).__name__}{' ' + repr(text) if text else ''}>"


class Misc(Widget):
    pass


class Frame(Widget):
    pass


class LabelFrame(Widget):
    pass


class Label(Widget):
    pass


class Button(Widget):
    """Records its command so tests can invoke it like a real click."""

    def invoke(self) -> Any:
        if self.options.get("state") == DISABLED:
            return None
        command = self.options.get("command")
        return command() if callable(command) else None

    def flash(self) -> None:
        pass


class Radiobutton(Widget):
    def invoke(self) -> Any:
        variable = self.options.get("variable")
        if isinstance(variable, Variable):
            variable.set(self.options.get("value"))
        command = self.options.get("command")
        return command() if callable(command) else None

    def select(self) -> None:
        variable = self.options.get("variable")
        if isinstance(variable, Variable):
            variable.set(self.options.get("value"))


class Checkbutton(Radiobutton):
    pass


class Entry(Widget):
    """Backed by its ``textvariable`` when one is supplied."""

    def __init__(self, master: Any = None, **options: Any) -> None:
        super().__init__(master, **options)
        self._text = ""

    def _variable(self) -> Variable | None:
        variable = self.options.get("textvariable")
        return variable if isinstance(variable, Variable) else None

    def get(self) -> str:
        variable = self._variable()
        return str(variable.get()) if variable else self._text

    def insert(self, index: Any, text: str) -> None:
        variable = self._variable()
        if variable:
            variable.set(str(variable.get()) + text)
        else:
            self._text += text

    def delete(self, first: Any, last: Any = None) -> None:
        variable = self._variable()
        if variable:
            variable.set("")
        else:
            self._text = ""


class Listbox(Widget):
    """Tracks items and selection; honours ``exportselection`` semantics."""

    def __init__(self, master: Any = None, **options: Any) -> None:
        super().__init__(master, **options)
        self.items: list[str] = []
        self._selection: set[int] = set()
        self._active: int | None = None

    def insert(self, index: Any, *elements: str) -> None:
        if index == END or index == "end":
            self.items.extend(elements)
        else:
            position = int(index)
            for offset, element in enumerate(elements):
                self.items.insert(position + offset, element)

    def delete(self, first: Any, last: Any = None) -> None:
        if first in (0, "0") and last in (END, "end"):
            self.items.clear()
            self._selection.clear()
            return
        start = 0 if first in (END, "end") else int(first)
        stop = start if last is None else (len(self.items) - 1 if last in (END, "end") else int(last))
        del self.items[start : stop + 1]
        self._selection = {i for i in self._selection if i < len(self.items)}

    def get(self, first: Any, last: Any = None) -> Any:
        if last is None:
            index = len(self.items) - 1 if first in (END, "end") else int(first)
            return self.items[index] if 0 <= index < len(self.items) else ""
        start = int(first)
        stop = len(self.items) - 1 if last in (END, "end") else int(last)
        return tuple(self.items[start : stop + 1])

    def size(self) -> int:
        return len(self.items)

    def curselection(self) -> tuple[int, ...]:
        return tuple(sorted(self._selection))

    def selection_set(self, first: Any, last: Any = None) -> None:
        start = int(first)
        stop = start if last is None else int(last)
        for index in range(start, stop + 1):
            if 0 <= index < len(self.items):
                self._selection.add(index)
        self._notify_export()

    select_set = selection_set

    def selection_clear(self, first: Any = 0, last: Any = None) -> None:
        if last in (END, "end") or last is None:
            self._selection.clear()
        else:
            for index in range(int(first), int(last) + 1):
                self._selection.discard(index)

    select_clear = selection_clear

    def selection_includes(self, index: int) -> bool:
        return int(index) in self._selection

    def activate(self, index: Any) -> None:
        self._active = int(index)

    def see(self, index: Any) -> None:
        pass

    def yview(self, *args: Any) -> None:
        pass

    def index(self, spec: Any) -> int:
        return len(self.items) if spec in (END, "end") else int(spec)

    # ------------------------------------------------------------------
    def _notify_export(self) -> None:
        """Reproduce the PRIMARY-selection conflict from GUI_VERIFICATION.md.

        A real ``tk.Listbox`` with ``exportselection=True`` owns the X PRIMARY
        selection, and only one widget can.  When a second such listbox gains
        a selection, Tk clears the first one's.  Modelling that here means the
        test-suite genuinely catches the bug rather than assuming it away.
        """
        if not self.options.get("exportselection", True):
            return
        root = self.winfo_toplevel()
        for widget in root.walk():
            if (
                isinstance(widget, Listbox)
                and widget is not self
                and widget.options.get("exportselection", True)
            ):
                widget._selection.clear()


class Text(Widget):
    def __init__(self, master: Any = None, **options: Any) -> None:
        super().__init__(master, **options)
        self.content = ""
        self.tags: dict[str, dict[str, Any]] = {}

    def insert(self, index: Any, text: str, *tags: Any) -> None:
        self.content += text

    def delete(self, first: Any, last: Any = None) -> None:
        self.content = ""

    def get(self, first: Any = "1.0", last: Any = END) -> str:
        return self.content

    def see(self, index: Any) -> None:
        pass

    def yview(self, *args: Any) -> None:
        pass

    def tag_configure(self, name: str, **options: Any) -> None:
        self.tags[name] = dict(options)

    tag_config = tag_configure

    def tag_add(self, name: str, first: Any, last: Any = None) -> None:
        pass


class Scrollbar(Widget):
    def set(self, first: Any, last: Any) -> None:
        pass


class Canvas(Widget):
    def __init__(self, master: Any = None, **options: Any) -> None:
        super().__init__(master, **options)
        self.yview_scroll_calls: list[tuple[Any, ...]] = []
        self.xview_scroll_calls: list[tuple[Any, ...]] = []
        self.itemconfig_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def create_line(self, *args: Any, **kwargs: Any) -> int:
        return 1

    def create_rectangle(self, *args: Any, **kwargs: Any) -> int:
        return 1

    def create_text(self, *args: Any, **kwargs: Any) -> int:
        return 1

    def create_window(self, *args: Any, **kwargs: Any) -> int:
        return 1

    def itemconfig(self, *args: Any, **kwargs: Any) -> None:
        self.itemconfig_calls.append((args, dict(kwargs)))

    def bbox(self, *args: Any) -> tuple[int, int, int, int]:
        return (0, 0, 100, 100)

    def yview(self, *args: Any) -> None:
        pass

    def xview(self, *args: Any) -> None:
        pass

    def yview_scroll(self, *args: Any) -> None:
        self.yview_scroll_calls.append(args)

    def xview_scroll(self, *args: Any) -> None:
        self.xview_scroll_calls.append(args)

    def delete(self, *args: Any) -> None:
        pass


class Scale(Widget):
    def get(self) -> float:
        return float(self.options.get("from_", 0))

    def set(self, value: float) -> None:
        self.options["value"] = value


class Spinbox(Entry):
    pass


class Menu(Widget):
    def add_command(self, **kwargs: Any) -> None:
        pass

    def add_separator(self, **kwargs: Any) -> None:
        pass

    def add_cascade(self, **kwargs: Any) -> None:
        pass


class Wm:
    """Window-manager methods shared by Tk and Toplevel."""

    def title(self, text: str | None = None) -> Any:
        if text is None:
            return getattr(self, "_title", "")
        self._title = text
        return None

    def geometry(self, spec: str | None = None) -> Any:
        if spec is None:
            return getattr(self, "_geometry", "")
        self._geometry = spec
        return None

    def minsize(self, width: int, height: int) -> None:
        self._minsize = (width, height)

    def maxsize(self, width: int, height: int) -> None:
        self._maxsize = (width, height)

    def resizable(self, width: bool, height: bool) -> None:
        pass

    def protocol(self, name: str, func: Callable[[], None] | None = None) -> None:
        if not hasattr(self, "_protocols"):
            self._protocols: dict[str, Callable[[], None]] = {}
        if func is not None:
            self._protocols[name] = func

    def transient(self, master: Any = None) -> None:
        self._transient_for = master

    def deiconify(self) -> None:
        self._mapped = True

    def iconify(self) -> None:
        self._mapped = False

    def withdraw(self) -> None:
        self._mapped = False

    def lift(self, above: Any = None) -> None:
        pass

    def attributes(self, *args: Any) -> None:
        pass

    def grab_set(self) -> None:
        pass

    def grab_release(self) -> None:
        pass

    def wm_title(self, text: str | None = None) -> Any:
        return self.title(text)


class Tk(Widget, Wm):
    """Fake root window."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        Widget.__init__(self, None)
        self._title = ""
        self._geometry = ""
        self._protocols: dict[str, Callable[[], None]] = {}
        self.mainloop_calls = 0

    def mainloop(self, n: int = 0) -> None:
        # Never blocks - tests drive handlers directly instead.
        self.mainloop_calls += 1

    def quit(self) -> None:
        pass

    def report_callback_exception(self, exc, val, tb) -> None:  # pragma: no cover
        raise val


class Toplevel(Widget, Wm):
    def __init__(self, master: Any = None, **options: Any) -> None:
        Widget.__init__(self, master, **options)
        self._title = ""
        self._geometry = ""
        self._protocols: dict[str, Callable[[], None]] = {}
        self._mapped = True


# ----------------------------------------------------------------------
# Submodules
# ----------------------------------------------------------------------
def _build_messagebox() -> types.ModuleType:
    module = types.ModuleType("tkinter.messagebox")

    def showinfo(title: str = "", message: str = "", **kwargs: Any) -> str:
        records.info.append((title, message))
        return "ok"

    def showerror(title: str = "", message: str = "", **kwargs: Any) -> str:
        records.errors.append((title, message))
        return "ok"

    def showwarning(title: str = "", message: str = "", **kwargs: Any) -> str:
        records.errors.append((title, message))
        return "ok"

    def askyesno(title: str = "", message: str = "", **kwargs: Any) -> bool:
        records.questions.append((title, message))
        return records.answer_yes

    def askokcancel(title: str = "", message: str = "", **kwargs: Any) -> bool:
        records.questions.append((title, message))
        return records.answer_yes

    module.showinfo = showinfo
    module.showerror = showerror
    module.showwarning = showwarning
    module.askyesno = askyesno
    module.askokcancel = askokcancel
    return module


def _build_font() -> types.ModuleType:
    module = types.ModuleType("tkinter.font")

    class Font:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._options = kwargs

        def measure(self, text: str) -> int:
            return len(text) * 7

        def metrics(self, *args: Any) -> dict[str, int]:
            return {"linespace": 16, "ascent": 12, "descent": 4}

    def families(*args: Any, **kwargs: Any) -> tuple[str, ...]:
        return ("Segoe UI", "DejaVu Sans", "TkDefaultFont")

    module.Font = Font
    module.families = families
    module.nametofont = lambda name: Font()
    return module


def _build_ttk() -> types.ModuleType:
    module = types.ModuleType("tkinter.ttk")
    for name in ("Frame", "Label", "Button", "Entry", "Combobox", "Notebook", "Treeview", "Separator"):
        module.__dict__[name] = type(name, (Widget,), {})

    class Style:
        def configure(self, *args: Any, **kwargs: Any) -> None:
            pass

        def theme_use(self, *args: Any) -> None:
            pass

        def map(self, *args: Any, **kwargs: Any) -> None:
            pass

    module.Style = Style
    return module


def _build_tkinter() -> types.ModuleType:
    module = types.ModuleType("tkinter")
    for name, value in globals().items():
        if not name.startswith("_") and name not in ("install", "uninstall", "records", "sys", "types"):
            module.__dict__[name] = value
    module.TkVersion = 8.6
    module.TclVersion = 8.6
    module.__stub__ = True
    return module


_ORIGINALS: dict[str, Any] = {}
_NAMES = ("tkinter", "tkinter.messagebox", "tkinter.font", "tkinter.ttk")


def install() -> types.ModuleType:
    """Register the fake tkinter modules in ``sys.modules``.

    Must be called *before* importing ``gui``.  Returns the fake root module.
    """
    for name in _NAMES:
        if name in sys.modules and name not in _ORIGINALS:
            _ORIGINALS[name] = sys.modules[name]

    root_module = _build_tkinter()
    messagebox = _build_messagebox()
    font = _build_font()
    ttk = _build_ttk()

    root_module.messagebox = messagebox
    root_module.font = font
    root_module.ttk = ttk

    sys.modules["tkinter"] = root_module
    sys.modules["tkinter.messagebox"] = messagebox
    sys.modules["tkinter.font"] = font
    sys.modules["tkinter.ttk"] = ttk
    return root_module


def uninstall() -> None:
    """Restore whatever was in ``sys.modules`` before :func:`install`."""
    for name in _NAMES:
        sys.modules.pop(name, None)
        if name in _ORIGINALS:
            sys.modules[name] = _ORIGINALS.pop(name)
