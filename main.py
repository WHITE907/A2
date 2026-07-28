#!/usr/bin/env python3
"""Project Ascension - entry point.

Usage::

    python3 main.py                 # play
    python3 main.py --seed 1234     # reproducible RNG, for debugging
    python3 main.py --check         # validate all content and exit

Tkinter is imported lazily inside :func:`main` so ``--check`` still works on a
machine without ``python3-tk`` installed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py", description="Project Ascension")
    parser.add_argument("--data-dir", default=None, help="override the content directory")
    parser.add_argument("--save-dir", default=None, help="override the save directory")
    parser.add_argument("--seed", type=int, default=None, help="seed the RNG for reproducible runs")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate all game content, print a summary, and exit",
    )
    return parser


def check_content(data_dir: str | None) -> int:
    """Load and cross-validate every content file without starting the GUI."""
    from engine.game import GAME_VERSION, Game
    from engine.managers.data_loader import ContentError

    game = Game(data_dir=data_dir)
    try:
        game.load_content()
    except ContentError as exc:
        print(f"Content error:\n{exc}", file=sys.stderr)
        return 1

    print(f"Project Ascension {GAME_VERSION} - content OK")
    for line in game.content_summary():
        print(f"  {line}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.check:
        return check_content(args.data_dir)

    try:
        import tkinter  # noqa: F401
    except ImportError:
        print(
            "Tkinter is not available.\n"
            "  Debian/Ubuntu: sudo apt-get install python3-tk\n"
            "  Fedora:        sudo dnf install python3-tkinter\n"
            "  Windows/macOS: reinstall Python with the Tcl/Tk option enabled\n"
            "\nRun 'python3 main.py --check' to verify content without a GUI.",
            file=sys.stderr,
        )
        return 1

    from gui.app import run

    run(data_dir=args.data_dir, save_dir=args.save_dir, seed=args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
