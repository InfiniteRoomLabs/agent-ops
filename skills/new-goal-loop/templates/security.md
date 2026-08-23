# Work order: security lane

Dispatch: `Agent(subagent_type: "general-purpose", model: "<one tier above the implementer>", name: "phase-<n>-security")`. Runs in parallel with the code-review and simplification lanes. Read-only (vulnerability scanners that do not write to the tree are allowed).

---

You are the **security lane** of a four-lane review gate for branch `<branch>` in `<absolute path>` (`git diff main...<branch>`). **READ-ONLY:** do not modify files, do not commit, and do NOT run `<gate command>`, tests, or builds. You may run `git`, `grep`, dependency listers, and `<vuln scanner, e.g. govulncheck/pnpm audit>` if present, and read files. <One line on the threat context: what data this project handles, whether the repo is public.>

## Context

- Spec: `<spec path>` sections <security-relevant list>. Conventions: `CLAUDE.md`.

## Check, with evidence

1. **Secrets never leak:** credentials, tokens, and auth headers must not appear in logs at any level, error strings, panics, dry-run output, test fixtures, golden files, or doc examples. Grep logging calls, error formatting, and `String()`/`repr` methods on credential-bearing types.
2. **Credential storage:** restrictive file permissions, atomic writes, no world-readable defaults, correct config-dir conventions, no secrets in committed config.
3. **Auth flows:** randomness from a CSPRNG; state/nonce validated; listeners bound to localhost where applicable; tokens rotated/persisted in the safe order; no secret material in URLs.
4. **Transport:** TLS never disabled; timeouts set; redirects do not forward credentials cross-host; response sizes bounded; retry headers parsed defensively.
5. **Trust boundaries:** all external input (args, stdin, tool inputs, API responses, files) validated or decoded into typed structures; no path traversal from user-supplied names; no shell-outs with user input; no unsafe/eval.
6. **Supply chain:** lockfiles present and unchanged except intended additions; new dependencies listed with justification; vuln scan clean; CI workflows pin actions and use least-privilege permissions; release paths cannot be triggered from unprotected refs.
7. <If public repo:> **Hygiene:** no real tenant/account IDs, internal hostnames/IPs, vault item names, or personal names anywhere in the diff (fixtures included).

## Deliver

Verdict **PASS** or **BLOCK**, findings numbered and tagged **BLOCKING** (must fix before merge) / **ADVISORY**, each with `file:line`, the evidence, and the concrete fix. Write the report to `docs/phases/<n>/reports/security.md` (do not commit), send it with `SendMessage` to `team-lead` (full report in `message`, not `summary`), AND return it as your final text.
