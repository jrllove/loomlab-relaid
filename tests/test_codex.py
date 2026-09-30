import json

from loomlab.codex import (
    agent_message_delta,
    completed_status,
    initialize_message,
    parse_jsonl,
    thread_resume_message,
    thread_start_message,
    turn_start_message,
)


def test_initialize_identifies_loomlab() -> None:
    message = initialize_message(7)
    payload = json.loads(message.to_jsonl())

    assert payload["id"] == 7
    assert payload["method"] == "initialize"
    assert payload["params"]["clientInfo"]["name"] == "loomlab_relaid"


def test_thread_messages_are_explicit() -> None:
    start = thread_start_message("gpt-5-codex", 8).payload
    resume = thread_resume_message("thread-123", 9).payload
    turn = turn_start_message("thread-123", "hello", 10).payload

    assert start["method"] == "thread/start"
    assert resume["params"]["threadId"] == "thread-123"
    assert turn["params"]["input"][0]["text"] == "hello"


def test_event_helpers_extract_only_expected_events() -> None:
    assert (
        agent_message_delta(
            {"method": "item/agentMessage/delta", "params": {"delta": "hi"}}
        )
        == "hi"
    )
    assert agent_message_delta({"method": "other", "params": {"delta": "hi"}}) is None

    assert (
        completed_status(
            {"method": "turn/completed", "params": {"turn": {"status": "completed"}}}
        )
        == "completed"
    )


def test_parse_jsonl_skips_blank_lines() -> None:
    events = list(parse_jsonl(['{"a":1}\n', "\n", '{"b":2}\n']))

    assert events == [{"a": 1}, {"b": 2}]
