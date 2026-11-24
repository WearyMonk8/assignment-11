# Harness walkthrough

A plain-language tour of how the agent works, so you can explain the code.
Files named here live in `src/assignment/agent/`.

## The big idea

A language model only produces text. A *harness* turns that into an agent: it
shows the model the task, lets it ask for actions (tool calls), runs those
actions, and shows the model what happened. This repeats until the model says it
is done. That cycle is called ReAct: **re**ason, **act**, observe, repeat.

There is one loop, in `base.py` (`Agent.run`). The two agents, `CodeAgent` and
`ChessAgent`, do not have their own loops. They only supply:

- their tools (what the model may call),
- their opening messages (system prompt and task), and
- `execute_tool_calls`, which actually runs a tool call.

## What the model sees each step (`build_prompt`)

Every request is rebuilt from scratch from three pieces:

1. **System message**: standing instructions (for `CodeAgent`: you are in a
   terminal at `/testbed`, plus a short catalog of skills if any were loaded).
2. **Task message**: the problem to solve, as if a user asked it.
3. **History** (`self.history`): everything since, in order. Each assistant
   message (the model's reasoning and tool calls) is followed by one `tool`
   message per call, linked by `tool_call_id`.

Because the prompt is rebuilt from state, `build_prompt` never changes anything.
Compaction (below) works by changing `self.history`.

## One trip around the loop (`Agent.run`)

1. **Step limit**: if the agent has already used its budget of model calls,
   stop with `StepLimitError`.
2. **Maybe compact**: if the prompt has grown past the threshold, shrink old
   history into a summary (Part 2).
3. **Ask the model** (`query_language_model`): send the prompt and tool list,
   record the request and response for the trajectory, and get back an
   assistant message.
4. **Remember it**: append that message to history.
5. **Act and observe**:
   - If it made tool calls, the subclass runs each one and returns one linked
     observation per call. Those go into history.
   - If it only wrote text, nothing runs. The harness adds a short user message
     nudging it to call a tool, so the next step makes sense.
6. **Done?** A tool such as `send_message` (code) or a finished game (chess)
   sets `self.finished`, which ends the loop.

Whatever happens, the `finally` block saves the trajectory (every prompt,
response and compaction) and stops the Modal sandbox, so a crash never leaves a
paid sandbox running or loses the log.

## How `CodeAgent` runs tools (`code_agent.py`)

- `execute`: runs a shell command in the sandbox. Output is formatted into
  tagged text. Anything over 10,000 characters keeps its start and end and
  notes how much was cut, so one big file cannot flood the prompt.
- `send_message`: means "I'm done". It sets `finished`; the harness then reads
  `patch.txt` as the submitted fix.
- `invoke_skill`: only offered when skills were loaded. The prompt lists just
  each skill's name and description; this tool returns the full skill text when
  the model asks for it (progressive disclosure).

Mistakes become observations, not crashes: an unknown tool, bad JSON
arguments, or a missing command come back as an `<error>` message, so the model
can see what went wrong and try again.

## Skills (`load_skills`)

Each folder under the skills path holds a `SKILL.md` that starts with YAML
frontmatter (`name`, `description`). Loading checks every folder, and refuses a
missing file, broken frontmatter, or a duplicate name with a clear error.

## Compaction (Part 2)

Long runs make the prompt long, which costs more and can overflow the model's
context window. Compaction swaps the old part of the history for a short,
model-written summary ("working memory").

- **When** (`maybe_compact_context`, provided): before each new action, the
  harness estimates the prompt size. Over the threshold, and with more than the
  number of recent steps to keep, it compacts and logs an event with the size
  before and after.
- **How** (`compact_context`, written in Part 2):
  1. Split history into an *old prefix* and the *recent steps*. A step starts
     at an assistant message and includes every tool observation after it, so
     the newest action always keeps its linked results intact.
  2. Turn the old prefix into plain text and send it, with the task, to the
     model under `COMPACTION_SYSTEM_PROMPT`. That prompt asks for factual notes
     under fixed headings: objective, constraints, files, commands, edits,
     results, failed approaches, tests, blockers and next action.
  3. Replace history with one user message holding the summary, followed by
     the recent steps. The system and task messages are untouched because
     `build_prompt` always adds them back in front.
- If the model returns an empty summary, history is left as it was (losing
  information is worse than a longer prompt), and the next step tries again.
- A later compaction simply summarizes the earlier summary along with the newer
  old steps.

Trade-off to remember: compaction saves tokens on every later step, but each
compaction is an extra model call, and details left out of the summary are gone
for good.

## Where `ChessAgent` fits (Part 3)

Same loop, different tools: `play_move`, then `simulate_move` and `run_python`
for planning in code. Its tool code lives in `chess_tools.py` so it can run in
the sandbox too.
