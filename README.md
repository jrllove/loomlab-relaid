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

## Browser extension proofs on Hearthdaemon

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

### Read-only ChatGPT observation with the persistent Scribe profile

Run this in a checkout with the browser extra installed, as the `jlove` Linux
user on Hearthdaemon. Set `SCRIBE_PROFILE_DIR` to the **existing** Scribe Chromium
user-data directory; it must be owned by `jlove` and inaccessible to other users.
The observer rejects a missing profile path. Close any other Chromium process
using that profile first.

```bash
SCRIBE_PROFILE_DIR=/absolute/path/to/existing/scribe-chromium
.venv/bin/python -m loomlab.browser --agent scribe --profile-dir "$SCRIBE_PROFILE_DIR" --observe --open-url https://chatgpt.com/
```

`--open-url` opens the normal ChatGPT home page in a new active tab; it does not
submit a message. To observe an existing conversation, replace the URL with its
normal `https://chatgpt.com/c/...` URL. The command performs the existing local
PING/PONG check, takes two read-only page samples, prints one JSON observation,
and exits. It reports `ready` when a visible profile control and composer are
present, `streaming` when a visible stop control is also present, and
`browser_state_unknown` for missing, conflicting, or changing signals. A composer
alone does not establish authentication because [ChatGPT permits guest
use](https://help.openai.com/en/articles/9125172-the-chatgpt-home-page). The
conversation URL excludes query parameters and fragments; the observer never
exports prompt or response text,
cookies, or auth tokens. `authenticated: true` is a UI observation, not a check
that this is the intended Scribe account.

For focused tests, install `.[dev,browser]`, install Chromium, and run
`pytest -q tests/test_browser.py`. The Chromium test intercepts a synthetic
ChatGPT page; it does not sign in to a real account. The JavaScript observer
tests also run through Node.js when available.
