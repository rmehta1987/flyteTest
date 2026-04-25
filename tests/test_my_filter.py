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
