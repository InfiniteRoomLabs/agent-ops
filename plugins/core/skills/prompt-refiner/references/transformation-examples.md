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

## Transformation Principles

- Research findings become specific file paths, function names, line numbers, and commit hashes in the output
- Shorter is better -- strip filler words, hedge language, tangents from the raw input
- Only include sections that add information (skip empty Approach or Boundaries)
- The "understood" summary is conversational; the structured prompt is directive and imperative
- Implicit assumptions in the raw input get surfaced explicitly in the structured output
