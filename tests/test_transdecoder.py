"""Tests for PASA-to-TransDecoder discovery and collection boundaries.

    The suite keeps PASA-result discovery and TransDecoder output discovery
    synthetic so these contracts can be validated without external TransDecoder or
    PASA binaries.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flyte.io import Dir

import flytetest.tasks.transdecoder as transdecoder_tasks
import flytetest.workflows.transdecoder as transdecoder_workflow
from flytetest.workflows.transdecoder import transdecoder_from_pasa


def _artifact_dir(path: Path) -> Dir:
    """Create a local Flyte directory wrapper from a filesystem path.

    Args:
        path: A filesystem path used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    return Dir(path=str(path))


def _read_json(path: Path) -> dict[str, object]:
    """Read a JSON payload for assertions.

    Args:
        path: A filesystem path used by the helper.

    Returns:
        The returned `dict[str, object]` value used by the caller.
"""
    return json.loads(path.read_text())


def _fixed_datetime() -> type:
    """Return a deterministic timestamp provider for result-directory naming.

    This helper keeps the test fixture deterministic and explicit.

    Returns:
        The returned type value used by the test fixture.
"""

    # Keep the synthetic result-directory name stable for manifest assertions.
    class _Stamp:
        """Fake datetime stamp that always returns the same test timestamp.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

        def strftime(self, fmt: str) -> str:
            """Return the fixed timestamp string expected by the assertions.

    Args:
        fmt: A value used by the helper.

    Returns:
        The returned `str` value used by the caller.
"""
            return "20260402_150000"

    class _FixedDatetime:
        """Shim object that mimics the subset of `datetime` used by the code.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

        @classmethod
        def now(cls) -> _Stamp:
            """Return the fixed timestamp stub used by the synthetic tests.

    This helper keeps the test fixture deterministic and explicit.

    Returns:
        The returned _Stamp value used by the test fixture.
"""
            return _Stamp()

    return _FixedDatetime


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    """Write a JSON payload with indentation for readable failures.

    Args:
        path: A filesystem path used by the helper.
        payload: The structured payload to serialize or inspect.

    Returns:
        The returned `Path` value used by the caller.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def _write_gff3(path: Path, records: list[str]) -> Path:
    """Write a minimal GFF3 file with a canonical header.

    Args:
        path: A filesystem path used by the helper.
        records: The records written into the synthetic file.

    Returns:
        The returned `Path` value used by the caller.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("##gff-version 3\n" + "\n".join(records) + "\n")
    return path


def _create_sparse_pasa_results(tmp_path: Path) -> Path:
    """Create a PASA bundle that relies on filename discovery instead of manifest outputs.

    Args:
        tmp_path: A filesystem path used by the helper.

    Returns:
        The returned `Path` value used by the caller.
"""
    results_dir = tmp_path / "pasa_results"
    pasa_dir = results_dir / "pasa"
    config_dir = results_dir / "config"
    pasa_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    (config_dir / "test.sqlite").write_text("")
    (pasa_dir / "test.assemblies.fasta").write_text(">tx1\nATGGCC\n")
    _write_gff3(
        pasa_dir / "test.pasa_assemblies.gff3",
        ["chr1\tPASA\ttranscript\t1\t20\t.\t+\t.\tID=pasa_tx1"],
    )
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "pasa_transcript_alignment",
            "sample_id": "sampleA",
            "outputs": {},
        },
    )
    return results_dir


class TransdecoderWorkflowDiscoveryTests(TestCase):
    """Workflow-level coverage for PASA result discovery before TransDecoder runs.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_transdecoder_from_pasa_discovers_pasa_outputs_by_database_stem(self) -> None:
        """Resolve PASA assemblies even when the bundle relies on filename conventions.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pasa_results = _create_sparse_pasa_results(tmp_path)
            calls: list[tuple[str, tuple[str, ...]]] = []

            def fake_train(**kwargs: object) -> Dir:
                """            Capture the TransDecoder training inputs and stage a synthetic run directory.


            Args:
                kwargs: Keyword arguments forwarded to the helper.

            Returns:
                The returned `Dir` value used by the caller.
            """
                calls.append(("train", tuple(sorted(kwargs.keys()))))
                self.assertTrue(str(kwargs["pasa_assemblies_fasta"].path).endswith("test.assemblies.fasta"))
                self.assertTrue(str(kwargs["pasa_assemblies_gff3"].path).endswith("test.pasa_assemblies.gff3"))
                run_dir = tmp_path / "transdecoder_run"
                run_dir.mkdir(parents=True, exist_ok=True)
                return _artifact_dir(run_dir)

            def fake_collect(**kwargs: object) -> Dir:
                """            Capture the TransDecoder collection inputs and stage a synthetic result directory.


            Args:
                kwargs: Keyword arguments forwarded to the helper.

            Returns:
                The returned `Dir` value used by the caller.
            """
                calls.append(("collect", tuple(sorted(kwargs.keys()))))
                self.assertEqual(kwargs["sample_id"], "sampleA")
                results_dir = tmp_path / "transdecoder_results"
                results_dir.mkdir(parents=True, exist_ok=True)
                return _artifact_dir(results_dir)

            with (
                patch.object(transdecoder_workflow, "transdecoder_train_from_pasa", side_effect=fake_train),
                patch.object(transdecoder_workflow, "collect_transdecoder_results", side_effect=fake_collect),
            ):
                transdecoder_from_pasa(
                    pasa_results=_artifact_dir(pasa_results),
                )

            self.assertEqual(calls[0][0], "train")
            self.assertEqual(calls[1][0], "collect")


class TransdecoderCollectionTests(TestCase):
    """Task-level coverage for TransDecoder output discovery and manifest shaping.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_collect_transdecoder_results_discovers_standard_outputs(self) -> None:
        """Collect the standard TransDecoder files when they exist with canonical suffixes.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pasa_results = _create_sparse_pasa_results(tmp_path)
            transcript_name = "test.assemblies.fasta"

            run_dir = tmp_path / "transdecoder_run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / transcript_name).write_text(">tx1\nATGGCC\n")
            (run_dir / f"{transcript_name}.transdecoder.gff3").write_text(
                "##gff-version 3\nchr1\tTransDecoder\tCDS\t1\t6\t.\t+\t0\tID=orf1\n"
            )
            _write_gff3(
                run_dir / f"{transcript_name}.transdecoder.genome.gff3",
                ["chr1\tTransDecoder\tCDS\t1\t6\t.\t+\t0\tID=orf1"],
            )
            (run_dir / f"{transcript_name}.transdecoder.bed").write_text("chr1\t0\t6\torf1\n")
            (run_dir / f"{transcript_name}.transdecoder.cds").write_text(">orf1\nATGGCC\n")
            (run_dir / f"{transcript_name}.transdecoder.pep").write_text(">orf1\nMA\n")
            (run_dir / f"{transcript_name}.transdecoder.mRNA").write_text(">orf1\nAUGGCC\n")
            (run_dir / f"{transcript_name}.transdecoder_dir").mkdir()

            with patch.object(transdecoder_tasks, "datetime", _fixed_datetime()):
                results = transdecoder_tasks.collect_transdecoder_results(
                    pasa_results=_artifact_dir(pasa_results),
                    transdecoder_run=_artifact_dir(run_dir),
                    sample_id="sampleA",
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertTrue((results_dir / "transdecoder" / f"{transcript_name}.transdecoder.genome.gff3").exists())
            self.assertEqual(manifest["stage"], "transdecoder_from_pasa")
            self.assertIn("inputs", manifest)
            self.assertIn("outputs", manifest)
            self.assertIn("assumptions", manifest)
            self.assertEqual(Path(str(manifest["outputs"]["input_transcripts_fasta"])).name, transcript_name)
            self.assertEqual(
                Path(str(manifest["outputs"]["transdecoder_genome_gff3"])).name,
                f"{transcript_name}.transdecoder.genome.gff3",
            )
            self.assertEqual(
                Path(str(manifest["outputs"]["source_pasa_assemblies_gff3"])).name,
                "test.pasa_assemblies.gff3",
            )
            self.assertIn("standard TransDecoder.LongOrfs followed by TransDecoder.Predict", " ".join(manifest["assumptions"]))
