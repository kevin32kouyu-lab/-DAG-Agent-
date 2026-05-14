---
name: plan-review-before-code
description: Always run cross-document consistency audit after plan changes, never start coding with known gaps
metadata:
  type: feedback
---

Before writing any implementation code, run a cross-document consistency audit between the design spec and all phase plans. Check for: file naming mismatches, import paths referencing non-existent files, forward references (classes used before they're created), missing model definitions, incomplete API contracts, and missing event types.

**Why:** During the competitive analysis agent project planning, 3 rounds of review uncovered 9+ issues across 7 plan documents — agent file splits, missing model classes (ScoringNode, SocialPost), forward references (AuditLogger), incomplete WebSocket events, bare dict instead of typed schema models, missing degradation logic, and missing review mode checkpoint. Catching these during planning saved significant rework.

**How to apply:** After any plan change, grep for class names, file paths, import statements, and event types across all plan documents. Verify forward references are safe. Check that every `git add` file exists in a `Create:` section. Every `from X import Y` should reference a module that exists in some plan.
