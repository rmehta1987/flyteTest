"""Tests for the PASA post-EVM refinement boundary.

    The suite keeps PASA update staging, round promotion, finalization, and
    collection synthetic so the boundary can be validated without PASA binaries.
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

from flyte.io import Dir, File

import flytetest.tasks.pasa as pasa
import flytetest.workflows.pasa as pasa_workflow
from flytetest.workflows.pasa import annotation_refinement_pasa


def _artifact_dir(path: Path) -> Dir:
    """Wrap a filesystem path in Flyte's `Dir` type for synthetic fixtures."""
    return Dir(path=str(path))


def _read_json(path: Path) -> dict[str, object]:
    """Load a JSON manifest into a dictionary for assertions."""
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    """Write a JSON payload with indentation for readable failures."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def _write_gff3(path: Path, records: list[str]) -> Path:
    """Write a minimal GFF3 file with a canonical header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("##gff-version 3\n" + "\n".join(records) + "\n")
    return path


def _fixed_datetime() -> type:
    """Return a deterministic timestamp provider for result-directory naming."""

    # Keep the synthetic result-directory name stable for manifest assertions.
    class _Stamp:
        """Datetime stub that always returns the same synthetic timestamp."""

        def strftime(self, fmt: str) -> str:
            """Return the fixed timestamp string expected by the assertions."""
            return "20260402_120000"

    class _FixedDatetime:
        """Shim that exposes the `datetime.now()` call used by the code."""

        @classmethod
        def now(cls) -> _Stamp:
            """Return the fixed timestamp stub used by the synthetic tests."""
            return _Stamp()

    return _FixedDatetime


def _create_pasa_results(tmp_path: Path) -> Path:
    """Create a minimal PASA bundle with the fields the update path consumes."""
    results_dir = tmp_path / "pasa_results"
    seqclean_dir = results_dir / "seqclean"
    config_dir = results_dir / "config"
    pasa_dir = results_dir / "pasa"
    seqclean_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    pasa_dir.mkdir(parents=True, exist_ok=True)

    clean_fasta = seqclean_dir / "trinity_transcripts.fa.clean"
    clean_fasta.write_text(">tx1\nATGGCC\n")
    align_config = config_dir / "pasa.alignAssembly.config"
    align_config.write_text("DATABASE=/tmp/original.sqlite\nOTHER=1\n")
    sqlite_database = config_dir / "test.sqlite"
    sqlite_database.write_text("")
    _write_gff3(
        pasa_dir / "test.sqlite.pasa_assemblies.gff3",
        ["chr1\tPASA\ttranscript\t1\t20\t.\t+\t.\tID=pasa_tx1"],
    )
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "pasa_transcript_alignment",
            "outputs": {
                "seqclean_clean_fasta": str(clean_fasta),
                "pasa_config": str(align_config),
                "sqlite_database": str(sqlite_database),
            },
        },
    )
    return results_dir


def _create_evm_results(tmp_path: Path) -> Path:
    """Create a minimal EVM bundle with the fields the update path consumes."""
    results_dir = tmp_path / "evm_results"
    execution_dir = results_dir / "evm_execution_inputs"
    execution_dir.mkdir(parents=True, exist_ok=True)

    genome_fasta = execution_dir / "genome.fa"
    genome_fasta.write_text(">chr1\nACGTACGTACGT\n")
    sorted_gff3 = _write_gff3(
        results_dir / "EVM.all.sort.gff3",
        ["chr1\tEVM\tgene\t10\t20\t.\t+\t.\tID=evm_gene1"],
    )
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "consensus_annotation_evm",
            "outputs": {
                "sorted_gff3": str(sorted_gff3),
            },
        },
    )
    return results_dir


class PasaUpdateTaskTests(TestCase):
    """Task-level coverage for the PASA post-EVM boundary.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_prepare_pasa_update_inputs_stages_existing_pasa_and_evm_bundles(self) -> None:
        """Stage the PASA database state and sorted EVM GFF3 without rebuilding upstream evidence.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pasa_results = _create_pasa_results(tmp_path)
            evm_results = _create_evm_results(tmp_path)
            annot_template = tmp_path / "pasa.annotCompare.TEMPLATE.txt"
            annot_template.write_text("DATABASE=/tmp/placeholder.sqlite\nANNOTATE=1\n")
            fasta36_binary = tmp_path / "fasta36"
            fasta36_binary.write_text("#!/bin/sh\n")

            prepared = pasa.prepare_pasa_update_inputs(
                pasa_results=_artifact_dir(pasa_results),
                evm_results=_artifact_dir(evm_results),
                pasa_annot_compare_template=File(path=str(annot_template)),
                fasta36_binary_path=str(fasta36_binary),
            )

            prepared_dir = Path(prepared.download_sync())
            manifest = _read_json(prepared_dir / "run_manifest.json")

            self.assertTrue((prepared_dir / "config" / "pasa.alignAssembly.config").exists())
            self.assertTrue((prepared_dir / "config" / "pasa.annotCompare.config").exists())
            self.assertTrue((prepared_dir / "annotations" / "current_annotations.gff3").exists())
            self.assertTrue((prepared_dir / "reference" / "genome.fa").exists())
            self.assertTrue((prepared_dir / "bin" / "fasta").is_symlink())
            self.assertIn("DATABASE=", (prepared_dir / "config" / "pasa.annotCompare.config").read_text())
            self.assertEqual(
                (prepared_dir / "annotations" / "current_annotations.gff3").read_text(),
                (evm_results / "EVM.all.sort.gff3").read_text(),
            )
            self.assertEqual(
                Path(str(manifest["outputs"]["sqlite_database"])).name,
                "test.sqlite",
            )

    def test_pasa_update_gene_models_promotes_new_round_output_to_current_annotations(self) -> None:
        """Promote the new PASA round output to the canonical current annotations path.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pasa_results = _create_pasa_results(tmp_path)
            evm_results = _create_evm_results(tmp_path)
            annot_template = tmp_path / "pasa.annotCompare.TEMPLATE.txt"
            annot_template.write_text("DATABASE=/tmp/placeholder.sqlite\n")

            prepared = pasa.prepare_pasa_update_inputs(
                pasa_results=_artifact_dir(pasa_results),
                evm_results=_artifact_dir(evm_results),
                pasa_annot_compare_template=File(path=str(annot_template)),
            )

            with patch.object(pasa, "run_tool", side_effect=lambda *args, **kwargs: None):
                loaded = pasa.pasa_load_current_annotations(
                    pasa_update_inputs=prepared,
                    round_index=1,
                )

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                """Stage the synthetic PASA update output for the promotion test."""
                self.assertIsNotNone(cwd)
                _write_gff3(
                    cwd / "test.sqlite.gene_structures_post_PASA_updates.1001.gff3",
                    ["chr1\tPASA\tgene\t30\t50\t.\t+\t.\tID=post_pasa_gene1"],
                )
                (cwd / "test.sqlite.gene_structures_post_PASA_updates.1001.bed").write_text(
                    "chr1\t29\t50\tpost_pasa_gene1\n"
                )

            with patch.object(pasa, "run_tool", side_effect=fake_run_tool):
                updated = pasa.pasa_update_gene_models(
                    loaded_pasa_update=loaded,
                    round_index=1,
                )

            updated_dir = Path(updated.download_sync())
            manifest = _read_json(updated_dir / "run_manifest.json")
            self.assertTrue((updated_dir / "annotations" / "current_annotations.gff3").exists())
            self.assertIn("post_pasa_gene1", (updated_dir / "annotations" / "current_annotations.gff3").read_text())
            self.assertEqual(manifest["relative_outputs"]["updated_gff3"], "test.sqlite.gene_structures_post_PASA_updates.1001.gff3")

    def test_annotation_refinement_pasa_collects_stable_final_outputs(self) -> None:
        """Run the synthetic workflow and collect stable post-PASA final filenames.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pasa_results = _create_pasa_results(tmp_path)
            evm_results = _create_evm_results(tmp_path)
            annot_template = tmp_path / "pasa.annotCompare.TEMPLATE.txt"
            annot_template.write_text("DATABASE=/tmp/placeholder.sqlite\n")
            update_counter = {"value": 0}

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                """Stage the synthetic PASA update output for the workflow collection test."""
                self.assertIsNotNone(cwd)
                script_name = cmd[1]
                if script_name == "Launch_PASA_pipeline.pl":
                    update_counter["value"] += 1
                    pid = 1000 + update_counter["value"]
                    _write_gff3(
                        cwd / f"test.sqlite.gene_structures_post_PASA_updates.{pid}.gff3",
                        [f"chr1\tPASA\tgene\t{20 + pid}\t{30 + pid}\t.\t+\t.\tID=round_{update_counter['value']}"],
                    )
                    (cwd / f"test.sqlite.gene_structures_post_PASA_updates.{pid}.bed").write_text(
                        f"chr1\t{19 + pid}\t{30 + pid}\tround_{update_counter['value']}\n"
                    )
                if script_name == "gff3sort.pl" and stdout_path is not None:
                    stdout_path.write_text(Path(cmd[-1]).read_text())

            with (
                patch.object(pasa, "run_tool", side_effect=fake_run_tool),
                patch.object(pasa, "datetime", _fixed_datetime()),
            ):
                results = annotation_refinement_pasa(
                    pasa_results=_artifact_dir(pasa_results),
                    evm_results=_artifact_dir(evm_results),
                    pasa_annot_compare_template=File(path=str(annot_template)),
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertTrue((results_dir / "post_pasa_updates.gff3").exists())
            self.assertTrue((results_dir / "post_pasa_updates.removed.gff3").exists())
            self.assertTrue((results_dir / "post_pasa_updates.sort.gff3").exists())
            self.assertEqual(
                sorted(path.name for path in (results_dir / "source_manifests").glob("*.json")),
                ["evm.run_manifest.json", "pasa.run_manifest.json"],
            )
            self.assertEqual(
                sorted(manifest["outputs"].keys()),
                ["final_removed_gff3", "final_sorted_gff3", "final_updated_gff3"],
            )
            self.assertTrue((results_dir / "staged_inputs" / "config" / "test.sqlite").exists())
            self.assertTrue((results_dir / "load_rounds" / "round_02" / "config" / "test.sqlite").exists())
            self.assertTrue((results_dir / "update_rounds" / "round_02" / "config" / "test.sqlite").exists())
            self.assertIn(
                "round_1",
                (results_dir / "load_rounds" / "round_02" / "annotations" / "current_annotations.gff3").read_text(),
            )
            self.assertIn(
                "round_1",
                (results_dir / "update_rounds" / "round_02" / "annotations" / "loaded_annotations.round_02.gff3").read_text(),
            )
            self.assertEqual(len(manifest["load_round_manifests"]), 2)
            self.assertEqual(len(manifest["update_round_manifests"]), 2)


class PasaUpdateWorkflowTests(TestCase):
    """Workflow-level coverage for the PASA post-EVM entrypoint contract.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_annotation_refinement_pasa_requires_at_least_two_rounds(self) -> None:
        """Reject round counts below the current PASA refinement contract minimum of two.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pasa_results = _create_pasa_results(tmp_path)
            evm_results = _create_evm_results(tmp_path)
            annot_template = tmp_path / "pasa.annotCompare.TEMPLATE.txt"
            annot_template.write_text("DATABASE=/tmp/placeholder.sqlite\n")

            with self.assertRaisesRegex(ValueError, "at least two PASA update rounds"):
                annotation_refinement_pasa(
                    pasa_results=_artifact_dir(pasa_results),
                    evm_results=_artifact_dir(evm_results),
                    pasa_annot_compare_template=File(path=str(annot_template)),
                    pasa_update_rounds=1,
                )

    def test_annotation_refinement_pasa_consumes_pasa_and_evm_bundles_only(self) -> None:
        """Use PASA and EVM bundles as the sole workflow-level biological inputs.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pasa_results = _create_pasa_results(tmp_path)
            evm_results = _create_evm_results(tmp_path)
            annot_template = tmp_path / "pasa.annotCompare.TEMPLATE.txt"
            annot_template.write_text("DATABASE=/tmp/placeholder.sqlite\n")
            calls: list[tuple[str, tuple[str, ...]]] = []

            def fake_prepare(**kwargs: object) -> Dir:
                """Record the PASA prepare inputs and return a synthetic staging directory."""
                calls.append(("prepare", tuple(sorted(kwargs.keys()))))
                prepared_dir = tmp_path / "prepared"
                prepared_dir.mkdir(parents=True, exist_ok=True)
                return _artifact_dir(prepared_dir)

            def fake_load(**kwargs: object) -> Dir:
                """Record the PASA load inputs and return a synthetic load-round directory."""
                calls.append(("load", tuple(sorted(kwargs.keys()))))
                load_dir = tmp_path / f"load_{len([item for item in calls if item[0] == 'load'])}"
                load_dir.mkdir(parents=True, exist_ok=True)
                return _artifact_dir(load_dir)

            def fake_update(**kwargs: object) -> Dir:
                """Record the PASA update inputs and return a synthetic update-round directory."""
                calls.append(("update", tuple(sorted(kwargs.keys()))))
                update_dir = tmp_path / f"update_{len([item for item in calls if item[0] == 'update'])}"
                update_dir.mkdir(parents=True, exist_ok=True)
                return _artifact_dir(update_dir)

            def fake_finalize(**kwargs: object) -> Dir:
                """Record the PASA finalize inputs and return a synthetic finalized directory."""
                calls.append(("finalize", tuple(sorted(kwargs.keys()))))
                finalized_dir = tmp_path / "finalized"
                finalized_dir.mkdir(parents=True, exist_ok=True)
                return _artifact_dir(finalized_dir)

            def fake_collect(**kwargs: object) -> Dir:
                """Record the PASA collect inputs and return a synthetic results directory."""
                calls.append(("collect", tuple(sorted(kwargs.keys()))))
                results_dir = tmp_path / "results"
                results_dir.mkdir(parents=True, exist_ok=True)
                return _artifact_dir(results_dir)

            with (
                patch.object(pasa_workflow, "prepare_pasa_update_inputs", side_effect=fake_prepare),
                patch.object(pasa_workflow, "pasa_load_current_annotations", side_effect=fake_load),
                patch.object(pasa_workflow, "pasa_update_gene_models", side_effect=fake_update),
                patch.object(pasa_workflow, "finalize_pasa_update_outputs", side_effect=fake_finalize),
                patch.object(pasa_workflow, "collect_pasa_update_results", side_effect=fake_collect),
            ):
                annotation_refinement_pasa(
                    pasa_results=_artifact_dir(pasa_results),
                    evm_results=_artifact_dir(evm_results),
                    pasa_annot_compare_template=File(path=str(annot_template)),
                )

            self.assertEqual(calls[0][0], "prepare")
            self.assertEqual(calls[-1][0], "collect")
            all_keys = {key for _, keys in calls for key in keys}
            self.assertIn("pasa_results", all_keys)
            self.assertIn("evm_results", all_keys)
            self.assertNotIn("transcript_evidence_results", all_keys)
            self.assertNotIn("protein_evidence_results", all_keys)


class AnnotationRefinementResultBundleTests(TestCase):
    """Tests for the biology-facing AnnotationRefinementResultBundle generic sibling type."""

    def test_collect_pasa_update_results_emits_generic_annotation_refinement_bundle_key(self):
        """New manifests must include the generic 'annotation_refinement_bundle' asset key."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = self._run_collect(tmp_path)
            self.assertIn("annotation_refinement_bundle", manifest["assets"])

    def test_collect_pasa_update_results_still_emits_legacy_pasa_gene_model_update_bundle_key(self):
        """Legacy 'pasa_gene_model_update_bundle' asset key must remain for historical replay."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = self._run_collect(tmp_path)
            self.assertIn("pasa_gene_model_update_bundle", manifest["assets"])

    def _run_collect(self, tmp_path: Path) -> dict:
        """Run collect_pasa_update_results with a minimal synthetic fixture and return the manifest."""
        pasa_results = _create_pasa_results(tmp_path)
        evm_results = _create_evm_results(tmp_path)

        staged_inputs_dir = tmp_path / "staged_inputs"
        staged_inputs_dir.mkdir(parents=True, exist_ok=True)
        (staged_inputs_dir / "reference").mkdir()
        (staged_inputs_dir / "reference" / "genome.fa").write_text(">chr1\nACGT\n")
        (staged_inputs_dir / "transcripts").mkdir()
        (staged_inputs_dir / "transcripts" / "transcripts.fa.clean").write_text(">tx1\nATGGCC\n")
        (staged_inputs_dir / "config").mkdir()
        (staged_inputs_dir / "config" / "pasa.alignAssembly.config").write_text(
            "DATABASE=/tmp/test.sqlite\n"
        )
        (staged_inputs_dir / "config" / "pasa.annotCompare.config").write_text(
            "DATABASE=/tmp/test.sqlite\n"
        )
        (staged_inputs_dir / "config" / "test.sqlite").write_text("")
        (staged_inputs_dir / "annotations").mkdir()
        (staged_inputs_dir / "annotations" / "current_annotations.gff3").write_text("##gff-version 3\n")
        _write_json(staged_inputs_dir / "run_manifest.json", {"stage": "pasa_update_inputs"})

        load_dir = tmp_path / "load_round_01"
        load_dir.mkdir(parents=True, exist_ok=True)
        _write_json(load_dir / "run_manifest.json", {"stage": "load", "round_index": 1})

        update_dir = tmp_path / "update_round_01"
        update_dir.mkdir(parents=True, exist_ok=True)
        updated_gff = update_dir / "updated.gff3"
        updated_gff.write_text("##gff-version 3\n")
        loaded_snap = update_dir / "loaded_annotations_snapshot.gff3"
        loaded_snap.write_text("##gff-version 3\n")
        current_annot = update_dir / "current_annotations.gff3"
        current_annot.write_text("##gff-version 3\n")
        _write_json(
            update_dir / "run_manifest.json",
            {
                "stage": "pasa_update_gene_models",
                "round_index": 1,
                "relative_outputs": {
                    "loaded_annotations_snapshot": "loaded_annotations_snapshot.gff3",
                    "updated_gff3": "updated.gff3",
                    "current_annotations_gff3": "current_annotations.gff3",
                },
            },
        )

        finalized_dir = tmp_path / "finalized"
        finalized_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "post_pasa_updates.gff3",
            "post_pasa_updates.removed.gff3",
            "post_pasa_updates.sort.gff3",
        ):
            (finalized_dir / name).write_text("##gff-version 3\n")
        _write_json(finalized_dir / "run_manifest.json", {"stage": "finalize_pasa_update_outputs"})

        with patch.object(pasa, "RESULTS_ROOT", str(tmp_path / "results")):
            with patch.object(pasa, "datetime", _fixed_datetime()):
                bundle = pasa.collect_pasa_update_results(
                    pasa_results=_artifact_dir(pasa_results),
                    evm_results=_artifact_dir(evm_results),
                    pasa_update_inputs=_artifact_dir(staged_inputs_dir),
                    load_rounds=[_artifact_dir(load_dir)],
                    update_rounds=[_artifact_dir(update_dir)],
                    finalized_outputs=_artifact_dir(finalized_dir),
                )
        return _read_json(Path(bundle.download_sync()) / "run_manifest.json")
