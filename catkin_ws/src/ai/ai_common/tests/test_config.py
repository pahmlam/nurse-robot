from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest
from pydantic import Field

from ai_common.config import (
    CommonSettings,
    ConfigError,
    FrozenSettings,
    deep_merge,
    env_overrides,
    load_settings,
    load_yaml,
    require_env,
)

PACKAGE_CONFIG = Path(__file__).resolve().parents[1] / "config" / "common.yaml"


class FollowSettings(FrozenSettings):
    distance_k: float
    min_bbox_height_px: int = 40
    enabled: bool = True


class SampleSettings(FrozenSettings):
    name: str
    follow: FollowSettings
    note: Optional[str] = None
    fps: float = Field(default=10.0, gt=0)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "cfg.yaml"
    path.write_text(text, encoding="utf-8")
    return path


# --- load_yaml -------------------------------------------------------------------------------


def test_load_yaml_returns_mapping(tmp_path: Path) -> None:
    path = _write(tmp_path, "name: robot\nfollow:\n  distance_k: 1.5\n")

    assert load_yaml(path) == {"name": "robot", "follow": {"distance_k": 1.5}}


def test_load_yaml_empty_file_returns_empty_dict(tmp_path: Path) -> None:
    assert load_yaml(_write(tmp_path, "")) == {}


def test_load_yaml_missing_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_yaml(tmp_path / "missing.yaml")


def test_load_yaml_invalid_syntax_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_yaml(_write(tmp_path, "name: [unclosed\n"))


def test_load_yaml_top_level_list_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="mapping"):
        load_yaml(_write(tmp_path, "- a\n- b\n"))


# --- deep_merge ------------------------------------------------------------------------------


def test_deep_merge_merges_nested_without_mutating_inputs() -> None:
    base = {"a": 1, "follow": {"distance_k": 1.0, "enabled": True}}
    override = {"follow": {"distance_k": 2.0}}

    merged = deep_merge(base, override)

    assert merged == {"a": 1, "follow": {"distance_k": 2.0, "enabled": True}}
    assert base == {"a": 1, "follow": {"distance_k": 1.0, "enabled": True}}
    assert override == {"follow": {"distance_k": 2.0}}


def test_deep_merge_scalar_replaces_mapping() -> None:
    assert deep_merge({"a": {"b": 1}}, {"a": 5}) == {"a": 5}


# --- env_overrides ---------------------------------------------------------------------------


def test_env_overrides_maps_nested_fields_to_prefixed_names() -> None:
    env = {"AI_NAME": "bot", "AI_FOLLOW_DISTANCE_K": "2.5", "UNRELATED": "x"}

    assert env_overrides(SampleSettings, env) == {
        "name": "bot",
        "follow": {"distance_k": "2.5"},
    }


def test_env_overrides_returns_empty_when_nothing_set() -> None:
    assert env_overrides(SampleSettings, {}) == {}


# --- load_settings ---------------------------------------------------------------------------


def test_load_settings_env_overrides_yaml_and_coerces_types(tmp_path: Path) -> None:
    path = _write(tmp_path, "name: robot\nfollow:\n  distance_k: 1.5\n  enabled: true\n")
    env = {"AI_FOLLOW_DISTANCE_K": "2.25", "AI_FOLLOW_ENABLED": "false", "AI_FPS": "15"}

    settings = load_settings(SampleSettings, path, env=env)

    assert settings.name == "robot"
    assert settings.follow.distance_k == pytest.approx(2.25)
    assert settings.follow.enabled is False
    assert settings.follow.min_bbox_height_px == 40
    assert settings.fps == pytest.approx(15.0)


def test_load_settings_without_yaml_uses_env_only() -> None:
    env = {"AI_NAME": "bot", "AI_FOLLOW_DISTANCE_K": "1.0"}

    settings = load_settings(SampleSettings, env=env)

    assert settings.name == "bot"


def test_load_settings_invalid_value_raises_config_error_naming_field(tmp_path: Path) -> None:
    path = _write(tmp_path, "name: robot\nfollow:\n  distance_k: 1.5\n")

    with pytest.raises(ConfigError, match="fps"):
        load_settings(SampleSettings, path, env={"AI_FPS": "-1"})


def test_load_settings_unknown_yaml_key_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, "name: robot\nfollow:\n  distance_k: 1.5\ntypo_key: 1\n")

    with pytest.raises(ConfigError, match="typo_key"):
        load_settings(SampleSettings, path, env={})


def test_settings_are_immutable(tmp_path: Path) -> None:
    settings = load_settings(SampleSettings, env={"AI_NAME": "a", "AI_FOLLOW_DISTANCE_K": "1"})

    with pytest.raises(Exception):  # noqa: B017 - pydantic raises ValidationError on frozen
        settings.name = "b"  # type: ignore[misc]


# --- require_env -----------------------------------------------------------------------------


def test_require_env_returns_values_when_present() -> None:
    assert require_env(["A", "B"], env={"A": "1", "B": "2", "C": "3"}) == {"A": "1", "B": "2"}


def test_require_env_lists_all_missing_and_empty_variables() -> None:
    with pytest.raises(ConfigError) as excinfo:
        require_env(["A", "B", "C"], env={"A": "1", "B": ""})

    message = str(excinfo.value)
    assert "B" in message and "C" in message
    assert "A," not in message


# --- CommonSettings + packaged YAML ----------------------------------------------------------


def test_packaged_common_yaml_loads() -> None:
    settings = load_settings(CommonSettings, PACKAGE_CONFIG, env={})

    assert settings.robot_id
    assert settings.log_level == "INFO"


def test_common_settings_normalises_log_level_case() -> None:
    settings = load_settings(CommonSettings, PACKAGE_CONFIG, env={"AI_LOG_LEVEL": "debug"})

    assert settings.log_level == "DEBUG"


def test_common_settings_rejects_unknown_log_level() -> None:
    with pytest.raises(ConfigError, match="log_level"):
        load_settings(CommonSettings, PACKAGE_CONFIG, env={"AI_LOG_LEVEL": "LOUD"})


def test_common_settings_reads_data_dir_from_env(tmp_path: Path) -> None:
    settings = load_settings(CommonSettings, PACKAGE_CONFIG, env={"AI_DATA_DIR": str(tmp_path)})

    assert settings.data_dir == tmp_path
