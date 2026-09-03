# Codex Continuity

This file is the local, account-independent context bundle for continuing Codex conversations in this workspace.

Use this file when you switch accounts and want to resume the same discussion. Keep it append-only unless a later turn explicitly replaces or deletes a section.

## How to use

1. Before ending a session, append a short summary of the current discussion.
2. On a new account, paste the latest summary back into the next chat or point Codex to this file.
3. Keep only durable context here: goals, decisions, constraints, and open follow-ups.

## Current conversation snapshot

- User wants Codex conversation records preserved locally so a different account can continue the same chat.
- Best practice is to keep a workspace-local continuity file instead of relying on account-bound chat history.
- The repository already has persistent project docs; this file is the dedicated handoff layer for account switching.

## Resume prompt

When starting a new chat on another account, use:

> 请基于本地的 CODEX_CONTINUITY.md 继续，不要重复已经确定的内容；如果缺少上下文，先读取这份文件再继续。

## Suggested entry format

```md
## 2026-08-25
- Goal:
- Decisions:
- Constraints:
- Open questions:
- Next steps:
```
