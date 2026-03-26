# 🎧 Runbook: Support Escalation

> **Mode**: NEXUS-Micro | **Duration**: 1-3 days | **Agents**: 3-5

---

## Scenario

A user has reported an issue through a support channel. The issue needs to be captured, classified, and routed to the right specialist for resolution. Not every issue is a bug -- some are feature requests, documentation gaps, or UX confusion. This runbook ensures structured triage, correct routing, and resolution tracking so nothing falls through the cracks.

## Agent Roster

### Triage
| Agent | Role |
|-------|------|
| **Support Responder** | First contact, captures issue context, classifies and routes |

### Resolution Specialists (one activated per issue)
| Agent | Role | Activated When |
|-------|------|----------------|
| **Debugger** | Investigates and fixes bugs | Issue classified as bug |
| **Feedback Synthesizer** | Processes feature requests into backlog items | Issue classified as feature request |
| **Technical Writer** | Fills documentation gaps | Issue classified as docs gap |
| **UX Researcher** | Investigates UX confusion patterns | Issue classified as UX confusion |

### Support (as needed)
| Agent | Role |
|-------|------|
| **Infrastructure Maintainer** | Assists Debugger with infrastructure-related bugs |
| **Sprint Prioritizer** | Receives processed items for backlog placement |

## Pre-Conditions

- [ ] Support channel is active and monitored
- [ ] Issue tracking system is accessible
- [ ] Agent routing paths are established

## Support Escalation Sequence

### Step 1: Issue Capture & Context (0-2 hours)

```
TRIGGER: User reports issue via support channel

Support Responder:
1. Acknowledge receipt to user
   - Confirm the issue was received
   - Set expectation for response timeline
   - Provide issue tracking ID
2. Capture full context
   - User description (verbatim)
   - Steps to reproduce (if applicable)
   - Environment details (browser, OS, account type)
   - Screenshots or screen recordings (if provided)
   - Timestamp of occurrence
   - Frequency: one-time, intermittent, or persistent
3. Check for known issues
   - Search existing issues for duplicates
   - Check recent deployments for related changes
   - Review status page for active incidents
4. If known issue found:
   - Link user report to existing issue
   - Provide user with workaround (if available)
   - Update issue with additional reproduction data
   - SKIP to Step 4 (tracking)

Output: Issue Context Record
  - Structured issue report with all captured details
  - Duplicate check result
  - Initial severity assessment
```

### Step 2: Classification (30 minutes)

```
Support Responder classifies the issue:

CLASSIFICATION MATRIX:

Bug (route to Debugger):
  - Application behaves differently than documented/expected
  - Error messages, crashes, data corruption
  - Performance degradation from established baseline
  - Regression from a previous working state
  Signals: "used to work", "error message", "broken", "crash", "wrong data"

Feature Request (route to Feedback Synthesizer):
  - User wants functionality that does not exist
  - User suggests improvement to existing functionality
  - Competitive feature comparison ("X does this, why don't you?")
  Signals: "would be nice", "can you add", "I wish", "feature", "suggestion"

Documentation Gap (route to Technical Writer):
  - User cannot find instructions for existing functionality
  - Documentation is outdated, incomplete, or contradictory
  - User followed docs but got unexpected results
  Signals: "where is the docs for", "docs say X but", "can't find how to", "no documentation"

UX Confusion (route to UX Researcher):
  - User can accomplish the task but the path is unclear
  - User misunderstands UI elements or terminology
  - User frequently asks about the same workflow
  - Multiple users report confusion about the same feature
  Signals: "confusing", "not intuitive", "can't figure out", "where do I", "I expected"

AMBIGUOUS CASES:
  - If bug vs. UX confusion: default to Bug (investigate first, reclassify if needed)
  - If feature request vs. docs gap: default to Documentation Gap (cheaper to fix)
  - If multiple classifications apply: route to primary, note secondary for follow-up

Output: Classification Decision
  - Issue type: [Bug / Feature Request / Documentation Gap / UX Confusion]
  - Routing target agent
  - Classification rationale
  - Secondary classification (if applicable)
```

### Step 3: Structured Handoff & Resolution (1-48 hours)

```
Support Responder hands off to the classified specialist with:
  - Issue Context Record (from Step 1)
  - Classification Decision (from Step 2)
  - User communication thread reference

ROUTE A -- Bug -> Debugger:
  Debugger:
  1. Reproduce the issue using provided steps
  2. Identify root cause
     - Code defect -> implement fix
     - Infrastructure issue -> escalate to Infrastructure Maintainer
     - External dependency -> document workaround, monitor upstream
  3. Verify fix resolves the issue
  4. Provide resolution summary to Support Responder

  Output: Bug Resolution
    - Root cause analysis
    - Fix applied (with reference to commit/deploy)
    - Verification evidence
    - Regression risk assessment

ROUTE B -- Feature Request -> Feedback Synthesizer:
  Feedback Synthesizer:
  1. Check if request aligns with existing roadmap items
  2. Assess request against product strategy
  3. Structure as backlog item with:
     - User impact and reach estimate
     - Alignment with product goals
     - Initial effort estimate
  4. Forward to Sprint Prioritizer for RICE scoring and backlog placement

  Output: Feature Request Record
    - Structured backlog item
    - Strategic alignment assessment
    - Recommended priority signal

ROUTE C -- Documentation Gap -> Technical Writer:
  Technical Writer:
  1. Identify the gap (missing, outdated, or incorrect docs)
  2. Write or update documentation
  3. Verify the documentation resolves the user's confusion
  4. Publish updated documentation

  Output: Documentation Update
    - What was added/changed
    - Location of updated docs
    - Verification that update addresses the original issue

ROUTE D -- UX Confusion -> UX Researcher:
  UX Researcher:
  1. Log the confusion pattern
  2. Check if this is a recurring theme (search support history)
  3. If recurring pattern detected:
     - Document as UX issue with frequency data
     - Propose interaction improvement
     - Forward to Sprint Prioritizer as UX debt item
  4. If isolated incident:
     - Suggest improved in-app guidance or tooltip
     - Recommend documentation clarification (hand off to Technical Writer)

  Output: UX Research Finding
    - Pattern analysis (isolated vs. recurring)
    - Proposed improvement (if recurring)
    - Backlog item for Sprint Prioritizer (if recurring)
```

### Step 4: Resolution Tracking & User Communication (Post-resolution)

```
Support Responder receives resolution output from the specialist:

1. Communicate resolution to user
   - Explain what was found
   - Describe what was done to resolve it
   - Provide any updated links (docs, release notes)
   - Ask user to confirm resolution
2. Update issue tracking
   - Record resolution type and timeline
   - Link to any artifacts (commits, doc updates, backlog items)
   - Record time-to-resolution
3. Close or escalate
   - IF user confirms resolved: close issue
   - IF user reports issue persists: re-enter Step 2 with additional context
   - IF resolution is deferred (feature request, UX debt): inform user of backlog status
4. Pattern detection
   - Flag if 3+ users report the same issue within a sprint
   - Escalate patterns to Sprint Prioritizer for priority boost

Output: Closed Issue Record
  - Full timeline from report to resolution
  - Classification and routing path taken
  - Resolution details and user confirmation
  - Pattern flag (if applicable)
```

## Completion Criteria

| Criterion | Owner | Status |
|-----------|-------|--------|
| Issue captured with full context and acknowledged to user | Support Responder | [ ] |
| Issue classified and routed to correct specialist | Support Responder | [ ] |
| Specialist has resolved or processed the issue | Debugger / Feedback Synthesizer / Technical Writer / UX Researcher | [ ] |
| User notified of resolution and issue tracking updated | Support Responder | [ ] |

## Escalation Matrix

| Condition | Escalate To | Action |
|-----------|------------|--------|
| Bug cannot be reproduced | Infrastructure Maintainer | Assist with environment-specific investigation |
| Bug is P0/P1 severity | Infrastructure Maintainer | Trigger incident-response runbook |
| Feature request is urgent business need | Studio Producer | Fast-track prioritization outside normal sprint cycle |
| 3+ users report same issue within a sprint | Sprint Prioritizer | Priority boost, pattern investigation |
| Resolution exceeds 48 hours for a bug | Project Shepherd | Resource reallocation or scope adjustment |
| User is escalating or dissatisfied | Support Responder + Studio Producer | Direct engagement, expedited resolution |

## Handoff Relationships

```
                     User Reports Issue
                            |
                            v
                    Support Responder
                (Step 1: Issue Capture)
                            |
                            v
                    Support Responder
                (Step 2: Classification)
                            |
               ┌────────────┼────────────┐────────────┐
               v            v            v            v
           Debugger    Feedback      Technical     UX
           (Bug)      Synthesizer   Writer        Researcher
                      (Feature)     (Docs Gap)    (UX Confusion)
               |            |            |            |
               v            v            v            v
          Fix applied   Backlog item   Docs updated  Pattern logged
                      created                      / improvement
               └────────────┼────────────┘────────────┘
                            |
                            v
                    Support Responder
              (Step 4: Resolution & Tracking)
                            |
                            v
                    User Notified
                    Issue Closed
```

---

*Support escalation is complete when the user's issue has been captured, classified, routed to the correct specialist, resolved (or tracked for future resolution), and the user has been notified of the outcome.*
