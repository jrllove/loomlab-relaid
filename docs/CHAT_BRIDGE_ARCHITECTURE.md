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

## Architecture review for the first browser proof

The proposed boundaries are appropriately small: LoomLab owns routing, turn
state, and policy; Electric Sheep supplies persistent context; the browser
adapter alone interprets ChatGPT page state; Codex remains a separate coding
service. The first proof should validate these boundaries with Scribe before
adding Forge, Discord, Electric Sheep integration, or Codex delegation.

| Risky assumption or failure mode | Required behavior for the first proof |
| --- | --- |
| A persistent profile stays signed in and on the intended account. Login expiry, account switching, challenges, or navigation can silently change the target. | Confirm the expected seat and conversation before submission. Treat an unverified identity or changed conversation as `browser_state_unknown` and stop. |
| Page structure and response signals remain stable. A selector change, modal, stalled stream, or tab reload can make completion ambiguous. | Keep page detection inside the adapter. Use bounded waits; report `browser_state_unknown` with a reason when submission or completion cannot be established. |
| A lost acknowledgement is safe to retry. A message may have reached ChatGPT even when the bridge missed its confirmation. | Allow one in-flight turn per seat. Record whether submission was observed; never resubmit an ambiguous turn automatically. Require inspection before another turn. |
| Two Linux users automatically isolate browser and bridge state. A shared profile path, native host, or local endpoint could still cross seats. | Run each profile and native host under its seat's Linux user, keep profile files user-only, and allow relay access only to that seat's local bridge. Bind each seat to its expected account and conversation; verify Forge independently after Scribe. |
| Context and logs are harmless to persist. Retrieved context may contain private text or credentials. | Keep Electric Sheep as the context store. Store only relay correlation and turn status in SQLite; do not log cookies, tokens, full prompts, retrieved context, or response bodies by default. |

`README.md` and `docs/MVP.md` describe the earlier Codex-first bootstrap. This
document is the proposed Chat bridge direction; its browser proof does not
change the existing Codex transport or grant new action permissions.

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

The browser adapter accepts `submit_message` as a command and translates
unstable page details into stable semantic events such as:

- `response_started`
- `response_delta`
- `response_complete`
- `conversation_changed`
- `browser_state_unknown`

Only the adapter should know about ChatGPT DOM details.
`response_delta` can carry message content and is not part of diagnostic logs.

For each seat, the session layer owns the profile path, expected ChatGPT
account, current conversation reference, and one in-flight turn. The adapter
reports what it can observe; it does not choose a different account or
conversation, authorize actions, or retry an uncertain submission. The relay
assigns a local turn ID before submission and records whether the turn was
accepted, visibly submitted, completed, or left uncertain. An uncertain turn
blocks further submissions for that seat until a human inspects the conversation.

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

The session layer assembles retrieved context for a specific turn before
submitting it. SQLite holds the turn-to-conversation reference and status, not
a second copy of Electric Sheep memory. The first browser proof uses a simple
prompt without retrieval; context integration is a later MVP step.

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

### Recommended acceptance checklist for the first Scribe browser proof

- [ ] Launch a persistent Scribe Chromium profile as `jlove`; verify the
  expected signed-in ChatGPT account before sending a message.
- [ ] Demonstrate extension-to-local-process PING/PONG through the chosen local
  bridge, with the bridge accessible only to `jlove`.
- [ ] Submit one harmless, uniquely identified prompt to a normal ChatGPT
  conversation and observe one complete reply. Record the local turn ID and
  conversation reference so the result can be checked in the browser.
- [ ] Reload the browser or restart the local process, then send a second turn
  into the same verified conversation without creating a duplicate first turn.
- [ ] Induce at least one uncertain state (for example, navigate away during a
  response). Show a bounded timeout or `browser_state_unknown`, no automatic
  resubmission, and a visible stop requiring human inspection.
- [ ] Produce local, timestamped records for turn ID, seat, conversation
  reference, state transitions, completion or failure reason, and elapsed time.
  Confirm that logs exclude session credentials and message content.

These checks are evidence for the browser proof, not implementation work in
this review. They require no Discord routing, Electric Sheep retrieval, Forge
session, or Codex delegation.

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
