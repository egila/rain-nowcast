"""Bounded in-memory cache for decoded radar frames."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from typing import Final

from .models import RadarFrame

MAX_CACHED_FRAMES: Final = 12


class RadarFrameCache:
    """Keep the newest distinct frames ordered by radar timestamp."""

    def __init__(self, max_frames: int = MAX_CACHED_FRAMES) -> None:
        """Initialize the bounded cache."""
        if max_frames < 2:
            raise ValueError("Radar frame cache must hold at least two frames")
        self._max_frames = max_frames
        self._frames: deque[RadarFrame] = deque(maxlen=max_frames)

    def add(self, frame: RadarFrame) -> bool:
        """Add a frame, ignoring duplicates and retaining timestamp order."""
        if any(existing.timestamp == frame.timestamp for existing in self._frames):
            return False

        ordered = sorted((*self._frames, frame), key=lambda item: item.timestamp)
        self._frames = deque(ordered[-self._max_frames :], maxlen=self._max_frames)
        return True

    def latest_pair(self) -> tuple[RadarFrame, RadarFrame] | None:
        """Return the two newest frames when enough data is available."""
        if len(self._frames) < 2:
            return None
        return self._frames[-2], self._frames[-1]

    @property
    def frames(self) -> tuple[RadarFrame, ...]:
        """Return frames as an immutable snapshot."""
        return tuple(self._frames)

    def __len__(self) -> int:
        """Return the number of cached frames."""
        return len(self._frames)

    def __iter__(self) -> Iterator[RadarFrame]:
        """Iterate over frames from oldest to newest."""
        return iter(self._frames)
