"""Tests for the flat-parameter MCP tools in flytetest.mcp_tools."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"
sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

import flytetest.mcp_tools as mcp_tools


_FAKE_RESULT = {"status": "ok", "recipe_id": "fake-id"}


class VcGermlineDiscoveryTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            result = mcp_tools.vc_germline_discovery(
                reference_fasta="/ref/hg38.fa",
                sample_ids=["NA12878"],
                r1_paths=["/reads/R1.fastq.gz"],
                known_sites=["/ref/dbsnp.vcf.gz"],
                intervals=["chr20"],
                cohort_id="test_cohort",
                r2_paths=["/reads/R2.fastq.gz"],
                partition="caslake",
                account="mylab",
            )
        mock_rw.assert_called_once()
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "germline_short_variant_discovery")
        self.assertEqual(kwargs["inputs"]["cohort_id"], "test_cohort")
        self.assertIn("ReferenceGenome", kwargs["bindings"])
        self.assertEqual(result, _FAKE_RESULT)

    def test_r2_paths_optional(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_germline_discovery(
                reference_fasta="/ref/hg38.fa",
                sample_ids=["S1"],
                r1_paths=["/reads/R1.fastq.gz"],
                known_sites=["/ref/dbsnp.vcf.gz"],
                intervals=["chr1"],
                cohort_id="cohort1",
            )
        _, kwargs = mock_rw.call_args
        self.assertNotIn("r2_paths", kwargs["inputs"])

    def test_resource_request_assembled(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_germline_discovery(
                reference_fasta="/ref/hg38.fa",
                sample_ids=["S1"],
                r1_paths=["/reads/R1.fastq.gz"],
                known_sites=["/ref/dbsnp.vcf.gz"],
                intervals=["chr1"],
                cohort_id="cohort1",
                partition="caslake",
                account="mylab",
                cpu=16,
                memory="64G",
                walltime="48:00:00",
            )
        _, kwargs = mock_rw.call_args
        rr = kwargs["resource_request"]
        self.assertEqual(rr["partition"], "caslake")
        self.assertEqual(rr["account"], "mylab")
        self.assertEqual(rr["cpu"], 16)
        self.assertEqual(rr["memory"], "64G")

    def test_dry_run_forwarded(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_germline_discovery(
                reference_fasta="/ref/hg38.fa",
                sample_ids=["S1"],
                r1_paths=["/reads/R1.fastq.gz"],
                known_sites=["/ref/dbsnp.vcf.gz"],
                intervals=["chr1"],
                cohort_id="cohort1",
                dry_run=True,
            )
        _, kwargs = mock_rw.call_args
        self.assertTrue(kwargs["dry_run"])


class VcPrepareReferenceTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_prepare_reference(
                reference_fasta="/ref/hg38.fa",
                known_sites=["/ref/dbsnp.vcf.gz"],
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "prepare_reference")
        self.assertIn("ReferenceGenome", kwargs["bindings"])

    def test_sif_paths_in_runtime_images(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_prepare_reference(
                reference_fasta="/ref/hg38.fa",
                known_sites=["/ref/dbsnp.vcf.gz"],
                gatk_sif="/images/gatk.sif",
                bwa_sif="/images/bwa.sif",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["runtime_images"]["gatk_sif"], "/images/gatk.sif")
        self.assertEqual(kwargs["runtime_images"]["bwa_sif"], "/images/bwa.sif")


class VcPreprocessSampleTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_preprocess_sample(
                reference_fasta="/ref/hg38.fa",
                r1="/reads/R1.fastq.gz",
                sample_id="NA12878",
                known_sites=["/ref/dbsnp.vcf.gz"],
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "preprocess_sample")
        self.assertEqual(kwargs["bindings"]["ReadPair"]["sample_id"], "NA12878")

    def test_r2_empty_not_in_inputs(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_preprocess_sample(
                reference_fasta="/ref/hg38.fa",
                r1="/reads/R1.fastq.gz",
                sample_id="S1",
                known_sites=["/ref/dbsnp.vcf.gz"],
            )
        _, kwargs = mock_rw.call_args
        self.assertNotIn("r2", kwargs["inputs"])


class VcGenotypeRefinementTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_genotype_refinement(
                reference_fasta="/ref/hg38.fa",
                joint_vcf="/vcf/joint.vcf.gz",
                snp_resources=["/ref/hapmap.vcf.gz"],
                snp_resource_flags=[{"resource_name": "hapmap", "prior": "15"}],
                indel_resources=["/ref/mills.vcf.gz"],
                indel_resource_flags=[{"resource_name": "mills", "prior": "12"}],
                cohort_id="cohort1",
                sample_count=30,
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "genotype_refinement")
        self.assertEqual(kwargs["inputs"]["sample_count"], 30)


class VcSmallCohortFilterTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_small_cohort_filter(
                reference_fasta="/ref/hg38.fa",
                joint_vcf="/vcf/joint.vcf.gz",
                cohort_id="trio1",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "small_cohort_filter")
        self.assertEqual(kwargs["inputs"]["cohort_id"], "trio1")


class VcPostGenotypingRefinementTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_post_genotyping_refinement(
                input_vcf="/vcf/filtered.vcf.gz",
                cohort_id="cohort1",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "post_genotyping_refinement")
        self.assertEqual(kwargs["bindings"], {"VariantCallSet": {"vcf_path": kwargs["inputs"]["input_vcf"]}})


class VcSequentialIntervalHaplotypeCallerTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_sequential_interval_haplotype_caller(
                reference_fasta="/ref/hg38.fa",
                aligned_bam="/bam/sample_recal.bam",
                sample_id="NA12878",
                intervals=["chr20"],
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "sequential_interval_haplotype_caller")
        self.assertEqual(kwargs["inputs"]["sample_id"], "NA12878")


class VcPreCallCoverageQcTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_pre_call_coverage_qc(
                reference_fasta="/ref/hg38.fa",
                aligned_bams=["/bam/s1_recal.bam"],
                sample_ids=["S1"],
                cohort_id="cohort1",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "pre_call_coverage_qc")
        self.assertEqual(kwargs["inputs"]["sample_ids"], ["S1"])


class VcPostCallQcSummaryTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_post_call_qc_summary(
                input_vcf="/vcf/filtered.vcf.gz",
                cohort_id="cohort1",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "post_call_qc_summary")
        self.assertEqual(kwargs["bindings"], {"VariantCallSet": {"vcf_path": kwargs["inputs"]["input_vcf"]}})


class VcAnnotateVariantsSnpeffTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_annotate_variants_snpeff(
                input_vcf="/vcf/filtered.vcf.gz",
                cohort_id="cohort1",
                snpeff_database="GRCh38.105",
                snpeff_data_dir="/data/snpeff/data",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "annotate_variants_snpeff")
        self.assertEqual(kwargs["inputs"]["snpeff_database"], "GRCh38.105")
        self.assertEqual(kwargs["bindings"], {"VariantCallSet": {"vcf_path": kwargs["inputs"]["input_vcf"]}})


class VcCustomFilterTests(TestCase):
    """Flat tool vc_custom_filter delegates to run_task with VariantCallSet binding."""

    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_task", return_value=_FAKE_RESULT) as mock_rt:
            result = mcp_tools.vc_custom_filter(
                vcf_path="/vcf/joint_called.vcf",
                min_qual=50.0,
            )
        mock_rt.assert_called_once()
        _, kwargs = mock_rt.call_args
        self.assertEqual(kwargs["task_name"], "my_custom_filter")
        self.assertEqual(kwargs["bindings"], {"VariantCallSet": {"vcf_path": "/vcf/joint_called.vcf"}})
        self.assertEqual(kwargs["inputs"], {"min_qual": 50.0})
        self.assertFalse(kwargs.get("dry_run"))
        self.assertEqual(result, _FAKE_RESULT)

    def test_default_min_qual(self) -> None:
        with patch("flytetest.server.run_task", return_value=_FAKE_RESULT) as mock_rt:
            mcp_tools.vc_custom_filter(vcf_path="/vcf/x.vcf")
        _, kwargs = mock_rt.call_args
        self.assertEqual(kwargs["inputs"]["min_qual"], 30.0)

    def test_dry_run_propagates(self) -> None:
        with patch("flytetest.server.run_task", return_value=_FAKE_RESULT) as mock_rt:
            mcp_tools.vc_custom_filter(vcf_path="/vcf/x.vcf", dry_run=True)
        _, kwargs = mock_rt.call_args
        self.assertTrue(kwargs["dry_run"])

    def test_resource_request_assembled(self) -> None:
        with patch("flytetest.server.run_task", return_value=_FAKE_RESULT) as mock_rt:
            mcp_tools.vc_custom_filter(
                vcf_path="/vcf/x.vcf",
                partition="caslake",
                account="mylab",
                cpu=2,
                memory="8Gi",
                walltime="01:00:00",
            )
        _, kwargs = mock_rt.call_args
        rr = kwargs["resource_request"]
        self.assertEqual(rr["partition"], "caslake")
        self.assertEqual(rr["account"], "mylab")
        self.assertEqual(rr["cpu"], 2)
        self.assertEqual(rr["memory"], "8Gi")
        self.assertEqual(rr["walltime"], "01:00:00")

    def test_default_resource_request_is_none(self) -> None:
        with patch("flytetest.server.run_task", return_value=_FAKE_RESULT) as mock_rt:
            mcp_tools.vc_custom_filter(vcf_path="/vcf/x.vcf")
        _, kwargs = mock_rt.call_args
        self.assertIsNone(kwargs["resource_request"])


class VcApplyCustomFilterTests(TestCase):
    """Flat tool vc_apply_custom_filter delegates to run_workflow with VariantCallSet binding."""

    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            result = mcp_tools.vc_apply_custom_filter(
                vcf_path="/vcf/joint_called.vcf",
                min_qual=50.0,
            )
        mock_rw.assert_called_once()
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "apply_custom_filter")
        self.assertEqual(kwargs["bindings"], {"VariantCallSet": {"vcf_path": "/vcf/joint_called.vcf"}})
        self.assertEqual(kwargs["inputs"], {"min_qual": 50.0})
        self.assertEqual(result, _FAKE_RESULT)

    def test_default_min_qual(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_apply_custom_filter(vcf_path="/vcf/x.vcf")
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["inputs"]["min_qual"], 30.0)

    def test_dry_run_propagates(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.vc_apply_custom_filter(vcf_path="/vcf/x.vcf", dry_run=True)
        _, kwargs = mock_rw.call_args
        self.assertTrue(kwargs["dry_run"])


class AnnotationBraker3Tests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.annotation_braker3(
                genome="/ref/genome.fa",
                rnaseq_bam_path="/rnaseq/RNAseq.bam",
                braker_species="fly",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "ab_initio_annotation_braker3")
        self.assertIn("ReferenceGenome", kwargs["bindings"])
        self.assertEqual(kwargs["inputs"]["rnaseq_bam_path"], "/rnaseq/RNAseq.bam")

    def test_empty_optional_fields_omitted(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.annotation_braker3(genome="/ref/genome.fa")
        _, kwargs = mock_rw.call_args
        self.assertNotIn("rnaseq_bam_path", kwargs["inputs"])
        self.assertNotIn("protein_fasta_path", kwargs["inputs"])
        self.assertNotIn("braker_species", kwargs["inputs"])


class AnnotationProteinEvidenceTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.annotation_protein_evidence(
                genome="/ref/genome.fa",
                protein_fastas=["/proteins/uniprot.fa"],
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "protein_evidence_alignment")
        self.assertEqual(kwargs["inputs"]["protein_fastas"], ["/proteins/uniprot.fa"])


class AnnotationBuscoQcTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.annotation_busco_qc(
                repeat_filter_results="/results/repeat_filter/",
                busco_lineages_text="eukaryota,insecta",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "annotation_qc_busco")
        self.assertIn("QualityAssessmentTarget", kwargs["bindings"])


class AnnotationEggnogTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.annotation_eggnog(
                repeat_filter_results="/results/repeat_filter/",
                eggnog_data_dir="/data/eggnog/",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "annotation_functional_eggnog")
        self.assertEqual(kwargs["inputs"]["eggnog_data_dir"], "/data/eggnog/")


class AnnotationAgatStatsTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.annotation_agat_stats(eggnog_results="/results/eggnog/")
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "annotation_postprocess_agat")

    def test_optional_fasta_included(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.annotation_agat_stats(
                eggnog_results="/results/eggnog/",
                annotation_fasta_path="/ref/genome.fa",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["inputs"]["annotation_fasta_path"], "/ref/genome.fa")


class AnnotationAgatConvertTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.annotation_agat_convert(eggnog_results="/results/eggnog/")
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "annotation_postprocess_agat_conversion")


class AnnotationAgatCleanupTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.annotation_agat_cleanup(
                agat_conversion_results="/results/agat_convert/"
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "annotation_postprocess_agat_cleanup")
        self.assertIsNone(kwargs["runtime_images"])


class AnnotationTable2AsnTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.annotation_table2asn(
                agat_cleanup_results="/results/agat_cleanup/",
                genome_fasta="/ref/genome_masked.fa",
                submission_template="/ncbi/template.sbt",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "annotation_postprocess_table2asn")
        self.assertEqual(kwargs["inputs"]["submission_template"], "/ncbi/template.sbt")

    def test_optional_locus_tag(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.annotation_table2asn(
                agat_cleanup_results="/results/agat_cleanup/",
                genome_fasta="/ref/genome_masked.fa",
                submission_template="/ncbi/template.sbt",
                locus_tag_prefix="DMELA",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["inputs"]["locus_tag_prefix"], "DMELA")

    def test_absent_locus_tag_omitted(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.annotation_table2asn(
                agat_cleanup_results="/results/agat_cleanup/",
                genome_fasta="/ref/genome_masked.fa",
                submission_template="/ncbi/template.sbt",
            )
        _, kwargs = mock_rw.call_args
        self.assertNotIn("locus_tag_prefix", kwargs["inputs"])


class AnnotationGffreadProteinsTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_task", return_value=_FAKE_RESULT) as mock_rt:
            mcp_tools.annotation_gffread_proteins(
                annotation_gff3="/results/braker3/braker.gff3",
                genome_fasta="/ref/genome.fa",
            )
        _, kwargs = mock_rt.call_args
        self.assertEqual(kwargs["task_name"], "gffread_proteins")
        self.assertEqual(kwargs["inputs"]["annotation_gff3"], "/results/braker3/braker.gff3")


class AnnotationBuscoAssessTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_task", return_value=_FAKE_RESULT) as mock_rt:
            mcp_tools.annotation_busco_assess(
                proteins_fasta="/results/proteins/annotation.fa",
                lineage_dataset="insecta_odb10",
            )
        _, kwargs = mock_rt.call_args
        self.assertEqual(kwargs["task_name"], "busco_assess_proteins")
        self.assertEqual(kwargs["inputs"]["lineage_dataset"], "insecta_odb10")


class AnnotationExonerateChunkTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_task", return_value=_FAKE_RESULT) as mock_rt:
            mcp_tools.annotation_exonerate_chunk(
                genome="/ref/genome.fa",
                protein_chunk="/chunks/chunk_001.fa",
            )
        _, kwargs = mock_rt.call_args
        self.assertEqual(kwargs["task_name"], "exonerate_align_chunk")
        self.assertEqual(kwargs["inputs"]["protein_chunk"], "/chunks/chunk_001.fa")


class RnaseqQcTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.rnaseq_qc(
                ref="/ref/transcriptome.fa",
                left="/reads/R1.fastq.gz",
                right="/reads/R2.fastq.gz",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["workflow_name"], "rnaseq_qc_quant")
        self.assertIn("ReadSet", kwargs["bindings"])
        self.assertEqual(kwargs["inputs"]["ref"], "/ref/transcriptome.fa")

    def test_sample_id_in_binding(self) -> None:
        with patch("flytetest.server.run_workflow", return_value=_FAKE_RESULT) as mock_rw:
            mcp_tools.rnaseq_qc(
                ref="/ref/transcriptome.fa",
                left="/reads/R1.fastq.gz",
                right="/reads/R2.fastq.gz",
                sample_id="sample_A",
            )
        _, kwargs = mock_rw.call_args
        self.assertEqual(kwargs["bindings"]["ReadSet"]["sample_id"], "sample_A")


class RnaseqFastqcTests(TestCase):
    def test_happy_path(self) -> None:
        with patch("flytetest.server.run_task", return_value=_FAKE_RESULT) as mock_rt:
            mcp_tools.rnaseq_fastqc(
                left="/reads/R1.fastq.gz",
                right="/reads/R2.fastq.gz",
            )
        _, kwargs = mock_rt.call_args
        self.assertEqual(kwargs["task_name"], "fastqc")
        self.assertEqual(kwargs["inputs"]["left"], "/reads/R1.fastq.gz")
        self.assertIsNone(kwargs["bindings"])

    def test_fastqc_sif_in_runtime_images(self) -> None:
        with patch("flytetest.server.run_task", return_value=_FAKE_RESULT) as mock_rt:
            mcp_tools.rnaseq_fastqc(
                left="/reads/R1.fastq.gz",
                right="/reads/R2.fastq.gz",
                fastqc_sif="/images/fastqc.sif",
            )
        _, kwargs = mock_rt.call_args
        self.assertEqual(kwargs["runtime_images"]["fastqc_sif"], "/images/fastqc.sif")


class ResourceRequestHelperTests(TestCase):
    """Unit-test the private _resource_request helper."""

    def test_returns_none_when_all_empty(self) -> None:
        rr = mcp_tools._resource_request("", "", 0, "", "", None, None)
        self.assertIsNone(rr)

    def test_partial_resource_request(self) -> None:
        rr = mcp_tools._resource_request("caslake", "mylab", 0, "", "", None, None)
        self.assertEqual(rr, {"partition": "caslake", "account": "mylab"})

    def test_all_fields_set(self) -> None:
        rr = mcp_tools._resource_request(
            "caslake", "mylab", 16, "64G", "12:00:00", ["/scratch"], ["python/3.11"]
        )
        self.assertIsNotNone(rr)
        self.assertEqual(rr["cpu"], 16)
        self.assertEqual(rr["shared_fs_roots"], ["/scratch"])
        self.assertEqual(rr["module_loads"], ["python/3.11"])


class AllToolsInModuleTests(TestCase):
    """Verify that __all__ lists every public tool and no extras."""

    def test_all_exports_callable(self) -> None:
        for name in mcp_tools.__all__:
            obj = getattr(mcp_tools, name)
            self.assertTrue(callable(obj), msg=f"{name} is not callable")
