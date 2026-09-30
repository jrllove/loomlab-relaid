import pytest

from loomlab.relay import Agent, Relay


def test_resolve_known_agent() -> None:
    relay = Relay([Agent("scribe", "Scribe", "review")])

    agent = relay.resolve("scribe")

    assert agent.display_name == "Scribe"


def test_unknown_agent_fails_closed() -> None:
    relay = Relay([])

    with pytest.raises(ValueError, match="Unknown agent"):
        relay.resolve("forge")
