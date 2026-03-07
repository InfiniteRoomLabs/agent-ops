# Question Patterns

Grounded question templates for Phase 3 of the prompt refiner.

## Core Rules

1. Every option must come from research findings -- never from assumptions
2. One decision point per question
3. 2-4 options per question
4. Include trade-offs in option descriptions
5. User can always provide freeform input
6. Always set `multiSelect` explicitly (true or false)

## AskUserQuestion Format

```
question: Clear, specific question ending with ?
header: Max 12 characters
multiSelect: true/false
options:
  - label: 1-5 words (scannable)
    description: Trade-offs, implications, research evidence
```

## Question Templates by Category

### Target -- "Which file/component?"

Use when research found multiple candidates for the same task.

```yaml
question: I found both `src/auth/login.ts` and `src/auth/oauth.ts` handle authentication -- which are you targeting?
header: Target
multiSelect: false
options:
  - label: login.ts (JWT flow)
    description: Handles username/password login, token generation. 189 lines, last modified 3 days ago.
  - label: oauth.ts (OAuth flow)
    description: Handles third-party OAuth providers. 245 lines, last modified 2 weeks ago.
  - label: Both files
    description: Change spans both authentication flows. More complex but ensures consistency.
```

### Scope -- "Should this also affect X?"

Use when research revealed related code that might be in scope.

```yaml
question: The validation logic in `UserService` is also duplicated in `AdminService` -- should the refactor cover both?
header: Scope
multiSelect: false
options:
  - label: UserService only
    description: Smaller change, lower risk. AdminService can be addressed separately later.
  - label: Both services
    description: Eliminates duplication now. More files touched but consistent result.
```

### Approach -- "Which pattern should this follow?"

Use when research found multiple existing patterns or valid implementation strategies.

```yaml
question: I found two validation patterns in the codebase -- which should this follow?
header: Approach
multiSelect: false
options:
  - label: Middleware pattern
    description: Used in routes/api.ts. Validates before handler runs. Centralized, reusable.
  - label: Inline validation
    description: Used in services/order.ts. Validates inside the function. Simpler, co-located with logic.
```

### Risk -- "How cautious should we be?"

Use when the task touches sensitive areas (auth, data, payments, infra).

```yaml
question: This modifies the token refresh flow -- how should we approach it?
header: Risk
multiSelect: false
options:
  - label: Conservative
    description: Add new flow alongside existing one, feature-flag the switch. Safer but more code.
  - label: Direct replacement
    description: Replace the current implementation in-place. Cleaner but riskier if something breaks.
```

### Acceptance -- "How will you know this is done?"

Use when the prompt has vague success criteria.

```yaml
question: What would success look like for this fix?
header: Done when
multiSelect: true
options:
  - label: Tests pass
    description: The 3 failing tests in test_auth.test.ts go green.
  - label: No console errors
    description: The "Invalid token" error at auth.ts:145 stops appearing.
  - label: Manual verification
    description: You can log in, navigate around, and stay logged in for 5+ minutes.
```

## Adaptive Thoroughness Guide

| Complexity | Rounds | When |
|------------|--------|------|
| Simple | 1 | Target is clear, approach has one obvious path |
| Moderate | 2 | Multiple valid approaches, or scope is ambiguous |
| Complex | 3 | Touches auth/data/infra, or multiple interconnected decisions |

Signs to stop asking and move to Phase 4:
- Target, scope, and approach are all resolved
- User said "just do it" or "good enough"
- Max 3 research-clarify loops reached

## Anti-Patterns

- **Generic options**: "Use best practices" -- options must cite specific files, patterns, or findings
- **Compound questions**: Asking about target AND approach in one question -- split them
- **Too many options**: More than 4 per question -- narrow down or split into multiple questions
- **Leading questions**: "Should we use the superior X approach?" -- present options neutrally with trade-offs
