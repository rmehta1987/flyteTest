"""Edge-case tests for the shared serialization module.

Covers all five public functions and both deserializer variants explicitly.
Uses only test-local dataclasses — no imports from planner_types, specs, or
types/assets.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.serialization import (
    SerializableMixin,
    _is_optional,
    deserialize_value_coercing,
    deserialize_value_strict,
    serialize_value_full,
    serialize_value_plain,
    serialize_value_with_dicts,
)


# ---------------------------------------------------------------------------
# Test-local dataclasses (no ManifestSerializable / SpecSerializable imports)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Leaf:
    path: Path
    name: str
    count: int | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class WithDict:
    metadata: dict[str, str]
    name: str


@dataclass(frozen=True, slots=True)
class WithNested:
    child: Leaf
    label: str
    opt_child: Leaf | None = None


@dataclass(frozen=True, slots=True)
class WithDictOfLeaves:
    items: dict[str, Leaf]


@dataclass(frozen=True, slots=True)
class HasToDictChild:
    """Non-mixin parent — used to test to_dict() detection."""

    path: Path

    def to_dict(self) -> dict:
        return {"path": str(self.path), "_custom": True}


@dataclass(frozen=True, slots=True)
class ContainsHasToDictChild:
    child: HasToDictChild
    name: str


@dataclass(frozen=True, slots=True)
class PlainMixinType(SerializableMixin):
    """Uses default _serialize_fn/_deserialize_fn (plain/strict)."""

    path: Path
    label: str
    count: int | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DictMixinType(SerializableMixin):
    _serialize_fn = staticmethod(serialize_value_with_dicts)
    _deserialize_fn = staticmethod(deserialize_value_strict)

    metadata: dict[str, str]
    name: str


@dataclass(frozen=True, slots=True)
class CoercingMixinType(SerializableMixin):
    _serialize_fn = staticmethod(serialize_value_full)
    _deserialize_fn = staticmethod(deserialize_value_coercing)

    name: str
    count: int
    flag: bool
    path: Path


# ---------------------------------------------------------------------------
# _is_optional
# ---------------------------------------------------------------------------


class TestIsOptional(unittest.TestCase):
    def test_optional_str(self) -> None:
        self.assertTrue(_is_optional(str | None))

    def test_optional_path(self) -> None:
        self.assertTrue(_is_optional(Path | None))

    def test_optional_int(self) -> None:
        self.assertTrue(_is_optional(Optional[int]))

    def test_non_optional_str(self) -> None:
        self.assertFalse(_is_optional(str))

    def test_non_optional_path(self) -> None:
        self.assertFalse(_is_optional(Path))

    def test_union_without_none_is_not_optional(self) -> None:
        self.assertFalse(_is_optional(int | str))


# ---------------------------------------------------------------------------
# serialize_value_plain
# ---------------------------------------------------------------------------


class TestSerializePlain(unittest.TestCase):
    def test_path_becomes_string(self) -> None:
        self.assertEqual(serialize_value_plain(Path("/data/file.txt")), "/data/file.txt")

    def test_tuple_becomes_list(self) -> None:
        result = serialize_value_plain(("a", "b"))
        self.assertEqual(result, ["a", "b"])
        self.assertIsInstance(result, list)

    def test_tuple_of_paths_serialized(self) -> None:
        result = serialize_value_plain((Path("/a"), Path("/b")))
        self.assertEqual(result, ["/a", "/b"])

    def test_scalar_passthrough(self) -> None:
        self.assertEqual(serialize_value_plain(42), 42)
        self.assertEqual(serialize_value_plain("hello"), "hello")
        self.assertIsNone(serialize_value_plain(None))

    def test_dataclass_serialized_field_by_field(self) -> None:
        leaf = Leaf(path=Path("/x"), name="n", count=3, tags=("t",))
        result = serialize_value_plain(leaf)
        self.assertEqual(result, {"path": "/x", "name": "n", "count": 3, "tags": ["t"]})

    def test_nested_dataclass_serialized_recursively(self) -> None:
        parent = WithNested(child=Leaf(path=Path("/c"), name="child"), label="p")
        result = serialize_value_plain(parent)
        self.assertEqual(result["child"]["path"], "/c")
        self.assertIsNone(result["opt_child"])

    def test_dict_not_recursed(self) -> None:
        """Plain serializer returns dict values as-is — no recursion into dict."""
        path_val = Path("/should/stay")
        d = {"key": path_val}
        result = serialize_value_plain(d)
        # dict is not Path/tuple/dataclass — returned as the same object
        self.assertIs(result["key"], path_val)


# ---------------------------------------------------------------------------
# serialize_value_with_dicts
# ---------------------------------------------------------------------------


class TestSerializeWithDicts(unittest.TestCase):
    def test_dict_keys_become_strings(self) -> None:
        result = serialize_value_with_dicts({1: "val"})
        self.assertIn("1", result)

    def test_dict_values_recursed(self) -> None:
        result = serialize_value_with_dicts({"k": Path("/data/f.txt")})
        self.assertEqual(result, {"k": "/data/f.txt"})

    def test_nested_dict_recursed(self) -> None:
        result = serialize_value_with_dicts({"outer": {"inner": Path("/p")}})
        self.assertEqual(result["outer"]["inner"], "/p")

    def test_path_and_tuple_still_work(self) -> None:
        self.assertEqual(serialize_value_with_dicts(Path("/a")), "/a")
        self.assertEqual(serialize_value_with_dicts(("x", "y")), ["x", "y"])

    def test_dataclass_with_dict_field(self) -> None:
        obj = WithDict(metadata={"k": "v"}, name="n")
        result = serialize_value_with_dicts(obj)
        self.assertEqual(result["metadata"], {"k": "v"})
        self.assertEqual(result["name"], "n")

    def test_dataclass_with_dict_of_leaves(self) -> None:
        obj = WithDictOfLeaves(items={"a": Leaf(path=Path("/leaf"), name="L")})
        result = serialize_value_with_dicts(obj)
        self.assertEqual(result["items"]["a"]["path"], "/leaf")


# ---------------------------------------------------------------------------
# serialize_value_full
# ---------------------------------------------------------------------------


class TestSerializeFull(unittest.TestCase):
    def test_to_dict_fallback_called(self) -> None:
        """serialize_value_full calls to_dict() on dataclasses that have it."""
        obj = HasToDictChild(path=Path("/p"))
        result = serialize_value_full(obj)
        self.assertTrue(result.get("_custom"))
        self.assertEqual(result["path"], "/p")

    def test_no_to_dict_falls_back_to_field_by_field(self) -> None:
        leaf = Leaf(path=Path("/l"), name="x")
        result = serialize_value_full(leaf)
        self.assertEqual(result["path"], "/l")

    def test_nested_to_dict_called_on_child(self) -> None:
        obj = ContainsHasToDictChild(child=HasToDictChild(path=Path("/c")), name="parent")
        result = serialize_value_full(obj)
        self.assertTrue(result["child"].get("_custom"))

    def test_dict_recursion_present(self) -> None:
        result = serialize_value_full({"k": Path("/p")})
        self.assertEqual(result["k"], "/p")

    def test_tuple_and_path(self) -> None:
        self.assertEqual(serialize_value_full(Path("/a")), "/a")
        self.assertEqual(serialize_value_full((Path("/a"),)), ["/a"])


# ---------------------------------------------------------------------------
# deserialize_value_strict
# ---------------------------------------------------------------------------


class TestDeserializeStrict(unittest.TestCase):
    def test_none_passthrough(self) -> None:
        self.assertIsNone(deserialize_value_strict(str, None))
        self.assertIsNone(deserialize_value_strict(Path, None))

    def test_any_passthrough(self) -> None:
        obj = object()
        self.assertIs(deserialize_value_strict(Any, obj), obj)

    def test_path_restored(self) -> None:
        result = deserialize_value_strict(Path, "/data/file.txt")
        self.assertIsInstance(result, Path)
        self.assertEqual(result, Path("/data/file.txt"))

    def test_tuple_restored(self) -> None:
        result = deserialize_value_strict(tuple[str, ...], ["a", "b"])
        self.assertIsInstance(result, tuple)
        self.assertEqual(result, ("a", "b"))

    def test_tuple_of_paths_restored(self) -> None:
        result = deserialize_value_strict(tuple[Path, ...], ["/a", "/b"])
        self.assertEqual(result, (Path("/a"), Path("/b")))
        self.assertIsInstance(result[0], Path)

    def test_dict_restored(self) -> None:
        result = deserialize_value_strict(dict[str, str], {"k": "v"})
        self.assertEqual(result, {"k": "v"})

    def test_dict_with_path_values(self) -> None:
        result = deserialize_value_strict(dict[str, Path], {"k": "/p"})
        self.assertIsInstance(result["k"], Path)

    def test_optional_none_stays_none(self) -> None:
        self.assertIsNone(deserialize_value_strict(str | None, None))

    def test_optional_non_none_unwrapped(self) -> None:
        result = deserialize_value_strict(Path | None, "/data/f.txt")
        self.assertIsInstance(result, Path)
        self.assertEqual(result, Path("/data/f.txt"))

    def test_dataclass_from_dict(self) -> None:
        payload = {"path": "/x", "name": "n", "count": 7, "tags": ["t"]}
        result = deserialize_value_strict(Leaf, payload)
        self.assertIsInstance(result, Leaf)
        self.assertEqual(result.path, Path("/x"))
        self.assertEqual(result.tags, ("t",))

    def test_no_scalar_coercion(self) -> None:
        """strict deserializer does NOT coerce int->str or str->int."""
        # str annotation, int value — returned as-is (not coerced)
        result = deserialize_value_strict(str, 42)
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)

        # int annotation, str value — returned as-is
        result2 = deserialize_value_strict(int, "5")
        self.assertEqual(result2, "5")
        self.assertIsInstance(result2, str)


# ---------------------------------------------------------------------------
# deserialize_value_coercing
# ---------------------------------------------------------------------------


class TestDeserializeCoercing(unittest.TestCase):
    def test_str_coercion(self) -> None:
        result = deserialize_value_coercing(str, 42)
        self.assertEqual(result, "42")
        self.assertIsInstance(result, str)

    def test_int_coercion(self) -> None:
        result = deserialize_value_coercing(int, "5")
        self.assertEqual(result, 5)
        self.assertIsInstance(result, int)

    def test_bool_coercion(self) -> None:
        self.assertTrue(deserialize_value_coercing(bool, 1))
        self.assertFalse(deserialize_value_coercing(bool, 0))

    def test_none_passthrough(self) -> None:
        self.assertIsNone(deserialize_value_coercing(str, None))

    def test_any_passthrough(self) -> None:
        obj = object()
        self.assertIs(deserialize_value_coercing(Any, obj), obj)

    def test_path_restored(self) -> None:
        result = deserialize_value_coercing(Path, "/data/f.txt")
        self.assertIsInstance(result, Path)

    def test_optional_non_none_with_coercion(self) -> None:
        result = deserialize_value_coercing(int | None, "7")
        self.assertEqual(result, 7)
        self.assertIsInstance(result, int)

    def test_tuple_with_coercion(self) -> None:
        result = deserialize_value_coercing(tuple[int, ...], ["1", "2", "3"])
        self.assertEqual(result, (1, 2, 3))

    def test_dict_with_coercion(self) -> None:
        result = deserialize_value_coercing(dict[str, int], {"a": "10"})
        self.assertEqual(result["a"], 10)
        self.assertIsInstance(result["a"], int)

    def test_dataclass_without_from_dict_reconstructed(self) -> None:
        """Coercing deserializer reconstructs plain dataclasses field-by-field."""
        payload = {"path": "/x", "name": "leaf", "count": 3, "tags": ["t"]}
        result = deserialize_value_coercing(Leaf, payload)
        self.assertIsInstance(result, Leaf)
        self.assertEqual(result.path, Path("/x"))


# ---------------------------------------------------------------------------
# SerializableMixin
# ---------------------------------------------------------------------------


class TestSerializableMixin(unittest.TestCase):
    def test_plain_mixin_to_dict(self) -> None:
        obj = PlainMixinType(
            path=Path("/data/f.txt"),
            label="example",
            count=None,
            tags=("a", "b"),
        )
        d = obj.to_dict()
        self.assertEqual(d["path"], "/data/f.txt")
        self.assertIsInstance(d["path"], str)
        self.assertIsNone(d["count"])
        self.assertEqual(d["tags"], ["a", "b"])
        self.assertIsInstance(d["tags"], list)

    def test_plain_mixin_from_dict(self) -> None:
        payload = {"path": "/data/f.txt", "label": "example", "count": None, "tags": ["a", "b"]}
        obj = PlainMixinType.from_dict(payload)
        self.assertIsInstance(obj.path, Path)
        self.assertEqual(obj.path, Path("/data/f.txt"))
        self.assertIsNone(obj.count)
        self.assertIsInstance(obj.tags, tuple)
        self.assertEqual(obj.tags, ("a", "b"))

    def test_plain_mixin_round_trip(self) -> None:
        obj = PlainMixinType(path=Path("/p"), label="L", count=5, tags=("x",))
        restored = PlainMixinType.from_dict(obj.to_dict())
        self.assertEqual(obj.path, restored.path)
        self.assertEqual(obj.label, restored.label)
        self.assertEqual(obj.count, restored.count)
        self.assertEqual(obj.tags, restored.tags)

    def test_dict_mixin_serializes_dicts(self) -> None:
        obj = DictMixinType(metadata={"key": "val"}, name="n")
        d = obj.to_dict()
        self.assertEqual(d["metadata"], {"key": "val"})

    def test_dict_mixin_round_trip(self) -> None:
        obj = DictMixinType(metadata={"k": "v"}, name="n")
        restored = DictMixinType.from_dict(obj.to_dict())
        self.assertEqual(restored.metadata, {"k": "v"})
        self.assertEqual(restored.name, "n")

    def test_coercing_mixin_round_trip(self) -> None:
        obj = CoercingMixinType(name="test", count=42, flag=True, path=Path("/p"))
        restored = CoercingMixinType.from_dict(obj.to_dict())
        self.assertEqual(restored.name, "test")
        self.assertEqual(restored.count, 42)
        self.assertTrue(restored.flag)
        self.assertIsInstance(restored.path, Path)

    def test_from_dict_skips_missing_fields(self) -> None:
        """from_dict tolerates payload missing optional fields."""
        payload = {"path": "/p", "label": "L"}
        obj = PlainMixinType.from_dict(payload)
        self.assertIsNone(obj.count)
        self.assertEqual(obj.tags, ())


if __name__ == "__main__":
    unittest.main()
