# 🗓 Runbook: Sprint Planning

> **Mode**: NEXUS-Micro | **Duration**: 1-2 days | **Agents**: 4-6

---

## Scenario

A sprint boundary has been reached or a new planning cycle is starting. Unprocessed feedback has accumulated, the backlog needs re-prioritization, and the team needs clear assignments and milestones for the upcoming sprint. This runbook takes raw feedback through to an approved, resource-allocated sprint plan.

## Agent Roster

| Agent | Role |
|-------|------|
| **Feedback Synthesizer** | Aggregates and structures recent feedback into actionable items |
| **Sprint Prioritizer** | Scores and ranks backlog using RICE, produces sprint backlog |
| **Project Shepherd** | Assigns tasks, sets milestones, updates project charter |
| **Studio Producer** | Reviews resource allocation, approves sprint scope, flags risks |
| **Analytics Reporter** | Provides velocity data and sprint metrics (if applicable) |
| **Executive Summary Generator** | Stakeholder communication (if applicable) |

## Pre-Conditions

- [ ] Previous sprint retrospective completed (or first sprint kickoff)
- [ ] Feedback channels have been active since last planning cycle
- [ ] Current project charter and backlog are accessible
- [ ] Velocity data from previous sprints is available (if not first sprint)

## Sprint Planning Sequence

### Step 1: Feedback Aggregation (0-4 hours)

```
TRIGGER: Sprint boundary reached / planning cycle initiated

Feedback Synthesizer:
1. Collect feedback from all channels
   - User reports and support tickets
   - Internal team observations
   - Analytics-flagged anomalies
   - Stakeholder requests
2. Deduplicate and categorize feedback
   - Bug reports
   - Feature requests
   - UX improvements
   - Performance concerns
   - Technical debt observations
3. Structure each item with:
   - Source and frequency (how many times reported)
   - User impact assessment
   - Suggested priority signal
4. Package into Feature Request Packet

Output: Feature Request Packet
  - Categorized feedback items with frequency counts
  - Impact assessments per item
  - Recommended priority signals
```

### Step 2: Backlog Prioritization (2-4 hours)

```
Sprint Prioritizer receives:
  - Feature Request Packet (from Step 1)
  - Existing backlog (carried over items)
  - Velocity data from previous sprints (if available)

Sprint Prioritizer:
1. Merge new items into existing backlog
   - Map Feature Request Packet items to existing backlog entries where applicable
   - Create new backlog entries for novel items
2. Score every item using RICE framework
   - Reach: How many users/segments affected?
   - Impact: How much does this move the needle? (3=massive, 2=high, 1=medium, 0.5=low, 0.25=minimal)
   - Confidence: How sure are we about reach and impact? (100%/80%/50%)
   - Effort: Person-sprints required (agent-days estimate)
3. Rank backlog by RICE score
4. Draw sprint capacity line
   - Based on team velocity (or estimated capacity for first sprint)
   - Items above the line form the sprint backlog
   - Items below the line stay in the icebox with their scores
5. Apply MoSCoW classification to sprint items
   - Must have: Sprint fails without these
   - Should have: High value, not blocking
   - Could have: Nice-to-have if capacity remains
   - Won't have: Explicitly deferred (with reason)

Output: Prioritized Sprint Backlog
  - Ranked items with RICE scores
  - MoSCoW classification per item
  - Capacity utilization estimate
  - Icebox contents with scores for future sprints
```

### Step 3: Task Assignment & Milestones (2-4 hours)

```
Project Shepherd receives:
  - Prioritized Sprint Backlog (from Step 2)
  - Current project charter
  - Agent availability and specialization map

Project Shepherd:
1. Break sprint backlog items into assignable tasks
   - Each task has a single owner
   - Each task has clear acceptance criteria
   - Each task has an effort estimate (hours/days)
2. Assign tasks to agents based on specialization
   - Match task type to agent capability
   - Balance workload across agents
   - Identify dependencies between tasks
3. Set sprint milestones
   - Mid-sprint checkpoint (end of day 2-3 for a 5-day sprint)
   - Feature-complete milestone
   - QA-complete milestone
   - Sprint review date
4. Update project charter
   - Record sprint goals
   - Update timeline with new milestones
   - Note any scope changes from previous plan
5. Identify blockers and dependencies
   - External dependencies (APIs, infrastructure, approvals)
   - Inter-task dependencies (task B requires task A output)
   - Risk items that could derail the sprint

Output: Sprint Plan
  - Task assignments with owners and estimates
  - Milestone schedule
  - Dependency map
  - Updated project charter
  - Identified blockers and mitigation strategies
```

### Step 4: Scope Approval & Risk Review (1-2 hours)

```
Studio Producer receives:
  - Sprint Plan (from Step 3)
  - Prioritized Sprint Backlog (from Step 2)
  - Feature Request Packet (from Step 1)

Studio Producer:
1. Review resource allocation
   - Are agents appropriately loaded (not over/under-committed)?
   - Are critical-path tasks assigned to senior agents?
   - Is there buffer for unexpected work (aim for 80% allocation)?
2. Validate sprint scope against business priorities
   - Does the sprint advance the current strategic goals?
   - Are Must-have items aligned with product roadmap?
   - Any high-value items incorrectly deprioritized?
3. Flag risks
   - Single points of failure (one agent on all critical tasks)
   - Aggressive estimates on complex items
   - External dependencies without confirmed availability
   - Scope that exceeds historical velocity
4. Approve or request adjustments
   - IF APPROVED: Sprint is green-lit, notify all agents
   - IF ADJUSTMENTS NEEDED: Return to Project Shepherd with specific changes
     (scope reduction, reassignment, timeline extension)

Output: Sprint Approval
  - Approval status: [APPROVED / ADJUSTMENTS NEEDED]
  - Risk register with mitigation owners
  - Resource allocation confirmation
  - Any scope modifications with rationale
```

## Completion Criteria

| Criterion | Owner | Status |
|-----------|-------|--------|
| Feedback aggregated and structured into Feature Request Packet | Feedback Synthesizer | [ ] |
| Backlog scored with RICE and sprint capacity line drawn | Sprint Prioritizer | [ ] |
| Tasks assigned, milestones set, project charter updated | Project Shepherd | [ ] |
| Resource allocation reviewed, scope approved, risks flagged | Studio Producer | [ ] |

## Escalation Matrix

| Condition | Escalate To | Action |
|-----------|------------|--------|
| Feedback volume too large to process in time | Studio Producer | Scope feedback window or add Feedback Synthesizer capacity |
| No clear priority winner (tied RICE scores) | Studio Producer | Business priority tiebreaker |
| Agent unavailability threatens sprint capacity | Project Shepherd + Studio Producer | Reassign or reduce scope |
| Stakeholder adds urgent items after approval | Studio Producer | Assess against approved scope, invoke change control |
| Sprint scope exceeds 120% of historical velocity | Sprint Prioritizer | Mandatory scope reduction before approval |

## Handoff Relationships

```
                   Sprint Boundary Reached
                           |
                           v
                  Feedback Synthesizer
              (Step 1: Feedback Aggregation)
                           |
                           v
                   Sprint Prioritizer
              (Step 2: Backlog Prioritization)
                           |
                           v
                    Project Shepherd
           (Step 3: Task Assignment & Milestones)
                           |
                           v
                    Studio Producer
            (Step 4: Scope Approval & Risk Review)
                           |
                    /             \
                   v               v
           All Assigned       [If adjustments]
           Agents notified    Back to Step 3
```

---

*Sprint planning is complete when feedback is synthesized, the backlog is prioritized, tasks are assigned with milestones, and Studio Producer has approved the sprint scope.*
