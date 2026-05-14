---
name: auto-commit-after-tasks
description: Automatically create git commits after completing meaningful units of work
metadata:
  type: feedback
---

After completing meaningful units of work (a task, a bug fix, a feature increment), automatically create a git commit with a descriptive message.

**Guidelines:**
- Commit when a logical unit is complete, not on every file save
- Use Chinese or English messages that describe the "why", not just "what"
- Follow existing commit message style in the repo (conventional commits: `feat:`, `fix:`, etc.)
- Run `git status` and `git diff` before committing to verify what's included
- Add specific files, not `git add -A` or `git add .`
- Never commit `.env`, credentials, or secrets

**Why:** User wants automatic checkpoints for work progress without manual intervention.

**How to apply:** After finishing a unit of work (passing tests, completed feature), stage relevant files and commit. Include `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` in the message.
