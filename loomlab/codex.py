"""Codex app-server transport primitives.

This module deliberately models the stdio protocol without owning process
authentication yet. That keeps protocol parsing independently testable.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class CodexMessage:
    payload: dict[str, Any]

    def to_jsonl(self) -> str:
        return json.dumps(self.payload, separators=(",", ":")) + "\n"


def initialize_message(request_id: int = 1) -> CodexMessage:
    return CodexMessage(
        {
            "id": request_id,
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "loomlab_relaid",
                    "title": "LoomLab Relaid",
                    "version": "0.1.0",
                }
            },
        }
    )


def initialized_message() -> CodexMessage:
    return CodexMessage({"method": "initialized", "params": {}})


def thread_start_message(model: str, request_id: int) -> CodexMessage:
    return CodexMessage(
        {
            "id": request_id,
            "method": "thread/start",
            "params": {"model": model},
        }
    )


def thread_resume_message(thread_id: str, request_id: int) -> CodexMessage:
    return CodexMessage(
        {
            "id": request_id,
            "method": "thread/resume",
            "params": {"threadId": thread_id},
        }
    )


def turn_start_message(thread_id: str, text: str, request_id: int) -> CodexMessage:
    return CodexMessage(
        {
            "id": request_id,
            "method": "turn/start",
            "params": {
                "threadId": thread_id,
                "input": [{"type": "text", "text": text}],
            },
        }
    )


def parse_jsonl(lines: Iterable[str]) -> Iterable[dict[str, Any]]:
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        yield json.loads(line)


def agent_message_delta(event: dict[str, Any]) -> str | None:
    if event.get("method") != "item/agentMessage/delta":
        return None
    params = event.get("params", {})
    delta = params.get("delta")
    return delta if isinstance(delta, str) else None


def completed_status(event: dict[str, Any]) -> str | None:
    if event.get("method") != "turn/completed":
        return None
    params = event.get("params", {})
    turn = params.get("turn", {})
    status = turn.get("status")
    return status if isinstance(status, str) else None
