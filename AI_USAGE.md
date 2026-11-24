# AI usage (draft)

> Draft written by Claude for the owner to review and edit. Items marked
> **(confirm)** need checking before this is final.

Most of the code and documentation in this submission was written by AI.
I directed the work, set the rules, and reviewed each change before merging.

## Tools used

### Claude Code Projects (Anthropic)

Claude Code running in the cloud, organized as a project with one
coordinating session and several work threads, each on its own git branch
and pull request.

- **Coordinator session:** split the assignment into waves, started the
  threads, and reported status to me. Wave 1 ran Part 1 and Part 3 in
  parallel; Wave 2 ran Part 2 after Part 1 merged, because both touch
  `base.py`.
- **Part 1 thread:** implemented the shared ReAct loop, prompt building and
  skill loading in `base.py`, and the `CodeAgent` tools.
- **Part 2 thread:** implemented context compaction in `base.py`, and wrote
  `RUNBOOK.md`, `HARNESS_WALKTHROUGH.md` and this draft.
- **Part 3 thread:** implemented the `ChessAgent` tools. **(confirm status)**

Rules I gave every thread: no credentials, no billable calls (no Modal
sandboxes, no LLM API calls), no edits to `tests/`, `tasks/` or
`chess_app/`, no hard-coded solutions, and no copy of the shared loop.
The AI checked its work only with the offline `make test`.

### Models

- Claude Opus 5.5: Part 2 thread. **(confirm the models for the
  coordinator and the Part 1 and Part 3 threads in each session's details)**

### Automated PR review

- A Codex review bot commented on pull requests in this repository.
  **(confirm)**

## What I did myself

- Ran all billable steps myself, following `RUNBOOK.md`: the code agent,
  SWE-bench and chess runs, and the checks on their patches. **(confirm
  once done)**
- Wrote or reviewed the analysis reports (`artifacts/token-usage-analysis.md`
  and `artifacts/observation-experiment.md`). **(confirm who wrote them)**
- Reviewed and merged each pull request.

## Context

I am not enrolled in the course. This was done for learning, with no
grading or course credit.
