# Runbook: billable runs

These are the steps for the runs that cost money (Modal sandboxes and LLM
tokens). Run them yourself, on your own machine, in WSL Ubuntu, from the repo
folder. Nothing here was run by Claude.

Each command is in its own block. Run them in order, and check the result
before moving on.

## 0. One-time setup

Install the Python environment and check the pinned submodules.

```bash
make setup
```

Sign in to Modal. This opens a browser.

```bash
uv run modal setup
```

Create your secrets file, then open `.env` in an editor and fill in
`OPENAI_BASE_URL` and `OPENAI_API_KEY`. Never commit `.env` (it is already in
`.gitignore`).

```bash
cp .env.example .env
```

Check Modal sign-in and the model endpoint without spending tokens.

```bash
make doctor
```

Confirm the free offline tests pass before spending anything. All tests should
pass once Part 3 is merged; until then, the 3 chess tests fail.

```bash
make test
```

## Safety check before and after every run

A crashed run can leave a sandbox running and burning credits. List them:

```bash
uv run modal container list
```

If one is left over, stop it with `uv run modal container stop` followed by its
container ID from the list.

## Part 1: repair the chess app

Run the coding agent. It writes `artifacts/fix.patch` and
`artifacts/part1-trajectory.json`.

```bash
make run-code-agent
```

Check the patch in a fresh testbed. Passing tests means Part 1 is done.

```bash
make check-part1
```

## Part 2: compaction on SWE-bench

Run the compacted agent (threshold 6,000 tokens is the Makefile default).

```bash
make run-swebench-agent INSTANCE=django__django-15368 COMPACT_THRESHOLD=6000
```

Check that the run compacted at least once. This prints the number of
compaction events and the estimated tokens before and after each one.

```bash
uv run python -c "import json; t=json.load(open('artifacts/django__django-15368-trajectory.json')); c=t['compactions']; print(len(c), [(e['estimated_tokens_before'], e['estimated_tokens_after']) for e in c])"
```

If it printed `0`, the run never compacted and does not count; run it again.

Check the patch against the SWE-bench tests.

```bash
make check-swebench INSTANCE=django__django-15368
```

Run the full-context baseline, saved under different names so it does not
overwrite the compacted run.

```bash
make run-swebench-agent INSTANCE=django__django-15368 COMPACT_THRESHOLD=0 SWEBENCH_PATCH=artifacts/django__django-15368-baseline.patch SWEBENCH_TRAJECTORY=artifacts/django__django-15368-baseline-trajectory.json
```

Compare token usage from both trajectories (each response's `usage` field), and
write your notes in `artifacts/token-usage-analysis.md`. This step is free.

## Part 3: chess (after the Part 3 branch is merged)

All chess runs need `artifacts/fix.patch` from Part 1.

Basic game. Writes `artifacts/part3-trajectory.json` and
`artifacts/game-result.json`. The printed HTTPS link shows the live board.

```bash
make run-chess-agent
```

The observation experiment, four runs.

```bash
make run-obs-deepseek-no-legal
```

```bash
make run-obs-deepseek-legal
```

```bash
make run-obs-gpt-oss-no-legal
```

```bash
make run-obs-gpt-oss-legal
```

Write the comparison in `artifacts/observation-experiment.md` (free).

Skill plus Python run. The command in ASSIGNMENT.md leaves out `--patch`, which
the CLI requires, and would overwrite `game-result.json`, so this version adds
both.

```bash
uv run assignment-play-chess --programmatic-tools --skills-path tasks/chess-skills --patch artifacts/fix.patch --trajectory artifacts/part3-python-skill-trajectory.json --result artifacts/part3-python-skill-result.json
```

## Finish

Run the container check above one last time, then build the submission ZIP
from `src/`, `artifacts/` and `AI_USAGE.md`. Leave out `.env`.
