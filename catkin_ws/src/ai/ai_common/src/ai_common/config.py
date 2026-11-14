"""Configuration loading: YAML defaults overridden by environment variables.

Precedence (lowest → highest): model defaults < YAML file < env vars.

Env var names are derived from the settings model: prefix ``AI_`` + field path joined by ``_``,
upper-cased. ``follow.distance_k`` → ``AI_FOLLOW_DISTANCE_K``. Only scalar fields can be set
from env (nested models are walked); lists/dicts must come from YAML.
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Type, TypeVar, Union

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

ENV_PREFIX = "AI_"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

PathLike = Union[str, Path]
SettingsT = TypeVar("SettingsT", bound=BaseModel)


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid. Startup should stop on this."""


class FrozenSettings(BaseModel):
    """Base for settings models: immutable, unknown keys rejected (catches YAML typos)."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class CommonSettings(FrozenSettings):
    """Settings shared by every AI node (ai_common/config/common.yaml)."""

    robot_id: str
    log_level: str = "INFO"
    data_dir: Optional[Path] = None

    @field_validator("log_level", mode="before")
    @classmethod
    def _check_log_level(cls, value: Any) -> str:
        level = str(value).upper()
        if level not in LOG_LEVELS:
            raise ValueError(f"must be one of {', '.join(LOG_LEVELS)}")
        return level


def load_yaml(path: PathLike) -> Dict[str, Any]:
    """Read a YAML mapping. Empty file → ``{}``."""
    file_path = Path(path)
    if not file_path.is_file():
        raise ConfigError(f"Config file not found: {file_path}")
    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {file_path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"Top level of {file_path} must be a mapping, got {type(data).__name__}")
    return data


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a new dict: ``override`` merged into ``base`` recursively. Inputs are untouched."""
    merged: Dict[str, Any] = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def _nested_model(annotation: Any) -> Optional[Type[BaseModel]]:
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return annotation
    return None


def env_overrides(
    model_cls: Type[BaseModel], env: Mapping[str, str], prefix: str = ENV_PREFIX
) -> Dict[str, Any]:
    """Collect raw string overrides for ``model_cls`` fields present in ``env`` (nested dict)."""
    overrides: Dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        env_name = f"{prefix}{name.upper()}"
        sub_model = _nested_model(field.annotation)
        if sub_model is not None:
            nested = env_overrides(sub_model, env, prefix=f"{env_name}_")
            if nested:
                overrides[name] = nested
        elif env_name in env:
            overrides[name] = env[env_name]
    return overrides


def load_settings(
    model_cls: Type[SettingsT],
    yaml_path: Optional[PathLike] = None,
    env: Optional[Mapping[str, str]] = None,
    prefix: str = ENV_PREFIX,
) -> SettingsT:
    """Build validated, immutable settings from YAML + env. Raises ``ConfigError`` on any issue."""
    environ = os.environ if env is None else env
    base = load_yaml(yaml_path) if yaml_path is not None else {}
    merged = deep_merge(base, env_overrides(model_cls, environ, prefix))
    try:
        return model_cls.model_validate(merged)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration for {model_cls.__name__}:\n{exc}") from exc


def require_env(names: Iterable[str], env: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """Return the values of required env vars; fail listing every missing or empty one."""
    environ = os.environ if env is None else env
    wanted = list(names)
    missing = [name for name in wanted if not environ.get(name)]
    if missing:
        raise ConfigError("Missing required environment variables: " + ", ".join(missing))
    return {name: environ[name] for name in wanted}
