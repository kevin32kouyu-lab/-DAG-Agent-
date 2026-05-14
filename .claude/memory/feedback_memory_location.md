---
name: memory-location-in-project
description: Memory files are stored in project directory, not default Claude config path
metadata:
  type: feedback
---

Memory files for this project must be saved in `e:/Agent_Project/.claude/memory/`, not in the default `C:\Users\1\.claude\projects\e--Agent-Project\memory\`.

**Why:** User explicitly requested all project memory files stay within the project folder.

**How to apply:** When saving any memory (user, feedback, project, reference), write to `e:/Agent_Project/.claude/memory/` and update `MEMORY.md` in that same directory.
