"""OpenCV-backed frame sources: video files (replay) and USB/V4L2 cameras."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Optional, Union

import cv2

from .base import Frame, FrameSource, FrameSourceError

CaptureFactory = Callable[..., Any]
Clock = Callable[[], float]


class _OpenCvSource(FrameSource):
    """Shared open/read/close around a ``cv2.VideoCapture``-like object."""

    def __init__(self, capture_factory: CaptureFactory) -> None:
        self._capture_factory = capture_factory
        self._capture: Optional[Any] = None
        self._index = 0

    @property
    def is_open(self) -> bool:
        return self._capture is not None

    def _open_capture(self, *args: Any) -> Any:
        capture = self._capture_factory(*args)
        if not capture.isOpened():
            capture.release()
            raise FrameSourceError(f"Cannot open video source {args[0]!r}")
        return capture

    def _grab(self) -> Optional[Any]:
        if self._capture is None:
            raise FrameSourceError("Frame source is not open; call open() or use 'with'")
        ok, image = self._capture.read()
        return image if ok and image is not None else None

    def _next_index(self) -> int:
        index = self._index
        self._index += 1
        return index

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


class VideoFileSource(_OpenCvSource):
    """Replays a video file. Stamps follow the video timeline: ``start_stamp + index / fps``.

    Deterministic stamps make replay tests reproducible regardless of processing speed.
    """

    def __init__(
        self,
        path: Union[str, Path],
        start_stamp: float = 0.0,
        fallback_fps: Optional[float] = None,
        capture_factory: CaptureFactory = cv2.VideoCapture,
    ) -> None:
        super().__init__(capture_factory)
        self._path = Path(path)
        self._start_stamp = start_stamp
        self._fallback_fps = fallback_fps
        self._fps = 0.0

    def open(self) -> None:
        if not self._path.is_file():
            raise FrameSourceError(f"Video file not found: {self._path}")
        capture = self._open_capture(str(self._path))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0.0:
            fps = self._fallback_fps or 0.0
        if fps <= 0.0:
            capture.release()
            raise FrameSourceError(f"Video {self._path} reports no FPS; pass fallback_fps")
        self._capture, self._fps, self._index = capture, fps, 0

    def read(self) -> Optional[Frame]:
        image = self._grab()
        if image is None:
            return None
        index = self._next_index()
        return Frame(image=image, stamp=self._start_stamp + index / self._fps, index=index)


class UsbCameraSource(_OpenCvSource):
    """USB webcam through V4L2. Stamp = ``clock()`` right after the frame is grabbed."""

    def __init__(
        self,
        device: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: Optional[float] = None,
        clock: Clock = time.time,
        capture_factory: CaptureFactory = cv2.VideoCapture,
    ) -> None:
        super().__init__(capture_factory)
        self._device = device
        self._settings = (
            (cv2.CAP_PROP_FRAME_WIDTH, width),
            (cv2.CAP_PROP_FRAME_HEIGHT, height),
            (cv2.CAP_PROP_FPS, fps),
        )
        self._clock = clock

    def open(self) -> None:
        capture = self._open_capture(self._device, cv2.CAP_V4L2)
        for prop, value in self._settings:
            if value is not None:
                capture.set(prop, value)
        self._capture, self._index = capture, 0

    def read(self) -> Optional[Frame]:
        image = self._grab()
        if image is None:
            raise FrameSourceError(f"Camera {self._device} read failed")
        stamp = self._clock()
        return Frame(image=image, stamp=stamp, index=self._next_index())
