---
name: project-working-dir
description: All code reads and writes for this project are scoped to the codex-backed/ directory
metadata:
  type: project
---

All code reads and writes must stay inside `codex-backed/`. The other top-level directories (`backend/`, `claude-backend/`, `legacy/`, `frontend/`) are not active development targets and must not be modified unless the user explicitly requests it.

**Why:** The project has multiple historical implementations; only `codex-backed/` is the current active engine being tuned.

**How to apply:** Before reading or editing any file, confirm it lives under `codex-backed/`. If a task seems to require touching another directory, ask the user to confirm first.
