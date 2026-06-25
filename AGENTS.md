# Repository Guidance

## Project purpose

This repository supports a short research paper comparing replication-factor
behavior in CockroachDB and HDFS. Preserve reproducibility and distinguish
pipeline checks, preliminary local evidence, and paper-grade evidence.

## Start here

Before changing experiments or paper claims, read:

- `README.md`
- `docs/experiment_plan.md`
- `docs/project_status.md`
- `paper/data/preliminary/README.md`

## Working conventions

- Treat `results/` as generated local evidence. It is intentionally ignored by
  Git. Do not delete partial or failed runs unless the user explicitly asks.
- Keep diagnostic runs separate from publishable datasets. In particular,
  CockroachDB RF=9 local failures are evidence about the environment limit, not
  normal performance observations.
- Validate a completed result directory before analyzing or curating it.
- For CockroachDB, require the expected RF/ratio/repetition matrix, zero
  connect/read/write errors, readable load files, and metrics without error
  rows.
- For HDFS, require the expected RF/reader/repetition matrix and positive read
  and write measurements.
- Low achieved QPS is not automatically a failed run. Report it as saturation
  or an unmet target and avoid comparing it as if throughput were controlled.
- Use randomized run order for evidence-grade sweeps and retain metadata,
  command parameters, logs, and per-run outputs.
- Curate only compact CSV summaries into `paper/data/preliminary/`; do not
  commit the full `results/` tree.
- Regenerate figures with `scripts/plot_preliminary_figures.py` after curated
  CSV changes. Keep prose, tables, captions, and plots numerically consistent.
- Do not strengthen paper claims beyond the quality of the underlying runs.
  Local Docker results have shared-host, cache, placement, and scheduler limits.

## Standard checks

CockroachDB:

```powershell
py scripts\validate_results.py --kind cockroach --results-dir <dir> --expected-rfs <rfs> --expected-ratios <ratios> --expected-repetitions <n>
py experiments\cockroach\analyze_results.py --results-dir <dir>
```

HDFS:

```powershell
py scripts\validate_results.py --kind hdfs --results-dir <dir> --expected-rfs <rfs> --expected-readers <readers> --expected-repetitions <n>
py experiments\hdfs\analyze_results.py --results-dir <dir>
```

Run syntax or targeted checks for any modified Python files. Inspect
`git status --short` before handoff and preserve unrelated user changes.

## Environment notes

- The main local CockroachDB setup has nine containers.
- The local HDFS setup has one NameNode, five DataNodes, and one client.
- On Windows, prefer `py` because `python` may resolve to the Microsoft Store
  alias.
- Git may not be on `PATH`; the standard installation is commonly available at
  `C:\Program Files\Git\cmd\git.exe`.
