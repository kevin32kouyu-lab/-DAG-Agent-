---
name: context-reconstruction-model
description: Cross-conversation context comes from CLAUDE.md + git log + code + design docs, not just memory files
metadata:
  type: feedback
---

When entering a new conversation, reconstruct project context from four sources working together:

1. **CLAUDE.md** — project status, architecture, development rules, current phase
2. **Git log** — what was done, in what order, commit messages explain "why"
3. **Current code state** — authoritative source of truth, always up to date
4. **Design/plan docs** — `docs/superpowers/specs/` and `docs/superpowers/plans/`

Memory files (`.claude/memory/`) only store what these four sources can't capture: user preferences, feedback rules, external references.

**Why:** User confirmed this is the desired operating model. Memory files are intentionally sparse supplements, not the primary context mechanism.

**How to apply:** At the start of a new conversation, do NOT rely solely on memory files. Read CLAUDE.md, check `git log --oneline`, check `git status`, and reference design docs to understand current state.
