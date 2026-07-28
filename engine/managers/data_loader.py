"""JSON loading and caching - the single door between disk and the engine.

Bible section 17: *"Cache JSON."*  Every manager goes through
:class:`DataLoader`, so a given file is parsed once per run no matter how many
managers want it, and content authors get one consistent error format when a
file is malformed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

__all__ = ["DataLoader", "ContentError", "DATA_DIR", "PROJECT_ROOT"]

#: Repository root - two levels up from ``engine/managers/``.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = PROJECT_ROOT / "data"


class ContentError(RuntimeError):
    """Raised when game content is missing or structurally invalid.

    Deliberately distinct from a plain ``ValueError``: this always means "a
    JSON file needs fixing", and the launcher can present it as a content
    problem rather than a crash.
    """


class DataLoader:
    """Reads and caches JSON documents from the data directory."""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._cache: dict[str, Any] = {}

    # ------------------------------------------------------------------
    def path_for(self, filename: str) -> Path:
        return self.data_dir / filename

    def exists(self, filename: str) -> bool:
        return self.path_for(filename).is_file()

    def load(self, filename: str, *, required: bool = True, default: Any = None) -> Any:
        """Load and cache one JSON file.

        Optional files (``required=False``) return ``default`` when absent,
        which lets content ship incrementally without the engine crashing.
        """
        if filename in self._cache:
            return self._cache[filename]

        path = self.path_for(filename)
        if not path.is_file():
            if required:
                raise ContentError(f"required data file not found: {path}")
            self._cache[filename] = default
            return default

        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ContentError(f"{path.name} is not valid JSON (line {exc.lineno}, col {exc.colno}): {exc.msg}") from exc
        except OSError as exc:
            raise ContentError(f"could not read {path}: {exc}") from exc

        self._cache[filename] = payload
        return payload

    def load_entries(self, filename: str, key: str, *, required: bool = True) -> list[dict[str, Any]]:
        """Load a document shaped ``{"<key>": [ ... ]}``.

        A bare top-level list is also accepted, because that is the shape
        people naturally write first and rejecting it adds no value.
        """
        payload = self.load(filename, required=required, default=None)
        if payload is None:
            return []
        if isinstance(payload, list):
            entries = payload
        elif isinstance(payload, Mapping):
            entries = payload.get(key, [])
        else:
            raise ContentError(f"{filename} must contain an object or a list")

        if not isinstance(entries, list):
            raise ContentError(f"{filename}: '{key}' must be a list")
        for index, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                raise ContentError(f"{filename}: entry {index} must be an object")
        return [dict(entry) for entry in entries]

    def load_mapping(self, filename: str, *, required: bool = True) -> dict[str, Any]:
        """Load a document whose top level is an object."""
        payload = self.load(filename, required=required, default={})
        if payload is None:
            return {}
        if not isinstance(payload, Mapping):
            raise ContentError(f"{filename} must contain a JSON object")
        return dict(payload)

    def clear_cache(self) -> None:
        """Drop cached documents - used by the content-reload dev tool."""
        self._cache.clear()
