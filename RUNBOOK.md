# Runbook: billable runs

This is the checklist for the runs that cost money. Everything here is run by
you on your own machine. Nothing in this file was run during development: the
code was built and checked only with the offline `make test`.

"Billable" means a step uses one of two paid services:

- **Modal**, a cloud service that starts a temporary Linux machine (a
  "sandbox") where the agent's commands run, so they never touch your PC.
- **An LLM provider**, the service that answers the agent's model requests.
  The harness talks to it through the OpenAI-compatible Chat Completions API,
  so any provider that offers that API and the model below will work.

## Where to run it

Run every command in your WSL Ubuntu terminal, not in PowerShell. The
Makefile and `uv` expect a Linux shell. Clone the repo inside WSL (for
example under `~/projects/`), because builds on `/mnt/c` or `/mnt/d` are
slow.

## 0. One-time setup (free)

Install uv, the Python package manager the repo uses:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen the terminal, then from the repo folder:

```bash
make setup
```

Sign in to Modal. This opens a browser window and stores a token in
`~/.modal.toml`, outside the repo:

```bash
uv run modal setup
```

Create your secrets file. `.env` is listed in `.gitignore`, so git will not
pick it up, but never paste its contents anywhere:

```bash
cp .env.example .env
```

```bash
nano .env
```

Fill in the four values. You are not enrolled, so there are no course
credits: use your own account with a provider that serves
`deepseek/deepseek-v4-flash-0731` (Part 3 also needs `openai/gpt-oss-120b`).
Those ids follow the `vendor/model` naming that router-style providers use;
check the exact ids on your provider's model page (medium confidence that
they match as written).

```dotenv
OPENAI_BASE_URL=https://your-provider.example/v1
OPENAI_API_KEY=your-key
OPENAI_MODEL=deepseek/deepseek-v4-flash-0731
OPENAI_MAX_RETRIES=5
```

Check everything without spending anything. This validates the submodule,
Modal sign-in and the model endpoint without starting a sandbox or
generating tokens:

```bash
make doctor
```

```bash
make test
```

Before you start, set a spending limit on both the Modal dashboard and your
LLM provider's dashboard.

## 1. Part 1: repair the chess app (billable)

```bash
make run-code-agent
```

Produces `artifacts/fix.patch` and `artifacts/part1-trajectory.json`. Then
check the patch in a fresh sandbox:

```bash
make check-part1
```

If the check fails, rerun `make run-code-agent`; generation is random, so a
second try can succeed. The Part 3 runs need a passing `fix.patch`.

## 2. Part 2: compaction on a SWE-bench task (billable)

Compacted run, with a 6,000-token threshold:

```bash
COMPACT_THRESHOLD=6000 SWEBENCH_PATCH=artifacts/django__django-15368.patch SWEBENCH_TRAJECTORY=artifacts/django__django-15368-trajectory.json make run-swebench-agent INSTANCE=django__django-15368
```

```bash
make check-swebench INSTANCE=django__django-15368
```

Confirm it compacted at least once. This prints the number of compaction
events and the estimated tokens before and after each:

```bash
uv run python -c "import json; c=json.load(open('artifacts/django__django-15368-trajectory.json'))['compactions']; print(len(c)); [print(e['step'], e['estimated_tokens_before'], e['estimated_tokens_after']) for e in c]"
```

Full-context baseline (no compaction), saved under different names:

```bash
COMPACT_THRESHOLD=0 SWEBENCH_PATCH=artifacts/django__django-15368-baseline.patch SWEBENCH_TRAJECTORY=artifacts/django__django-15368-baseline-trajectory.json make run-swebench-agent INSTANCE=django__django-15368
```

Then write `artifacts/token-usage-analysis.md` comparing the two
trajectories. The `responses[*].usage.prompt_tokens` field in each
trajectory gives the real prompt size per step.

## 3. Part 3: chess agent (billable, after the Part 3 code is merged)

Do these only once the ChessAgent tools are merged and `make test` is fully
green.

```bash
make run-chess-agent
```

The observation experiment, four runs:

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

Then write `artifacts/observation-experiment.md`. Finally the skill run:

```bash
uv run assignment-play-chess --programmatic-tools --skills-path tasks/chess-skills --trajectory artifacts/part3-python-skill-trajectory.json
```

## After every session: check for leftover sandboxes

A crashed run can leave a sandbox running and billing. List them:

```bash
uv run modal container list
```

Stop any that are still listed, using the id from that list:

```bash
uv run modal container stop CONTAINER_ID
```

## If something fails

- `make doctor` fails on the endpoint: check `OPENAI_BASE_URL` (it usually
  ends in `/v1`) and the model id.
- Repeated TLS or download errors: that points to a VPN, proxy or antivirus,
  not the code. Check those before retrying.
- `StepLimitError`: the agent ran out of steps. Raise the budget with
  `STEPS=300` before the `make` command.
