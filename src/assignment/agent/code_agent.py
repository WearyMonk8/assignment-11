"""The Part 1 coding agent: fix a software issue and submit a git patch."""

from __future__ import annotations

import json
from typing import Any

from assignment.agent.base import (
    DEFAULT_COMPACTION_KEEP_RECENT_STEPS,
    DEFAULT_COMPACTION_MAX_TOKENS,
    Agent,
    format_tool_output,
)
from assignment.agent.tools import EXECUTE_TOOL, SEND_MESSAGE_TOOL
from assignment.env import Environment

# Optional `execute` arguments the model may override. Anything it leaves out
# or sends as null falls back to Environment.execute's defaults.
EXECUTE_OPTIONS = ("shell", "cwd", "timeout", "env")

# Result keys shown to the model. `output` already holds stdout followed by
# stderr, so the separate `stdout` and `stderr` streams would only repeat it.
OBSERVATION_KEYS = ("output", "returncode", "exception_info")

SYSTEM_PROMPT_TEMPLATE = """You are a software engineering agent working in a Linux sandbox. You fix
issues in the repository at {cwd} by running shell commands.

<system_information>
{{
  "machine": {machine},
  "release": {release},
  "system": {system},
  "version": {version}
}}
</system_information>

How to work:
- Act only through tool calls. Use `execute` to run one bash command per call.
- Each command runs in a fresh subshell, so `cd` and `export` do not persist.
  Pass `cwd` or `env` instead.
- First reproduce the problem, then make the smallest change that fixes it,
  then verify the fix by rerunning the reproduction and the relevant tests.
- Keep output short: read files in ranges and filter long logs.
- Do not modify tests to make them pass.
- When you are done, call `send_message` with a summary of what you changed.
  You cannot do any more work after calling it."""

SKILLS_PROMPT_TEMPLATE = """

Reusable skills are available. Call `invoke_skill` with a skill's name to load
its full instructions, and follow them in place of your default approach.

<skills>
{catalog}
</skills>"""

TASK_PROMPT_TEMPLATE = """Resolve the following issue in the repository at {cwd}.

<issue>
{task}
</issue>"""


class CodeAgent(Agent):
    """An agent that fixes a software issue and submits a git patch."""

    def __init__(
        self,
        task: str,
        environment: Environment,
        model: str | None = None,
        logs_save_path: str | None = None,
        step_limit: int = 100,
        skills_path: str | None = None,
        auto_stop_environment: bool = True,
        compact_threshold_tokens: int | None = None,
        compaction_keep_recent_steps: int = DEFAULT_COMPACTION_KEEP_RECENT_STEPS,
        compaction_max_tokens: int = DEFAULT_COMPACTION_MAX_TOKENS,
    ):
        super().__init__(
            environment=environment,
            model=model,
            logs_save_path=logs_save_path,
            step_limit=step_limit,
            skills_path=skills_path,
            auto_stop_environment=auto_stop_environment,
            compact_threshold_tokens=compact_threshold_tokens,
            compaction_keep_recent_steps=compaction_keep_recent_steps,
            compaction_max_tokens=compaction_max_tokens,
        )
        self.task = task
        self.submitted_patch = ""

        # TODO(Part 1.3): Make the `execute` and `send_message` tools available
        # to the agent.
        self.tools.extend([EXECUTE_TOOL, SEND_MESSAGE_TOOL])

        # TODO(1.1.b): Construct the system prompt and task_prompt. These
        # should be usable by the `Agent.build_prompt` method.
        # json.dumps renders each value as a JSON string inside the block.
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            cwd=environment.cwd,
            machine=json.dumps(environment.machine),
            release=json.dumps(environment.release),
            system=json.dumps(environment.system),
            version=json.dumps(environment.version),
        )
        # TODO(1.4): If any skills are available to the agent, make their
        # descriptions/metadata available to the agent in the prompt.
        # Only the short metadata goes here; the full body is revealed by
        # invoke_skill (progressive disclosure).
        if self.skills:
            catalog = "\n\n".join(skill["metadata"] for skill in self.skills.values())
            self.system_prompt += SKILLS_PROMPT_TEMPLATE.format(catalog=catalog)

        self.task_prompt = TASK_PROMPT_TEMPLATE.format(cwd=environment.cwd, task=task)

    def execute_tool_calls(
        self, tool_calls: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        """Execute ``execute`` and ``send_message`` calls in the code sandbox."""

        # TODO(Part 1.3): Parse each call, execute recognized tools, and return
        # one message per call (there may be multiple tool calls in one agent
        # response!). Malformed JSON and unknown tools must become recoverable
        # observations relayed to the agent instead of exceptions.
        return [
            {
                "role": "tool",
                "tool_call_id": call.get("id", ""),
                "content": self._run_tool_call(call),
            }
            for call in tool_calls
        ]

    def _run_tool_call(self, call: dict[str, Any]) -> str:
        """Run one tool call and return its observation text.

        Any problem with the call itself comes back as an <error> observation,
        so the model can see what went wrong and try again.
        """

        if self.finished:
            return "<error>The task was already submitted; this call was not run.</error>"

        function = call.get("function") or {}
        name = function.get("name")
        known = {tool["function"]["name"] for tool in self.tools}
        if name not in known:
            return f"<error>Unknown tool {name!r}. Available tools: {', '.join(sorted(known))}.</error>"

        try:
            arguments = json.loads(function.get("arguments") or "{}")
        except json.JSONDecodeError as exc:
            return f"<error>Arguments for {name} are not valid JSON: {exc}</error>"
        if not isinstance(arguments, dict):
            return f"<error>Arguments for {name} must be a JSON object.</error>"

        if name == "execute":
            command = arguments.get("command")
            if not isinstance(command, (str, list)) or not command:
                return "<error>execute needs a non-empty `command` string or list.</error>"
            options = {
                key: arguments[key]
                for key in EXECUTE_OPTIONS
                if arguments.get(key) is not None
            }
            result = self.env.execute(command, **options)
            return format_tool_output(
                {key: result[key] for key in OBSERVATION_KEYS if key in result}
            )

        if name == "send_message":
            # Submitting ends the run; the harness reads patch.txt afterwards.
            self.finished = True
            return "Message sent. The task is complete."

        # invoke_skill: the only other tool, registered by Agent when skills exist.
        skill = self.skills.get(arguments.get("name"))
        if skill is None:
            return (
                f"<error>Unknown skill {arguments.get('name')!r}. "
                f"Available skills: {', '.join(sorted(self.skills))}.</error>"
            )
        return skill["content"]
