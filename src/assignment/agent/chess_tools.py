"""Chess tool implementations, decoupled from the agent that registers them.

Every function here takes the HTTP client explicitly instead of reading it off
an agent, so the same code can run in the agent process or inside the sandbox
beside the server it talks to.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

CHESS_PORT = 8000


def _request_state(
    client: httpx.Client, method: str, endpoint: str, **kwargs: Any
) -> dict[str, Any]:
    """Make one chess API request and validate its JSON response."""

    response = client.request(method, endpoint, **kwargs)
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Chess server returned non-JSON ({response.status_code})."
        ) from exc
    if response.status_code >= 400:
        detail = (
            payload.get("detail", payload) if isinstance(payload, dict) else payload
        )
        raise ValueError(str(detail))
    if not isinstance(payload, dict):
        raise RuntimeError("Chess server response must be a JSON object.")
    return payload


def _error(message: str) -> str:
    """Wrap a problem as an observation the model can read and recover from."""

    return f"<chess_error>{message}</chess_error>"


def _parse_arguments(name: str, arguments: str) -> dict[str, Any]:
    """Decode one tool call's raw JSON arguments into a dict, or raise ValueError."""

    try:
        parsed = json.loads(arguments or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Arguments for {name} are not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Arguments for {name} must be a JSON object.")
    return parsed


def _call_server(client: httpx.Client, endpoint: str, payload: dict) -> str:
    """POST to the chess API and return its JSON, or a <chess_error>."""

    try:
        state = _request_state(client, "POST", endpoint, json=payload)
    except ValueError as exc:  # The server rejected the position or move.
        return _error(f"Rejected by the chess server: {exc}")
    except (httpx.HTTPError, RuntimeError) as exc:  # Transport or bad reply.
        return _error(f"Could not reach the chess server: {exc}")
    return json.dumps(state)


def _simulate_move(client: httpx.Client, arguments: str) -> str:
    """New tool: inspect FEN or simulate one ply without changing the game.

    Takes the raw JSON arguments of one tool call and returns the observation
    to send back, so a bad argument or a server error reaches the model as a
    recoverable ``<chess_error>`` instead of ending the run.
    """
    try:
        parsed = _parse_arguments("simulate_move", arguments)
    except ValueError as exc:
        return _error(str(exc))
    fen, move = parsed.get("fen"), parsed.get("move")
    if not isinstance(fen, str) or not fen:
        return _error("simulate_move needs a non-empty `fen` string.")
    if move is not None and not isinstance(move, str):
        return _error("simulate_move `move` must be a UCI string or null.")
    return _call_server(client, "/api/simulate", {"fen": fen, "move": move})


def _play_move(client: httpx.Client, arguments: str) -> str:
    """Existing tool: play one move as White and return the resulting state.

    Takes the raw JSON arguments of one tool call. Returns the new state, or a
    `<chess_error>` observation if the move could not be played.
    """
    try:
        parsed = _parse_arguments("play_move", arguments)
    except ValueError as exc:
        return _error(str(exc))
    move = parsed.get("move")
    if not isinstance(move, str) or not move:
        return _error("play_move needs a `move` string in UCI notation, e.g. e2e4.")
    return _call_server(client, "/api/move", {"move": move})


def _run_python(env: Any, port: int, arguments: str) -> str:
    """New tool: run Python with access to the existing registered tools.

    The snippet runs inside the sandbox, which already has the tool
    implementations and the chess server, so code the model wrote never
    executes in the agent process.
    """
    try:
        parsed = _parse_arguments("run_python", arguments)
    except ValueError as exc:
        return _error(str(exc))
    code = parsed.get("code")
    if not isinstance(code, str) or not code.strip():
        return _error("run_python needs a non-empty `code` string.")

    # Base64 keeps quotes, newlines, and $ in the code away from the shell.
    encoded = base64.b64encode(code.encode()).decode()
    result = env.execute(
        ["python", "/opt/assignment/sandbox_python.py", str(port), encoded],
        shell=False,
    )
    if result.get("returncode") != 0:
        detail = result.get("exception_info") or result.get("stderr") or "unknown failure"
        return _error(f"The Python sandbox failed: {detail}")
    # The runner's JSON (stdout, stderr, error) goes back unchanged.
    return result.get("stdout", "")


def _invoke_skill(skills: dict[str, dict[str, str]], arguments: str) -> str:
    """Existing tool: load one skill's instructions into the conversation."""
    try:
        parsed = _parse_arguments("invoke_skill", arguments)
    except ValueError as exc:
        return _error(str(exc))
    name = parsed.get("name")
    if not isinstance(name, str):
        return _error("invoke_skill needs a `name` string.")
    skill = skills.get(name)
    if skill is None:
        return _error(f"Unknown skill {name!r}. Available skills: {', '.join(sorted(skills))}.")
    return skill["content"]


def _game_state(client: httpx.Client, reset: bool = False) -> dict:
    """Read the live game, or start a new one and read the opening position."""

    method, endpoint = ("POST", "/api/reset") if reset else ("GET", "/api/state")
    return _request_state(client, method, endpoint)
