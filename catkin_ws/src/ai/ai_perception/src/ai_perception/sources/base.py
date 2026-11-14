"""Frame source interface: video files, USB cameras and (later) Pi Camera share one API."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Optional

import numpy as np


class FrameSourceError(RuntimeError):
    """Source cannot be opened or a live camera failed to deliver a frame."""


@dataclass(frozen=True, eq=False)
class Frame:
    """One captured image. ``stamp`` is capture time in seconds (never processing time)."""

    image: np.ndarray  # HxWx3 BGR uint8
    stamp: float
    index: int


class FrameSource(ABC):
    """Usage: ``with source: for frame in source: ...``.

    ``read()`` returns ``None`` only at a clean end of stream (video file). A live camera that
    fails raises ``FrameSourceError`` so the caller can degrade explicitly.
    """

    @property
    @abstractmethod
    def is_open(self) -> bool: ...

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def read(self) -> Optional[Frame]: ...

    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> FrameSource:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __iter__(self) -> Iterator[Frame]:
        while True:
            frame = self.read()
            if frame is None:
                return
            yield frame
