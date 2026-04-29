"""Pure-Python VCF filtering helpers.

Intentionally dependency-free: no pysam, no htslib, no external packages.
Import only from the standard library. This makes the helpers testable without
any container, SIF, or Flyte stub.
"""
from __future__ import annotations

from pathlib import Path


def filter_vcf(
    in_path: Path,
    out_path: Path,
    min_qual: float,
    stats: dict[str, int] | None = None,
) -> None:
    """Write a QUAL-filtered copy of a plain-text VCF.

    Rules:
    - Header lines (starting with ``#``) are always preserved.
    - Data lines with a numeric QUAL >= ``min_qual`` are kept.
    - Data lines with QUAL below ``min_qual`` are dropped.
    - Data lines with QUAL equal to ``.`` (missing) are dropped — a filter
      should only pass records that affirmatively meet the quality criterion.
    - Data lines with an unparseable QUAL field are dropped (same rationale).
    - Malformed lines (fewer than 6 tab-separated fields, or blank lines)
      are dropped, not propagated. A "filtered" VCF must remain readable by
      downstream tools (bcftools, GATK); silently passing through corrupt
      content would explode at the next stage with a less actionable error.

    The function is intentionally permissive about input formatting (no spec
    validation, no header-section enforcement) and strict about output
    correctness — every data line written must be at least minimally
    parseable as a VCF record.

    Args:
        in_path:  Readable plain-text VCF (uncompressed).
        out_path: Destination path; parent directory must already exist.
        min_qual: Minimum QUAL value (inclusive) to retain a record.
        stats:    Optional mutable mapping; when provided, populated with
                  per-run counts (``malformed_lines_dropped``,
                  ``low_qual_dropped``, ``missing_qual_dropped``,
                  ``records_kept``). Use this when the caller needs to record
                  filter statistics in a manifest or stderr summary.
    """
    counts = {
        "malformed_lines_dropped": 0,
        "low_qual_dropped": 0,
        "missing_qual_dropped": 0,
        "records_kept": 0,
    }
    with in_path.open() as fh_in, out_path.open("w") as fh_out:
        for line in fh_in:
            if line.startswith("#"):
                fh_out.write(line)
                continue
            stripped = line.rstrip("\n").rstrip("\r")
            if not stripped:
                # Blank line in the data section — not a record. Drop and count.
                counts["malformed_lines_dropped"] += 1
                continue
            # Cap split at column 6: only QUAL (index 5) is needed to decide
            # whether to keep the line, and the original line is written back
            # unchanged. For cohort-scale VCFs (10–50M records) this avoids
            # allocating the full INFO/FORMAT/sample column list per line.
            fields = stripped.split("\t", 6)
            if len(fields) < 6:
                counts["malformed_lines_dropped"] += 1
                continue
            qual_field = fields[5]
            if qual_field == ".":
                counts["missing_qual_dropped"] += 1
                continue
            try:
                qual = float(qual_field)
            except ValueError:
                counts["malformed_lines_dropped"] += 1
                continue
            if qual >= min_qual:
                fh_out.write(line)
                counts["records_kept"] += 1
            else:
                counts["low_qual_dropped"] += 1

    if stats is not None:
        stats.update(counts)


def count_vcf_records(vcf_path: Path) -> dict:
    """Count header and data lines in a plain-text VCF.

    Walks the file once and returns a small dict with two keys:

    - ``header_lines`` — number of lines starting with ``#``.
    - ``data_lines``   — number of non-blank, non-header lines.

    Blank lines are ignored entirely (counted as neither header nor data).
    The function does not validate VCF spec compliance — every non-blank,
    non-``#`` line counts toward ``data_lines`` regardless of column count.
    This makes it safe to use as a sanity-check counter even on partially
    malformed inputs.

    The toy task that wraps this helper exists for the testing-chapter
    walkthrough (`docs/tutorials/user_authored_tasks/07_testing.md`); it is
    a deliberately minimal, dependency-free function so each layer of the
    test ladder has an obvious failure mode to demonstrate.

    Args:
        vcf_path: Readable plain-text VCF (uncompressed).

    Returns:
        A dict with integer ``header_lines`` and ``data_lines`` counts.
    """
    counts = {"header_lines": 0, "data_lines": 0}
    with vcf_path.open() as fh:
        for line in fh:
            if line.startswith("#"):
                counts["header_lines"] += 1
                continue
            if not line.strip():
                continue
            counts["data_lines"] += 1
    return counts
