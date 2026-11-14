"""Follow-me target: largest-bbox person → (x, y) in base_footprint (D-006, AI_PROPOSAL §7.2).

Output frame follows REP-103: x forward, y LEFT. Only (x, y) is used by moving_server's
track_person_executor; orientation is ignored there.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

from pydantic import Field

from ai_common.config import FrozenSettings
from ai_common.schemas import PersonState

Position = Tuple[float, float]

HEAD_KEYPOINTS = (0, 1, 2, 3, 4)  # COCO: nose, eyes, ears
ANKLE_KEYPOINTS = (15, 16)


class FollowSettings(FrozenSettings):
    """Env prefix ``AI_FOLLOW_``. Pixel values are in the coordinates of ``PersonState.bbox``."""

    fx: float = Field(gt=0, description="Focal length [px], from camera intrinsics")
    cx: float = Field(description="Principal point x [px]")
    distance_k: float = Field(gt=0, description="d = k / bbox_height_px, calibrated (T1.3)")
    min_confidence: float = Field(ge=0, le=1)
    min_bbox_height_px: float = Field(gt=0, description="Shorter = too far away, ignored")
    follow_distance_m: float = Field(gt=0, description="Keep equal to moving_server's")
    ema_alpha: float = Field(gt=0, le=1, description="Weight of the new measurement")
    min_keypoint_score: float = Field(ge=0, le=1)


def select_target(
    persons: Sequence[PersonState], settings: FollowSettings
) -> Optional[PersonState]:
    """Largest bbox among confident, close-enough people. No identity lock (D-006)."""
    candidates = [
        p
        for p in persons
        if p.confidence >= settings.min_confidence and p.bbox.height >= settings.min_bbox_height_px
    ]
    return max(candidates, key=lambda p: p.bbox.area, default=None)


def _any_visible(person: PersonState, indices: Sequence[int], min_score: float) -> bool:
    return any(person.keypoints[i].score >= min_score for i in indices)


def estimate_position(person: PersonState, settings: FollowSettings) -> Position:
    u, _ = person.bbox.center
    bearing = math.atan((settings.cx - u) / settings.fx)  # left of image centre → +y
    distance = settings.distance_k / person.bbox.height
    fully_visible = _any_visible(
        person, HEAD_KEYPOINTS, settings.min_keypoint_score
    ) and _any_visible(person, ANKLE_KEYPOINTS, settings.min_keypoint_score)
    if not fully_visible:
        # Cropped body → short bbox → distance overestimated; never let the robot close in.
        distance = min(distance, settings.follow_distance_m)
    return (distance * math.cos(bearing), distance * math.sin(bearing))


def step(
    previous: Optional[Position], persons: Sequence[PersonState], settings: FollowSettings
) -> Optional[Position]:
    """One frame. ``None`` = nobody to follow: stop publishing and pass ``None`` next frame."""
    target = select_target(persons, settings)
    if target is None:
        return None
    x, y = estimate_position(target, settings)
    if previous is None:
        return (x, y)
    a = settings.ema_alpha
    return (a * x + (1 - a) * previous[0], a * y + (1 - a) * previous[1])
