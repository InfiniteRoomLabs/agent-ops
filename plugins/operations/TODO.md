# Operations Plugin -- Planned Components

Business operations, vendor management, scheduling, and process automation for a solo-dev LLC running contracts and open source projects.

## Agents

### project-intake
- **Purpose**: Structured interview for onboarding new client projects. Gathers scope, timeline, budget, tech stack, deliverables. Produces a project brief document.
- **Model**: sonnet
- **Color**: green (creation)
- **Tools**: Read, Write, Glob, Grep, WebSearch, WebFetch
- **Tags**: function: [operations, executive], scenario: [client-onboarding], custom: [contracts, intake, projects]
- **Output**: `docs/projects/YYYY-MM-DD-{client}-{project}-brief.md` with scope, timeline, tech requirements, deliverables, acceptance criteria

### vendor-evaluator
- **Purpose**: Evaluate SaaS tools, hosting providers, and service vendors using structured criteria and web research.
- **Model**: sonnet
- **Color**: cyan (analysis)
- **Tools**: Read, Write, WebSearch, WebFetch
- **Tags**: function: [operations, engineering], scenario: [vendor-evaluation], custom: [saas, hosting, tools]
- **Output**: Comparison matrix with weighted scoring (pricing, features, reliability, support, integration, lock-in risk)

## Skills

### scope-tracker
- **Purpose**: Track project scope, change requests, and milestone progress against the original project brief.
- **Tags**: function: [operations], scenario: [project-management], custom: [scope, milestones, change-requests]
- **Mechanism**: Maintains a `scope-log.md` per project with original scope, change requests (date, description, impact), and milestone status.

### sow-generator
- **Purpose**: Generate a Statement of Work from a project brief. Covers deliverables, timeline, payment schedule, IP ownership, acceptance criteria.
- **Tags**: function: [operations, finance], scenario: [client-onboarding, contract-management], custom: [sow, contracts, legal]
- **Mechanism**: Template-driven generation from project-intake output. User fills in rate/payment terms.

## Commands

### status-report
- **Purpose**: Generate a project status report from git history, open issues, and task progress.
- **Tags**: function: [operations, executive], scenario: [project-management, client-communication], custom: [status, reporting]
- **Mechanism**: Uses `git log --since`, GitHub MCP for open issues/PRs, reads task files. Produces markdown status report suitable for client communication.
- **allowed-tools**: Bash(git:*), Bash(gh:*), Read, Glob, Grep

### time-log
- **Purpose**: Quick time entry logging for billable hours tracking.
- **Tags**: function: [operations, finance], scenario: [time-tracking], custom: [billing, hours]
- **Mechanism**: Appends to `time-log.csv` with date, project, hours, description. Supports weekly summaries.
- **allowed-tools**: Read, Write

## Hooks

None planned initially. Consider a SessionStart hook that loads active project context from `.claude/operations.local.md`.

## Dependencies on Other Plugins
- **research**: vendor-evaluator may delegate deep research to research:competitor-scanner
- **finance**: sow-generator and time-log feed into finance:invoice-gen
- **core**: All components use standard tagging convention
