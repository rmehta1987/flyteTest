"""Shared serialization primitives and layer-specific wrappers.

Three behavioral layers exist in this project (planner, specs, assets).
Each layer gets a serialize/deserialize pair that preserves its current
round-trip semantics.  This module is independently testable and does not
import from planner_types, specs, or types/assets.

Serialize wrappers:
  serialize_value_plain       -- planner layer (Path, tuple, dataclass)
  serialize_value_with_dicts  -- spec layer (adds dict recursion)
  serialize_value_full        -- asset layer (adds dict + to_dict() fallback)

Deserialize wrappers:
  deserialize_value_strict    -- planner + spec layers (no scalar coercion)
  deserialize_value_coercing  -- asset layer (adds str/int/bool coercion)

Mixin:
  SerializableMixin -- plain class, provides to_dict()/from_dict() via
                       _serialize_fn/_deserialize_fn class attributes.
"""

from __future__ import annotations

import types
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _is_optional(annotation: Any) -> bool:
    origin = get_origin(annotation)
    return origin in (Union, types.UnionType) and type(None) in get_args(annotation)


# ---------------------------------------------------------------------------
# Serialize wrappers
# ---------------------------------------------------------------------------


def _serialize_core(value: Any) -> Any:
    """Path->str, tuple->list, dataclass field-by-field. Planner layer behavior."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_serialize_core(item) for item in value]
    if is_dataclass(value):
        return {f.name: _serialize_core(getattr(value, f.name)) for f in fields(value)}
    return value


serialize_value_plain = _serialize_core


def serialize_value_with_dicts(value: Any) -> Any:
    """Path->str, tuple->list, dict recursion, dataclass. Spec layer behavior."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [serialize_value_with_dicts(item) for item in value]
    if isinstance(value, dict):
        return {str(k): serialize_value_with_dicts(v) for k, v in value.items()}
    if is_dataclass(value):
        return {f.name: serialize_value_with_dicts(getattr(value, f.name)) for f in fields(value)}
    return value


def serialize_value_full(value: Any) -> Any:
    """Path->str, tuple->list, dict recursion, dataclass with to_dict() fallback. Asset layer behavior."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [serialize_value_full(item) for item in value]
    if isinstance(value, dict):
        return {str(k): serialize_value_full(v) for k, v in value.items()}
    if is_dataclass(value):
        if hasattr(value, "to_dict"):
            return value.to_dict()
        return {f.name: serialize_value_full(getattr(value, f.name)) for f in fields(value)}
    return value


# ---------------------------------------------------------------------------
# Deserialize wrappers
# ---------------------------------------------------------------------------


def _deserialize_core(annotation: Any, value: Any) -> Any:
    """None/Any passthrough, Path, tuple, dict, Optional unwrapping, dataclass. No scalar coercion."""
    if value is None:
        return None
    if annotation is Any:
        return value
    if annotation is Path:
        return Path(str(value))

    origin = get_origin(annotation)
    if origin is tuple:
        item_type = get_args(annotation)[0]
        return tuple(_deserialize_core(item_type, item) for item in value)
    if origin is dict:
        key_type, value_type = get_args(annotation)
        return {
            _deserialize_core(key_type, k): _deserialize_core(value_type, v)
            for k, v in value.items()
        }
    if _is_optional(annotation):
        inner = [t for t in get_args(annotation) if t is not type(None)]
        if len(inner) == 1:
            return _deserialize_core(inner[0], value)
    if isinstance(annotation, type) and is_dataclass(annotation):
        if hasattr(annotation, "from_dict"):
            return annotation.from_dict(value)
        hints = get_type_hints(annotation)
        return annotation(
            **{
                f.name: _deserialize_core(hints[f.name], value[f.name])
                for f in fields(annotation)
                if isinstance(value, Mapping) and f.name in value
            }
        )
    return value


deserialize_value_strict = _deserialize_core


def deserialize_value_coercing(annotation: Any, value: Any) -> Any:
    """Adds str/int/bool scalar coercion over strict deserialization. Asset layer behavior."""
    if value is None:
        return None
    if annotation is Any:
        return value
    if annotation is Path:
        return Path(str(value))
    if annotation is str:
        return str(value)
    if annotation is int:
        return int(value)
    if annotation is bool:
        return bool(value)

    origin = get_origin(annotation)
    if origin is tuple:
        item_type = get_args(annotation)[0]
        return tuple(deserialize_value_coercing(item_type, item) for item in value)
    if origin is dict:
        key_type, value_type = get_args(annotation)
        return {
            deserialize_value_coercing(key_type, k): deserialize_value_coercing(value_type, v)
            for k, v in value.items()
        }
    if _is_optional(annotation):
        inner = [t for t in get_args(annotation) if t is not type(None)]
        if len(inner) == 1:
            return deserialize_value_coercing(inner[0], value)
    if isinstance(annotation, type) and is_dataclass(annotation):
        if hasattr(annotation, "from_dict"):
            return annotation.from_dict(value)
        hints = get_type_hints(annotation)
        return annotation(
            **{
                f.name: deserialize_value_coercing(hints[f.name], value[f.name])
                for f in fields(annotation)
                if isinstance(value, Mapping) and f.name in value
            }
        )
    return value


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------


class SerializableMixin:
    """Plain-class mixin that provides to_dict()/from_dict() via class-level function pointers.

    Subclasses set _serialize_fn and _deserialize_fn to the appropriate
    layer wrapper before the dataclass decorator runs:

        class SpecSerializable(SerializableMixin):
            _serialize_fn = staticmethod(serialize_value_with_dicts)
            _deserialize_fn = staticmethod(deserialize_value_strict)

    Compatible with @dataclass(frozen=True, slots=True) consumers.
    """

    _serialize_fn = staticmethod(_serialize_core)
    _deserialize_fn = staticmethod(_deserialize_core)

    def to_dict(self) -> dict:
        return {f.name: self._serialize_fn(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def from_dict(cls, payload: Mapping) -> Any:
        hints = get_type_hints(cls)
        kwargs = {}
        for f in fields(cls):
            if f.name not in payload:
                continue
            kwargs[f.name] = cls._deserialize_fn(hints[f.name], payload[f.name])
        return cls(**kwargs)
