# Harness walkthrough

This explains, in plain language, how the agent harness works. File and
method names are given so you can follow along in the code.

## The idea in one paragraph

A language model only turns text into more text. A harness lets it *do*
things. The harness shows the model the task and what has happened so far,
the model replies with an action (a "tool call", such as "run this shell
command"), the harness runs that action, and the result (an "observation")
is added to what the model sees next time. Repeating "reason, act, observe"
is called **ReAct**. That is the whole loop.

## The pieces

| Piece | Where | What it does |
|---|---|---|
| `Agent` | `src/assignment/agent/base.py` | The shared loop. Knows nothing about code or chess. |
| `CodeAgent` | `src/assignment/agent/code_agent.py` | Adds coding tools: `execute` (run a shell command) and `send_message` (say "done"). |
| `ChessAgent` | `src/assignment/agent/chess_agent.py` | Adds chess tools such as `play_move`. Reuses the same loop. |
| Environment | `src/assignment/env.py` | The Modal sandbox where commands really run. |
| Skills | `tasks/code-skills/`, `tasks/chess-skills/` | Extra instructions the model can load on demand. |

The split matters: `Agent` decides *when* things happen, and each subclass
decides *what its tools do*. The loop is written once, in `Agent.run`, and
the subclasses never copy it.

## What the model sees each step (`build_prompt`)

Chat models take a list of messages, each with a role:

1. **system**: standing instructions (the rules, the machine it is on, the
   list of available skills).
2. **user**: the task, for example the bug report to fix.
3. **user, only after compaction**: the working memory (see below).
4. **history**: every assistant message so far, each followed by one
   **tool** message per tool call it made. A tool message carries the same
   `tool_call_id` as its call, which is how the model matches results to
   actions.

`build_prompt` rebuilds this list from scratch every step and changes
nothing, so calling it is always safe.

## The loop (`Agent.run`)

Each pass through the `while` loop does this:

1. **Check the budget.** If `step_limit` model calls have been used, stop
   with `StepLimitError` so a confused agent cannot run forever.
2. **Compact if needed.** Call `maybe_compact_context()` (Part 2, below).
3. **Ask the model.** `query_language_model()` sends the prompt plus the
   tool definitions and returns the assistant's message.
4. **Record it.** The message goes onto `history`.
5. **Act and observe.** If the message has tool calls, the subclass's
   `execute_tool_calls()` runs them and returns one tool message per call,
   which also go onto `history`. If the model replied with plain text and
   no tool call, the harness adds a short user nudge ("call a tool") so the
   conversation stays valid and the model gets back on track.
6. **Stop when done.** The subclass sets `finished = True` when the task is
   over (for `CodeAgent`, when the model calls `send_message`).

Whatever happens, the `finally` block saves the full trajectory (every
prompt, response and compaction) to a JSON file and shuts the sandbox down,
so a crash never leaves a sandbox running or loses the log.

## Mistakes become observations, not crashes

If the model calls a tool that does not exist, sends broken JSON arguments,
or passes the wrong type, `CodeAgent` returns an `<error>...</error>`
observation instead of raising. The model reads the error and tries again,
the way a person would after a typo. Long command output is trimmed in the
middle (`format_tool_output`) so one huge file cannot flood the prompt.

## Skills: progressive disclosure

The system prompt lists only each skill's name and one-line description.
When the model wants the full instructions, it calls `invoke_skill` with the
name, and the whole `SKILL.md` comes back as an observation. This keeps the
prompt short until a skill is actually needed. `load_skills` reads the
skill folders and rejects missing, malformed or duplicate ones.

## Compaction: keeping the prompt small (Part 2)

Every step adds to `history`, so the prompt keeps growing. Long prompts cost
more and eventually do not fit. Compaction replaces old steps with a short
summary the model writes itself, called **working memory**.

How it works:

1. Before each step, `maybe_compact_context()` estimates the prompt size. If
   it is under `compact_threshold_tokens`, or there are too few steps to
   compact, nothing happens.
2. Otherwise `compact_context()` splits `history` in two:
   - an **old prefix**, to be summarized;
   - a **recent tail**: the latest `compaction_keep_recent_steps` steps,
     each an assistant action together with all of its tool results. These
     are kept word for word, so the model still sees exactly what it just
     did and what happened.
3. It sends a separate model request (with no tools) containing a summary
   instruction (`COMPACTION_SYSTEM_PROMPT`), the task, any earlier working
   memory, and the old prefix written out as plain text. The instruction
   asks for short factual notes under fixed headings: objective,
   constraints, files, commands, edits, results, failed approaches, tests,
   blockers and next action.
4. The reply becomes the new `working_memory`, and the old prefix is dropped
   from `history`. The next prompt is: system, task, working memory, recent
   tail. The system and task messages are never changed.
5. If the model returns an empty summary, nothing is dropped, so no
   information is lost silently.

Each later compaction folds the previous working memory into the new one,
so there is only ever one summary. Every compaction is logged with its
before and after size, which is how you can show it actually shrank the
prompt.

The trade-off: compaction saves tokens on every later step, but costs one
extra model call each time it runs, and a summary can leave out a detail
the agent later needs.

## Checking it without spending money

`make test` runs the unit tests with a fake model and a fake sandbox, so it
is free and offline. The real runs are in `RUNBOOK.md`.
