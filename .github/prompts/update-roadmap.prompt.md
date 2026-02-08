---
description: "Update ROADMAP.md when the user wants to change direction, skip tasks, or add new work."
---
# Update the Roadmap

## Trigger

This prompt is triggered when the user says anything like:
- "Let's change direction"
- "Actually let's do X instead"
- "Skip that"
- "Add X to the plan"
- "Update roadmap: [change]"

## Procedure

### 1. Read Current Roadmap
Read `ROADMAP.md` to understand the current state.

### 2. Identify the Change
Classify the change:
- **Skip/Remove:** Mark with ~~strikethrough~~ and add a note: `(Skipped: [reason] — [date])`
- **Add new task:** Insert in the appropriate phase with a clear description
- **Reorder:** Move tasks and update dependencies
- **Change scope:** Modify task descriptions and update estimates
- **New phase:** Add a new phase section with tasks, estimates, and dependencies

### 3. Apply the Change
Edit `ROADMAP.md` immediately. Preserve:
- All existing completed items (never remove history)
- Phase numbering (renumber only if phases are added/removed)
- Risk register (update if the change affects risks)
- Architecture decisions (add new ones, never delete without explicit approval)

### 4. Confirm
Show the user the specific changes made:
> "Updated ROADMAP.md:
> - Removed: [task] (reason)
> - Added: [task] in Phase X
> - Changed: [description of change]"

### 5. Update Current Work
If the change affects in-progress work:
- Update the todo list to reflect new priorities
- Stop current task if it's been deprioritized
- Start the newly prioritized task

## Important Rules

- ROADMAP.md is the SOURCE OF TRUTH — always keep it current
- Never delete completed items — they're project history
- Every change needs a reason (even if brief)
- If the user's change conflicts with architecture decisions, SAY SO before applying
