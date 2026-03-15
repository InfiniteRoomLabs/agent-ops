---
id: "026"
title: Claude Code Accessibility Plugins
status: raw
source: claude-code-session
date: 2026-03-11
tags: [accessibility, adhd, neurodiversity, plugins, skills, ux, claude-code]
outcome: [open-source-tool, framework, product]
---

# Claude Code Accessibility Plugins

## Original Idea

Claude Code skills and plugins that alter how Claude behaves and approaches tasks based on accessibility needs. Not accessibility in the "screen reader" sense (though that too) -- accessibility in the cognitive sense. How the AI communicates, structures work, paces interactions, and manages complexity should adapt to how the user's brain works.

First target: an ADHD productivity plugin.

## The ADHD Plugin -- What It Looks Like

### Problem Space

ADHD developers deal with:

- **Executive dysfunction**: Knowing what to do but not being able to start
- **Working memory limits**: Losing track of where you are mid-task
- **Decision paralysis**: Too many choices = no choice
- **Time blindness**: No internal sense of how long things take or have taken
- **Context switching cost**: Derailing is expensive, re-entry is painful
- **Information overload**: Walls of text cause shutdown, not understanding
- **Hyperfocus traps**: Productive until suddenly it's 3am and you've refactored the wrong thing

### Behavioral Changes

When the ADHD accessibility plugin is active, Claude Code should:

**1. Micro-chunking by default**
- Break every task into the smallest possible next step
- Never present more than 3 action items at once
- TodoWrite becomes aggressive -- everything gets tracked, nothing lives only in prose
- Each todo item should be completable in under 5 minutes

**2. Reduce decision points**
- Make opinionated choices instead of presenting options
- "I'll use X" instead of "Would you prefer X, Y, or Z?"
- Only ask questions when genuinely ambiguous -- otherwise just pick the best option and move
- When asking, limit to 2 choices max with a clear recommendation

**3. Response brevity mode**
- Maximum 3-4 lines of prose per response unless code is involved
- Lead with what changed or what's next, not what was analyzed
- No preamble, no "Great question!", no "Let me think about this"
- Use bullet points over paragraphs, always

**4. Momentum preservation**
- After completing a step, immediately state the next step and start it
- Never end a response with "What would you like to do next?" -- instead say "Next I'll do X" or "Done. Moving to Y"
- Keep the flywheel spinning -- the hardest part is starting, so never let the user stop

**5. Progress dopamine**
- Frequent, visible progress markers (todo completions, checkmarks, counts)
- "3/7 done" style progress indicators
- Celebrate micro-completions briefly: "Done." not a paragraph of summary
- Make the todo list a dopamine drip, not a guilt list

**6. Context anchoring**
- Begin every response with a 1-line "You are here" anchor: what we're doing and where we are in it
- After any interruption or tangent, proactively re-anchor: "Back to X -- we were on step 3/5"
- Never assume the user remembers what happened 10 messages ago -- re-state context cheaply

**7. Anti-rabbit-hole guardrails**
- If a tangent emerges, flag it: "That's a tangent -- want to park it or switch?"
- Track parked tangents in a separate todo group so they're not lost (reduces anxiety) but not blocking
- If refactoring scope starts creeping, call it out explicitly

**8. Time awareness**
- Periodically note elapsed working time if sessions run long
- Suggest natural break points: "Good stopping point -- 4 tasks done, 2 remaining"
- Frame work in time-bounded chunks: "This next part is ~5 min of work"

**9. Sensory-friendly formatting**
- No dense code walls without context headers
- Use whitespace generously
- Section headers on any response longer than 5 lines
- Avoid ALL CAPS for emphasis (use **bold** instead)

### Implementation as a Claude Code Skill/Plugin

```
# .claude/plugins/accessibility-adhd.md

## Activation
This plugin activates when the user sets their accessibility profile to include ADHD,
or when they run `/accessibility adhd on`.

## Behavior Overrides
- response_style: terse
- decision_mode: opinionated
- todo_granularity: micro
- progress_display: always
- context_anchoring: every_response
- max_prose_lines: 4
- max_options_presented: 2
- momentum: never_stop
- tangent_detection: active
- time_awareness: periodic
```

## Other Accessibility Profiles to Build

### Dyslexia
- Prefer code over prose explanations
- Use consistent, simple vocabulary
- Avoid homophones and ambiguous phrasing
- Structure output with strong visual hierarchy

### Anxiety / Perfectionism
- Normalize iterative, imperfect progress
- Frame changes as reversible ("we can always revert")
- Reduce language that implies stakes ("critical", "breaking", "dangerous")
- Explicit safety nets: "Tests pass, nothing broke"

### Autism Spectrum
- Be precise and literal -- avoid idioms and metaphors
- State assumptions explicitly rather than implying
- Consistent, predictable response structure every time
- Don't interpret emotional subtext in technical requests

### Low Vision / Screen Reader
- Describe code changes in plain language before showing diffs
- Avoid relying on visual formatting for meaning
- Use explicit section markers instead of whitespace hierarchy
- Provide alt-text-style descriptions for any diagrams or ASCII art

### Cognitive Fatigue / Brain Fog
- Ultra-short responses
- Binary yes/no decisions only
- Automate everything possible -- minimize user input needed
- "I'll handle it" mode -- just do the work, report results

## Architecture

This should be a **plugin framework**, not hardcoded profiles:

1. **Profile definitions** -- YAML/MD files describing behavioral modifications
2. **Skill overrides** -- Hooks into Claude Code's system prompt and tool behavior
3. **Composability** -- Users can combine profiles (ADHD + Dyslexia) with conflict resolution
4. **User-tunable** -- Each behavioral knob is individually adjustable
5. **Community-contributed** -- Open source profiles that users share and refine

## Relationship to Other Ideas

- **025 (Recursive Tool Infrastructure)**: This is recursion applied to the human-AI interface layer -- a tool that changes how you use tools
- **003 (Claude Code Mega-Framework)**: Accessibility profiles as a framework extension point
- **024 (Agent Emotional Presence)**: Emotional awareness meets cognitive accessibility -- complementary systems
