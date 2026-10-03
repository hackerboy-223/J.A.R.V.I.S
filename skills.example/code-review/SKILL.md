# Code Review

Review a change as a careful coding assistant.

## Procedure

1. Read only the files needed for the requested change.
2. Identify correctness, security, compatibility, and maintainability issues.
3. Prefer small patches over broad rewrites.
4. Never read or expose secret files such as .env.
5. If a change writes or patches a file, use the workspace file tools and respect confirmation.
6. After edits, summarize exactly what changed and what still needs runtime verification.
