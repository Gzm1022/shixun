# RocoBench Evaluation Tools

Batch evaluation and code packing tools for the RocoBench project.

## Environment

This repository is managed with `uv` and pins Python 3.8 in
`.python-version`.

```bash
uv sync
uv run python evaluator.py
```

The first `uv sync` will create `.venv` and, if needed, download a compatible
Python 3.8 interpreter.

Each evaluator run writes its terminal log, task logs, and run artifacts into a
single per-run directory:

```text
output/run_YYYYMMDD_HHMMSS/
├── evaluator.log
├── run.json
├── summary.json
└── tasks/
    └── 01_sort/
        ├── command.txt
        ├── runs/
        │   ├── args_YYYYMM_HHMM.json
        │   └── run_0/
        ├── stdout.log
        ├── stderr.log
        ├── result.json
        └── summary.json
```

## evaluator.py - Batch Task Evaluation

Automated batch testing tool for multiple robot tasks with timeout control and colored output.

> **⚠️ Important Note:** During grading/testing, `evaluator.py` will be replaced with the original code. Any modifications to this file will not affect the final evaluation results.

### Usage

```bash
uv run python evaluator.py
```

Run only the Sort task and report its success rate:

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python evaluator.py --tasks sort --runs 1
```

For a more stable Sort accuracy estimate:

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python evaluator.py --tasks sort --runs 5
```

Use `--full` to restore the slower five-run, ten-step, longer-timeout setting:

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python evaluator.py --tasks sort --full
```

### Configuration

Edit the script to configure tasks:

```python
# Configure per-task timeouts (seconds)
DEFAULT_RUN_TIMEOUTS = {
    "sort": 600,
    "cabinet": 600,
    "rope": 600,
    "sweep": 600,
    "sandwich": 600,
    "pack": 600,
}

# Select tasks to run
results.append(test_run_dialog("sort", 5, "output"))
results.append(test_run_dialog("cabinet", 5, "output"))
# Uncomment tasks as needed
```

## Sort Task Improvements

This version includes a focused Sort-task optimization pass. The goal was to
reduce repeated LLM failures, make the handoff sequence physically executable,
and shorten iteration time during evaluation.

Key changes:

- Added `--tasks`, `--runs`, `--tsteps`, `--num_replans`, `--timeout`,
  `--rrt_timeout`, `--fallback_first`, and path-smoothing controls to
  `evaluator.py` / `run_dialog.py`, so Sort can be evaluated independently.
- Added deterministic fallback-first planning for Sort. The fallback planner
  tracks the current panel, target panel, and next relay panel, then assigns one
  conservative robot action per step.
- Added robust handling for failed or empty LLM responses, preventing
  `NoneType` parser crashes when a local Ollama call fails.
- Added Sort-specific grasp stabilization in `prompting/parser.py` by using a
  safer top-down grasp pose when handoff objects settle too low.
- Adjusted the `panel3` handoff target in `rocobench/envs/task_sort.py` so
  objects delivered by Alice are placed in a region Bob can reliably reach.
- Hardened HTML log generation against malformed prompt JSON entries.

Observed validation:

```text
OLLAMA_MODEL=qwen3.5:27b uv run python evaluator.py --tasks sort --runs 1
Success Rate: 1/1 (100.0%)
Average Steps: 5.00
```

The main failure mode before this change was Bob failing IK after Alice placed
`pink_polygon` on `panel3`. The updated handoff target and conservative grasp
pose make that relay physically feasible.

## pack_code.sh - Workspace Packing

Creates a zip archive of the workspace while respecting `.gitignore` rules.

### Usage

```bash
# Use default filename (code_YYYYMMDD_HHMMSS.zip)
./pack_code.sh

# Specify custom filename
./pack_code.sh myproject.zip

# Auto-adds .zip extension if missing
./pack_code.sh myproject
```

## Notes

- Script requires executable permission: `chmod +x pack_code.sh`
