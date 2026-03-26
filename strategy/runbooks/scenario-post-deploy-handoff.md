# 🚢 Runbook: Post-Deploy Handoff

> **Mode**: NEXUS-Micro | **Duration**: 1-2 days | **Agents**: 4-6

---

## Scenario

A deployment has just been executed. The code is live, but the work is not done. This runbook ensures the transition from "deployed" to "operationally stable" by verifying monitoring, briefing support, and establishing observation tasks for the next sprint.

## Agent Roster

| Agent | Role |
|-------|------|
| **Infrastructure Maintainer** | Monitoring verification lead |
| **DevOps Automator / CICD Engineer** | Deployment executor, pipeline confirmation |
| **Support Responder** | Product briefing recipient, user-facing readiness |
| **Sprint Prioritizer** | Observation task creation for next sprint |
| **Analytics Reporter** | Baseline metrics capture (if applicable) |
| **Executive Summary Generator** | Stakeholder communication (if applicable) |

## Pre-Conditions

- [ ] Deployment execution completed successfully
- [ ] CI/CD pipeline shows green for the deployed artifact
- [ ] Deployment environment confirmed (staging promoted to production, or direct production deploy)

## Post-Deploy Sequence

### Step 1: Deployment Confirmation (0-30 minutes)

```
TRIGGER: Deployment pipeline reports success

DevOps Automator / CICD Engineer:
1. Confirm deployment artifact matches the expected build
2. Verify rollback mechanism is available and tested
3. Confirm environment variables and secrets are correctly applied
4. Record deployment metadata:
   - Deployed version/tag
   - Deployment timestamp
   - Deploying agent/actor
   - Affected services

Output: Deployment Confirmation Record
```

### Step 2: Monitoring Verification (30-60 minutes post-deploy)

```
Infrastructure Maintainer:
1. Verify dashboards reflect the new deployment
   - Application metrics updating (request rate, latency, error rate)
   - Resource utilization within expected bounds (CPU, memory, disk)
   - No anomalous log patterns in Loki/log aggregator
2. Confirm alerting rules are active
   - Health check endpoints responding
   - Error rate alerts armed with correct thresholds
   - Latency alerts armed (P95/P99 within SLO)
3. Smoke-test critical paths
   - Hit key endpoints and verify 2xx responses
   - Confirm database connectivity and query performance
   - Verify external integrations responding
4. Establish post-deploy baseline
   - Record current error rate
   - Record current latency percentiles
   - Record current resource utilization
   - Compare against pre-deploy baselines (flag regressions)

Output: Monitoring Verification Report
  - Dashboard status: [OK / DEGRADED / ALERTING]
  - Alerts armed: [list]
  - Smoke test results: [PASS / FAIL with details]
  - Baseline comparison: [NOMINAL / REGRESSION with specifics]
```

### Step 3: Product Briefing (1-2 hours post-deploy)

```
Infrastructure Maintainer hands off to Support Responder:

Support Responder receives briefing covering:
1. What changed
   - Features added/modified (plain language, not commit messages)
   - Bug fixes included
   - Known limitations or temporary workarounds
2. User impact
   - Which user segments are affected
   - Any behavior changes users will notice
   - Any migration or data changes users should be aware of
3. Support preparedness
   - New FAQ entries needed
   - Updated troubleshooting steps
   - Rollback criteria (what would trigger a rollback and who to contact)
4. Escalation paths
   - Who to contact for deployment-related issues
   - Severity classification for new-deployment issues

Output: Product Briefing Document
  - Changelog summary (user-facing)
  - Support playbook updates
  - Escalation contacts and criteria
```

### Step 4: Observation Task Creation (within 24 hours)

```
Sprint Prioritizer receives:
  - Monitoring Verification Report (from Step 2)
  - Product Briefing Document (from Step 3)
  - Any flags or regressions identified

Sprint Prioritizer creates observation tasks for the next sprint:
1. Performance observation window
   - Monitor error rate for 48-72 hours post-deploy
   - Compare latency trends against pre-deploy baseline
   - Flag any slow degradation not caught by immediate alerts
2. User feedback collection
   - Track support ticket volume related to changed features
   - Monitor user-reported issues for patterns
   - Collect qualitative feedback on new/changed features
3. Regression watch
   - Run extended test suite against production (if applicable)
   - Monitor edge cases identified during QA but not blocking
   - Verify performance under real-world traffic patterns
4. Follow-up items
   - Technical debt introduced during sprint (if any accepted)
   - Documentation updates needed
   - Monitoring improvements identified during verification

Output: Observation Tasks added to next sprint backlog
  - Each task tagged with the deployment version
  - Each task has clear success/completion criteria
  - Priority: P2 (Medium) unless regressions found (then P1)
```

## Completion Criteria

| Criterion | Owner | Status |
|-----------|-------|--------|
| Deployment confirmed and metadata recorded | DevOps Automator / CICD Engineer | [ ] |
| Dashboards verified, alerts armed, smoke tests pass | Infrastructure Maintainer | [ ] |
| Support Responder briefed with changelog and escalation paths | Support Responder | [ ] |
| Observation tasks created and added to next sprint backlog | Sprint Prioritizer | [ ] |

## Escalation Matrix

| Condition | Escalate To | Action |
|-----------|------------|--------|
| Monitoring shows regression post-deploy | Infrastructure Maintainer + DevOps Automator | Assess rollback vs. hotfix |
| Smoke tests fail | DevOps Automator | Immediate rollback, trigger incident-response runbook |
| Support ticket spike within 4 hours | Support Responder + Sprint Prioritizer | Escalate to P1, assess severity |
| Stakeholder visibility needed | Executive Summary Generator | Deploy summary briefing |

## Handoff Relationships

```
                    Deployment Complete
                          |
                          v
              DevOps Automator / CICD Engineer
              (Step 1: Deployment Confirmation)
                          |
                          v
                Infrastructure Maintainer
              (Step 2: Monitoring Verification)
                     /          \
                    v            v
          Support Responder   Sprint Prioritizer
          (Step 3: Briefing)  (Step 4: Observation Tasks)
```

---

*Post-deploy handoff is complete when monitoring is verified, support is briefed, and observation tasks are queued for the next sprint.*
