# AI usage (draft)

_Draft written by Claude for the owner to check and edit. Confirm each line
before submitting._

## Tools used

### Claude Code, through Claude Projects on claude.ai

- **What it is:** Anthropic's coding agent, run in cloud sessions from a
  claude.ai project. A coordinator session split the work into threads, and
  each thread worked on its own git branch and opened a pull request.
- **Model:** Claude Opus 5.5 (`claude-opus-5-5`). This is the model the Part 2
  thread ran on. _Owner: confirm the model for the other threads (Part 1 and
  Part 3) from their sessions._
- **How it was used:**
  - Part 1: wrote the shared ReAct loop in `base.py` (prompt building, loop,
    skill loading) and the `CodeAgent` tool executor in `code_agent.py`.
  - Part 2: wrote `compact_context`, the compaction system prompt, and the call
    to `maybe_compact_context` in the loop.
  - Part 3: wrote the `ChessAgent` tools in `chess_tools.py` and
    `chess_agent.py`.
  - Docs: wrote `RUNBOOK.md` (steps for the billable runs) and
    `HARNESS_WALKTHROUGH.md` (a plain-language explanation of the code), and
    drafted this file.
  - Ran the free offline test suite (`make test`) to check the code.
- **What it did not do:** it made no billable calls (no Modal sandboxes and no
  LLM API calls for the agent), did not handle credentials, and did not edit
  `tests/`, `tasks/` or `chess_app/`. The billable runs, the artifacts they
  produce, and the written reports (`token-usage-analysis.md`,
  `observation-experiment.md`) are _owner: fill in how these were produced_.

### Codex code review bot on GitHub

- Reviewed the pull requests on the fork automatically. _Owner: confirm, and
  say whether any of its suggestions were applied._

## How the work was checked

Each pull request was reviewed by the owner before merging. _Owner: describe
your own review and what you changed by hand, if anything._
