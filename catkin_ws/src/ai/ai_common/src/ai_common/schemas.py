"""Shared data schemas for AI modules.

Field types use ``typing.Optional/Tuple/Dict`` (not ``X | None`` / ``tuple[...]``) because pydantic
evaluates annotations at runtime and the robot container runs Python 3.8.

``AiEvent`` mirrors the backend payload in spec/docs/interfaces.md §4 (draft v0).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NUM_COCO_KEYPOINTS = 17


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --- Perception ------------------------------------------------------------------------------


class Keypoint(FrozenModel):
    """Image-plane keypoint in pixels."""

    x: float
    y: float
    score: float = Field(ge=0.0, le=1.0)


class BBox(FrozenModel):
    """Axis-aligned box in pixels, (x1, y1) top-left, (x2, y2) bottom-right."""

    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def _check_corners(self) -> BBox:
        if self.x2 < self.x1:
            raise ValueError("x2 must be >= x1")
        if self.y2 < self.y1:
            raise ValueError("y2 must be >= y1")
        return self

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)


class PersonState(FrozenModel):
    """One tracked person in one frame (YOLOv8-pose output after tracking)."""

    track_id: int = Field(ge=0)
    bbox: BBox
    keypoints: Tuple[Keypoint, ...]
    confidence: float = Field(ge=0.0, le=1.0)
    stamp: float = Field(ge=0.0, description="Capture time of the frame, seconds")

    @field_validator("keypoints")
    @classmethod
    def _check_keypoint_count(cls, value: Tuple[Keypoint, ...]) -> Tuple[Keypoint, ...]:
        if len(value) != NUM_COCO_KEYPOINTS:
            raise ValueError(f"expected {NUM_COCO_KEYPOINTS} COCO keypoints, got {len(value)}")
        return value


# --- Events ----------------------------------------------------------------------------------


class EventType(str, Enum):
    FALL = "FALL"
    FIRE = "FIRE"
    SMOKE = "SMOKE"
    GAS = "GAS"
    ENV_ANOMALY = "ENV_ANOMALY"
    LOW_BATTERY = "LOW_BATTERY"
    HELP_REQUEST = "HELP_REQUEST"
    REMINDER_RESULT = "REMINDER_RESULT"


class Severity(IntEnum):
    INFO = 0
    WARNING = 1
    CRITICAL = 2


class EventState(str, Enum):
    SUSPECT = "SUSPECT"
    CONFIRMED = "CONFIRMED"
    RECOVERED = "RECOVERED"
    RESOLVED = "RESOLVED"


class EventLocation(FrozenModel):
    frame: str = "map"
    x: float
    y: float
    room_hint: Optional[str] = None


class AiEvent(FrozenModel):
    event_id: str = Field(min_length=1)
    robot_id: str = Field(min_length=1)
    type: EventType
    severity: Severity
    state: EventState
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime
    location: Optional[EventLocation] = None
    snapshot_ref: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone offset")
        return value

    def to_backend_dict(self) -> Dict[str, Any]:
        """JSON-ready dict matching the backend payload contract."""
        return self.model_dump(mode="json")


# --- Energy / voice --------------------------------------------------------------------------


class EnergyStatus(FrozenModel):
    soc: float = Field(ge=0.0, le=1.0, description="State of charge 0..1")
    soc_confident: bool = Field(description="True if updated while the robot was at rest")
    eta_runtime_s: float = Field(ge=0.0)
    need_charge: bool
    stamp: float = Field(ge=0.0)


class VoiceState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
