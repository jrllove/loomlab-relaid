# LoomLab Relaid

Lightweight relay for two subscription-backed Codex collaborators.

## MVP goals

- Run two named, persistent Codex sessions: **Scribe** and **Forge**
- Route human and agent messages through a shared relay
- Give each agent an isolated Git worktree
- Allow edit, test, commit, push, PR, and merge only within explicit policy
- Pause and escalate to John when a task crosses a boundary or becomes ambiguous
- Keep the relay small, local, auditable, and free of metered API dependencies

## Planned architecture

```text
John / Discord
      |
 LoomLab Relay
   /       \
Scribe    Forge
   \       /
  Git worktrees
       |
     GitHub
```

## Status

Bootstrap phase. Discord and Codex app-server integrations are intentionally not wired yet.
