---
description: "Start a new phase from the ROADMAP. Reads the roadmap, presents tasks, asks clarifying questions, and gets approval before starting."
---
# Start a New Roadmap Phase

## Step 1: Read Current State

Read `ROADMAP.md` in the workspace root. Identify:
- Which phases are already complete (marked ✅)
- Which phase is being requested
- All prerequisite phases and their status
- All tasks in the target phase

## Step 2: Verify Prerequisites

If any prerequisite phases are incomplete, STOP and warn the user:
> "Phase X requires Phase Y to be complete first. Phase Y status: [status]. Should I complete Phase Y first, or proceed anyway?"

## Step 3: Present Phase Plan

Present the phase to the user as a numbered task list:

```
## Phase X: [Name]

Tasks:
1. [ ] Task description
2. [ ] Task description
3. [ ] Task description

Estimated effort: X weeks
Dependencies: [list]
```

## Step 4: Ask Clarifying Questions

ALWAYS ask these questions before starting:
1. **Acceptance criteria:** "What does 'done' look like for this phase? The roadmap says [X]. Any additions?"
2. **Constraints:** "Any constraints or preferences not in the roadmap?"
3. **Scope adjustment:** "Should we add, remove, or reorder any tasks?"
4. **Priority:** "What is the priority order among these tasks?"

## Step 5: Get Confirmation

Wait for user confirmation before writing any code. Present the final task list and say:
> "Ready to begin. I'll work through these tasks in order, running tests after each. Confirm to start."

## Step 6: Execute

- Create a todo list with all approved tasks
- Work through them one at a time
- Run tests after each task
- Report progress after each task completes
- **For every code change, ask: "How does the end user experience this? Is it accessible through the Pipeline? Are imports clean? Are errors helpful?"** (Rule 9)
- Update ROADMAP.md when the phase is complete (mark it ✅)
