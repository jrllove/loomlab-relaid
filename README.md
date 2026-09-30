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

## Browser extension smoke proof on Hearthdaemon

Run as the `forge` Linux user from this checkout:

```bash
cd /home/forge/src/loomlab-relaid
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[browser]'
.venv/bin/python -m playwright install chromium
.venv/bin/python -m loomlab.browser --agent forge --profile-dir /home/forge/.local/state/loomlab/forge-chromium
```

The last line is the repeatable Hearthdaemon run command. It launches Playwright's
Chromium headlessly with the unpacked test extension, waits for the extension's
service worker, and asks it to send `PING` to a temporary loopback HTTP listener.
The harness prints the extension ID and `PONG` when the local process replies, then
keeps the browser open until Ctrl-C. The user-data directory survives restarts;
give each agent a different directory and run it as that agent's Linux user. Pass
`--headed` to show the browser when a desktop session is available.

For the browser integration test, install `.[dev,browser]` instead and run
`pytest -q tests/test_browser.py` after installing Chromium. This proof opens only
the extension's own page. Neither the launcher nor the test accesses ChatGPT.
