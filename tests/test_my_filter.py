"""Pure-logic unit tests for filter_vcf.

No Flyte, no stubs, no config imports.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from flytetest.tasks._filter_helpers import filter_vcf


_SYNTHETIC_VCF = """\
##fileformat=VCFv4.2
##FILTER=<ID=PASS,Description="All filters passed">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr20\t100\t.\tA\tT\t10.0\tPASS\t.
chr20\t200\t.\tC\tG\t50.0\tPASS\t.
chr20\t300\t.\tT\tA\t100.0\tPASS\t.
chr20\t400\t.\tG\tC\t.\tPASS\t.
"""


@pytest.fixture
def vcf_files(tmp_path):
    in_vcf = tmp_path / "input.vcf"
    out_vcf = tmp_path / "output.vcf"
    in_vcf.write_text(_SYNTHETIC_VCF)
    return in_vcf, out_vcf


class TestFilterVcfBasicContract:
    def test_headers_preserved(self, vcf_files):
        in_vcf, out_vcf = vcf_files
        filter_vcf(in_vcf, out_vcf, min_qual=30.0)
        lines = out_vcf.read_text().splitlines()
        header_lines = [l for l in lines if l.startswith("#")]
        assert len(header_lines) == 3  # ##fileformat, ##FILTER, #CHROM header

    def test_low_qual_record_dropped(self, vcf_files):
        in_vcf, out_vcf = vcf_files
        filter_vcf(in_vcf, out_vcf, min_qual=30.0)
        content = out_vcf.read_text()
        # pos 100 has QUAL=10, which is below threshold
        assert "chr20\t100\t" not in content

    def test_high_qual_records_kept(self, vcf_files):
        in_vcf, out_vcf = vcf_files
        filter_vcf(in_vcf, out_vcf, min_qual=30.0)
        content = out_vcf.read_text()
        assert "chr20\t200\t" in content   # QUAL=50
        assert "chr20\t300\t" in content   # QUAL=100

    def test_missing_qual_dropped(self, vcf_files):
        in_vcf, out_vcf = vcf_files
        filter_vcf(in_vcf, out_vcf, min_qual=30.0)
        content = out_vcf.read_text()
        # pos 400 has QUAL=. → must be dropped
        assert "chr20\t400\t" not in content

    def test_threshold_is_inclusive(self, vcf_files):
        """A record with QUAL == min_qual exactly must be kept."""
        in_vcf, out_vcf = vcf_files
        filter_vcf(in_vcf, out_vcf, min_qual=50.0)
        content = out_vcf.read_text()
        assert "chr20\t200\t" in content   # QUAL=50 exactly

    def test_all_numeric_pass_when_min_qual_zero(self, vcf_files):
        in_vcf, out_vcf = vcf_files
        filter_vcf(in_vcf, out_vcf, min_qual=0.0)
        out_lines = [l for l in out_vcf.read_text().splitlines() if not l.startswith("#")]
        # QUAL=. is still dropped; the three numeric records pass
        assert len(out_lines) == 3

    def test_empty_vcf_produces_empty_output(self, tmp_path):
        in_vcf = tmp_path / "empty.vcf"
        out_vcf = tmp_path / "empty_out.vcf"
        in_vcf.write_text("")
        filter_vcf(in_vcf, out_vcf, min_qual=30.0)
        assert out_vcf.read_text() == ""

    def test_headers_only_vcf_preserved_unchanged(self, tmp_path):
        in_vcf = tmp_path / "headers_only.vcf"
        out_vcf = tmp_path / "headers_only_out.vcf"
        content = "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        in_vcf.write_text(content)
        filter_vcf(in_vcf, out_vcf, min_qual=30.0)
        assert out_vcf.read_text() == content


_MALFORMED_VCF = (
    "##fileformat=VCFv4.2\n"
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
    "chr20\t100\t.\tA\tT\t50.0\tPASS\t.\n"      # valid, kept
    "truncated\tline\twith\tonly\tfive\n"        # malformed: 5 fields
    "\n"                                          # malformed: blank line
    "chr20\t300\t.\tT\tA\tnotanumber\tPASS\t.\n"  # malformed: unparseable QUAL
    "chr20\t400\t.\tC\tG\t10.0\tPASS\t.\n"        # valid but below threshold
    "chr20\t500\t.\tA\tG\t.\tPASS\t.\n"           # missing QUAL
)


class TestFilterVcfMalformedHandling:
    """Malformed lines are dropped (not propagated) and counted via stats dict.

    Previously these lines would pass through to the filtered output, where
    downstream tools (bcftools, GATK) would explode at a less actionable
    point. The on-ramp filter now drops + counts them so a corrupt input is
    visible in the manifest rather than buried in a downstream stack trace.
    """

    @pytest.fixture
    def malformed_files(self, tmp_path):
        in_vcf = tmp_path / "malformed.vcf"
        out_vcf = tmp_path / "malformed_out.vcf"
        in_vcf.write_text(_MALFORMED_VCF)
        return in_vcf, out_vcf

    def test_malformed_lines_not_propagated(self, malformed_files):
        in_vcf, out_vcf = malformed_files
        filter_vcf(in_vcf, out_vcf, min_qual=30.0)
        content = out_vcf.read_text()
        # Only the QUAL=50 record should survive.
        assert "truncated" not in content
        assert "notanumber" not in content
        data_lines = [l for l in content.splitlines() if not l.startswith("#") and l.strip()]
        assert len(data_lines) == 1
        assert "chr20\t100\t" in data_lines[0]

    def test_stats_dict_records_per_category_counts(self, malformed_files):
        in_vcf, out_vcf = malformed_files
        stats: dict[str, int] = {}
        filter_vcf(in_vcf, out_vcf, min_qual=30.0, stats=stats)
        assert stats == {
            "malformed_lines_dropped": 3,   # truncated + blank + unparseable QUAL
            "low_qual_dropped": 1,           # QUAL=10
            "missing_qual_dropped": 1,       # QUAL=.
            "records_kept": 1,               # QUAL=50
        }

    def test_stats_dict_optional(self, malformed_files):
        """Omitting stats must not raise; the function still filters correctly."""
        in_vcf, out_vcf = malformed_files
        filter_vcf(in_vcf, out_vcf, min_qual=30.0)  # no stats kwarg
        data_lines = [
            l for l in out_vcf.read_text().splitlines()
            if not l.startswith("#") and l.strip()
        ]
        assert len(data_lines) == 1

    def test_blank_line_in_data_section_dropped(self, tmp_path):
        in_vcf = tmp_path / "blank.vcf"
        out_vcf = tmp_path / "blank_out.vcf"
        in_vcf.write_text(
            "##fileformat=VCFv4.2\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            "\n"
            "chr1\t100\t.\tA\tT\t50.0\tPASS\t.\n"
        )
        stats: dict[str, int] = {}
        filter_vcf(in_vcf, out_vcf, min_qual=30.0, stats=stats)
        assert "\n\n" not in out_vcf.read_text()
        assert stats["malformed_lines_dropped"] == 1
        assert stats["records_kept"] == 1

    def test_records_kept_count_matches_output(self, tmp_path):
        """records_kept must equal the number of non-header lines in the output."""
        in_vcf = tmp_path / "all_pass.vcf"
        out_vcf = tmp_path / "all_pass_out.vcf"
        in_vcf.write_text(
            "##fileformat=VCFv4.2\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            "chr1\t100\t.\tA\tT\t100.0\tPASS\t.\n"
            "chr1\t200\t.\tC\tG\t100.0\tPASS\t.\n"
            "chr1\t300\t.\tT\tA\t100.0\tPASS\t.\n"
        )
        stats: dict[str, int] = {}
        filter_vcf(in_vcf, out_vcf, min_qual=30.0, stats=stats)
        out_data = [
            l for l in out_vcf.read_text().splitlines()
            if not l.startswith("#") and l.strip()
        ]
        assert stats["records_kept"] == len(out_data) == 3
