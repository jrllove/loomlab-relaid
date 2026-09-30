# Chat Bridge Architecture

## Purpose

LoomLab Relaid should let John collaborate with two named generalist ChatGPT
agents, **Scribe** and **Forge**, from a shared Discord room.

Ordinary ChatGPT Chat is the primary reasoning surface. Codex is a specialist
coding service invoked when advantageous, not the default conversational engine.

## Design principles

1. **Chat first.** Scribe and Forge primarily operate through persistent normal
   ChatGPT conversations.
2. **Codex is a specialist.** Coding-intensive tasks may be delegated to the
   already-proven Codex app-server identities.
3. **Electric Sheep is the mind layer.** Memory, retrieved context, project
   history, decisions, and model-independent continuity live outside the model.
4. **Discord is the human control plane.** Discord is an input/output transport,
   not the internal source of truth.
5. **LoomLab owns routing and policy.** Models do not decide whether privileged
   actions are allowed.
6. **Browser automation is replaceable.** ChatGPT-specific browser behavior is
   isolated behind a small adapter.
7. **Failure should be visible.** Unknown browser states halt and escalate rather
   than triggering heroic recovery loops.

## Target architecture

```text
                    Discord
                       |
                       v
                +--------------+
                | LoomLab Relay|
                +------+-------+
                       |
           +-----------+-----------+
           |                       |
           v                       v
     Scribe Session           Forge Session
           |                       |
    Electric Sheep             Electric Sheep
           |                       |
           v                       v
    Browser Adapter            Browser Adapter
           |                       |
           v                       v
      ChatGPT Chat             ChatGPT Chat
           |                       |
           +-----------+-----------+
                       |
              specialist requests
                       |
           +-----------+-----------+
           |                       |
       Scribe Codex             Forge Codex
           |                       |
           +-----------+-----------+
                       |
                  Git / GitHub
```

## Browser stack

Preferred stack for the MVP:

- Playwright
- persistent Chromium profiles
- one profile per named ChatGPT seat
- LoomLab Chrome extension
- Chrome Native Messaging or an equivalent local bridge
- Python relay
- SQLite for local state

The browser adapter should translate unstable page details into stable semantic
events such as:

- `submit_message`
- `response_started`
- `response_delta`
- `response_complete`
- `conversation_changed`
- `browser_state_unknown`

Only the adapter should know about ChatGPT DOM details.

## Identity boundaries

Scribe:

```text
Linux user: jlove
ChatGPT seat: Scribe
Codex identity: jlove
Browser profile: isolated persistent Scribe profile
```

Forge:

```text
Linux user: forge
ChatGPT seat: Forge
Codex identity: forge
Browser profile: isolated persistent Forge profile
```

## Electric Sheep insertion point

Incoming user text is enriched before model submission:

```text
Discord/user input
      |
      v
Electric Sheep retrieval
      |
      v
Context assembly
      |
      v
ChatGPT conversation
```

Electric Sheep must remain model-independent so the same memory/context layer
can later support ChatGPT, local models, or other providers.

## Codex delegation

A Chat agent may request specialist coding work through LoomLab. LoomLab then
invokes the already-proven Codex app-server identity associated with that agent.

The Chat agent remains the generalist coordinator. Codex returns implementation
results, tests, commits, or review findings to the Chat conversation.

## MVP proof sequence

1. Launch one persistent Chromium profile for Scribe.
2. Load a tiny LoomLab extension.
3. Prove extension <-> local process PING/PONG.
4. Prove one normal ChatGPT turn can be submitted and observed.
5. Repeat independently for Forge.
6. Route messages through the LoomLab relay.
7. Add Discord input/output.
8. Insert Electric Sheep context.
9. Add controlled Chat -> Codex delegation.

## Non-goals for the first browser proof

- multi-agent autonomy
- automatic merges
- Drive writes
- elaborate retry machinery
- generalized browser automation
- more than two ChatGPT identities
- production-grade daemonization

## Acceptance milestone: WAZZZAAAPP

The milestone is complete when a single Discord channel can visibly host:

```text
John:   WAZZZAAAPP?!
Scribe: WAZZZAAAPP?!
Forge:  WAZZZAAAPP?!
```

with Scribe and Forge responses originating from their independent normal
ChatGPT sessions through LoomLab Relaid.
