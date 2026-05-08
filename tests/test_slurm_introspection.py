"""Synthetic coverage for read-only Slurm introspection helpers.

Phase 0 step 05 of the Slurm UX rollout.  Mocks ``sinfo`` so the test suite
runs without a live Slurm controller; the parsing and structured-reply
contract are the real targets.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.slurm_introspection import (
    list_slurm_partitions,
    list_slurm_partitions_reply,
)


class ListSlurmPartitionsTests(TestCase):
    """Covers the sinfo-shelling helper and its structured reply wrapper."""

    @patch("flytetest.slurm_introspection.shutil.which", return_value="/usr/bin/sinfo")
    @patch("flytetest.slurm_introspection.subprocess.run")
    def test_parses_typical_sinfo_output(self, mock_run, mock_which) -> None:
        mock_run.return_value = MagicMock(
            stdout=(
                "caslake* up 1-00:00:00 200 50/100/0/200\n"
                "broadwl up 2-00:00:00 100 5/95/0/100\n"
            ),
            stderr="",
            returncode=0,
        )

        result = list_slurm_partitions()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "caslake")  # default-partition * stripped
        self.assertEqual(result[0]["state"], "up")
        self.assertEqual(result[0]["max_walltime"], "1-00:00:00")
        self.assertEqual(result[0]["available_nodes"], 100)  # idle slot of alloc/idle
        self.assertEqual(result[0]["total_nodes"], 200)
        self.assertEqual(result[1]["name"], "broadwl")
        self.assertEqual(result[1]["available_nodes"], 95)

    @patch("flytetest.slurm_introspection.shutil.which", return_value="/usr/bin/sinfo")
    @patch("flytetest.slurm_introspection.subprocess.run")
    def test_skips_blank_and_short_rows(self, mock_run, mock_which) -> None:
        mock_run.return_value = MagicMock(
            stdout=(
                "\n"
                "caslake up 1-00:00:00 100 10/90/0/100\n"
                "incomplete row\n"
            ),
            stderr="",
            returncode=0,
        )

        result = list_slurm_partitions()

        # Only the well-formed row should make it through.
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "caslake")

    @patch("flytetest.slurm_introspection.shutil.which", return_value="/usr/bin/sinfo")
    @patch("flytetest.slurm_introspection.subprocess.run")
    def test_unparseable_node_counts_default_to_zero(self, mock_run, mock_which) -> None:
        mock_run.return_value = MagicMock(
            stdout="caslake up INFINITE many alloc/idle/other/total\n",
            stderr="",
            returncode=0,
        )

        result = list_slurm_partitions()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["max_walltime"], "INFINITE")
        self.assertEqual(result[0]["total_nodes"], 0)
        self.assertEqual(result[0]["available_nodes"], 0)

    @patch("flytetest.slurm_introspection.shutil.which", return_value=None)
    def test_raises_when_sinfo_missing(self, mock_which) -> None:
        with self.assertRaises(FileNotFoundError):
            list_slurm_partitions()


class ListSlurmPartitionsReplyTests(TestCase):
    """Structured-reply wrapper used directly by the MCP tool."""

    @patch("flytetest.slurm_introspection.shutil.which", return_value="/usr/bin/sinfo")
    @patch("flytetest.slurm_introspection.subprocess.run")
    def test_supported_true_on_success(self, mock_run, mock_which) -> None:
        mock_run.return_value = MagicMock(
            stdout="caslake up 1-00:00:00 100 10/90/0/100\n",
            stderr="",
            returncode=0,
        )

        reply = list_slurm_partitions_reply()

        self.assertTrue(reply["supported"])
        self.assertEqual(len(reply["partitions"]), 1)
        self.assertEqual(reply["partitions"][0]["name"], "caslake")

    @patch("flytetest.slurm_introspection.shutil.which", return_value=None)
    def test_supported_false_when_sinfo_missing(self, mock_which) -> None:
        reply = list_slurm_partitions_reply()

        self.assertFalse(reply["supported"])
        self.assertEqual(reply["reason"], "sinfo_unavailable")
        self.assertIn("sinfo", reply["message"])
        self.assertEqual(reply["partitions"], [])

    @patch("flytetest.slurm_introspection.shutil.which", return_value="/usr/bin/sinfo")
    @patch("flytetest.slurm_introspection.subprocess.run")
    def test_supported_false_when_sinfo_fails(self, mock_run, mock_which) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["sinfo"], stderr="sinfo: error: scheduler unavailable\n"
        )

        reply = list_slurm_partitions_reply()

        self.assertFalse(reply["supported"])
        self.assertEqual(reply["reason"], "sinfo_failed")
        self.assertIn("scheduler unavailable", reply["message"])
        self.assertEqual(reply["partitions"], [])
