# LoomLab Codex execution boundary

Codex operates inside this repository as a coding and review worker. LoomLab Relaid, or the human operator until Relaid owns the action, performs privileged repository mutations outside the Codex sandbox.

## Allowed

- Read and modify files in the current workspace.
- Run tests, linters, formatters, build tools, and local scripts.
- Use read-only Git commands such as `git status`, `git diff`, `git log`, and inspection of already-fetched refs.
- Use outbound network access for documentation, dependency installation, and other read-oriented research when the sandbox permits it.
- Complete all useful local implementation, review, and validation work before escalating an outer action.

## Do not attempt

- GitHub MCP write operations.
- `git push`.
- Creating, updating, closing, approving, or merging pull requests through GitHub.
- Creating or deleting remote branches.
- Retrying an operation that has already failed because of sandbox, approval-policy, network-policy, credential, or protected-`.git` restrictions.
- Creating scratch clones or alternate Git paths solely to bypass those restrictions.
- Workarounds intended to evade the sandbox or approval boundary.

If GitHub state is needed, prefer already-fetched local refs. If the required ref is missing or stale, request that the operator fetch it outside Codex rather than repeatedly trying GitHub access.

## Escalation format

When a required action is blocked by this boundary, continue all useful local work first. Then stop and report exactly one concise request:

`OUTER ACTION REQUIRED: <specific action and exact command or information needed>`

Examples:

`OUTER ACTION REQUIRED: Fetch origin/forge/issue-2-browser-profile in the repository, then rerun this review.`

`OUTER ACTION REQUIRED: Push the current branch to origin so PR #4 updates.`

Do not spend additional attempts trying alternate GitHub write paths unless explicitly instructed to do so.

## Review behavior

When reviewing another agent's work:

- Prefer local refs and local diffs.
- Separate defects introduced by the reviewed change from pre-existing repository debt.
- Keep findings within the assigned issue or PR scope.
- Do not merge.
- If all scoped findings are resolved, say so clearly and identify any unrelated baseline issues separately.
