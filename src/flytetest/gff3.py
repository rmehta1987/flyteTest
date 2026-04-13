"""Shared GFF3 helpers for ordered parsing, formatting, and attribute lookups.

This module keeps the current repo contract explicit and reviewable.
"""

from __future__ import annotations

from collections.abc import Sequence


def escape_value(value: str) -> str:
    """Escape one GFF3 attribute value deterministically."""
    return (
        value.replace("%", "%25")
        .replace(";", "%3B")
        .replace("=", "%3D")
        .replace("&", "%26")
        .replace(",", "%2C")
        .replace("\t", "%09")
        .replace("\n", "%0A")
        .replace("\r", "%0D")
    )


def parse_attributes(attribute_text: str) -> list[tuple[str, str]]:
    """Parse one GFF3 attribute column into an ordered list of pairs.

    Args:
        attribute_text: Raw ninth-column text from a GFF3 record.

    Returns:
        Ordered attribute key/value pairs, or an empty list for `.` and blank
        columns.
    """
    if not attribute_text or attribute_text == ".":
        return []
    parsed: list[tuple[str, str]] = []
    for item in attribute_text.split(";"):
        if not item:
            continue
        if "=" in item:
            key, value = item.split("=", 1)
        else:
            key, value = item, ""
        parsed.append((key, value))
    return parsed


def format_attributes(attributes: Sequence[tuple[str, str]]) -> str:
    """Format ordered GFF3 attribute pairs back into a column string.

    Args:
        attributes: Ordered attribute pairs to serialize.

    Returns:
        A GFF3 attribute column string, or `.` when no attributes are present.
    """
    if not attributes:
        return "."
    return ";".join(f"{key}={value}" if value else key for key, value in attributes)


def attribute_value(attributes: Sequence[tuple[str, str]], key: str) -> str | None:
    """Return the first matching value for one attribute key.

    Args:
        attributes: Ordered attribute pairs to search.
        key: Attribute key to look up.

    Returns:
        The first matching value, or `None` when the key is absent.
    """
    for current_key, current_value in attributes:
        if current_key == key:
            return current_value
    return None


def attribute_values(attributes: Sequence[tuple[str, str]], key: str) -> tuple[str, ...]:
    """Return all comma-split values for one attribute key in order.

    Args:
        attributes: Ordered attribute pairs to search.
        key: Attribute key to collect.

    Returns:
        All non-empty comma-separated values for the key, in encounter order.
    """
    values: list[str] = []
    for current_key, current_value in attributes:
        if current_key != key:
            continue
        values.extend(part for part in current_value.split(",") if part)
    return tuple(values)
