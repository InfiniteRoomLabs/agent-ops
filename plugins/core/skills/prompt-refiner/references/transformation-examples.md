# Transformation Examples

Before/after examples showing how ramblings become structured prompts in Phase 4.

## Bug Fix Example

**Raw input:**
> the login is broken again, something about tokens idk, users keep getting kicked out, it was fine yesterday

**Here's what I understood:**
> Fix the JWT validation failure in `src/auth/login.ts` that started after yesterday's commit `a3f2b1c`. Users are getting 401 errors and being logged out mid-session. The token refresh flow in `src/auth/refresh.ts` should remain untouched.

**Structured prompt:**

```
## Goal
Fix the JWT token validation bug in the login flow that causes users to be logged out mid-session.

## Context
- `src/auth/login.ts` handles JWT validation -- the `validateToken()` function at line 89 is failing
- Commit `a3f2b1c` (yesterday) changed the token expiry logic and likely introduced the regression
- `src/auth/refresh.ts` handles token refresh separately and is working correctly
- 2 failing tests in `tests/auth.test.ts` related to token validation

## Requirements
- Fix the validation logic so valid tokens are no longer rejected
- Ensure the 2 failing tests in `tests/auth.test.ts` pass
- Verify users can stay logged in through normal session duration

## Boundaries
- Do not modify the token refresh flow in `src/auth/refresh.ts`
- Do not change the OAuth integration in `src/auth/oauth.ts`
```

## Feature Example

**Raw input:**
> we need some kind of caching, the dashboard is slow, maybe redis? or whatever, just make it faster

**Here's what I understood:**
> Add Redis caching to the dashboard API endpoints in `src/api/dashboard.ts`. The `/api/dashboard/stats` endpoint currently makes 4 database queries averaging 800ms total. Cache responses with a 5-minute TTL, using the existing Redis connection in `src/db/redis.ts`.

**Structured prompt:**

```
## Goal
Add Redis caching to the dashboard API to reduce response times from ~800ms to under 100ms for cached requests.

## Context
- `src/api/dashboard.ts` has 3 endpoints: `/stats`, `/activity`, `/summary`
- `/stats` is the slowest -- 4 database queries, ~800ms average response
- Redis is already configured in `src/db/redis.ts` with an active connection pool
- No existing caching anywhere in the API layer

## Requirements
- Cache `/api/dashboard/stats` responses in Redis with a 5-minute TTL
- Use the existing Redis connection in `src/db/redis.ts`
- Add cache invalidation when dashboard data is updated via `src/api/admin.ts`
- Log cache hits/misses for monitoring

## Approach
Follow the middleware pattern used in `src/middleware/rateLimit.ts` -- add a caching middleware that checks Redis before hitting the database.
```

## Refactor Example

**Raw input:**
> the user service is a mess, like 500 lines, functions everywhere, can you clean it up somehow

**Here's what I understood:**
> Split `src/services/UserService.ts` (487 lines, 12 methods) into focused modules. The validation methods (`validateEmail`, `validatePassword`, `validateProfile`) move to `UserValidationService`. The notification methods (`sendWelcomeEmail`, `sendPasswordReset`) move to `UserNotificationService`. Keep the core CRUD methods in `UserService`.

**Structured prompt:**

```
## Goal
Split the 487-line UserService into 3 focused service modules following the single-responsibility pattern already used in `src/services/OrderService.ts`.

## Context
- `src/services/UserService.ts` has 12 methods across 3 concerns: CRUD, validation, notifications
- `src/services/OrderService.ts` (147 lines) is the cleanest service -- use it as the pattern reference
- 23 files import from UserService (mapped via grep)
- Test file `tests/services/user.test.ts` has 34 tests covering all 12 methods

## Requirements
- Extract validation methods to `src/services/UserValidationService.ts`: `validateEmail`, `validatePassword`, `validateProfile`
- Extract notification methods to `src/services/UserNotificationService.ts`: `sendWelcomeEmail`, `sendPasswordReset`
- Keep CRUD methods in `UserService.ts`: `create`, `getById`, `update`, `delete`, `list`, `search`
- Update all 23 import sites to use the new module paths
- Split the test file to match: `user.test.ts`, `user-validation.test.ts`, `user-notification.test.ts`

## Boundaries
- Preserve the existing public API -- callers should need only import path changes, not behavioral changes
- Do not refactor the methods themselves -- only move them
```

## Compound Example

**Raw input:**
> Okay in our ideas we specified that we need to have some infra set up (jenkins, et al). Let's generate a plan in the infra project to get those all set up. Let's brainstorm and first identify any other services we'd need. I know other things we'll need is some kind of headless cms or static page generator for our company site... We also will need an Open Telemetry service... we'll need a grafana service... All projects should connect to the open telemetry... We can even discuss self-hosting Sentry... We need to have terraform, ansible, docker, kubernetes... There's also ideas in the ideas project... Go investigate and be thorough and brainstorm stuff with me

**Here's what I understood:**
> Plan the full infrastructure stack for the company, starting from a brainstorm. This spans the infra repo (`infinite-room-labs-infra/`) and pulls requirements from the ideas repo (`ideas/`). There are 6 concern areas: CI/CD (Jenkins), observability (OpenTelemetry + Grafana + Netdata), error tracking (Sentry or alternative), company website (headless CMS + hosting), IaC tooling structure (Terraform/Ansible/Docker/K8s), and cross-project integration (every project reports telemetry). Some decisions are firm (need observability), some are exploratory (Sentry vs alternatives, CMS approach). You want to brainstorm before committing to a plan.

**Structured prompt (compound format):**

```
## Goal
Brainstorm and plan the complete infrastructure stack for Infinite Room Labs, covering CI/CD, observability, company website hosting, and IaC structure. Research existing ideas and infra conventions before proposing a plan.

## Work Streams

### 1. CI/CD Pipeline
**Goal**: Set up Jenkins (or evaluate alternatives) for automated builds, tests, and deployments.
**Context**: Ideas repo mentions Jenkins specifically. Infra repo uses Terraform Cloud + Ansible.
**Requirements**: Must integrate with all company projects. Docker-based builds.
**Open questions**: Jenkins specifically, or evaluate alternatives (Woodpecker, Drone)?

### 2. Observability Stack
**Goal**: Deploy OpenTelemetry collector, Grafana dashboards, and per-node system metrics.
**Context**: No existing observability infrastructure. All projects need to report telemetry.
**Requirements**: OTel collector with project onboarding automation. Netdata or equivalent on every node. Grafana for visualization.
**Open questions**: OTel project onboarding -- templated or manual? Hosted Grafana Cloud free tier vs self-hosted?

### 3. Error Tracking
**Goal**: Set up error tracking for all projects.
**Context**: Sentry mentioned as option. Free dev tier available. Self-hosting is also possible.
**Requirements**: All projects report errors to a central service.
**Open questions**: Self-host Sentry, use free tier, or evaluate alternatives (GlitchTip)?

### 4. Company Website
**Goal**: Stand up company site with headless CMS and cost-effective hosting.
**Context**: Needs an API backend. Preference for FOSS/self-hosted or free-tier hosted (Vercel, Cloudflare Workers).
**Requirements**: Headless CMS linked to frontend. Minimal hosting cost.
**Open questions**: CMS choice (Strapi, Directus, Payload)? Hosting platform?

### 5. IaC Structure
**Goal**: Define how Terraform, Ansible, Docker, and Kubernetes are organized in the infra project.
**Context**: Infra repo already has `terraform/` with environments/providers hierarchy and `root.hcl` for Terragrunt.
**Requirements**: Clear structure documented in the infra project. Each tool gets its own top-level directory.
**Open questions**: K8s cluster setup -- managed (k3s) or cloud provider?

### 6. Cross-Project Integration
**Goal**: Ensure every project connects to observability and CI/CD automatically.
**Context**: Need templates or automation for onboarding new projects to OTel and Jenkins.
**Requirements**: Standardized approach so new projects get monitoring and CI from day one.
**Open questions**: SDK integration guide? CI template repo?

## Sequencing
1. IaC Structure (defines where everything lives)
2. CI/CD (unblocks automated deployment of subsequent services)
3. Observability (foundation for monitoring everything else)
4. Error Tracking (depends on observability patterns)
5. Company Website (independent but lower priority)
6. Cross-Project Integration (depends on 2 + 3 being operational)

## Boundaries
- Research the ideas repo before proposing -- prior thinking exists there
- Stay within free/low-cost tiers where possible (early-stage company)
- Use existing infra repo conventions (Terraform hierarchy, Terragrunt)
```

**Skill chain**: Execute into brainstorming skill (user said "let's brainstorm").

## Transformation Principles

- Research findings become specific file paths, function names, line numbers, and commit hashes in the output
- Shorter is better -- strip filler words, hedge language, tangents from the raw input
- Only include sections that add information (skip empty Approach or Boundaries)
- The "understood" summary is conversational; the structured prompt is directive and imperative
- Implicit assumptions in the raw input get surfaced explicitly in the structured output
