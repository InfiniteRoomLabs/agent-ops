---
name: manual-test
description: Write, run, or retire a manual regression test (<testdir>/manual/MT-*.md with a logfmt .results file beside it). Use after a fix that only a live system, a real remote, or a human eye can verify ("record this as a manual test", "smoke test the fix", "re-check this live"), when release-prep reaches Step 4a ("run the manual tests"), or when an automated test now covers one ("retire MT-NNN").
tags:
  function: [engineering]
  scenario: [release-management, regression-testing]
  custom: [manual-test, live-check, smoke-test, results-log]
---

# Manual tests

A manual test is a defect's regression test that cannot run in the automated suite yet: it needs a live, audited system, a real remote, or a human eye. Every such defect gets one with its fix. The runner is a Claude Code session with the relevant MCP tools (a human can run a test only when every step is a Bash command or a manual action; say which in the header). Each run appends one line to a results file that is committed with the change it certifies. The count of active manual tests per repo is tracked debt (agent-ops TESTING.md standard S5) that automation drives toward zero; nothing here builds the tooling that will count it, only the data it will read.

## Iron laws

- A manual test exists because it cannot run offline. If a fixture, mock, or tmpfs remote could prove it, write the automated test instead.
- The live budget is a ceiling. Zero retries, zero polling, zero loops, zero parallel calls. The first failed step ends the run.
- Committed files (script, results, bug report, CHANGELOG line) carry `<placeholder>`s, threshold words, enum words, and shas. Never a resolved id, name, title, item date, document id, URL, home path, or a count of a person's own records.
- One run per test per version. A second run is a second audited read and a second line; both stay in the record.
- An empty `.results` file is an unrun test. The release gate treats it as a stop, not a pass.

## Where things live

`<testdir>/manual/`, where `<testdir>` is the directory the repo's automated tests already use (`test/` in amds-mcp, `tests/` in agent-ops); a repo with neither uses `tests/manual/`. Inside: `MT-<nnn>-<slug>.md` (the script) beside `MT-<nnn>-<slug>.results` (its log), same basename; `retired/` holds pairs an automated test replaced. `<nnn>` is three digits, allocated per repo in order (`ls <testdir>/manual/MT-*.md | sort | tail -1`), never reused; moving a pair to `retired/` does not free its id. `<slug>` is kebab-case and names the claim, not the bug date. `MT-001` is what CHANGELOG lines, `docs/bugs/` resolutions, and release notes cite. Placeholder values live outside the tree in the repo's gitignored `mise.local.toml` `[env]` block as `MT_<NAME>`; `mise exec -- printenv MT_<NAME>` from the repo root resolves one. A placeholder's resolved value also goes into the org redaction term list (`~/.claude/public-readiness-terms.txt`, read through `resolve-redaction-terms.py`) before the first commit that could mention it, so the repo's staged-index redaction check backs the run-time oracle below; a value too common to list (a city name) is caught by the run-time oracle only, and the Placeholders bullet says so. This skill is the only copy of the format; repos link to it, they do not paste it.

## Format choice

The script is the IEEE 829 test-case shape (id, preconditions, numbered steps, each with action, expected result, and what to record) trimmed to Markdown with three labelled lines per step; when a step's output is JSON the expected result is a `jq -e` expression, so a model and a human reach the same verdict without interpretation (jq is already on the machine). Gherkin without Cucumber lost: Given/When/Then is free text until someone writes step definitions, "And" invites several actions per step, and it has no slot for a read budget. Results are logfmt (`key=value key="quoted value"`): append-only by nature, `grep result=FAIL` is the whole query language until tooling exists, a human can type a line by hand, and every language has a parser. TAP lost because a TAP document is one run, so appending runs breaks every parser; JUnit XML is neither appendable nor greppable; JSONL loses to logfmt for a human typing or grepping a line. The only rule added to logfmt is the key order below.

## Script format (`MT-<nnn>-<slug>.md`)

Markdown, ASCII only (`--`, `->`), prose never hard-wrapped. Do not write `.skip(`, `.only(`, `.todo(`, `eslint-disable`, or `@ts-ignore` anywhere in the file: repos grep their whole test directory for those tokens and the gate would fail on the script.

### Header

- Line 1: `# MT-<nnn> -- <the one-line claim the test proves>`
- Line 2: one sentence, `Added in <version> for <bug or phase link>`, naming what the test guards and where the offline half lives.
- Then five bullets, all required:
  - **Runner:** who can execute it. `a Claude Code session with the <name> MCP server registered` whenever any step is a `tool` step (a human in that session can only ask Claude to make the call, at which point Claude is the runner); `human` only when every step is Bash or manual. Name every step that is manual.
  - **Placeholders:** every `<name>` used below with its env var (`MT_<NAME>`: uppercase, `-` -> `_`) and the statement that values live in the gitignored `mise.local.toml` `[env]`, are in the redaction term list (or why not), and never appear in a committed file.
  - **Live budget:** the maximum number of tool calls that touch the live system, which steps they are, how many of them navigate (fetch a page or sign in, the ones an audited system logs as activity), and the prohibitions: no retries, no polling, no loops, and the tools that must not be called inside a run because they are not the thing under test. Steps that open an individual item or download anything are allowed only when that item is the thing under test, and the header says so. State how a BLOCKED that needs a forbidden tool to clear (an MFA prompt) is resolved between runs.
  - **Automate when:** the concrete condition under which this test becomes an automated one (a fixture, a sandbox, a snapshot), or `never: <reason>` for a permanent live smoke.
  - **Preconditions:** checkable local state (tree, config, server registered, which directory Bash steps run from, which steps must run back to back). An unmet precondition is `BLOCKED`, not `FAIL`.

### Steps (`## Steps`, then `### <n>. <title>` per step)

Exactly one tool call or one manual action per step, three labelled lines:

- `Do (<kind>):` what to execute, verbatim. `<kind>` is `Bash` (a local command, no network), `tool` (an MCP tool name plus a JSON argument object, placeholders inside it), or `manual` (an action only a human performs, written as the words the human needs; a Claude runner prints the line verbatim, asks the human to confirm it is done, and ends its turn). A live step carries `(live <k>)` in its title, and `(navigation <j>)` when it navigates.
- `Expect:` decidable from the step's output alone. For JSON output, a `jq -e` expression over the saved result (exit 0 is pass). For Bash output, the exact shape (`exit 0`, `no output`, `exactly one line matching <regex>`). For manual steps, one yes/no observable. Name the known bad outcomes and classify each: `-> BLOCKED` for "could not run" (an MFA prompt, a stale process, an unset placeholder, a pool that idle-closed between steps), `-> FAIL` for "the product is wrong". Never "looks right".
- `Record:` `key=<which value from the output>` pairs for the results line, or `nothing`. Values are threshold words (`ge1`, `zero`), enum words, shas, durations. Never ids, names, titles, item dates, paths, URLs, or an error's `message` or `path`; for an error, the `kind` only. A count of items that belong to a person (documents, messages, appointments) is a personal datum once the repo has a public remote: record the threshold word the Expect tested, not the number.

Rules: one action per step (if you need "and", you need another step); the live budget equals the number of `(live k)` steps, no slack; a failed `Expect` ends the run at that step with no retry and no skipping ahead; a `BLOCKED` before the first live step spent nothing, so fix the blocker and start a new run (a new line); a `BLOCKED` raised by a live step still spent that call and `live=` says so.

### Result (`## Result`)

The results line template for this test, fixed keys first, then its record keys in step order, and the file it appends to. Nothing else.

### Template

```markdown
# MT-<nnn> -- <claim>

Added in <version> for `docs/bugs/<file>.md` (<what it guards>; offline half: <test file>).

- **Runner:** a Claude Code session with the `<server>` MCP server registered. Step <n> is manual.
- **Placeholders:** `<x>` -- `MT_X` in the gitignored `mise.local.toml` `[env]`, present in the redaction term list; resolved values never appear in this file, the `.results` file, a commit message, or a bug report.
- **Live budget:** <n> tool calls (steps <a>-<b>), <m> of them navigations. No retries, no polling, no loops. Do not call <tools> inside a run; <how a BLOCKED that needs one is cleared between runs>.
- **Automate when:** <condition> | never: <reason>
- **Preconditions:** <list>; Bash steps run from the repo root; steps <a>-<b> run back to back.

## Steps

### 1. <title>
Do (Bash): `<command>`
Expect: <shape>
Record: `<key>=<value>`

### 2. <title> (live 1, navigation 1)
Do (tool): `<tool> {"arg": "<x>"}`, result written verbatim to `<scratch>/MT-<nnn>/step2.json`
Expect: `jq -e '<expr>' <scratch>/MT-<nnn>/step2.json` exits 0; `{"status":"mfa_required"}` -> BLOCKED; an error object (`kind` present) -> FAIL, record `kind` only.
Record: `<key>=<threshold word>`

## Result

Append one line to `<testdir>/manual/MT-<nnn>-<slug>.results`:
`ts= test=MT-<nnn> repo= result= version= build= runner= live= failed= <record keys> [note=""]`
```

## Results format (`MT-<nnn>-<slug>.results`)

1. One logfmt line per run, appended at the end (`printf '%s\n' "<line>" >> <file>`). Lines are never edited, reordered, or deleted; a wrong line is corrected by appending another with `note="supersedes <ts>"`.
2. Fixed keys, in this order, always present: `ts` (UTC ISO-8601 to the second, `Z`; the time the run started, kept across turns), `test` (`MT-<nnn>`), `repo` (repo basename, so concatenated files keep provenance), `result` (`PASS`, `FAIL`, `BLOCKED`, `SKIP`, `RETIRED`), `version` (the version under test from the manifest), `build` (short sha of HEAD when the run started; in a release run the release commit is its child), `runner` (`claude-code:<model id>`, `human`, or `script:<command>`; new values may be added, none removed, never a person's name), `live` (live calls actually made, integer, including the one that raised a BLOCKED), `failed` (step number that failed or was blocked, or `-`).
3. Then the test's record keys, in script order, only for steps that ran.
4. Then, optionally and last, `note="..."`: double-quoted ASCII, no newlines, no inner double quotes, the only free-text slot. For a FAIL it carries `kind=<error kind>` and nothing more specific; for a BLOCKED, the one-word reason (`mfa_required`, `pool idle-closed`, `stale server`, `placeholder <name> unset`, `result too large`).
5. Values with spaces are double-quoted, everything else bare; keys are `[a-z_][a-z0-9_]*`. Keys are only ever added, never change meaning; a new meaning is a new key (that is the whole versioning rule, so no schema version field).
6. The file is committed; the repo's redaction check runs on it like any staged file. The release gate reads only the last line, and a file with no lines is an unrun test.

Query language until tooling exists: `grep -h result=FAIL <testdir>/manual/*.results`, `tail -n1 <testdir>/manual/MT-001-*.results`, `ls <testdir>/manual/MT-*.md | wc -l` (the manual count the org drives to zero).

Examples:

```
ts=2026-10-27T21:04:11Z test=MT-001 repo=amds-mcp result=PASS version=0.1.2 build=9f3e2c1 runner=claude-code:claude-fable-5-1 live=4 failed=- a_docs=ge1 a_path=ok b_docs=ge1 b_path=ok
ts=2026-10-27T20:31:40Z test=MT-001 repo=amds-mcp result=FAIL version=0.1.2 build=9f3e2c1 runner=claude-code:claude-fable-5-1 live=2 failed=9 a_docs=ge1 note="kind=unexpected_state"
ts=2026-10-27T20:12:02Z test=MT-001 repo=amds-mcp result=BLOCKED version=0.1.2 build=9f3e2c1 runner=claude-code:claude-fable-5-1 live=1 failed=8 note="mfa_required"
```

## Procedure: writing a test

1. Confirm it is manual: name the blocker. That sentence is the `Automate when:` line.
2. Take the next id, copy the template, fill the header from the bug report, not from memory.
3. Write the steps from the verification you just did by hand (the fix's own smoke test is the first run). Non-live steps first (tree, version, build, reload, freshness), live steps last, and a state read placed after the navigation it verifies, never before. Where a precondition can silently change between two steps (an idle timeout, a pool relaunch), say in Preconditions that those steps run back to back and classify the symptom as BLOCKED in the Expect.
4. Count the live steps and navigations; write the budget to match; list the tools the test must not call inside a run and how a BLOCKED that needs one is cleared between runs.
5. Replace every operator value with a `<placeholder>`, document its `MT_<NAME>`, and put the value in `mise.local.toml` `[env]`. Then check every resolved value against the org redaction term list with the resolver script and add any that is missing (or say in the header why it cannot be listed) before the first commit, so the repo's staged-index check backs the run-time oracle.
6. Create the empty `.results` file. Grep both files against the redaction term list (`scripts/redaction-check.sh` on the staged index where the repo has it, else `resolve-redaction-terms.py` piped to grep). Repos that format Markdown run their formatter. Add a CHANGELOG line under Added; cite the id from the bug file's Resolution section; land the test on `main` before the release that first runs it.

## Procedure: running a test (release-prep Step 4a calls this once per active test)

1. Read the header. Resolve each placeholder with `mise exec -- printenv MT_<NAME>`; an empty one is `BLOCKED` with `note="placeholder <name> unset"`. Keep resolved values in context only; a Bash step that needs one uses `mise exec -- sh -c '... "$MT_<NAME>" ...'` so the value never appears in a command line.
2. Check the preconditions; unmet -> `BLOCKED`.
3. Count the live steps; if the count exceeds the budget line, the script is invalid: `BLOCKED` before the first live step. Take `ts` and `build` now; they do not change for the rest of the run.
4. Execute steps in order, one tool call per step. `Bash` and `tool` steps run as written with placeholders substituted. For a `tool` step with a `jq -e` Expect: write the tool result's `text` block verbatim to `<scratch>/MT-<nnn>/step<n>.json` with the Write tool (no reformatting, no trimming), confirm `jq -e . <file>` exits 0 (the copy is intact), then run the Expect expression; exit 0 is pass. A result too large to re-emit intact is `BLOCKED` with `note="result too large"`; never decide a long list by eye. A `manual` step ends the runner's turn: print the Do line verbatim, ask the human to confirm it is done, and stop; the run resumes in the next message with the same `ts` and `build`, placeholders re-resolved with `mise exec -- printenv` before the next tool step. On the first miss stop: set `failed=<n>`, classify per the step's Expect, record only the error `kind`. Never make a live call the script does not list, never retry, never poll. A tool forbidden by the header is forbidden inside a run only: a `BLOCKED` that needs it (an MFA code) is cleared between runs by the human, or by the session on the human's say-so, outside any run; the sign-in attempt that raised it was a live call and the line says so (`live=1 failed=<n> note="mfa_required"`); then a new run starts and writes a new line.
5. Build the line (fixed keys, the record keys of steps that ran, optional note) and append it. Then run the redaction oracle over every file the run wrote: the `.results` file, the `MT-<nnn>-<slug>.md` if it was touched, and any bug report or CHANGELOG line written during the run: `mise exec -- sh -c 'grep -c "$MT_<NAME>" <file>'` for every placeholder and every file must print `0` (grep exits 1, which is the expected outcome), and the repo's redaction check on the staged index must pass. A hit means the line is wrong: append a corrected line with `note="supersedes <ts>"` and tell the user the file needs a history rewrite before it is pushed. Then delete `<scratch>/MT-<nnn>/`: the saved results hold live-system content.
6. Commit the `.results` change with the release commit when inside release-prep; otherwise on the commit that carries its CHANGELOG line (`... (live re-check MT-<nnn> PASS)`), because a changelog guard may block a results-only commit on `main`.
7. On FAIL: open `docs/bugs/<YYYY-MM-DD>-<slug>.md` in the repo's redacted bug-report shape (tenants as tenant A / tenant B, people by role, no item names, dates, or ids, no screenshot path) and tell the user the release is blocked. Do not re-run to see if it passes.

## Procedure: retiring a test

When the `Automate when:` condition is met and the automated test is merged, in the same commit: append `result=RETIRED note="replaced by <automated test path>"` to the `.results`, `git mv` both files to `<testdir>/manual/retired/`, CHANGELOG line under Removed. The release gate's glob never sees `retired/`; the history under it is the evidence the defect was watched across releases before it was automated.

## Read-budget rules

- Every tool call that touches the live system counts, including one that returns an error or raises a BLOCKED, and including a sign-in the server performs inside a call (state it in the header: "sign-in, if needed, happens inside step N and is counted there").
- No polling, no sleep-and-retry, no `until` loops, no parallel calls to the same system.
- Never open an individual item (message, document, record) or download anything unless the header names it as the thing under test.
- A script with no budget line is not runnable; fix the header first.

## Anti-patterns

- Eyeballing a jq Expect over a long list. Running a live call that is not a step. "Just one more read" after a FAIL. Editing a results line. Recording a title, a sender, an item date, an id, a count of a person's records, or an error `path` (it points at a screenshot that may hold personal data). Leaving `<scratch>/MT-<nnn>/` behind. Writing the test after the release instead of with the fix. Putting a manual test into the automated gate (`check.sh`, pytest, vitest). Treating BLOCKED as PASS. Treating an empty `.results` as PASS.

## Not built yet, and what adds it

A runner script (when a test exceeds about 15 steps or CI must execute one). A `.results` parser or dashboard (when a second repo has results, or someone asks which manual test is flaky). A CI job on a stale `.results` (when a repo's release is cut by CI rather than in a session). An org-wide registry or any Featmap/Plane/Slack posting (when the third repo has manual tests; until then the CHANGELOG line and the committed `.results` are the communication). Step-level results (`steps=` key, when an analyzer needs it). An id-allocation tool (`ls | sort | tail -1` below about 20 tests per repo). A PreToolUse guard on `git tag` without a current PASS line (after the second release through Step 4a, if the skill proved the weak point). Automatic placeholder substitution (a `mise` task printing the resolved set, when a test has more than three placeholders). `jq` pinned in `mise.toml [tools]` (the day CI runs a manual test).
