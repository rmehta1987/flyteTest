"""Tests for the shared GFF3 helpers and the migrated task-module aliases.

    The 18b slice moved the parsing, formatting, escaping, and attribute lookup
    rules into a shared helper module. These tests keep that mechanical surface
    stable while leaving the EggNOG and repeat-filter biology unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

import flytetest.gff3 as gff3
import flytetest.tasks.eggnog as eggnog
import flytetest.tasks.filtering as filtering


class Gff3HelperTests(TestCase):
    """Coverage for ordered GFF3 parsing, formatting, escaping, and lookup helpers.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_parse_and_format_preserve_order_and_blank_fields(self) -> None:
        """Round-trip ordered attributes while keeping bare keys and empty input stable.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        attributes = gff3.parse_attributes("ID=gene1;Name=alpha;flag;Parent=gene0,gene1")
        self.assertEqual(
            attributes,
            [
                ("ID", "gene1"),
                ("Name", "alpha"),
                ("flag", ""),
                ("Parent", "gene0,gene1"),
            ],
        )
        self.assertEqual(gff3.format_attributes(attributes), "ID=gene1;Name=alpha;flag;Parent=gene0,gene1")
        self.assertEqual(gff3.parse_attributes("."), [])
        self.assertEqual(gff3.format_attributes([]), ".")

    def test_escape_value_encodes_gff3_special_characters(self) -> None:
        """Ensure the shared escape helper preserves the existing GFF3 encoding rules.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        self.assertEqual(
            gff3.escape_value("alpha;beta=gamma&delta,epsilon\tline\ncarriage\rpercent%"),
            "alpha%3Bbeta%3Dgamma%26delta%2Cepsilon%09line%0Acarriage%0Dpercent%25",
        )

    def test_attribute_value_helpers_preserve_first_value_and_parent_splitting(self) -> None:
        """Keep first-match lookups and comma-split ID/Parent value sets deterministic.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        attributes = gff3.parse_attributes("ID=gene1;Parent=tx1,tx2;Parent=tx3;Name=alpha")
        self.assertEqual(gff3.attribute_value(attributes, "ID"), "gene1")
        self.assertEqual(gff3.attribute_value(attributes, "Parent"), "tx1,tx2")
        self.assertEqual(gff3.attribute_values(attributes, "Parent"), ("tx1", "tx2", "tx3"))
        self.assertEqual(gff3.attribute_values(attributes, "ID"), ("gene1",))

    def test_task_module_aliases_point_at_shared_helpers(self) -> None:
        """Confirm the migrated task modules re-export the shared GFF3 helpers.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        self.assertIs(eggnog._parse_gff3_attributes, gff3.parse_attributes)
        self.assertIs(eggnog._format_gff3_attributes, gff3.format_attributes)
        self.assertIs(eggnog._escape_gff3_value, gff3.escape_value)
        self.assertIs(eggnog._attribute_value, gff3.attribute_value)
        self.assertIs(filtering._parse_attributes, gff3.parse_attributes)
        self.assertIs(filtering._attribute_values, gff3.attribute_values)
