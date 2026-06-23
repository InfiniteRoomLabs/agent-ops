# 🏗️ Phase 1 Playbook -- Strategy & Architecture

> **Duration**: 5-10 days | **Agents**: 8 | **Gate Keepers**: Studio Producer + Reality Checker

---

## Objective

Define what we're building, how it's structured, and what success looks like -- before writing a single line of code. Every architectural decision is documented. Every feature is prioritized. Every dollar is accounted for.

## Pre-Conditions

- [ ] Phase 0 Quality Gate passed (GO decision)
- [ ] Phase 0 Handoff Package received
- [ ] Stakeholder alignment on project scope

## Scoping-Complete Gate

Before the architecture and design work begins, the Orchestrator must verify that onboarding and scoping are complete. This intermediate gate prevents the pipeline from advancing into heavy planning with incomplete requirements, undefined stakeholders, or missing project governance.

**Gate Keeper**: Agents Orchestrator
**Triggered**: Before Step 1 activation
**Blocking**: All Step 1/2/3 work is held until this gate passes

### Checklist

| # | Criterion | Evidence Source | Status |
|---|-----------|----------------|--------|
| 1 | Requirements document exists (PRD from Requirements Engineer) | Requirements Engineer PRD deliverable | ☐ |
| 2 | Stakeholder map is defined (all actors, roles, decision authority, and communication preferences documented) | Project Shepherd stakeholder analysis or Requirements Engineer Domain 2 output | ☐ |
| 3 | Project charter/kickoff is completed (scope, objectives, success criteria, constraints, and sponsor sign-off recorded) | Project Shepherd project charter document | ☐ |
| 4 | Communication cadence is established (status report frequency, escalation paths, and channel assignments agreed upon) | Project Shepherd communication plan | ☐ |
| 5 | Timeline/milestone plan exists (high-level milestones with target dates and dependencies identified) | Project Shepherd milestone plan or Studio Producer strategic timeline | ☐ |

### Verification Protocol

The Orchestrator verifies each criterion by confirming the artifact exists and contains substantive content -- not just a template with placeholder text. Specifically:

1. **Requirements document**: Must contain at least one complete user story with acceptance criteria, or a PRD with problem statement, user roles, and functional requirements sections populated.
2. **Stakeholder map**: Must name at least the project sponsor, primary decision-maker, and key technical and business stakeholders with their roles and communication preferences.
3. **Project charter**: Must include a problem statement, project objectives, scope boundaries (in-scope and out-of-scope), success criteria, and sponsor acknowledgment.
4. **Communication cadence**: Must specify the reporting frequency (daily/weekly), the escalation chain, and the channels used for each type of communication (status updates, blockers, decisions).
5. **Timeline/milestone plan**: Must include at least three milestones with target date ranges and must identify cross-phase dependencies.

### Gate Failure Handling

```
IF scoping-complete gate FAILS:
  +-- Orchestrator identifies which criteria are not met
  +-- Routes incomplete items to the responsible agent:
  |     Requirements document --> Requirements Engineer
  |     Stakeholder map       --> Project Shepherd or Requirements Engineer
  |     Project charter       --> Project Shepherd
  |     Communication cadence --> Project Shepherd
  |     Timeline/milestones   --> Project Shepherd or Studio Producer
  +-- Agent completes the artifact and re-submits
  +-- Orchestrator re-evaluates the gate
  +-- Maximum 3 re-attempts before escalation to Studio Producer
```

### Gate Decision

- **PASS**: All five criteria verified. Proceed to Step 1 (Strategic Framing).
- **FAIL**: Specific criteria not met. Route to responsible agents for completion.

---

## Planning-Complete Gate

The Orchestrator must verify that planning is complete before the pipeline advances to Phase 2 (Foundation & Scaffolding). This gate prevents the Build phase from starting without documented architecture decisions, a milestone plan, assigned resources, and recorded tech stack choices.

**Gate Keeper**: Agents Orchestrator
**Triggered**: After architecture and planning work completes, before Phase 2 activation
**Blocking**: Phase 2 activation is held until this gate passes

### Checklist

| # | Criterion | What "Done" Looks Like | Responsible Agent |
|---|-----------|------------------------|-------------------|
| 1 | Architecture document exists and is reviewed | Architecture doc covers all spec requirements. At least one reviewer (Reality Checker or Backend Architect) has signed off with comments resolved. | Backend Architect (author), Reality Checker (reviewer) |
| 2 | Sprint plan / milestone plan exists | At least 3 milestones with target date ranges, or a sprint backlog with estimated velocity. Cross-phase dependencies are identified. | Sprint Prioritizer or Project Shepherd |
| 3 | Resource assignments are defined | Every workstream has a named lead agent or team. No critical-path work is unassigned. Capacity conflicts are resolved. | Senior Project Manager |
| 4 | Tech stack decisions are documented | Language, framework, infrastructure, and third-party service choices are recorded with rationale. Each decision includes alternatives considered and why they were rejected. | Backend Architect or UX Architect |

### Gate Failure Handling

```
IF planning-complete gate FAILS:
  +-- Orchestrator identifies which criteria are not met
  +-- Routes incomplete items to the responsible agent:
  |     Architecture doc missing/unreviewed --> Backend Architect + Reality Checker
  |     Milestone plan missing              --> Sprint Prioritizer or Project Shepherd
  |     Resource assignments undefined      --> Senior Project Manager
  |     Tech stack undocumented             --> Backend Architect or UX Architect
  +-- Agent completes the artifact and re-submits
  +-- Orchestrator re-evaluates the gate
  +-- Maximum 3 re-attempts before escalation to Studio Producer
```

### Gate Decision

- **PASS**: All four criteria verified. Proceed to Phase 2 (Foundation & Scaffolding).
- **FAIL**: Specific criteria not met. Route to responsible agents for completion.

---

## Agent Activation Sequence

### Step 1: Strategic Framing (Day 1-3, Parallel)

#### 🎬 Studio Producer -- Strategic Portfolio Alignment
```
Activate Studio Producer for strategic portfolio alignment on [PROJECT].

Input: Phase 0 Executive Summary + Market Analysis Report
Deliverables required:
1. Strategic Portfolio Plan with project positioning
2. Vision, objectives, and ROI targets
3. Resource allocation strategy
4. Risk/reward assessment
5. Success criteria and milestone definitions

Align with: Organizational strategic objectives
Format: Strategic Portfolio Plan Template
Timeline: 3 days
```

#### 🎭 Brand Guardian -- Brand Identity System
```
Activate Brand Guardian for brand identity development on [PROJECT].

Input: Phase 0 UX Research (personas, journey maps)
Deliverables required:
1. Brand Foundation (purpose, vision, mission, values, personality)
2. Visual Identity System (colors, typography, spacing as CSS variables)
3. Brand Voice and Messaging Architecture
4. Logo system specifications (if new brand)
5. Brand usage guidelines

Format: Brand Identity System Document
Timeline: 3 days
```

#### 💰 Finance Tracker -- Budget and Resource Planning
```
Activate Finance Tracker for financial planning on [PROJECT].

Input: Studio Producer strategic plan + Phase 0 Tech Stack Assessment
Deliverables required:
1. Comprehensive project budget with category breakdown
2. Resource cost projections (agents, infrastructure, tools)
3. ROI model with break-even analysis
4. Cash flow timeline
5. Financial risk assessment with contingency reserves

Format: Financial Plan with ROI Projections
Timeline: 2 days
```

### Step 2: Technical Architecture (Day 3-7, Parallel, after Step 1 outputs available)

#### 🏛️ UX Architect -- Technical Architecture + UX Foundation
```
Activate UX Architect for technical architecture on [PROJECT].

Input: Brand Guardian visual identity + Phase 0 UX Research
Deliverables required:
1. CSS Design System (variables, tokens, scales)
2. Layout Framework (Grid/Flexbox patterns, responsive breakpoints)
3. Component Architecture (naming conventions, hierarchy)
4. Information Architecture (page flow, content hierarchy)
5. Theme System (light/dark/system toggle)
6. Accessibility Foundation (WCAG 2.1 AA baseline)

Files to create:
- css/design-system.css
- css/layout.css
- css/components.css
- docs/ux-architecture.md

Format: Developer-Ready Foundation Package
Timeline: 4 days
```

#### 🏗️ Backend Architect -- System Architecture
```
Activate Backend Architect for system architecture on [PROJECT].

Input: Phase 0 Tech Stack Assessment + Compliance Requirements
Deliverables required:
1. System Architecture Specification
   - Architecture pattern (microservices/monolith/serverless/hybrid)
   - Communication pattern (REST/GraphQL/gRPC/event-driven)
   - Data pattern (CQRS/Event Sourcing/CRUD)
2. Database Schema Design with indexing strategy
3. API Design Specification with versioning
4. Authentication and Authorization Architecture
5. Security Architecture (defense in depth)
6. Scalability Plan (horizontal scaling strategy)

Format: System Architecture Specification
Timeline: 4 days
```

#### 🤖 AI Engineer -- ML Architecture (if applicable)
```
Activate AI Engineer for ML system architecture on [PROJECT].

Input: Backend Architect system architecture + Phase 0 Data Audit
Deliverables required:
1. ML System Design
   - Model selection and training strategy
   - Data pipeline architecture
   - Inference strategy (real-time/batch/edge)
2. AI Ethics and Safety Framework
3. Model monitoring and retraining plan
4. Integration points with main application
5. Cost projections for ML infrastructure

Condition: Only activate if project includes AI/ML features
Format: ML System Design Document
Timeline: 3 days
```

#### 👔 Senior Project Manager -- Spec-to-Task Conversion
```
Activate Senior Project Manager for task list creation on [PROJECT].

Input: ALL Phase 0 documents + Architecture specs (as available)
Deliverables required:
1. Comprehensive Task List
   - Quote EXACT requirements from spec (no luxury features)
   - Each task has clear acceptance criteria
   - Dependencies mapped between tasks
   - Effort estimates (story points or hours)
2. Work Breakdown Structure
3. Critical path identification
4. Risk register for implementation

Rules:
- Do NOT add features not in the specification
- Quote exact text from requirements
- Be realistic about effort estimates

Format: Task List with acceptance criteria
Timeline: 3 days
```

### Step 3: Prioritization (Day 7-10, Sequential, after Step 2)

#### 🎯 Sprint Prioritizer -- Feature Prioritization
```
Activate Sprint Prioritizer for backlog prioritization on [PROJECT].

Input:
- Senior Project Manager -> Task List
- Backend Architect -> System Architecture
- UX Architect -> UX Architecture
- Finance Tracker -> Budget Framework
- Studio Producer -> Strategic Plan

Deliverables required:
1. RICE-scored backlog (Reach, Impact, Confidence, Effort)
2. Sprint assignments with velocity-based estimation
3. Dependency map with critical path
4. MoSCoW classification (Must/Should/Could/Won't)
5. Release plan with milestone mapping

Validation: Studio Producer confirms strategic alignment
Format: Prioritized Sprint Plan
Timeline: 2 days
```

## Quality Gate Checklist

| # | Criterion | Evidence Source | Status |
|---|-----------|----------------|--------|
| 1 | Architecture covers 100% of spec requirements | Senior PM task list cross-referenced with architecture | ☐ |
| 2 | Brand system complete (logo, colors, typography, voice) | Brand Guardian deliverable | ☐ |
| 3 | All technical components have implementation path | Backend Architect + UX Architect specs | ☐ |
| 4 | Budget approved and within constraints | Finance Tracker plan | ☐ |
| 5 | Sprint plan is velocity-based and realistic | Sprint Prioritizer backlog | ☐ |
| 6 | Security architecture defined | Backend Architect security spec | ☐ |
| 7 | Compliance requirements integrated into architecture | Legal requirements mapped to technical decisions | ☐ |

## Gate Decision

**Dual sign-off required**: Studio Producer (strategic) + Reality Checker (technical)

- **APPROVED**: Proceed to Phase 2 with full Architecture Package
- **REVISE**: Specific items need rework (return to relevant Step)
- **RESTRUCTURE**: Fundamental architecture issues (restart Phase 1)

## Handoff to Phase 2

```markdown
## Phase 1 -> Phase 2 Handoff Package

### Architecture Package:
1. Strategic Portfolio Plan (Studio Producer)
2. Brand Identity System (Brand Guardian)
3. Financial Plan (Finance Tracker)
4. CSS Design System + UX Architecture (UX Architect)
5. System Architecture Specification (Backend Architect)
6. ML System Design (AI Engineer -- if applicable)
7. Comprehensive Task List (Senior Project Manager)
8. Prioritized Sprint Plan (Sprint Prioritizer)

### For DevOps Automator:
- Deployment architecture from Backend Architect
- Environment requirements from System Architecture
- Monitoring requirements from Infrastructure needs

### For Frontend Developer:
- CSS Design System from UX Architect
- Brand Identity from Brand Guardian
- Component architecture from UX Architect
- API specification from Backend Architect

### For Backend Architect (continuing):
- Database schema ready for deployment
- API scaffold ready for implementation
- Auth system architecture defined
```

---

*Phase 1 is complete when Studio Producer and Reality Checker both sign off on the Architecture Package.*
