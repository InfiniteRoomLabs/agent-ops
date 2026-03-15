---
name: init-adhd
description: Guide the user through setting up ADHD accessibility mode configuration in their CLAUDE.md frontmatter. Use when the user wants to enable or configure ADHD mode for the first time, or reconfigure their existing setup.
allowed-tools: Read, Edit, Write, Bash, Glob
tags:
  function: [operations]
  scenario: [accessibility, setup]
  custom: [adhd, neurodiversity, configuration, onboarding]
---

# Initialize ADHD Accessibility Mode

Interactive setup wizard for configuring ADHD accessibility mode in CLAUDE.md YAML frontmatter. Guides the user through behavior selection and writes the config.

## Step 1: Locate Target File

Check both locations for existing CLAUDE.md files:

1. **Global**: `~/.claude/CLAUDE.md`
2. **Project**: `./CLAUDE.md` (current working directory)

Read both files if they exist. Check whether either already has YAML frontmatter (starts with `---`), and whether that frontmatter already contains an `accessibility.adhd` section.

Present what you found:

- If **neither exists**: Tell the user and ask which to create (global or project)
- If **both exist, neither configured**: Ask which to configure -- explain that global applies everywhere, project applies only here
- If **one already configured**: Show current config and ask if they want to update it or configure the other file
- If **both configured**: Show both configs and ask which to update

Keep it to 2 options max. Default recommendation: global (most users want it everywhere).

## Step 2: Choose Configuration Profile

Present these three paths. Do NOT list all 9 behaviors yet -- reduce the decision.

**Option A: Full mode (recommended)**
> All 9 behaviors enabled with sensible defaults. Best starting point -- you can always tune later.

**Option B: Pick a preset**
> Choose from common configurations:
> - **Focus-only**: Everything except time awareness (for users who find time tracking anxiety-inducing)
> - **Tight brevity**: Everything with max 2 prose lines and 1 option max
> - **Exploration-friendly**: Everything except anti-rabbit-hole (for users who enjoy deep dives)
> - **Essentials-only**: Just micro-chunking, reduced decisions, and momentum

**Option C: Custom**
> Walk through each behavior one by one.

Ask the user to pick A, B, or C. Default to A if they seem unsure.

## Step 3: Custom Configuration (only if Option C)

If the user chose custom, walk through behaviors in **groups**, not one at a time. Present each group as a batch.

### Group 1: Response Style

> These control how Claude talks to you:
> - **Response brevity** -- max 4 lines of prose per response (tunable)
> - **Sensory-friendly formatting** -- clean whitespace, bold not CAPS, section headers
> - **Reduced decisions** -- Claude picks instead of asking, max 2 options (tunable)
>
> Enable all three? Or tell me which to disable.

If they want to tune `max_prose_lines` or `max_options`, ask for their preferred values.

### Group 2: Task Management

> These control how Claude structures work:
> - **Micro-chunking** -- tiny steps, max 3 items, everything tracked via TodoWrite
> - **Momentum** -- never stops, always states and starts the next action
> - **Progress dopamine** -- "3/7 done" counters, brief celebrations
>
> Enable all three? Or tell me which to disable.

### Group 3: Focus Protection

> These protect your attention:
> - **Context anchoring** -- every response starts with "you are here" line
> - **Anti-rabbit-hole** -- flags tangents, offers to park them for later
> - **Time awareness** -- notes elapsed time, suggests breaks (tunable interval)
>
> Enable all three? Or tell me which to disable.

If they want to tune `break_interval_minutes`, ask for their preferred value.

## Step 4: Generate Config

Build the YAML frontmatter block from their choices. Only include keys that differ from the "all true" default -- keep the config minimal.

**If all behaviors enabled with defaults:**

```yaml
---
accessibility:
  adhd:
    enabled: true
---
```

**If some behaviors disabled or values tuned:**

```yaml
---
accessibility:
  adhd:
    enabled: true
    time_awareness: false
    max_prose_lines: 2
---
```

Only write `false` values and non-default numeric values. Omitted keys default to `true` / their default number.

## Step 5: Write Config

### If the target file has NO existing frontmatter

Prepend the generated YAML block to the top of the file, followed by a blank line, then the existing content.

### If the target file HAS existing frontmatter

Parse the existing frontmatter. Merge the `accessibility.adhd` section into it, preserving all other frontmatter keys. Write the updated frontmatter back.

**Be careful**: Do not lose any existing frontmatter content. Read the full file first, modify only the frontmatter section, and write back.

### If the target file does not exist

Create it with just the frontmatter block. Add a comment below suggesting the user add their project instructions:

```yaml
---
accessibility:
  adhd:
    enabled: true
---

# Add your project instructions below
```

## Step 6: Verify

Run the config detection script to confirm the config is readable:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/accessibility-config.py
```

If it outputs JSON with the expected behaviors, confirm success:

> "ADHD mode configured. It will auto-activate on your next session. Run `/agency:accessibility-adhd` to activate it right now."

If the script produces no output or unexpected output, diagnose:
- Check the YAML is valid (proper indentation, `---` delimiters)
- Show the user what the file looks like and offer to fix it

## Anti-Patterns

- Do NOT present all 9 behaviors individually in step 2. Group them to reduce decision load.
- Do NOT write config keys that match the defaults. Keep the YAML minimal -- only write overrides.
- Do NOT overwrite existing file content. Always read first, merge, write back.
- Do NOT skip the verification step. Always run the config script to confirm.
- Do NOT auto-activate without asking. Offer to activate now, but let the user decide.
