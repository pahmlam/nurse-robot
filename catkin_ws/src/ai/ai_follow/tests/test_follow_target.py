from __future__ import annotations

import math
from pathlib import Path

import pytest

from ai_common.config import ConfigError, load_settings
from ai_common.schemas import NUM_COCO_KEYPOINTS, BBox, Keypoint, PersonState
from ai_follow.core.target import (
    FollowSettings,
    estimate_position,
    select_target,
    step,
)

PACKAGE_CONFIG = Path(__file__).resolve().parents[1] / "config" / "follow.yaml"

SETTINGS = FollowSettings(
    fx=500.0,
    cx=320.0,
    distance_k=600.0,  # h = 300 px → 2.0 m
    min_confidence=0.5,
    min_bbox_height_px=100.0,
    follow_distance_m=1.0,
    ema_alpha=0.5,
    min_keypoint_score=0.3,
)

HEAD = range(0, 5)  # COCO nose, eyes, ears
ANKLES = (15, 16)


def _person(
    u: float = 320.0,
    height: float = 300.0,
    width: float = 100.0,
    confidence: float = 0.9,
    track_id: int = 0,
    hidden: tuple = (),
) -> PersonState:
    keypoints = tuple(
        Keypoint(x=0.0, y=0.0, score=0.0 if i in hidden else 0.9) for i in range(NUM_COCO_KEYPOINTS)
    )
    bbox = BBox(x1=u - width / 2, y1=10.0, x2=u + width / 2, y2=10.0 + height)
    return PersonState(
        track_id=track_id, bbox=bbox, keypoints=keypoints, confidence=confidence, stamp=1.0
    )


# --- select_target ---------------------------------------------------------------------------


def test_select_target_picks_largest_bbox_area() -> None:
    near = _person(height=300, width=120, track_id=1)
    far = _person(height=150, width=60, track_id=2)

    assert select_target([far, near], SETTINGS) is near


def test_select_target_ignores_low_confidence_even_if_largest() -> None:
    big_unsure = _person(height=400, confidence=0.3, track_id=1)
    small_sure = _person(height=200, confidence=0.8, track_id=2)

    assert select_target([big_unsure, small_sure], SETTINGS) is small_sure


def test_select_target_ignores_people_too_far_away() -> None:
    assert select_target([_person(height=80)], SETTINGS) is None


def test_select_target_returns_none_for_empty_frame() -> None:
    assert select_target([], SETTINGS) is None


# --- estimate_position (base_footprint: x forward, y LEFT, REP-103) ---------------------------


def test_person_straight_ahead_is_on_x_axis_at_k_over_h() -> None:
    x, y = estimate_position(_person(u=320.0, height=300.0), SETTINGS)

    assert x == pytest.approx(2.0)
    assert y == pytest.approx(0.0)


def test_person_right_of_image_center_has_negative_y() -> None:
    # u - cx = fx → 45° to the right
    x, y = estimate_position(_person(u=820.0, height=300.0), SETTINGS)

    assert y < 0
    assert math.atan2(y, x) == pytest.approx(-math.pi / 4)
    assert math.hypot(x, y) == pytest.approx(2.0)


def test_person_left_of_image_center_has_positive_y() -> None:
    _, y = estimate_position(_person(u=120.0, height=300.0), SETTINGS)

    assert y > 0


@pytest.mark.parametrize("hidden", [tuple(HEAD), ANKLES])
def test_cropped_person_distance_is_capped_at_follow_distance(hidden: tuple) -> None:
    # Head or feet cut off → bbox too short → k/h overestimates distance; never step closer.
    x, y = estimate_position(_person(u=320.0, height=300.0, hidden=hidden), SETTINGS)

    assert math.hypot(x, y) == pytest.approx(SETTINGS.follow_distance_m)


def test_one_visible_ankle_is_enough_to_trust_distance() -> None:
    x, _ = estimate_position(_person(height=300.0, hidden=(15,)), SETTINGS)

    assert x == pytest.approx(2.0)


# --- step (select + estimate + EMA) ----------------------------------------------------------


def test_step_without_previous_returns_raw_position() -> None:
    assert step(None, [_person(height=300.0)], SETTINGS) == pytest.approx((2.0, 0.0))


def test_step_blends_with_previous_using_ema_alpha() -> None:
    assert step((1.0, 1.0), [_person(height=300.0)], SETTINGS) == pytest.approx((1.5, 0.5))


def test_step_returns_none_when_nobody_valid() -> None:
    # Invariant: no guessed position once the person is lost.
    assert step((1.0, 0.0), [_person(height=50.0)], SETTINGS) is None


# --- settings --------------------------------------------------------------------------------


def test_packaged_follow_yaml_loads_and_env_overrides_k() -> None:
    settings = load_settings(
        FollowSettings, PACKAGE_CONFIG, env={"AI_FOLLOW_DISTANCE_K": "700"}, prefix="AI_FOLLOW_"
    )

    assert settings.distance_k == pytest.approx(700.0)
    assert settings.follow_distance_m == pytest.approx(1.0)  # = moving_server default


@pytest.mark.parametrize(
    "field, value", [("fx", "0"), ("ema_alpha", "0"), ("ema_alpha", "1.5"), ("distance_k", "-1")]
)
def test_invalid_follow_settings_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ConfigError, match=field):
        load_settings(
            FollowSettings,
            PACKAGE_CONFIG,
            env={f"AI_FOLLOW_{field.upper()}": value},
            prefix="AI_FOLLOW_",
        )
