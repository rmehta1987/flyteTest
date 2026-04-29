# Chapter 3: Execution modes

Every task in flyteTest reaches its actual work through a single helper:
`run_tool` in `src/flytetest/config.py`. That helper supports three mutually
exclusive execution modes, and choosing the right one is the most consequential
decision when you author a new task. This chapter shows each mode with a real
snippet from the repo and ends with a decision tree.

The three modes are:

1. **SIF / container** — invoke a tool inside an Apptainer/Singularity image.
2. **Native executable** — invoke a binary already on `PATH` (typically loaded
   via a cluster module).
3. **Python callable** — call a pure-Python function in-process; no
   subprocess, no container.

`run_tool` itself is a thin dispatcher; the signature documents the contract:

`src/flytetest/config.py:246`

```python
def run_tool(
    cmd: list[str] | None = None,
    sif: str = "",
    bind_paths: list[Path] | None = None,
    cwd: Path | None = None,
    stdout_path: Path | None = None,
    *,
    python_callable: Callable[..., Any] | None = None,
    callable_kwargs: dict[str, Any] | None = None,
) -> None:
```

If `python_callable` is set, mode 3 wins. Otherwise, a non-empty `sif` selects
mode 1; an empty `sif` selects mode 2.

## Mode 1 — SIF (containerized)

Use this when the tool ships in a curated container image — the typical case
for third-party bioinformatics binaries (GATK, bwa-mem2, SnpEff, BRAKER3,
FastQC). The image path is passed as the second argument; bind paths are
mounted read-write inside the container.

`src/flytetest/tasks/qc.py:35`

```python
run_tool(
    ["fastqc", "--quiet", str(left_path), str(right_path), "--outdir", str(out_dir)],
    fastqc_sif,
    [left_path.parent, right_path.parent, out_dir.parent],
)
```

The `fastqc_sif: str = ""` parameter on the task signature accepts the
container path at call time. The default registry value lives under
`execution_defaults.runtime_images` (see chapter 06). When `fastqc_sif` is
empty, this same call falls through into native mode.

When to use SIF mode:

- The tool has an upstream-curated container.
- You want bit-identical behavior across local laptops and the cluster.
- The cluster does not load the binary as a module.

## Mode 2 — Native executable

Use this when the binary is on `PATH` on the compute node, usually because the
cluster exposes it through `module load`. No container is started; `run_tool`
runs the command via `subprocess.run` directly.

The native form of a `run_tool` call is:

```python
run_tool(cmd, sif="", bind_paths=[])
```

In practice, every SIF-mode task in this repo doubles as a native-mode task by
leaving its `_sif` argument as the default empty string. `bcftools_stats` is a
representative example — its registry default ships an image, but a caller who
omits `bcftools_sif` and instead loads `bcftools/1.20` as a module gets the
same behavior at the binary level:

`src/flytetest/tasks/variant_calling.py:1144`

```python
run_tool(["bash", "-c", cmd_str], bcftools_sif, [vcf.parent, out_dir])
```

When `bcftools_sif == ""`, `run_tool` skips the container wrapping and
executes `bash -c` directly. To make a task native-only, declare the relevant
`module_loads` in its registry entry (see `AGENTS.md` for the
`DEFAULT_SLURM_MODULE_LOADS` extension pattern) and either keep `_sif` as an
optional fallback or drop it from the signature entirely.

When to use native mode:

- The binary is provided by a cluster module (`Rscript`, `samtools`,
  `bcftools`, custom compiled tools).
- No suitable container exists, or container overhead matters.
- Local development uses the same binary the cluster does.

## Mode 3 — Python callable

Use this when the task body is pure Python with no external binary
dependency: threshold filters, format converters, statistics aggregations,
small AST or text rewrites. `run_tool` invokes your function in-process and
returns; nothing else changes about the task wrapper shape.

`src/flytetest/tasks/variant_calling.py:1290`

```python
run_tool(
    python_callable=filter_vcf,
    callable_kwargs={
        "in_path": in_vcf,
        "out_path": out_vcf,
        "min_qual": min_qual,
        "stats": stats,
    },
)
```

The `cmd`, `sif`, and `bind_paths` arguments are ignored when
`python_callable` is set. The pure-logic helper (`filter_vcf` here, defined in
`src/flytetest/tasks/_filter_helpers.py`) stays free of Flyte types and is
unit-testable on its own.

In the registry entry for a Python-callable task, set
`runtime_images={}` and `module_loads=("python/3.11.9",)`. The Slurm preflight
(`check_offline_staging`) will not block submission on a missing image, and
the task does not need `apptainer/1.4.1` loaded.

When to use Python-callable mode:

- The logic is pure Python, no subprocess.
- You want plain `pytest` coverage of the logic with no harness or container.
- The task is a thin orchestration step around an existing repo helper.

## Decision tree

Walk this top to bottom; pick the first match.

1. Is the logic pure Python (no external binary)? **Python callable.**
2. Is there a curated container image for the tool? **SIF.**
3. Is the binary available on `PATH` via a cluster module? **Native.**
4. Otherwise: package the tool into a container and use **SIF**, or stop and
   ask for review — see `.codex/agent/architecture.md`.

## Forward pointers

Regardless of mode, every task wrapper still produces output files, calls
`require_path` on them, and writes a `run_manifest_<stage>.json` via
`build_manifest_envelope` — that contract is mode-independent.

- [Chapter 4: Manifests and outputs](04_manifests.md) — the manifest contract
  and `MANIFEST_OUTPUT_KEYS` enforcement.
- [Chapter 6: Registry entry deep-dive](06_registry.md) — declaring
  `runtime_images` (SIF mode) and `module_loads` (native and Python-callable).
