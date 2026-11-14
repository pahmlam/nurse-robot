"""Frame sources with one interface for replay (video file) and live cameras."""

from .base import Frame, FrameSource, FrameSourceError
from .opencv_source import UsbCameraSource, VideoFileSource

__all__ = ["Frame", "FrameSource", "FrameSourceError", "UsbCameraSource", "VideoFileSource"]
