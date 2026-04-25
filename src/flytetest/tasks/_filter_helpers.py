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
