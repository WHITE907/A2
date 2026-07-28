"""Deterministic random source for the engine.

Every roll in the game (hit, crit, loot, encounters) goes through a single
``GameRandom`` instance owned by the game state.  Two reasons:

1. **Testability** - seeding the source makes combat reproducible, so the
   test-suite can assert on exact damage numbers instead of ranges.
2. **Save fidelity** - the generator's internal state is serialised with the
   save file, so loading a save resumes the exact same stream of rolls the
   player would have got had they never quit.

The GUI never touches this module; per bible section 5 all rolls happen inside
the engine.
"""

from __future__ import annotations

import random
from typing import Any, Iterable, Sequence, TypeVar

T = TypeVar("T")

__all__ = ["GameRandom"]


class GameRandom:
    """Thin, serialisable wrapper around :class:`random.Random`."""

    __slots__ = ("_rng", "_seed")

    def __init__(self, seed: int | None = None) -> None:
        self._seed: int | None = seed
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def seed(self) -> int | None:
        """The seed this generator was created/reseeded with, if any."""
        return self._seed

    def reseed(self, seed: int | None) -> None:
        """Restart the stream from ``seed``."""
        self._seed = seed
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Rolls
    # ------------------------------------------------------------------
    def chance(self, probability: float) -> bool:
        """Return ``True`` with the given probability.

        Values outside ``[0, 1]`` are treated as guaranteed failure/success so
        callers never have to clamp before asking.
        """
        if probability <= 0.0:
            return False
        if probability >= 1.0:
            return True
        return self._rng.random() < probability

    def random(self) -> float:
        """Uniform float in ``[0.0, 1.0)``."""
        return self._rng.random()

    def randint(self, low: int, high: int) -> int:
        """Inclusive integer roll; tolerates a reversed range."""
        if low > high:
            low, high = high, low
        return self._rng.randint(low, high)

    def uniform(self, low: float, high: float) -> float:
        """Uniform float between the two bounds, in either order."""
        if low > high:
            low, high = high, low
        return self._rng.uniform(low, high)

    def choice(self, population: Sequence[T]) -> T:
        """Pick one element uniformly.  Raises on an empty sequence."""
        if not population:
            raise ValueError("cannot choose from an empty sequence")
        return self._rng.choice(population)

    def weighted_choice(self, weighted: Iterable[tuple[T, float]]) -> T:
        """Pick one element from ``(value, weight)`` pairs.

        Non-positive weights are skipped entirely, which lets callers express
        "this entry is currently disabled" as ``weight: 0`` in JSON rather than
        having to filter the list themselves.
        """
        pairs = [(value, float(weight)) for value, weight in weighted if float(weight) > 0.0]
        if not pairs:
            raise ValueError("weighted_choice needs at least one positive weight")
        total = sum(weight for _, weight in pairs)
        roll = self._rng.random() * total
        upto = 0.0
        for value, weight in pairs:
            upto += weight
            if roll < upto:
                return value
        return pairs[-1][0]

    def shuffled(self, population: Sequence[T]) -> list[T]:
        """Return a shuffled *copy*, leaving the caller's sequence untouched."""
        items = list(population)
        self._rng.shuffle(items)
        return items

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Serialise the full internal generator state.

        ``random.Random.getstate`` returns a tuple containing a nested tuple of
        ints; JSON turns tuples into lists, so :meth:`load_state` converts back.
        """
        version, internal, gauss = self._rng.getstate()
        return {
            "seed": self._seed,
            "state": {
                "version": version,
                "internal": list(internal),
                "gauss_next": gauss,
            },
        }

    def load_state(self, payload: dict[str, Any] | None) -> None:
        """Restore a state produced by :meth:`to_dict`.

        A missing/corrupt payload is not fatal: the generator simply keeps
        rolling from wherever it is.  A broken RNG state should never be able to
        make an otherwise-valid save file unloadable.
        """
        if not payload:
            return
        self._seed = payload.get("seed")
        state = payload.get("state")
        if not isinstance(state, dict):
            return
        try:
            version = int(state["version"])
            internal = tuple(int(value) for value in state["internal"])
            gauss = state.get("gauss_next")
            self._rng.setstate((version, internal, gauss))
        except (KeyError, TypeError, ValueError):
            # Unusable state - fall back to a fresh stream from the saved seed.
            self._rng = random.Random(self._seed)
