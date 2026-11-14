from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import pytest

from ai_perception.sources import (
    Frame,
    FrameSourceError,
    UsbCameraSource,
    VideoFileSource,
)

WIDTH, HEIGHT, FPS, N_FRAMES = 64, 48, 10.0, 5


@pytest.fixture()
def video_path(tmp_path: Path) -> Path:
    """Write a tiny MJPG .avi whose frame i is filled with brightness 40*i."""
    path = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (WIDTH, HEIGHT))
    assert writer.isOpened()
    for i in range(N_FRAMES):
        writer.write(np.full((HEIGHT, WIDTH, 3), 40 * i, dtype=np.uint8))
    writer.release()
    return path


# --- VideoFileSource -------------------------------------------------------------------------


def test_video_file_source_yields_all_frames_with_timeline_stamps(video_path: Path) -> None:
    with VideoFileSource(video_path, start_stamp=100.0) as source:
        frames = list(source)

    assert [f.index for f in frames] == list(range(N_FRAMES))
    assert [f.stamp for f in frames] == pytest.approx([100.0 + i / FPS for i in range(N_FRAMES)])
    assert frames[0].image.shape == (HEIGHT, WIDTH, 3)
    assert abs(int(frames[3].image.mean()) - 120) <= 3  # MJPG is lossy


def test_video_file_source_returns_none_at_end_of_stream(video_path: Path) -> None:
    with VideoFileSource(video_path) as source:
        for _ in range(N_FRAMES):
            assert source.read() is not None
        assert source.read() is None


def test_video_file_source_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FrameSourceError, match="not found"):
        VideoFileSource(tmp_path / "nope.mp4").open()


def test_video_file_source_unreadable_file_raises(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.avi"
    bogus.write_bytes(b"not a video")

    with pytest.raises(FrameSourceError, match="Cannot open"):
        VideoFileSource(bogus).open()


def test_read_before_open_raises(video_path: Path) -> None:
    with pytest.raises(FrameSourceError, match="not open"):
        VideoFileSource(video_path).read()


def test_close_is_idempotent(video_path: Path) -> None:
    source = VideoFileSource(video_path)
    source.open()
    source.close()
    source.close()

    assert not source.is_open


def test_video_file_source_uses_fallback_fps_when_file_reports_none(video_path: Path) -> None:
    factory = _FakeCaptureFactory(frames_to_return=2, fps=0.0)

    with VideoFileSource(video_path, fallback_fps=4.0, capture_factory=factory) as source:
        frames = list(source)

    assert [f.stamp for f in frames] == pytest.approx([0.0, 0.25])


def test_video_file_source_without_fps_and_without_fallback_raises(video_path: Path) -> None:
    factory = _FakeCaptureFactory(frames_to_return=2, fps=0.0)

    with pytest.raises(FrameSourceError, match="FPS"):
        VideoFileSource(video_path, capture_factory=factory).open()


# --- UsbCameraSource (camera replaced by a fake capture) -------------------------------------


class _FakeCapture:
    def __init__(self, frames_to_return: int, fps: float, opened: bool = True) -> None:
        self._remaining = frames_to_return
        self._fps = fps
        self._opened = opened
        self.props: List[Tuple[int, float]] = []
        self.released = False

    def isOpened(self) -> bool:  # noqa: N802 - mirrors cv2.VideoCapture
        return self._opened

    def set(self, prop: int, value: float) -> bool:
        self.props.append((prop, value))
        return True

    def get(self, prop: int) -> float:
        return self._fps if prop == cv2.CAP_PROP_FPS else 0.0

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self._remaining <= 0:
            return False, None
        self._remaining -= 1
        return True, np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)

    def release(self) -> None:
        self.released = True


class _FakeCaptureFactory:
    def __init__(self, frames_to_return: int, fps: float = 30.0, opened: bool = True) -> None:
        self.capture = _FakeCapture(frames_to_return, fps, opened)
        self.calls: List[tuple] = []

    def __call__(self, *args: object) -> _FakeCapture:
        self.calls.append(args)
        return self.capture


def test_usb_camera_stamps_with_injected_clock_and_applies_settings() -> None:
    ticks = iter([5.0, 5.1])
    factory = _FakeCaptureFactory(frames_to_return=2)
    source = UsbCameraSource(
        device=2, width=640, height=480, fps=15, clock=lambda: next(ticks), capture_factory=factory
    )

    with source:
        first, second = source.read(), source.read()

    assert isinstance(first, Frame) and isinstance(second, Frame)
    assert (first.stamp, second.stamp) == (5.0, 5.1)
    assert (first.index, second.index) == (0, 1)
    assert factory.calls == [(2, cv2.CAP_V4L2)]
    assert (cv2.CAP_PROP_FRAME_WIDTH, 640) in factory.capture.props
    assert (cv2.CAP_PROP_FPS, 15) in factory.capture.props
    assert factory.capture.released


def test_usb_camera_read_failure_raises_instead_of_ending_stream() -> None:
    factory = _FakeCaptureFactory(frames_to_return=0)

    source = UsbCameraSource(device=0, clock=lambda: 0.0, capture_factory=factory)

    with source, pytest.raises(FrameSourceError, match="read failed"):
        source.read()


def test_usb_camera_that_cannot_open_raises() -> None:
    factory = _FakeCaptureFactory(frames_to_return=0, opened=False)

    with pytest.raises(FrameSourceError, match="Cannot open"):
        UsbCameraSource(device=0, capture_factory=factory).open()
