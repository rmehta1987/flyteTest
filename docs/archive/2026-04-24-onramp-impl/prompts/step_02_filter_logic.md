# Step 02 — Pure-Python Filter Logic and Unit Test

This step adds the pure-Python implementation that `my_custom_filter` will call
through `run_tool`. Keep it entirely separate from Flyte wiring — no imports from
`flytetest.config`, no `File`, no `variant_calling_env`. This layer must be
testable with plain `pytest` and no stubs.

---

## New file — `src/flytetest/tasks/_filter_helpers.py`

```python
"""Pure-Python VCF filtering helpers.

Intentionally dependency-free: no pysam, no htslib, no external packages.
Import only from the standard library. This makes the helpers testable without
any container, SIF, or Flyte stub.
"""
from __future__ import annotations

from pathlib import Path


def filter_vcf(in_path: Path, out_path: Path, min_qual: float) -> None:
    """Write a QUAL-filtered copy of a plain-text VCF.

    Rules:
    - Header lines (starting with ``#``) are always preserved.
    - Data lines with a numeric QUAL >= ``min_qual`` are kept.
    - Data lines with QUAL below ``min_qual`` are dropped.
    - Data lines with QUAL equal to ``.`` (missing) are treated as below
      threshold and dropped — a filter should only pass records that
      affirmatively meet the quality criterion.

    Args:
        in_path:  Readable plain-text VCF (uncompressed).
        out_path: Destination path; parent directory must already exist.
        min_qual: Minimum QUAL value (inclusive) to retain a record.
    """
    with in_path.open() as fh_in, out_path.open("w") as fh_out:
        for line in fh_in:
            if line.startswith("#"):
                fh_out.write(line)
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 6:
                # Malformed line — preserve it rather than silently dropping.
                fh_out.write(line)
                continue
            qual_field = fields[5]
            if qual_field == ".":
                continue  # missing QUAL treated as below threshold
            try:
                qual = float(qual_field)
            except ValueError:
                continue  # unparseable QUAL treated as below threshold
            if qual >= min_qual:
                fh_out.write(line)
```

---

## New file — `tests/test_my_filter.py`

```python
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
        assert "QUAL\t10.0" not in content  # pos 100, QUAL=10 → dropped
        assert "pos 100" not in content

    def test_high_qual_records_kept(self, vcf_files):
        in_vcf, out_vcf = vcf_files
        filter_vcf(in_vcf, out_vcf, min_qual=30.0)
        content = out_vcf.read_text()
        # QUAL=50 and QUAL=100 both meet threshold
        assert "\t50.0\t" in content
        assert "\t100.0\t" in content

    def test_missing_qual_dropped(self, vcf_files):
        in_vcf, out_vcf = vcf_files
        filter_vcf(in_vcf, out_vcf, min_qual=30.0)
        content = out_vcf.read_text()
        # pos 400 has QUAL=. → must be dropped
        assert "chr20\t400" not in content

    def test_threshold_is_inclusive(self, vcf_files):
        """A record with QUAL == min_qual exactly must be kept."""
        in_vcf, out_vcf = vcf_files
        filter_vcf(in_vcf, out_vcf, min_qual=50.0)
        content = out_vcf.read_text()
        assert "\t50.0\t" in content

    def test_all_pass_when_min_qual_zero(self, vcf_files):
        in_vcf, out_vcf = vcf_files
        filter_vcf(in_vcf, out_vcf, min_qual=0.0)
        out_lines = [l for l in out_vcf.read_text().splitlines() if not l.startswith("#")]
        # QUAL=. is still dropped (missing ≠ 0)
        assert len(out_lines) == 3

    def test_empty_vcf_produces_empty_output(self, tmp_path):
        in_vcf = tmp_path / "empty.vcf"
        out_vcf = tmp_path / "empty_out.vcf"
        in_vcf.write_text("")
        filter_vcf(in_vcf, out_vcf, min_qual=30.0)
        assert out_vcf.read_text() == ""
```

---

## Verification

```bash
python3 -m compileall src/flytetest/tasks/_filter_helpers.py

PYTHONPATH=src python3 -m pytest tests/test_my_filter.py -v
# Expected: 7 tests pass, 0 failures
```

All tests must pass before proceeding to Step 03. If a test reveals a logic bug,
fix `_filter_helpers.py` here — do not adjust the test to match wrong behavior.
