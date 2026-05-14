---
name: auto-save-important-decisions
description: Automatically save important design/architecture decisions to project memory
metadata:
  type: feedback
---

When encountering important decisions during implementation, automatically judge relevance and save to `.claude/memory/` without waiting for the user to ask.

**What qualifies as "important decision":**
- Architecture choices that differ from the plan
- Trade-off decisions with non-obvious rationale
- New patterns or conventions established
- External dependencies or versions pinned for a reason
- Scope changes (deferring, adding, or removing planned work)

**Why:** User wants decisions preserved across conversations without having to remember to ask each time.

**How to apply:** After making a significant decision during implementation, write a project or feedback memory file and update MEMORY.md. Don't ask for permission — just do it.
