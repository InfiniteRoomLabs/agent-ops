# 🎨 Runbook: UX Design Sprint

> **Mode**: NEXUS-Micro | **Duration**: 3-5 days | **Agents**: 4-6

---

## Scenario

A new feature, product, or major redesign requires a structured design process before engineering begins. User research needs to inform architecture decisions, and visual designs need to be validated before implementation. This runbook takes the team from raw user insights through to implementation-ready design specifications.

## Agent Roster

### Core Design Team
| Agent | Role |
|-------|------|
| **UX Researcher** | Conducts user research, produces personas and pain point maps |
| **UX Architect** | Translates research into information architecture and interaction patterns |
| **UI Designer** | Creates visual designs and component specifications |

### Quality Amplifiers (Optional, activated at Step 4)
| Agent | Role |
|-------|------|
| **Impeccable Critique** | Reviews design quality against heuristics and standards |
| **Bolder** | Challenges safe choices, amplifies creative ambition |
| **Brand Guardian** | Ensures designs align with brand identity (if applicable) |

## Pre-Conditions

- [ ] Feature brief or product requirement document is available
- [ ] Target user segments are identified
- [ ] Business goals and success metrics are defined
- [ ] Design system exists (or this sprint will establish one)

## Design Sprint Sequence

### Step 1: User Research (Day 1-2)

```
TRIGGER: Feature brief / PRD approved for design work

UX Researcher:
1. Define research scope
   - Which user segments are relevant?
   - What decisions does this research need to inform?
   - What do we already know vs. what are our assumptions?
2. Conduct research activities
   - Review existing user feedback and support tickets
   - Analyze behavioral data and usage patterns
   - Conduct user interviews or surveys (if time permits)
   - Competitive analysis of similar experiences
3. Synthesize findings into personas
   - 2-4 personas representing key user segments
   - Each persona includes:
     - Demographics and context
     - Goals and motivations
     - Frustrations and pain points
     - Current workflows and tools
     - Comfort with technology / accessibility needs
4. Map pain points
   - Current journey map with friction points highlighted
   - Severity rating per pain point (critical / high / medium / low)
   - Opportunity areas where design can reduce friction
5. Document accessibility requirements
   - Cognitive accessibility considerations (ADHD, dyslexia)
   - Motor and visual accessibility needs
   - Device and context constraints

Output: Research Package
  - User personas (2-4)
  - Pain point map with severity ratings
  - Opportunity areas ranked by impact
  - Accessibility requirements checklist
  - Key quotes and evidence supporting findings
```

### Step 2: Information Architecture & Interaction Design (Day 2-3)

```
UX Architect receives:
  - Research Package (from Step 1)
  - Feature brief / PRD
  - Existing design system (if applicable)

UX Architect:
1. Define information architecture
   - Content hierarchy and organization
   - Navigation structure and wayfinding
   - Taxonomy and labeling conventions
   - Relationship mapping between content types
2. Design user flows
   - Primary task flows (happy path)
   - Error and edge case flows
   - Onboarding and first-use flows
   - Flow annotations with decision points
3. Create wireframes
   - Low-fidelity wireframes for key screens
   - Layout structure and content placement
   - Interactive element placement and behavior
   - Responsive breakpoint considerations
4. Define interaction patterns
   - State transitions (loading, empty, error, success)
   - Micro-interactions and feedback mechanisms
   - Form behaviors and validation patterns
   - Navigation transitions and animations
5. Validate against research
   - Map wireframes back to personas and pain points
   - Confirm each opportunity area is addressed
   - Verify accessibility requirements are met in the architecture

Output: Architecture Package
  - Information architecture diagram
  - User flow diagrams (annotated)
  - Wireframes for key screens
  - Interaction pattern specifications
  - Research-to-design traceability matrix
```

### Step 3: Visual Design & Component Specifications (Day 3-4)

```
UI Designer receives:
  - Architecture Package (from Step 2)
  - Research Package (from Step 1)
  - Brand guidelines (if applicable)
  - Existing design system (if applicable)

UI Designer:
1. Establish visual direction
   - Color palette application to wireframes
   - Typography hierarchy and scale
   - Spacing and layout grid system
   - Iconography and illustration style
2. Create high-fidelity designs
   - Key screens at full visual fidelity
   - All states represented (default, hover, active, disabled, error)
   - Responsive variants (mobile, tablet, desktop)
   - Dark/light mode variants (if applicable)
3. Specify components
   - Component anatomy (padding, margins, borders)
   - Token references (colors, typography, spacing from design system)
   - Behavioral specifications (animations, transitions)
   - Accessibility annotations (contrast ratios, focus states, ARIA hints)
4. Create design handoff artifacts
   - Annotated mockups with measurements
   - Component specification sheets
   - Asset exports (icons, illustrations, images)
   - Interaction prototypes (click-through or animated)
5. Document design decisions
   - Rationale for key visual choices
   - Trade-offs considered and why current approach was chosen
   - Assumptions that should be validated post-launch

Output: Design Package
  - High-fidelity mockups (all screens, all states)
  - Component specifications with tokens
  - Asset library
  - Interactive prototype
  - Design decision log
```

### Step 4: Design Review & Amplification (Day 4-5, Optional)

```
Impeccable Critique receives:
  - Design Package (from Step 3)
  - Research Package (from Step 1)
  - Architecture Package (from Step 2)

Impeccable Critique:
1. Heuristic evaluation
   - Nielsen's 10 usability heuristics
   - Accessibility standards (WCAG 2.1 AA minimum)
   - Consistency with existing design system
   - Platform conventions adherence
2. Research alignment check
   - Does the design address identified pain points?
   - Are persona needs met by the proposed experience?
   - Are accessibility requirements fulfilled?
3. Rate and report
   - Issue severity: critical / major / minor / cosmetic
   - Specific, actionable recommendations per issue
   - Highlight strengths to preserve

Bolder (if Impeccable Critique rates design as "safe" or "conventional"):
1. Identify areas where the design plays it too safe
   - Interactions that could be more delightful
   - Visual treatments that could be more distinctive
   - Opportunities for signature moments in the experience
2. Propose amplified alternatives
   - 2-3 bolder variants for identified areas
   - Risk/reward assessment for each variant
   - Recommendation on which to pursue

UI Designer incorporates feedback:
1. Address critical and major issues from Impeccable Critique
2. Evaluate and selectively adopt Bolder suggestions
3. Update Design Package with revisions
4. Document what changed and why

Output: Reviewed Design Package
  - Updated mockups addressing review feedback
  - Review response log (addressed / deferred / rejected with rationale)
  - Final component specifications
  - Implementation-ready design artifacts
```

## Completion Criteria

| Criterion | Owner | Status |
|-----------|-------|--------|
| User research conducted, personas and pain point map delivered | UX Researcher | [ ] |
| Information architecture, wireframes, and interaction patterns defined | UX Architect | [ ] |
| High-fidelity designs and component specifications created | UI Designer | [ ] |
| Design review completed and feedback incorporated (if Step 4 activated) | Impeccable Critique + UI Designer | [ ] |

## Escalation Matrix

| Condition | Escalate To | Action |
|-----------|------------|--------|
| Research reveals fundamental conflict with PRD assumptions | Studio Producer | Reassess feature scope before continuing design |
| Accessibility requirements cannot be met with current approach | UX Architect + UI Designer | Redesign interaction pattern, do not compromise accessibility |
| Design system gaps block component specification | UI Designer + Frontend Developer | Extend design system in parallel |
| Impeccable Critique flags critical usability issues | UX Architect | Revisit architecture before visual refinement |
| Stakeholder feedback contradicts user research | UX Researcher + Studio Producer | Data-driven resolution, research takes precedence over opinion |

## Handoff Relationships

```
                   Feature Brief / PRD Approved
                              |
                              v
                        UX Researcher
                   (Step 1: User Research)
                              |
                              v
                        UX Architect
              (Step 2: IA & Interaction Design)
                              |
                              v
                        UI Designer
                  (Step 3: Visual Design)
                              |
                              v
                  [Optional Quality Gate]
                     /              \
                    v                v
         Impeccable Critique      Bolder
          (Heuristic review)   (Amplification)
                     \              /
                      v            v
                     UI Designer
               (Incorporate feedback)
                          |
                          v
                 Implementation-Ready
                  Design Package
```

---

*UX design sprint is complete when research-backed, reviewed design artifacts are ready for engineering handoff, with all component specifications and interaction patterns documented.*
