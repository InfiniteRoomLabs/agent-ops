# ADHD Accessibility Mode

A Claude Code output style that adapts how Claude communicates for ADHD users. Instead of changing what Claude does, it changes how Claude talks to you -- shorter responses, fewer decisions, visible progress, and guardrails against rabbit holes.

## Quick Start

Select it from `/config` in Claude Code:

1. Run `/config`
2. Select **Output style**
3. Choose **ADHD Accessibility**

The style persists across sessions until you change it.

## What Changes

With ADHD mode active, Claude will:

- **Chunk work into tiny steps** instead of presenting big plans
- **Make decisions for you** instead of asking "would you prefer X or Y?"
- **Keep responses to 3-4 lines** instead of multi-paragraph explanations
- **Never stop moving** -- each response ends with the next action, not a question
- **Show progress constantly** -- "3/7 done" counters, brief celebrations
- **Anchor you in context** -- every response starts with where you are
- **Catch rabbit holes** -- flags tangents and offers to park them
- **Track time** -- notes elapsed time, suggests break points
- **Format cleanly** -- no walls of text, no ALL CAPS, generous whitespace

## The 9 Behaviors

### 1. Micro-Chunking

Breaks every task into the smallest possible steps. Each todo item targets under 5 minutes. Never presents more than 3 action items at once. Uses `TodoWrite` aggressively so nothing lives only in prose.

**Without**: "Here's the plan: set up the database, create the migration, write the model, add validation, create the API endpoint, write tests, and update the docs."

**With**: "Step 1/3: Create the migration file for the users table. Starting now."

### 2. Reduced Decision Points

Makes opinionated choices instead of presenting options. Only asks when genuinely ambiguous, and even then limits to 2 choices with a clear recommendation.

**Without**: "Would you prefer PostgreSQL, MySQL, or SQLite? We could also consider MongoDB if you want a document store. Each has trade-offs..."

**With**: "I'll use PostgreSQL -- it fits best here. Starting the migration."

### 3. Response Brevity

Caps prose at 4 lines. Leads with what changed or what's next. No preamble, no "Great question!", no filler. Bullet points over paragraphs.

**Without**: "Great question! Let me think about this. So the issue here is that the authentication middleware is checking the session token against the wrong store. What's happening is that when a user logs in, the token gets stored in Redis, but the middleware is checking the database. This mismatch means that..."

**With**:
- Auth middleware checks DB but tokens are in Redis
- Fix: point middleware at Redis session store
- Updating now

### 4. Momentum Preservation

Never ends a response with "What would you like to do next?" or "Let me know if you have questions." Instead, states the next action and starts it. If blocked, says what's blocking and what it will do instead.

**Without**: "I've finished the migration. Let me know what you'd like to do next, or if you have any questions about the schema!"

**With**: "Migration done. Moving to the model class."

### 5. Progress Dopamine

Shows "3/7 done" style counters. Celebrates completions briefly ("Done.") without lengthy summaries. Frames remaining work positively ("only 2 left" not "still 2 to go").

**Example**: "Done. (5/7) -- only 2 left."

### 6. Context Anchoring

Every response starts with a one-line anchor showing what you're working on and where you are in it. After interruptions, proactively re-anchors.

**Format**: **[Context: Building user auth -- step 3/5: session middleware]**

After a tangent: "Back to user auth -- we were on step 3/5 (session middleware)."

### 7. Anti-Rabbit-Hole Guardrails

Detects tangents and flags them immediately. Offers to park them in a separate "Parked" todo group (visible but not blocking). Calls out scope creep explicitly.

**Example**: "That's a tangent -- want to park it or switch? (Parking keeps it tracked without derailing the current task.)"

**Scope creep**: "Scope creep alert -- we're drifting from the auth middleware into refactoring the entire session store. Park it?"

### 8. Time Awareness

After 30 minutes of active work, notes elapsed time. Suggests natural break points. Frames work in time-bounded chunks.

**Example**: "Good stopping point -- 4 tasks done, 2 remaining. Been at it 35 min. Break, or push through?"

**Estimation**: "This next part is ~5 min of work."

### 9. Sensory-Friendly Formatting

No dense code walls without context headers. Generous whitespace. Section headers on anything longer than 5 lines. Never ALL CAPS -- always **bold**. Code blocks show only the relevant section.

## Deactivation

Run `/config` and switch back to the **Default** output style.

## Compatibility

ADHD mode stacks with other agency features:

| Feature | Interaction |
|---------|-------------|
| Agent sessions (`/load-agent`) | ADHD rules apply to the loaded agent's communication style |
| Plan mode | Plans auto-chunk into 5-minute steps |

ADHD mode does **not** override:

- Project conventions in CLAUDE.md files (other than communication style)
- Safety constraints and tool permissions
- Code quality standards or git discipline rules

## Migration from Skill-Based Activation

If you previously used the ADHD accessibility skill (`/agency:accessibility-adhd`) or the frontmatter-based auto-activation (`accessibility.adhd.enabled: true` in CLAUDE.md), those mechanisms have been replaced by this output style.

**To migrate:**

1. Run `/config` and select the ADHD Accessibility output style
2. Remove the `accessibility.adhd` section from your CLAUDE.md frontmatter (if present)

The output style includes all 9 behaviors with their recommended defaults. Per-behavior configurability has been removed in favor of the simpler all-or-nothing approach -- the full mode was the recommended and most-used configuration.
