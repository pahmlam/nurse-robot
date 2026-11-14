from __future__ import annotations

import io
import json
import logging

from ai_common.log import JsonFormatter, get_logger, log_event


def _logger(name: str) -> tuple:
    stream = io.StringIO()
    logger = get_logger(name, level="DEBUG", stream=stream)
    return logger, stream


def _lines(stream: io.StringIO) -> list:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_log_event_writes_one_json_line_with_module_event_and_data() -> None:
    logger, stream = _logger("test_follow")

    log_event(logger, "target_lost", frames_missing=7, bearing=0.12)

    [record] = _lines(stream)
    assert record["module"] == "test_follow"
    assert record["event"] == "target_lost"
    assert record["level"] == "INFO"
    assert record["data"] == {"frames_missing": 7, "bearing": 0.12}
    assert record["ts"].endswith("+00:00")


def test_log_event_keeps_vietnamese_text_readable() -> None:
    logger, stream = _logger("test_voice")

    log_event(logger, "tts_cached", phrase="Bác đã uống thuốc chưa ạ?")

    assert "Bác đã uống thuốc chưa ạ?" in stream.getvalue()


def test_log_event_respects_level() -> None:
    stream = io.StringIO()
    logger = get_logger("test_level", level="WARNING", stream=stream)

    log_event(logger, "debug_only", level=logging.DEBUG)
    log_event(logger, "hailo_missing", level=logging.ERROR, device="/dev/hailo0")

    assert [r["event"] for r in _lines(stream)] == ["hailo_missing"]


def test_log_event_includes_exception_trace() -> None:
    logger, stream = _logger("test_exc")

    try:
        raise ValueError("boom")
    except ValueError:
        log_event(logger, "frame_failed", level=logging.ERROR, exc_info=True)

    [record] = _lines(stream)
    assert "ValueError: boom" in record["exc"]


def test_get_logger_does_not_duplicate_handlers() -> None:
    stream = io.StringIO()
    first = get_logger("test_dup", stream=stream)
    second = get_logger("test_dup", stream=stream)

    log_event(second, "once")

    assert first is second
    assert len(_lines(stream)) == 1


def test_formatter_handles_plain_logging_calls() -> None:
    logger, stream = _logger("test_plain")

    logger.warning("plain message %s", "x")

    [record] = _lines(stream)
    assert record["event"] == "plain message x"
    assert "data" not in record


def test_formatter_serialises_non_json_values_as_strings() -> None:
    record = logging.LogRecord("ai.x", logging.INFO, __file__, 1, "evt", None, None)
    record.event = "evt"
    record.data = {"obj": object()}

    payload = json.loads(JsonFormatter().format(record))

    assert payload["data"]["obj"].startswith("<object object")
