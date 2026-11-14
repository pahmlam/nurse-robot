from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_common.schemas import (
    NUM_COCO_KEYPOINTS,
    AiEvent,
    BBox,
    EnergyStatus,
    EventState,
    EventType,
    Keypoint,
    PersonState,
    Severity,
    VoiceState,
)

FIXTURES = Path(__file__).parent / "fixtures"
ICT = timezone(timedelta(hours=7))


def _keypoints(score: float = 0.9) -> tuple:
    return tuple(Keypoint(x=float(i), y=float(i), score=score) for i in range(NUM_COCO_KEYPOINTS))


# --- BBox ------------------------------------------------------------------------------------


def test_bbox_geometry() -> None:
    box = BBox(x1=10, y1=20, x2=50, y2=120)

    assert box.width == 40
    assert box.height == 100
    assert box.area == 4000
    assert box.center == (30, 70)


def test_bbox_rejects_inverted_corners() -> None:
    with pytest.raises(ValidationError, match="x2"):
        BBox(x1=50, y1=0, x2=10, y2=10)
    with pytest.raises(ValidationError, match="y2"):
        BBox(x1=0, y1=50, x2=10, y2=10)


# --- PersonState -----------------------------------------------------------------------------


def test_person_state_valid() -> None:
    person = PersonState(
        track_id=3,
        bbox=BBox(x1=0, y1=0, x2=10, y2=20),
        keypoints=_keypoints(),
        confidence=0.8,
        stamp=12.5,
    )

    assert len(person.keypoints) == NUM_COCO_KEYPOINTS


def test_person_state_requires_17_keypoints() -> None:
    with pytest.raises(ValidationError, match="17"):
        PersonState(
            track_id=0,
            bbox=BBox(x1=0, y1=0, x2=1, y2=1),
            keypoints=_keypoints()[:5],
            confidence=0.5,
            stamp=0.0,
        )


def test_keypoint_score_out_of_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Keypoint(x=0, y=0, score=1.5)


def test_person_state_is_immutable() -> None:
    person = PersonState(
        track_id=0,
        bbox=BBox(x1=0, y1=0, x2=1, y2=1),
        keypoints=_keypoints(),
        confidence=0.5,
        stamp=0.0,
    )

    with pytest.raises(ValidationError):
        person.track_id = 5  # type: ignore[misc]


# --- AiEvent: contract with backend (spec/docs/interfaces.md §4) ------------------------------


def test_ai_event_round_trips_backend_contract_sample() -> None:
    sample = json.loads((FIXTURES / "backend_event_v0.json").read_text(encoding="utf-8"))

    event = AiEvent.model_validate(sample)

    assert event.type is EventType.FALL
    assert event.severity is Severity.CRITICAL
    assert event.state is EventState.CONFIRMED
    assert event.to_backend_dict() == sample


def test_ai_event_minimal_serialises_optional_fields_as_null() -> None:
    event = AiEvent(
        event_id="e-1",
        robot_id="nurse-01",
        type=EventType.GAS,
        severity=Severity.WARNING,
        state=EventState.SUSPECT,
        confidence=0.4,
        timestamp=datetime(2026, 11, 10, 14, 3, 22, tzinfo=ICT),
    )

    payload = event.to_backend_dict()

    assert payload["type"] == "GAS"
    assert payload["severity"] == 1
    assert payload["timestamp"] == "2026-11-10T14:03:22+07:00"
    assert payload["location"] is None
    assert payload["snapshot_ref"] is None
    assert payload["details"] == {}


def test_ai_event_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        AiEvent(
            event_id="e-1",
            robot_id="nurse-01",
            type=EventType.FIRE,
            severity=Severity.CRITICAL,
            state=EventState.CONFIRMED,
            confidence=0.9,
            timestamp=datetime(2026, 11, 10, 14, 3, 22),
        )


def test_ai_event_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        AiEvent(
            event_id="e-1",
            robot_id="nurse-01",
            type="EARTHQUAKE",  # type: ignore[arg-type]
            severity=Severity.INFO,
            state=EventState.SUSPECT,
            confidence=0.1,
            timestamp=datetime(2026, 11, 10, tzinfo=ICT),
        )


# --- EnergyStatus / VoiceState ---------------------------------------------------------------


def test_energy_status_bounds() -> None:
    status = EnergyStatus(
        soc=0.42, soc_confident=True, eta_runtime_s=3600, need_charge=False, stamp=1.0
    )

    assert status.soc == pytest.approx(0.42)
    with pytest.raises(ValidationError):
        EnergyStatus(soc=1.2, soc_confident=True, eta_runtime_s=0, need_charge=False, stamp=0)
    with pytest.raises(ValidationError):
        EnergyStatus(soc=0.5, soc_confident=True, eta_runtime_s=-1, need_charge=False, stamp=0)


def test_voice_state_values_match_ros_topic_contract() -> None:
    assert [s.value for s in VoiceState] == ["IDLE", "LISTENING", "THINKING", "SPEAKING"]
