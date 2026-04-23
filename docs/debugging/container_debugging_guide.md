# Container Debugging Guide

Personal reference for diagnosing Apptainer/Singularity issues in HPC jobs.

---

## 1. Read the error path literally

When Apptainer fails to open an image, the full path in the error tells you
what it was actually trying to open — not what you *intended* to give it.

```
FATAL: could not open image /scratch/.../results/.tmp/busco_run_xxx/busco/data/images/tool.sif
```

Break the path apart:
- What is the prefix? (project root, tmp dir, home dir, cwd?)
- Where does the intended relative path start? (`data/images/tool.sif`)
- The prefix *is* whatever the process thought its cwd was.

---

## 2. Identify where the SIF path is resolved

Find the line that turns the SIF input into an absolute path.
Common patterns:

| Pattern | Risk |
|---|---|
| `Path(sif).resolve()` | Uses `os.getcwd()` — fragile if cwd changes |
| `str(Path(sif).absolute())` | Same risk |
| Passing a relative string directly to `apptainer exec` | Apptainer resolves it itself, using the *subprocess* cwd |
| `Path(__file__).resolve().parents[N] / sif` | Safe — anchored to source file location |

**Rule:** Never resolve a relative SIF path against cwd. Always anchor to something stable.

---

## 3. Understand what cwd is at each layer

There are three cwds that matter and they can all be different:

| Layer | Set by | Affects |
|---|---|---|
| Shell (sbatch script) | `cd repo_root` or `#SBATCH --chdir=` | The bash script's cwd |
| Python process | Inherited from shell at startup | `Path(...).resolve()`, `os.getcwd()` |
| Child subprocess | `subprocess.run(cwd=...)` | Only the child — never the parent Python process |

Gotcha: `subprocess.run(cmd, cwd=work_dir)` does **not** change the Python
process's cwd. Only the child process runs in `work_dir`. But if you call
`Path(sif).resolve()` *before* the subprocess, you're using the Python cwd,
which may or may not be what you want.

---

## 4. Check if Slurm changes cwd

By default, Slurm starts jobs in `$SLURM_SUBMIT_DIR` (the directory where
`sbatch` was called). If the job was submitted from somewhere other than the
project root, a `cd repo_root` in the script body fixes it.

Alternatively, add this to the sbatch directives to make it explicit:
```bash
#SBATCH --chdir=/absolute/path/to/project
```

The shell `cd` in the script body works too, but only after the shell starts —
the interpreter won't see the directive form.

---

## 5. Check bind paths

Apptainer only sees paths that are explicitly bound (`-B src:dest`).
If a bind path is missing, the container starts but the command silently
fails or produces "no such file" errors from inside.

Common oversights:
- The input data directory is not bound
- The output directory is not bound (writes fail silently)
- The SIF file itself does not need to be bound — it is opened by the host
- Bind paths must exist on the host before the container starts

Verify with `--bind` and check that source paths exist:
```bash
apptainer exec --cleanenv -B /data:/data /path/to/tool.sif tool --help
```

---

## 6. `--cleanenv` removes environment variables

`--cleanenv` strips the host environment inside the container. This is
usually correct for reproducibility, but it also removes:
- `$PATH` additions from module loads
- `$LD_LIBRARY_PATH`
- Any custom tool config env vars

If the tool fails with "command not found" or missing library errors inside
the container, check whether it depends on an env var that got stripped.
Pass needed vars explicitly with `--env VAR=value` or use `--env-file`.

---

## 7. Local reproduction before re-submitting to Slurm

Before submitting another job, reproduce the apptainer call locally on the
login node with the exact same arguments:

```bash
apptainer exec --cleanenv \
  -B /path/to/data:/path/to/data \
  -B /path/to/output:/path/to/output \
  /absolute/path/to/tool.sif \
  tool --arg1 val1
```

If it fails locally, fix it locally. Submitting to Slurm to test small changes
wastes queue time and introduces scheduler delays into your debug loop.

If the login node doesn't have Apptainer, use `--fakeroot` or an interactive
job (`srun --pty bash`) to get a compute node shell.

---

## 8. Check image integrity

If the image opens but the tool crashes immediately:
```bash
apptainer inspect /path/to/tool.sif          # check metadata
apptainer verify /path/to/tool.sif           # check signature if signed
apptainer exec tool.sif tool --version       # quick smoke test
```

If the pull was interrupted or the disk was full, the SIF file may be
truncated. Re-pull:
```bash
apptainer pull tool.sif docker://image:tag
```

---

## 9. Debuggable path vs fragile path

**Fragile:** the SIF path is a relative string stored in a config/bundle,
resolved at an arbitrary point in the call stack where cwd is unknown.

**Debuggable:** the SIF path is resolved to absolute as early as possible,
at a point where the cwd is known (or using an anchor that doesn't depend
on cwd at all).

Example of safe anchoring in Python:
```python
# config.py is at src/flytetest/config.py
# parents[2] is the project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

def resolve_sif(sif: str) -> str:
    p = Path(sif)
    return str(p if p.is_absolute() else PROJECT_ROOT / p)
```

---

## 10. Quick diagnostic checklist

- [ ] Does the absolute path in the error make sense? What prefix got added?
- [ ] Is the SIF file at the resolved path? (`ls -lh /resolved/path/tool.sif`)
- [ ] Does the container open at all? (`apptainer exec tool.sif echo ok`)
- [ ] Are all bind paths mounted and do they exist on the host?
- [ ] Is `--cleanenv` stripping something the tool needs?
- [ ] Did the sbatch job start in the expected directory? (check `pwd` in the sbatch script output)
- [ ] Is the SIF file complete? (check file size matches the expected image)
