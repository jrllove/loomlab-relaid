# LoomLab Relaid MVP

## Objective

Provide one shared control plane where John can talk to two named Codex
collaborators, Scribe and Forge, while they can hand work to each other and
operate on code within explicit boundaries.

## Non-goals for v0.1

- Browser automation of chatgpt.com
- Metered OpenAI API-key usage
- OpenHands or another agent framework
- Google Drive write integration
- More than two collaborators
- A web dashboard

## Milestones

1. **Relay core** - named agents, conservative policy, tests.
2. **Codex transport** - one local app-server process can initialize, start or
   resume a thread, submit a turn, stream output, and report completion.
3. **Dual identities** - run Scribe and Forge with separate ChatGPT-plan
   authentication contexts.
4. **Git isolation** - one worktree per agent/task.
5. **Discord control plane** - John can address one or both agents in #loomlab.
6. **Collaboration loop** - explicit handoff/review/block/done signals.
7. **Guarded GitHub actions** - policy-gated push, PR, and merge.

## Safety rule

LoomLab, not the model, decides whether a privileged action is permitted.
