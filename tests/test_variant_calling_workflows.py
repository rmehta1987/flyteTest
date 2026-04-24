"""Tests for the GATK4 variant calling workflow compositions (Milestone B → I)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flyte.io import File

import flytetest.workflows.variant_calling as variant_calling_wf
from flytetest.workflows.variant_calling import (
    MANIFEST_OUTPUT_KEYS,
    annotate_variants_snpeff,
    germline_short_variant_discovery,
    post_call_qc_summary,
    post_genotyping_refinement,
    pre_call_coverage_qc,
    prepare_reference,
    preprocess_sample,
    preprocess_sample_from_ubam,
    sequential_interval_haplotype_caller,
    small_cohort_filter,
)


def _fake_file(path: str) -> File:
    f = MagicMock(spec=File)
    f.path = path
    f.download_sync = MagicMock(return_value=path)
    return f


class PrepareReferenceRegistryTests(TestCase):
    """Guard the prepare_reference registry entry shape."""

    def test_prepare_reference_registry_entry_shape(self) -> None:
        """Entry exists with category=workflow and stage_order=1."""
        from flytetest.registry import get_entry

        entry = get_entry("prepare_reference")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 1)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("prepared_ref", output_names)
        self.assertIn("prepared_ref", MANIFEST_OUTPUT_KEYS)


class PrepareReferenceInvocationTests(TestCase):
    """Verify prepare_reference calls sub-tasks in the correct order."""

    def _run_prepare_reference(self, ref_fasta, known_site_files):
        fake_result = _fake_file(str(ref_fasta))

        def fake_create_seq_dict(reference_fasta, gatk_sif=""):
            return fake_result

        def fake_index_feature(vcf, gatk_sif=""):
            return fake_result

        def fake_bwa_index(reference_fasta, bwa_sif=""):
            return MagicMock(path=str(ref_fasta))

        with (
            patch.object(variant_calling_wf, "create_sequence_dictionary", side_effect=fake_create_seq_dict) as mock_csd,
            patch.object(variant_calling_wf, "index_feature_file", side_effect=fake_index_feature) as mock_iff,
            patch.object(variant_calling_wf, "bwa_mem2_index", side_effect=fake_bwa_index) as mock_bwa,
        ):
            result = prepare_reference(
                reference_fasta=File(path=str(ref_fasta)),
                known_sites=known_site_files,
            )
            return result, mock_csd, mock_iff, mock_bwa

    def test_sub_tasks_called_in_order(self) -> None:
        """create_sequence_dictionary, index_feature_file, then bwa_mem2_index."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")
            known_sites = [File(path=str(tmp_path / "dbsnp.vcf")),
                           File(path=str(tmp_path / "mills.vcf"))]

            result, mock_csd, mock_iff, mock_bwa = self._run_prepare_reference(
                ref_fasta, known_sites
            )

        mock_csd.assert_called_once()
        mock_bwa.assert_called_once()
        self.assertEqual(mock_iff.call_count, 2)

    def test_index_feature_file_called_per_known_site(self) -> None:
        """index_feature_file is called once per entry in known_sites."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")
            known_sites = [
                File(path=str(tmp_path / "dbsnp.vcf")),
                File(path=str(tmp_path / "mills.vcf")),
                File(path=str(tmp_path / "hapmap.vcf")),
            ]

            _, _, mock_iff, _ = self._run_prepare_reference(ref_fasta, known_sites)

        self.assertEqual(mock_iff.call_count, 3)


class PrepareReferenceManifestTests(TestCase):
    """Verify prepare_reference emits a well-formed run_manifest.json."""

    def test_prepare_reference_emits_prepared_ref_manifest(self) -> None:
        """Manifest contains prepared_ref pointing at the reference path."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")

            captured_manifests: list[dict] = []

            def capture_write_json(path, data):
                captured_manifests.append(data)

            with (
                patch.object(variant_calling_wf, "create_sequence_dictionary", return_value=_fake_file(str(ref_fasta))),
                patch.object(variant_calling_wf, "index_feature_file", return_value=_fake_file(str(ref_fasta))),
                patch.object(variant_calling_wf, "bwa_mem2_index", return_value=MagicMock(path=str(ref_fasta))),
                patch.object(variant_calling_wf, "_write_json", side_effect=capture_write_json),
            ):
                result = prepare_reference(
                    reference_fasta=File(path=str(ref_fasta)),
                    known_sites=[],
                )

        self.assertIsNotNone(result)
        self.assertEqual(result.path, str(ref_fasta))
        self.assertTrue(any(m.get("stage") == "prepare_reference" for m in captured_manifests))
        prep_manifest = next(m for m in captured_manifests if m.get("stage") == "prepare_reference")
        self.assertIn("prepared_ref", prep_manifest["outputs"])


# ---------------------------------------------------------------------------
# preprocess_sample
# ---------------------------------------------------------------------------

class PreprocessSampleRegistryTests(TestCase):
    """Guard the preprocess_sample registry entry shape."""

    def test_preprocess_sample_registry_entry_shape(self) -> None:
        """Entry exists with category=workflow, stage_order=2."""
        from flytetest.registry import get_entry

        entry = get_entry("preprocess_sample")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 2)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("preprocessed_bam", output_names)
        self.assertIn("preprocessed_bam", MANIFEST_OUTPUT_KEYS)


class PreprocessSampleInvocationTests(TestCase):
    """Verify preprocess_sample calls sub-tasks in order."""

    def test_sub_tasks_called_in_order(self) -> None:
        """bwa_mem2_mem → sort_sam → mark_duplicates → base_recalibrator → apply_bqsr."""
        call_order: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")
            r1 = tmp_path / "r1.fq.gz"
            r1.write_text("@r\n")

            def fake_bwa_mem(**kw):
                call_order.append("bwa_mem2_mem")
                return _fake_file("/tmp/s1_aligned.bam")

            def fake_sort(**kw):
                call_order.append("sort_sam")
                return _fake_file("/tmp/s1_sorted.bam")

            def fake_dedup(**kw):
                call_order.append("mark_duplicates")
                return (_fake_file("/tmp/s1_dedup.bam"), _fake_file("/tmp/s1_metrics.txt"))

            def fake_bqsr(**kw):
                call_order.append("base_recalibrator")
                return _fake_file("/tmp/s1_bqsr.table")

            def fake_apply(**kw):
                call_order.append("apply_bqsr")
                return _fake_file("/tmp/s1_recal.bam")

            with (
                patch.object(variant_calling_wf, "bwa_mem2_mem", side_effect=fake_bwa_mem),
                patch.object(variant_calling_wf, "sort_sam", side_effect=fake_sort),
                patch.object(variant_calling_wf, "mark_duplicates", side_effect=fake_dedup),
                patch.object(variant_calling_wf, "base_recalibrator", side_effect=fake_bqsr),
                patch.object(variant_calling_wf, "apply_bqsr", side_effect=fake_apply),
            ):
                preprocess_sample(
                    reference_fasta=File(path=str(ref_fasta)),
                    r1=File(path=str(r1)),
                    sample_id="s1",
                    known_sites=[File(path="/tmp/dbsnp.vcf")],
                )

        self.assertEqual(
            call_order,
            ["bwa_mem2_mem", "sort_sam", "mark_duplicates", "base_recalibrator", "apply_bqsr"],
        )


class PreprocessSampleManifestTests(TestCase):
    """Verify preprocess_sample returns a File and writes a manifest."""

    def test_preprocess_sample_returns_file(self) -> None:
        """Return value is a File pointing at the recalibrated BAM."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_fasta = tmp_path / "genome.fa"
            ref_fasta.write_text(">chr1\nACGT\n")
            r1 = tmp_path / "r1.fq.gz"
            r1.write_text("@r\n")

            with (
                patch.object(variant_calling_wf, "bwa_mem2_mem", return_value=_fake_file("/tmp/a.bam")),
                patch.object(variant_calling_wf, "sort_sam", return_value=_fake_file("/tmp/s.bam")),
                patch.object(variant_calling_wf, "mark_duplicates", return_value=(_fake_file("/tmp/d.bam"), _fake_file("/tmp/m.txt"))),
                patch.object(variant_calling_wf, "base_recalibrator", return_value=_fake_file("/tmp/bqsr.table")),
                patch.object(variant_calling_wf, "apply_bqsr", return_value=_fake_file("/tmp/s1_recal.bam")),
            ):
                result = preprocess_sample(
                    reference_fasta=File(path=str(ref_fasta)),
                    r1=File(path=str(r1)),
                    sample_id="s1",
                    known_sites=[File(path="/tmp/dbsnp.vcf")],
                )

        self.assertEqual(result.path, "/tmp/s1_recal.bam")


# ---------------------------------------------------------------------------
# germline_short_variant_discovery
# ---------------------------------------------------------------------------

class GermlineShortVariantDiscoveryRegistryTests(TestCase):
    """Guard the germline_short_variant_discovery registry entry shape."""

    def test_germline_short_variant_discovery_registry_entry_shape(self) -> None:
        """Entry exists with category=workflow, stage_order=3."""
        from flytetest.registry import get_entry

        entry = get_entry("germline_short_variant_discovery")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 3)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("genotyped_vcf", output_names)
        self.assertIn("genotyped_vcf", MANIFEST_OUTPUT_KEYS)


class GermlineShortVariantDiscoveryInvocationTests(TestCase):
    """Verify germline_short_variant_discovery validation and call counts."""

    def test_raises_on_sample_ids_r1_paths_length_mismatch(self) -> None:
        """ValueError when sample_ids and r1_paths differ in length."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                germline_short_variant_discovery(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    sample_ids=["s1", "s2"],
                    r1_paths=[File(path="/tmp/r1.fq.gz")],
                    known_sites=[File(path="/tmp/dbsnp.vcf")],
                    intervals=["chr20"],
                )

    def test_raises_on_r2_paths_length_mismatch(self) -> None:
        """ValueError when r2_paths is provided but length mismatches sample_ids."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                germline_short_variant_discovery(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    sample_ids=["s1", "s2"],
                    r1_paths=[File(path="/tmp/r1a.fq.gz"), File(path="/tmp/r1b.fq.gz")],
                    known_sites=[File(path="/tmp/dbsnp.vcf")],
                    intervals=["chr20"],
                    r2_paths=[File(path="/tmp/r2a.fq.gz")],
                )

    def test_per_sample_and_cohort_call_counts(self) -> None:
        """preprocess_sample and haplotype_caller called once per sample; combine/joint once."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_vcf = _fake_file("/tmp/cohort.vcf")

            def fake_preprocess(**kw):
                return _fake_file(f"/tmp/{kw['sample_id']}.bam")

            def fake_hc(**kw):
                return _fake_file(f"/tmp/{kw['sample_id']}.g.vcf")

            with (
                patch.object(variant_calling_wf, "preprocess_sample", side_effect=fake_preprocess) as mock_pp,
                patch.object(variant_calling_wf, "haplotype_caller", side_effect=fake_hc) as mock_hc,
                patch.object(variant_calling_wf, "combine_gvcfs", return_value=fake_vcf) as mock_cg,
                patch.object(variant_calling_wf, "joint_call_gvcfs", return_value=fake_vcf) as mock_jc,
            ):
                germline_short_variant_discovery(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    sample_ids=["s1", "s2"],
                    r1_paths=[File(path="/tmp/r1a.fq.gz"), File(path="/tmp/r1b.fq.gz")],
                    known_sites=[File(path="/tmp/dbsnp.vcf")],
                    intervals=["chr20"],
                )

        self.assertEqual(mock_pp.call_count, 2)
        self.assertEqual(mock_hc.call_count, 2)
        mock_cg.assert_called_once()
        mock_jc.assert_called_once()


class GermlineShortVariantDiscoveryManifestTests(TestCase):
    """Verify germline_short_variant_discovery returns the joint VCF File."""

    def test_returns_joint_vcf_file(self) -> None:
        """Return value is the File from joint_call_gvcfs."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_vcf = _fake_file("/tmp/cohort_genotyped.vcf")

            with (
                patch.object(variant_calling_wf, "preprocess_sample", return_value=_fake_file("/tmp/s1.bam")),
                patch.object(variant_calling_wf, "haplotype_caller", return_value=_fake_file("/tmp/s1.g.vcf")),
                patch.object(variant_calling_wf, "combine_gvcfs", return_value=fake_vcf),
                patch.object(variant_calling_wf, "joint_call_gvcfs", return_value=fake_vcf),
            ):
                result = germline_short_variant_discovery(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    sample_ids=["s1"],
                    r1_paths=[File(path="/tmp/r1.fq.gz")],
                    known_sites=[File(path="/tmp/dbsnp.vcf")],
                    intervals=["chr20"],
                )

        self.assertEqual(result.path, "/tmp/cohort_genotyped.vcf")


# ---------------------------------------------------------------------------
# GenotypeRefinement workflow tests (Milestone D → I)
# ---------------------------------------------------------------------------


class GenotypeRefinementRegistryTests(TestCase):
    """Guard the genotype_refinement registry entry shape."""

    def test_genotype_refinement_registry_entry_shape(self) -> None:
        """Entry exists at workflow stage_order 4 with refined_vcf output."""
        from flytetest.registry import get_entry

        entry = get_entry("genotype_refinement")
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 4)
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        output_names = [f.name for f in entry.outputs]
        self.assertIn("refined_vcf", output_names)
        # sample_count now in inputs
        input_names = [f.name for f in entry.inputs]
        self.assertIn("sample_count", input_names)


class GenotypeRefinementWorkflowTests(TestCase):
    """Verify genotype_refinement two-pass VQSR ordering and manifest."""

    _SNP_RESOURCES = [File(path="/data/hapmap.vcf.gz"), File(path="/data/dbsnp.vcf")]
    _SNP_FLAGS = [
        {"resource_name": "hapmap", "known": "false", "training": "true", "truth": "true", "prior": "15"},
        {"resource_name": "dbsnp", "known": "true", "training": "false", "truth": "false", "prior": "2"},
    ]
    _INDEL_RESOURCES = [File(path="/data/mills.vcf.gz"), File(path="/data/dbsnp.vcf")]
    _INDEL_FLAGS = [
        {"resource_name": "mills", "known": "false", "training": "true", "truth": "true", "prior": "12"},
        {"resource_name": "dbsnp", "known": "true", "training": "false", "truth": "false", "prior": "2"},
    ]

    def test_genotype_refinement_runs(self) -> None:
        """Workflow completes and returns a File."""
        from flytetest.workflows.variant_calling import genotype_refinement

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(variant_calling_wf, "variant_recalibrator",
                             side_effect=[
                                 (_fake_file("/tmp/snp.recal"), _fake_file("/tmp/snp.tranches")),
                                 (_fake_file("/tmp/indel.recal"), _fake_file("/tmp/indel.tranches")),
                             ]),
                patch.object(variant_calling_wf, "apply_vqsr",
                             side_effect=[
                                 _fake_file("/tmp/snp_filtered.vcf.gz"),
                                 _fake_file("/tmp/indel_filtered.vcf.gz"),
                             ]),
            ):
                result = genotype_refinement(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    joint_vcf=File(path="/tmp/cohort.vcf.gz"),
                    snp_resources=self._SNP_RESOURCES,
                    snp_resource_flags=self._SNP_FLAGS,
                    indel_resources=self._INDEL_RESOURCES,
                    indel_resource_flags=self._INDEL_FLAGS,
                    cohort_id="cohort1",
                    sample_count=5,
                )

        self.assertEqual(result.path, "/tmp/indel_filtered.vcf.gz")

    def test_genotype_refinement_indel_uses_snp_vcf(self) -> None:
        """INDEL pass input_vcf is the SNP apply_vqsr output, not the original joint_vcf."""
        from flytetest.workflows.variant_calling import genotype_refinement

        snp_filtered = _fake_file("/tmp/cohort_vqsr_snp.vcf.gz")
        vr_calls: list[dict] = []

        def capturing_vr(**kwargs):
            vr_calls.append(kwargs)
            mode = kwargs["mode"]
            return (_fake_file(f"/tmp/{mode.lower()}.recal"), _fake_file(f"/tmp/{mode.lower()}.tranches"))

        av_calls: list[dict] = []

        def capturing_av(**kwargs):
            av_calls.append(kwargs)
            mode = kwargs["mode"]
            if mode == "SNP":
                return snp_filtered
            return _fake_file("/tmp/indel_filtered.vcf.gz")

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(variant_calling_wf, "variant_recalibrator", side_effect=capturing_vr),
                patch.object(variant_calling_wf, "apply_vqsr", side_effect=capturing_av),
            ):
                genotype_refinement(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    joint_vcf=File(path="/tmp/cohort.vcf.gz"),
                    snp_resources=self._SNP_RESOURCES,
                    snp_resource_flags=self._SNP_FLAGS,
                    indel_resources=self._INDEL_RESOURCES,
                    indel_resource_flags=self._INDEL_FLAGS,
                    cohort_id="cohort1",
                    sample_count=5,
                )

        # Second variant_recalibrator call must have received the SNP-filtered File
        self.assertEqual(len(vr_calls), 2)
        self.assertIs(vr_calls[1]["cohort_vcf"], snp_filtered)

    def test_genotype_refinement_threads_sample_count_through_both_passes(self) -> None:
        """sample_count is forwarded to both variant_recalibrator calls."""
        from flytetest.workflows.variant_calling import genotype_refinement

        vr_calls: list[dict] = []

        def capturing_vr(**kwargs):
            vr_calls.append(kwargs)
            mode = kwargs["mode"]
            return (_fake_file(f"/tmp/{mode.lower()}.recal"), _fake_file(f"/tmp/{mode.lower()}.tranches"))

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(variant_calling_wf, "variant_recalibrator", side_effect=capturing_vr),
                patch.object(variant_calling_wf, "apply_vqsr",
                             side_effect=[_fake_file("/tmp/snp.vcf.gz"), _fake_file("/tmp/indel.vcf.gz")]),
            ):
                genotype_refinement(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    joint_vcf=File(path="/tmp/cohort.vcf.gz"),
                    snp_resources=self._SNP_RESOURCES,
                    snp_resource_flags=self._SNP_FLAGS,
                    indel_resources=self._INDEL_RESOURCES,
                    indel_resource_flags=self._INDEL_FLAGS,
                    cohort_id="cohort1",
                    sample_count=15,
                )

        self.assertEqual(vr_calls[0]["sample_count"], 15)
        self.assertEqual(vr_calls[1]["sample_count"], 15)


# ---------------------------------------------------------------------------
# Milestone E Step 03 — preprocess_sample_from_ubam
# ---------------------------------------------------------------------------

class PreprocessSampleFromUbamWorkflowTests(TestCase):
    """Verify preprocess_sample_from_ubam calls sub-tasks in the correct order."""

    def _patch_all(self, *, sort_sam_mock=None):
        """Return a context manager patching all sub-tasks."""
        patches = [
            patch.object(variant_calling_wf, "bwa_mem2_mem",
                         return_value=_fake_file("/tmp/s1_aligned.bam")),
            patch.object(variant_calling_wf, "merge_bam_alignment",
                         return_value=_fake_file("/tmp/s1_merged.bam")),
            patch.object(variant_calling_wf, "mark_duplicates",
                         return_value=(_fake_file("/tmp/s1_dedup.bam"), _fake_file("/tmp/s1_metrics.txt"))),
            patch.object(variant_calling_wf, "base_recalibrator",
                         return_value=_fake_file("/tmp/s1_bqsr.table")),
            patch.object(variant_calling_wf, "apply_bqsr",
                         return_value=_fake_file("/tmp/s1_recal.bam")),
        ]
        if sort_sam_mock is not None:
            patches.append(patch.object(variant_calling_wf, "sort_sam", sort_sam_mock))
        from contextlib import ExitStack
        stack = ExitStack()
        mocks = [stack.enter_context(p) for p in patches]
        return stack, mocks

    def test_preprocess_sample_from_ubam_runs(self) -> None:
        """Returns a File pointing at the recalibrated BAM."""
        with tempfile.TemporaryDirectory() as tmp:
            stack, _ = self._patch_all()
            with stack:
                result = preprocess_sample_from_ubam(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    r1=File(path="/tmp/r1.fq.gz"),
                    ubam=File(path="/tmp/sample.ubam"),
                    sample_id="s1",
                    known_sites=[File(path="/tmp/dbsnp.vcf")],
                )

        self.assertEqual(result.path, "/tmp/s1_recal.bam")

    def test_no_sort_sam_called(self) -> None:
        """sort_sam is never invoked — MergeBamAlignment handles coordinate sorting."""
        with tempfile.TemporaryDirectory() as tmp:
            sort_sam_mock = MagicMock()
            stack, _ = self._patch_all(sort_sam_mock=sort_sam_mock)
            with stack:
                preprocess_sample_from_ubam(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    r1=File(path="/tmp/r1.fq.gz"),
                    ubam=File(path="/tmp/sample.ubam"),
                    sample_id="s1",
                    known_sites=[File(path="/tmp/dbsnp.vcf")],
                )

        sort_sam_mock.assert_not_called()

    def test_merge_bam_alignment_receives_aligned_bam(self) -> None:
        """merge_bam_alignment is called with aligned_bam from bwa_mem2_mem output."""
        with tempfile.TemporaryDirectory() as tmp:
            aligned = _fake_file("/tmp/s1_aligned.bam")
            mock_merge = MagicMock(return_value=_fake_file("/tmp/s1_merged.bam"))
            with (
                patch.object(variant_calling_wf, "bwa_mem2_mem", return_value=aligned),
                patch.object(variant_calling_wf, "merge_bam_alignment", mock_merge),
                patch.object(variant_calling_wf, "mark_duplicates",
                             return_value=(_fake_file("/tmp/s1_dedup.bam"), _fake_file("/tmp/m.txt"))),
                patch.object(variant_calling_wf, "base_recalibrator",
                             return_value=_fake_file("/tmp/s1_bqsr.table")),
                patch.object(variant_calling_wf, "apply_bqsr",
                             return_value=_fake_file("/tmp/s1_recal.bam")),
            ):
                preprocess_sample_from_ubam(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    r1=File(path="/tmp/r1.fq.gz"),
                    ubam=File(path="/tmp/sample.ubam"),
                    sample_id="s1",
                    known_sites=[File(path="/tmp/dbsnp.vcf")],
                )

        _call_kwargs = mock_merge.call_args.kwargs
        self.assertIs(_call_kwargs.get("aligned_bam"), aligned)

    def test_registry_entry_shape(self) -> None:
        """Registry entry exists at workflow stage 5 with preprocessed_bam_from_ubam output."""
        from flytetest.registry import get_entry

        entry = get_entry("preprocess_sample_from_ubam")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 5)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("preprocessed_bam_from_ubam", output_names)
        self.assertIn("preprocessed_bam_from_ubam", MANIFEST_OUTPUT_KEYS)


# ---------------------------------------------------------------------------
# Milestone I Step 03 — sequential_interval_haplotype_caller (renamed)
# ---------------------------------------------------------------------------

class SequentialIntervalHaplotypeCallerTests(TestCase):
    """Verify sequential_interval_haplotype_caller workflow."""

    def test_sequential_haplotype_caller_runs(self) -> None:
        """Returns a File with the gathered GVCF path."""
        with tempfile.TemporaryDirectory() as tmp:
            gathered = _fake_file("/tmp/s1_gathered.g.vcf.gz")
            with (
                patch.object(variant_calling_wf, "haplotype_caller", return_value=_fake_file("/tmp/s1.g.vcf")),
                patch.object(variant_calling_wf, "gather_vcfs", return_value=gathered),
            ):
                result = sequential_interval_haplotype_caller(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    aligned_bam=File(path="/tmp/s1.bam"),
                    sample_id="s1",
                    intervals=["chr1", "chr2"],
                )

        self.assertEqual(result.path, "/tmp/s1_gathered.g.vcf.gz")

    def test_haplotype_caller_called_once_per_interval(self) -> None:
        """haplotype_caller invoked exactly once per interval."""
        with tempfile.TemporaryDirectory() as tmp:
            mock_hc = MagicMock(return_value=_fake_file("/tmp/s1.g.vcf"))
            with (
                patch.object(variant_calling_wf, "haplotype_caller", mock_hc),
                patch.object(variant_calling_wf, "gather_vcfs", return_value=_fake_file("/tmp/s1_gathered.g.vcf.gz")),
            ):
                sequential_interval_haplotype_caller(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    aligned_bam=File(path="/tmp/s1.bam"),
                    sample_id="s1",
                    intervals=["chr1", "chr2", "chr3"],
                )

        self.assertEqual(mock_hc.call_count, 3)

    def test_gather_vcfs_receives_gvcfs_in_interval_order(self) -> None:
        """gather_vcfs receives gvcfs in the same order as intervals."""
        with tempfile.TemporaryDirectory() as tmp:
            gvcf_paths = [f"/tmp/s1_interval_{i}.g.vcf" for i in range(3)]
            call_idx = [0]

            def fake_hc(**kwargs):
                f = _fake_file(gvcf_paths[call_idx[0]])
                call_idx[0] += 1
                return f

            gathered_gvcfs: list[list] = []

            def capture_gather(**kwargs):
                gathered_gvcfs.append(kwargs.get("gvcfs", []))
                return _fake_file("/tmp/s1_gathered.g.vcf.gz")

            with (
                patch.object(variant_calling_wf, "haplotype_caller", side_effect=fake_hc),
                patch.object(variant_calling_wf, "gather_vcfs", side_effect=capture_gather),
            ):
                sequential_interval_haplotype_caller(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    aligned_bam=File(path="/tmp/s1.bam"),
                    sample_id="s1",
                    intervals=["chr1", "chr2", "chr3"],
                )

        passed_paths = [f.path for f in gathered_gvcfs[0]]
        self.assertEqual(passed_paths, gvcf_paths)

    def test_empty_intervals_raises(self) -> None:
        """ValueError raised when intervals is empty."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                sequential_interval_haplotype_caller(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    aligned_bam=File(path="/tmp/s1.bam"),
                    sample_id="s1",
                    intervals=[],
                )

    def test_registry_entry_shape(self) -> None:
        """Registry entry exists at workflow stage 6 with scattered_gvcf output."""
        from flytetest.registry import get_entry

        entry = get_entry("sequential_interval_haplotype_caller")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 6)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("scattered_gvcf", output_names)
        self.assertIn("scattered_gvcf", MANIFEST_OUTPUT_KEYS)

    def test_manifest_assumption_mentions_milestone_k(self) -> None:
        """Manifest assumptions describe synchronous execution and reference Milestone K."""
        from flytetest.registry import get_entry

        entry = get_entry("sequential_interval_haplotype_caller")
        constraints_text = " ".join(entry.compatibility.composition_constraints)
        self.assertIn("Milestone K", constraints_text)
        self.assertIn("synchronous", constraints_text.lower())


# ---------------------------------------------------------------------------
# Milestone G Step 02 — post_genotyping_refinement
# ---------------------------------------------------------------------------

class PostGenotypingRefinementTests(TestCase):
    """Verify post_genotyping_refinement workflow."""

    def test_post_genotyping_refinement_runs(self) -> None:
        """Returns the CGP File from calculate_genotype_posteriors."""
        with tempfile.TemporaryDirectory() as tmp:
            cgp_file = _fake_file("/tmp/cohort1_cgp.vcf.gz")
            with patch.object(variant_calling_wf, "calculate_genotype_posteriors", return_value=cgp_file):
                result = post_genotyping_refinement(
                    input_vcf=File(path="/tmp/cohort.vcf.gz"),
                    cohort_id="cohort1",
                )

        self.assertEqual(result.path, "/tmp/cohort1_cgp.vcf.gz")

    def test_registry_entry_shape(self) -> None:
        """Registry entry exists at workflow stage 7 with refined_vcf_cgp output."""
        from flytetest.registry import get_entry

        entry = get_entry("post_genotyping_refinement")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 7)

        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("refined_vcf_cgp", output_names)
        self.assertIn("refined_vcf_cgp", MANIFEST_OUTPUT_KEYS)

    def test_supporting_callsets_forwarded(self) -> None:
        """supporting_callsets is forwarded to calculate_genotype_posteriors."""
        with tempfile.TemporaryDirectory() as tmp:
            cs = [File(path="/tmp/s.vcf")]
            mock_cgp = MagicMock(return_value=_fake_file("/tmp/cgp.vcf.gz"))
            with patch.object(variant_calling_wf, "calculate_genotype_posteriors", mock_cgp):
                post_genotyping_refinement(
                    input_vcf=File(path="/tmp/cohort.vcf.gz"),
                    cohort_id="cohort1",
                    supporting_callsets=cs,
                )

        self.assertIs(mock_cgp.call_args.kwargs.get("supporting_callsets"), cs)


class PostGenotypingRefinementSignatureTests(TestCase):
    """Milestone H: verify post_genotyping_refinement no longer accepts ref_path."""

    def test_signature_has_no_ref_path(self) -> None:
        """post_genotyping_refinement signature must not include ref_path."""
        import inspect
        sig = inspect.signature(post_genotyping_refinement)
        self.assertNotIn("ref_path", sig.parameters,
                         "ref_path must be dropped from post_genotyping_refinement")

    def test_registry_inputs_match_signature(self) -> None:
        """Registry inputs do not include ref_path."""
        from flytetest.registry import get_entry
        entry = get_entry("post_genotyping_refinement")
        input_names = [f.name for f in entry.inputs]
        self.assertNotIn("ref_path", input_names)


class PrepareReferenceIdempotencyTests(TestCase):
    """Milestone H: verify prepare_reference skips steps when outputs exist."""

    def test_skips_sequence_dictionary_when_dict_exists(self) -> None:
        """CreateSequenceDictionary is not called when .dict already exists."""
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "genome.fa"
            ref.write_text(">chr1\nACGT\n")
            ref.with_suffix(".dict").write_text("existing dict")

            mock_csd = MagicMock()
            mock_iff = MagicMock()
            mock_bwa = MagicMock(return_value=MagicMock(path=str(ref)))

            captured_manifests: list[dict] = []
            with (
                patch.object(variant_calling_wf, "create_sequence_dictionary", mock_csd),
                patch.object(variant_calling_wf, "index_feature_file", mock_iff),
                patch.object(variant_calling_wf, "bwa_mem2_index", mock_bwa),
                patch.object(variant_calling_wf, "_write_json", side_effect=lambda p, d: captured_manifests.append(d)),
            ):
                prepare_reference(
                    reference_fasta=File(path=str(ref)),
                    known_sites=[],
                )

        mock_csd.assert_not_called()
        prep = next(m for m in captured_manifests if m.get("stage") == "prepare_reference")
        self.assertIn("create_sequence_dictionary", prep["outputs"]["skipped_steps"])

    def test_skips_index_feature_file_when_tbi_exists(self) -> None:
        """IndexFeatureFile is not called for a VCF that already has a .tbi index."""
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "genome.fa"
            ref.write_text(">chr1\nACGT\n")
            ref.with_suffix(".dict").write_text("dict")
            vcf = Path(tmp) / "dbsnp.vcf.gz"
            vcf.write_text("vcf")
            tbi = Path(tmp) / "dbsnp.vcf.gz.tbi"
            tbi.write_text("tbi")

            mock_iff = MagicMock()
            captured_manifests: list[dict] = []
            with (
                patch.object(variant_calling_wf, "create_sequence_dictionary", MagicMock()),
                patch.object(variant_calling_wf, "index_feature_file", mock_iff),
                patch.object(variant_calling_wf, "bwa_mem2_index", MagicMock(return_value=MagicMock(path=str(ref)))),
                patch.object(variant_calling_wf, "_write_json", side_effect=lambda p, d: captured_manifests.append(d)),
            ):
                prepare_reference(
                    reference_fasta=File(path=str(ref)),
                    known_sites=[File(path=str(vcf))],
                )

        mock_iff.assert_not_called()
        prep = next(m for m in captured_manifests if m.get("stage") == "prepare_reference")
        self.assertIn("index_feature_file", prep["outputs"]["skipped_steps"])

    def test_skips_bwa_index_when_all_suffixes_present(self) -> None:
        """bwa_mem2_index is not called when all 5 BWA index files exist."""
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "genome.fa"
            ref.write_text(">chr1\nACGT\n")
            ref.with_suffix(".dict").write_text("dict")
            for suffix in (".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"):
                Path(str(ref) + suffix).write_text("idx")

            mock_bwa = MagicMock()
            captured_manifests: list[dict] = []
            with (
                patch.object(variant_calling_wf, "create_sequence_dictionary", MagicMock()),
                patch.object(variant_calling_wf, "index_feature_file", MagicMock()),
                patch.object(variant_calling_wf, "bwa_mem2_index", mock_bwa),
                patch.object(variant_calling_wf, "_write_json", side_effect=lambda p, d: captured_manifests.append(d)),
            ):
                prepare_reference(
                    reference_fasta=File(path=str(ref)),
                    known_sites=[],
                )

        mock_bwa.assert_not_called()
        prep = next(m for m in captured_manifests if m.get("stage") == "prepare_reference")
        self.assertIn("bwa_mem2_index", prep["outputs"]["skipped_steps"])

    def test_force_true_reruns_all_steps(self) -> None:
        """With force=True all steps run even when outputs already exist."""
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "genome.fa"
            ref.write_text(">chr1\nACGT\n")
            ref.with_suffix(".dict").write_text("dict")
            for suffix in (".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"):
                Path(str(ref) + suffix).write_text("idx")

            mock_csd = MagicMock()
            mock_bwa = MagicMock(return_value=MagicMock(path=str(ref)))

            with (
                patch.object(variant_calling_wf, "create_sequence_dictionary", mock_csd),
                patch.object(variant_calling_wf, "index_feature_file", MagicMock()),
                patch.object(variant_calling_wf, "bwa_mem2_index", mock_bwa),
            ):
                prepare_reference(
                    reference_fasta=File(path=str(ref)),
                    known_sites=[],
                    force=True,
                )

        mock_csd.assert_called_once()
        mock_bwa.assert_called_once()


# ---------------------------------------------------------------------------
# Milestone I Step 04 — small_cohort_filter workflow
# ---------------------------------------------------------------------------

class SmallCohortFilterWorkflowTests(TestCase):
    """Verify small_cohort_filter two-pass SNP→INDEL workflow."""

    def test_two_passes_chain_snp_into_indel(self) -> None:
        """Second variant_filtration call receives SNP-filtered output as input_vcf."""
        with tempfile.TemporaryDirectory() as tmp:
            snp_filtered = _fake_file("/tmp/cohort_snp_filtered.vcf.gz")
            final_filtered = _fake_file("/tmp/cohort_indel_filtered.vcf.gz")
            vf_calls: list[dict] = []

            def capture_vf(**kwargs):
                vf_calls.append(kwargs)
                if kwargs.get("mode") == "SNP":
                    return snp_filtered
                return final_filtered

            with patch.object(variant_calling_wf, "variant_filtration", side_effect=capture_vf):
                result = small_cohort_filter(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    joint_vcf=File(path="/tmp/cohort.vcf"),
                    cohort_id="cohort1",
                )

        self.assertEqual(len(vf_calls), 2)
        self.assertEqual(vf_calls[0]["mode"], "SNP")
        self.assertEqual(vf_calls[1]["mode"], "INDEL")
        self.assertIs(vf_calls[1]["input_vcf"], snp_filtered)
        self.assertEqual(result.path, "/tmp/cohort_indel_filtered.vcf.gz")

    def test_workflow_accepts_expression_overrides(self) -> None:
        """Custom filter expressions are threaded through both passes."""
        with tempfile.TemporaryDirectory() as tmp:
            snp_exprs = [("MYSNP", "QD < 1.0")]
            indel_exprs = [("MYINDEL", "FS > 100.0")]
            vf_calls: list[dict] = []

            def capture_vf(**kwargs):
                vf_calls.append(kwargs)
                return _fake_file(f"/tmp/{kwargs['mode'].lower()}_filtered.vcf.gz")

            with patch.object(variant_calling_wf, "variant_filtration", side_effect=capture_vf):
                small_cohort_filter(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    joint_vcf=File(path="/tmp/cohort.vcf"),
                    cohort_id="cohort1",
                    snp_filter_expressions=snp_exprs,
                    indel_filter_expressions=indel_exprs,
                )

        self.assertEqual(vf_calls[0]["filter_expressions"], snp_exprs)
        self.assertEqual(vf_calls[1]["filter_expressions"], indel_exprs)

    def test_manifest_tracks_final_filtered_vcf(self) -> None:
        """Workflow manifest outputs include small_cohort_filtered_vcf."""
        with tempfile.TemporaryDirectory() as tmp:
            final = _fake_file("/tmp/final_filtered.vcf.gz")
            captured: list[dict] = []

            with (
                patch.object(variant_calling_wf, "variant_filtration",
                             side_effect=[_fake_file("/tmp/snp.vcf.gz"), final]),
                patch.object(variant_calling_wf, "_write_json", side_effect=lambda p, d: captured.append(d)),
            ):
                small_cohort_filter(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    joint_vcf=File(path="/tmp/cohort.vcf"),
                    cohort_id="cohort1",
                )

        manifest = next(m for m in captured if m.get("stage") == "small_cohort_filter")
        self.assertIn("small_cohort_filtered_vcf", manifest["outputs"])
        self.assertIn("small_cohort_filtered_vcf", MANIFEST_OUTPUT_KEYS)

    def test_registry_entry_shape(self) -> None:
        """Registry entry at workflow stage 8."""
        from flytetest.registry import get_entry
        entry = get_entry("small_cohort_filter")
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 8)
        self.assertIn("small_cohort_filtered_vcf", [f.name for f in entry.outputs])


# ---------------------------------------------------------------------------
# Milestone I Step 05 — pre_call_coverage_qc and post_call_qc_summary
# ---------------------------------------------------------------------------

class PreCallCoverageQcWorkflowTests(TestCase):
    """Verify pre_call_coverage_qc workflow."""

    def test_collect_called_per_sample(self) -> None:
        """collect_wgs_metrics called once per BAM; multiqc_summarize called once."""
        with tempfile.TemporaryDirectory() as tmp:
            mock_collect = MagicMock(side_effect=[
                (_fake_file("/tmp/s1_wgs.txt"), _fake_file("/tmp/s1_insert.txt")),
                (_fake_file("/tmp/s2_wgs.txt"), _fake_file("/tmp/s2_insert.txt")),
            ])
            mock_multiqc = MagicMock(return_value=_fake_file("/tmp/multiqc.html"))

            with (
                patch.object(variant_calling_wf, "collect_wgs_metrics", mock_collect),
                patch.object(variant_calling_wf, "multiqc_summarize", mock_multiqc),
            ):
                result = pre_call_coverage_qc(
                    reference_fasta=File(path="/tmp/ref.fa"),
                    aligned_bams=[File(path="/tmp/s1.bam"), File(path="/tmp/s2.bam")],
                    sample_ids=["s1", "s2"],
                    cohort_id="cohort1",
                )

        self.assertEqual(mock_collect.call_count, 2)
        mock_multiqc.assert_called_once()
        self.assertEqual(result.path, "/tmp/multiqc.html")

    def test_raises_on_length_mismatch(self) -> None:
        """ValueError when aligned_bams and sample_ids lengths differ."""
        with self.assertRaises(ValueError):
            pre_call_coverage_qc(
                reference_fasta=File(path="/tmp/ref.fa"),
                aligned_bams=[File(path="/tmp/s1.bam")],
                sample_ids=["s1", "s2"],
                cohort_id="cohort1",
            )


class PostCallQcSummaryWorkflowTests(TestCase):
    """Verify post_call_qc_summary workflow."""

    def test_bcftools_stats_then_multiqc(self) -> None:
        """bcftools_stats called, then multiqc_summarize with stats as first QC file."""
        with tempfile.TemporaryDirectory() as tmp:
            stats = _fake_file("/tmp/cohort1_stats.txt")
            report = _fake_file("/tmp/multiqc.html")
            mock_stats = MagicMock(return_value=stats)
            mock_multiqc = MagicMock(return_value=report)

            with (
                patch.object(variant_calling_wf, "bcftools_stats", mock_stats),
                patch.object(variant_calling_wf, "multiqc_summarize", mock_multiqc),
            ):
                result = post_call_qc_summary(
                    input_vcf=File(path="/tmp/cohort.vcf.gz"),
                    cohort_id="cohort1",
                )

        mock_stats.assert_called_once()
        mock_multiqc.assert_called_once()
        passed_inputs = mock_multiqc.call_args.kwargs["qc_inputs"]
        self.assertIs(passed_inputs[0], stats)
        self.assertEqual(result.path, "/tmp/multiqc.html")

    def test_extra_qc_files_propagated(self) -> None:
        """extra_qc_files appended to multiqc qc_inputs."""
        with tempfile.TemporaryDirectory() as tmp:
            stats = _fake_file("/tmp/stats.txt")
            extra = _fake_file("/tmp/extra.txt")
            mock_multiqc = MagicMock(return_value=_fake_file("/tmp/multiqc.html"))

            with (
                patch.object(variant_calling_wf, "bcftools_stats", return_value=stats),
                patch.object(variant_calling_wf, "multiqc_summarize", mock_multiqc),
            ):
                post_call_qc_summary(
                    input_vcf=File(path="/tmp/cohort.vcf.gz"),
                    cohort_id="cohort1",
                    extra_qc_files=[extra],
                )

        passed_inputs = mock_multiqc.call_args.kwargs["qc_inputs"]
        self.assertEqual(len(passed_inputs), 2)
        self.assertIs(passed_inputs[1], extra)


# ---------------------------------------------------------------------------
# Milestone I Step 06 — annotate_variants_snpeff workflow
# ---------------------------------------------------------------------------

class AnnotateVariantsSnpeffWorkflowTests(TestCase):
    """Verify annotate_variants_snpeff workflow."""

    def test_workflow_returns_annotated_vcf(self) -> None:
        """Workflow return is the annotated VCF, not the genes file."""
        with tempfile.TemporaryDirectory() as tmp:
            annotated = _fake_file("/tmp/cohort1_snpeff.vcf")
            genes = _fake_file("/tmp/cohort1_snpeff.genes.txt")
            with patch.object(variant_calling_wf, "snpeff_annotate", return_value=(annotated, genes)):
                result = annotate_variants_snpeff(
                    input_vcf=File(path="/tmp/cohort.vcf"),
                    cohort_id="cohort1",
                    snpeff_database="GRCh38.105",
                    snpeff_data_dir="/data/snpeff",
                )

        self.assertEqual(result.path, "/tmp/cohort1_snpeff.vcf")

    def test_workflow_threads_database_and_data_dir(self) -> None:
        """snpeff_database and snpeff_data_dir passed through unchanged to snpeff_annotate."""
        with tempfile.TemporaryDirectory() as tmp:
            mock_ann = MagicMock(return_value=(_fake_file("/tmp/ann.vcf"), _fake_file("/tmp/genes.txt")))
            with patch.object(variant_calling_wf, "snpeff_annotate", mock_ann):
                annotate_variants_snpeff(
                    input_vcf=File(path="/tmp/cohort.vcf"),
                    cohort_id="cohort1",
                    snpeff_database="hg38",
                    snpeff_data_dir="/custom/snpeff",
                )

        kw = mock_ann.call_args.kwargs
        self.assertEqual(kw["snpeff_database"], "hg38")
        self.assertEqual(kw["snpeff_data_dir"], "/custom/snpeff")

    def test_registry_entry_shape(self) -> None:
        """Registry entry at workflow stage 11 with annotated_vcf output."""
        from flytetest.registry import get_entry
        entry = get_entry("annotate_variants_snpeff")
        self.assertEqual(entry.category, "workflow")
        self.assertEqual(entry.compatibility.pipeline_stage_order, 11)
        self.assertIn("annotated_vcf", [f.name for f in entry.outputs])
        self.assertIn("annotated_vcf", MANIFEST_OUTPUT_KEYS)
