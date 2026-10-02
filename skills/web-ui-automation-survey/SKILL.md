---
name: web-ui-automation-survey
description: "Use when asked to click through, map or document a web app's UI so it can be automated or tested: explores the live app read-only and writes an exhaustive Page → Component → Element survey report with selectors, routines and user stories."
tags:
  function: [engineering, research]
  scenario: [ui-automation, test-planning, app-discovery]
  custom: [browser, selectors, puppeteer, read-only, survey]
---

# Web UI automation survey

Explore a live web app the person is signed into and write the report someone would need to automate it: every page, component and element with its selector, the routines an automation would run, and user stories. The report is written from what the app renders and ships, and it is the only deliverable. Turning it into code is the job of the `web-ui-automation-components` skill; mention that in one line at the end and do not start it unasked.

The organising idea is **Page → (is comprised of) → Components → (are comprised of) → other Components + Elements**. A sidebar is a component, and each of its menu items is a component too, because an item carries state of its own (it is active, it has a notification badge with a count). Anything that repeats or carries state is a component with properties (what an automation reads) and actions (what it clicks). Model the state the app actually renders, nothing speculative.

The request usually names the app or the tab, and that is enough to begin. Ask first only if you cannot tell which app, tab or account role is meant.

This is a long job and your context may be compacted on the way. Keep a task list (one item per step and per group of pages) and keep the notes file current: it is what lets the work resume and what the report is checked against.

## Ground rules

You are inside someone's real account, so the survey has to leave it exactly as it was found.

- **Look, don't act.** Opening menus, tabs, accordions and dropdowns, hovering, scrolling and typing into search or filter boxes are fine. Anything that sends, saves, deletes, starts, stops, pays, uploads, downloads, toggles a setting, changes permissions or signs out is not. Record such a control as *Not exercised* and learn what it does from the code (step 6).
- **Navigation is not automatically safe.** Classify a route before visiting it. Never open sign-out, unsubscribe, confirm, verify or token links. Opening an unread item marks it read, so open only items that are already read, or describe the view from the code.
- **Check before clicking anything that is not plain navigation.** Some controls act the moment they are clicked, with no confirmation: on one surveyed panel the code showed that toggling the power switch stops the server at once. Read the label, the element type and, when unsure, the handler in the bundle first. If you still cannot tell, do not click.
- **Open a dialog only to capture it**, and only when opening it is harmless. Close with Cancel or Escape, never Enter, which often confirms. Do not trigger native browser dialogs (alert, confirm, a leave-page prompt): they freeze the browser tool.
- **Edit a field only where the form has an explicit Save step**, only to reveal a dependent control, and put the old value back before leaving. If fields save as they change, do not edit them.
- **Never sign in for the person.** If a login page appears or the session expires mid-survey, stop, ask them to sign in, then continue from your notes.
- **Keep secrets and personal data out of the report.** Pages hold more than they show: passwords in plain text inputs, credentials inside link URLs, bearer tokens in client state. Raw findings live only in the scratch notes. The report names the product and its public host, and uses placeholders for everything that identifies this person's tenant, account or records (`{tenant}`, `{patientId}`, `{serverName}`, `{ip}`), including the host when it is specific to their tenant. Never copy raw notes to a project, to memory or to delivered files.
- **Say how you know.** Label every page and feature **Verified** (seen live), **Inferred** (read from the bundle, translations or API but not rendered for this account), **Not exercised** (deliberately not clicked) or **Not verified** (tried, and the app failed; say how). The person will plan real automation from this, so a selector reconstructed from a template has to look like a guess.
- The app may log every view in an audit trail. Visit each page once and do everything for it in that visit; do not reload or poll in loops.
- If something you did turns out to have changed state, stop and tell the person exactly what happened.

## 1. Set up

Load the browser skill for the tool in use (`chrome-browser` for Claude in Chrome) and follow it for tabs and permissions. Work in the tab the person points at; if they gave only a URL, open a new tab on it. If no browser tool is connected, say so: a signed-in app cannot be surveyed any other way.

In your scratch (temporary working) directory create `survey-notes.md` and append to it after every page: trees, selectors, counts, option lists, API calls. Keep `identifiers.txt` beside it, one per line, with every real identifier you come across (ids, names, usernames, emails, phone numbers, addresses, IPs, tenant and display names); the report is grepped against it before delivery.

## 2. Install the helpers

Run the **Survey helpers** block at the end of this skill once through the page-scripting tool. It defines `window.__sv`:

| Call | Use |
|---|---|
| `__sv.dump('SV-NAV', 'nav')` | Print the DOM tree under a selector (or an element), one line per node: `tag#id.classes[attrs] "own text"`. Options: `{ depth: 8, max: 40, text: 60, classes: 6 }`. `max` is children shown per parent. `text: 0` prints structure only: no text, no field values, no free-text attribute values. Use it on regions full of personal data. |
| `__sv.out('SV-OPTS', value)` | Print anything you computed yourself (option labels, table headers, store keys, a JSON extract). |
| `__sv.hook()` then `__sv.out('SV-CALLS', __sv.calls)` | Record what the app asks its backend from now on: method, path, GraphQL operation text, and request and response *shapes* (types, not values). `__sv.loaded()` lists the paths requested before the hook existed. |
| `__sv.scripts()`, `__sv.load(0)`, `__sv.grep('SV-ROUTES', /path:"[^"]+"/, 0)` | List the script files, load one into `__sv.bundle` (index or URL; it is asynchronous, so check `__sv.bundle.length` in the next call), search it in the page. The third argument adds that many characters of context around each match. |

Output goes to the console in parts headed `SV-NAV# part1/3`, because tool results are cut short. Read it with the console-reading tool using the pattern `SV-NAV#`, and clear the console afterwards. Give every dump its own tag.

What the helpers hide: URLs keep their shape only (credentials masked, numeric and uuid path segments shown as `{id}`, query parameter names without values), password-like fields and token-like attributes print as `***`, and `grep` prints the standalone word `location` as `LOC` and passes quoted URLs that carry a query through the same masking. Everything else is printed as it is. Masking cannot recognise a name or a diagnosis in visible text, which is why the notes stay in scratch.

The helpers change nothing in the account. They live in the page's memory, and `hook()` wraps the page's network functions there, so any reload or full navigation removes them; run the block again (it keeps what it has recorded when it is still present).

## 3. Recon

Call `__sv.hook()` first, then answer these before walking pages. They become §1 of the report and decide how every routine waits and selects.

- **Framework and version**, and how to reach the router and client state from the page. Vue 3: the mount element (often `#app`) has `__vue_app__`, which gives `.version`, `.config.globalProperties.$router.getRoutes()` and `$pinia._s`, a Map of stores whose action names tell you what each button calls. Angular: the `[ng-version]` attribute; routes and state are not reachable in a production build, so use the bundle. React (17 and later): nodes carry `__reactFiber$…` and `__reactProps$…` keys; state is usually not reachable, so use the bundle and the network hook. A server-rendered multi-page app reloads on every navigation: reinstall the helpers on each page and expect no client router.
- **URL shape**: which segments are tenant, region or record ids. They become placeholders.
- **Backend style**: REST, GraphQL, WebSocket subscriptions, and where live values come from.
- **Stable hooks**: `data-testid` and its cousins, roles and `aria-*`, custom element tags, BEM classes. **Unstable**: auto-numbered ids (`mat-select-8`, `vs5__listbox`), hashed classes, utility classes. State the selector policy in the report.
- **Readiness**: does `document.title` change per route? Are there skeletons or `aria-busy`? An active nav item? A page heading? Choose the signal each page routine will wait for.
- **Overlays**: where dialogs, dropdown panels, menus and toasts render (often moved to `body` or an overlay container), how many dialog systems coexist, how long toasts live.
- **Session**: what "signed out" looks like (URL, host, title), token refresh, idle or keep-alive prompts.
- **Danger and secrets**: controls that act without confirmation, and sensitive values present in the DOM or client state.
- **Files**: how downloads and uploads work (blob, new window, hidden form, native picker).
- **Traps**: sticky or mobile duplicates that repeat ids and test ids; iframes (legacy pages, payment forms, which are never automated); virtualised lists that render only the visible slice; third-party scripts and feature flags.

## 4. Inventory

Model the shell first: the app frame, the navigation (sidebar, top bar, account menu, sub-menus and tabs) and the global overlays. For each nav item record its key, label, route, icon, section and whatever state it carries (active, external, disabled, badge and count, children).

Then list every route without visiting any: nav items, tabs and sub-routes from the dumps, plus routes in the router table or bundle that the menu does not show. Mark each one visit, do not visit (see the ground rules) or not reachable for this account. This list becomes the route table and the coverage matrix.

## 5. One deep visit per page

For each route marked visit, capture in a single visit (and add to the inventory any tab or sub-route the visit reveals):

- route, title, heading, the nav item that leads there, tabs
- the component tree down to leaf elements, with a selector for each
- every table: columns, row markup, empty state, sorting, pagination or virtual scroll
- every form: each field's label, selector, control type and constraints. Open each dropdown and note where its panel renders. List a fixed option set in full; for a data-backed list give the count and the shape of an option.
- every menu, context menu and row action
- dialogs and toasts: structure and copy, either opened and cancelled or read from the code
- loading, empty and error states
- what the page calls: `__sv.calls` for this visit, plus `__sv.loaded()` on the first page
- features switched off for this account (flags, role, plan), as Inferred, from the code

Count with a query (`querySelectorAll(...).length`), not by eye; wrong counts were the most common error found in review. For a large enumeration (a settings schema, a long option list), print it as JSON through `__sv.out`, save the console output to a notes file as it is, and generate the report appendix from that file by script instead of transcribing it.

Dumps are the main instrument. Take a screenshot only when the structure does not explain what is on screen.

## 6. Read the code for what you did not trigger

Everything marked Not exercised or do-not-visit still has to be described, and the shipped code has the answers.

- **Bundle.** `__sv.scripts()`, load the main file (and the lazy route chunks it names), then search for: route config, endpoint paths, GraphQL operations (as text, or compiled: `operation:"mutation",name:{kind:"Name",value:"…"`), component names, the handler behind a risky button, dialog and toast copy, feature flags, table column definitions.
- **Translations.** If the app loads an i18n JSON file, fetch it. It holds the copy of every dialog, toast and empty state you did not trigger. It can be large, so filter by key prefix in the page before printing.

When the survey is finished, reload the tab once so the network hook and the loaded source are gone.

## 7. Tool quirks (Claude in Chrome)

| Symptom | Do |
|---|---|
| A `javascript_tool` result is cut off after about a thousand characters | Print through `__sv.out` / `__sv.dump` and read with `read_console_messages`. |
| Old output comes back when reading the console | Use a fresh tag per dump, keep the `#` in the pattern, clear after reading. |
| `[BLOCKED: Cookie/query string data]` | Seen when a script or its output touched `location`, cookies or URLs with query strings. Take the current URL from the tab context, and print URLs and source only through the helpers. |
| `read_network_requests` returns nothing | Use `__sv.hook()` and `__sv.loaded()`. |
| A batch of browser actions fails part-way | It spanned a navigation. Navigate in its own call, then reinstall the helpers. |

## 8. Write the report

Write `{app}-automation-survey.md` from the notes. It is a Markdown file, not a doc, because it travels with the code built from it. Keep this structure; the components skill reads it by section and routine id.

```
# {App} — UI Survey for Automation
  Intro: date surveyed, URL shape with placeholders, what was and was not surveyed, how it was captured
  Conventions: placeholders; the evidence labels; selector policy
## 1. Platform facts that shape every automation routine     table: Topic | What was observed | Automation consequence
## 2. The component model (Page → Components → Components + Elements)
   2.1 Shell (tree)   2.2 Navigation (tree, menu-item property table, table of observed items)
   2.3 Other shell components, if any   2.4 Shared primitives (a property table each: switch, select, table, dialog, toast, …)
## 3. Pages, features, routines and user stories            3.0 Authentication (how sign-in works, how a dead session looks), then one subsection per page
## 4. Cross-cutting routines                                 generic routines, defined here; index of page routines; read-only vs write
## 5. Route table
## 6. API surface                                            endpoints with parameter names; operations; client state worth reading, if reachable
## 7. Feature inventory / coverage matrix                    Area | Feature | Route | Status | Side effect
## 8. Open items                                             everything Inferred that a first live run must confirm
## Appendix A …                                              large schemas and option lists, when there are any
```

Every page subsection has the same parts: a heading with route and evidence label, the tree, the properties, the APIs, the routines, notes when there is something to say, and the user stories. This invented example shows the depth expected:

````
### 3.4 Invoices — `/{tenant}/billing/invoices` — Verified (download and pay Not exercised)

```
InvoicesPage  main[data-testid="invoices-page"]
├── PageTitle            h1 "Invoices"
├── FilterBar            form[data-testid="invoice-filters"]
│   ├── statusSelect     div[role=combobox][aria-label="Status"]     (options render in body > div.select-panel: All, Open, Paid, Void)
│   └── searchInput      input[name="q"][placeholder="Search invoices"]
├── InvoicesTable        table[aria-label="Invoices"]                 (columns: Number, Date, Amount, Status; empty state p.empty "No invoices yet")
│   └── InvoiceRow ×N    tbody tr[data-invoice-id]
│       ├── number       td.col-number > a[href="/{tenant}/billing/invoices/{invoiceId}"]
│       ├── status       td.col-status > span.badge                   (Open | Paid | Void)
│       └── rowMenu      button[aria-label="Actions"]                 → menu: View, Download PDF (Not exercised), Pay (Not exercised)
└── Paginator            nav[aria-label="Pagination"]                 (range label "1–10 of N"; Previous / Next)
```

Properties for an `Invoice`: `id` (row attribute), `number`, `date`, `amount`, `status`, `href`.

APIs: `GET /api/{tenant}/invoices?status&q&page` → `{ total, items: [{ id, number, date, amount, status }] }`.

Routines
- **R-INVOICES-LIST(status?)**: R-NAV-SIDEBAR(billing) → wait for `table[aria-label="Invoices"]` with `aria-busy="false"` → optionally R-SELECT(statusSelect, status) → read rows, following the paginator until the range label reaches N.
- **R-INVOICE-PAY(number)** (write): row menu → Pay → dialog "Pay invoice?" → Confirm → expect toast "Payment submitted". Not exercised; copy from the translations.

Notes: the table re-renders on every filter change (search is debounced by about 300 ms). Amounts are formatted per locale.

User stories
- US-4.1 As a customer I can list my invoices, filter them by status and search them by number.
- US-4.2 As a customer I can pay an open invoice after confirming.
- US-4.3 As an automation I can export all invoices across pages as typed records without triggering any action.
````

Conventions:

- **Trees**: one node per line as `Name   selector   (note)`. Components in PascalCase, elements in camelCase, `×N` for repeats, `→` for what an action triggers.
- **Routines**: `R-{AREA}-{VERB}`. Each one reads navigate → wait signal → read or act → expected feedback, and is marked `(write)`, `(destructive)` or `(write, no dialog)` where it applies. Generic routines (navigate, select an option, read a table, expect a dialog, expect a toast) are defined once in §4; page routines are defined in §3 and indexed in §4, which also classifies every routine as read-only or write.
- **User stories**: `US-{page}.{n}`, numbered per page, including the automation's own stories.
- **Selectors** are plain CSS. Text matching happens in code, so no `:has-text()`. Use attribute selectors for ids containing dots, and scope ids that are duplicated.

"Exhaustive" means every route is visited or accounted for, every interactive element appears in a tree with a selector, every table's columns and every fixed option set are listed, every dialog and toast is described, and every feature has a row in the coverage matrix. For scale: two apps of a dozen or so pages each produced reports of roughly a thousand lines.

## 9. Check and deliver

1. Code fences balance, every table has a consistent column count, and a `|` inside a code span in a table cell is escaped.
2. Every routine id that is referenced is defined exactly once, and every page routine appears in the §4 index. Story numbers are sequential.
3. Grep the report for every line of `identifiers.txt`. Zero hits.
4. Give a subagent the report and the notes (or, without subagents, reread the report against the notes yourself) and ask for findings only: is every selector, route, API path, option list and UI string supported by the notes or marked Inferred; do counts and names match; is there any personal data or secret; are there internal contradictions; is the Markdown sound. Fix what is confirmed. When a finding contradicts the notes, recheck the source before changing anything, because reviewers are sometimes wrong.

Deliver the report file. Close with a few sentences: what was covered, the findings that matter most to anyone automating this app (controls that act without confirmation, secrets exposed in the page, a faster path that avoids the DOM), and what is Inferred and needs a first live run. Add one line saying the `web-ui-automation-components` skill can build typed Puppeteer components from the report. No step-by-step recap.

## Survey helpers

```js
(() => {
  const sv = (window.__sv = window.__sv || { calls: [], bundle: '', hooked: false });
  const rawFetch = sv.rawFetch || (sv.rawFetch = window.fetch.bind(window));
  const SECRET = /pass|secret|token|jwt|bearer|api[-_]?key|credential|csrf|session|ssn|cvv|card/i;
  const SHOW = ['href', 'src', 'action', 'role', 'type', 'name', 'placeholder', 'title', 'for', 'target', 'disabled', 'checked'];
  // Attributes whose values are structure, not content: safe to print even in structure-only mode.
  const STRUCT = /^(role|type|name|for|target|disabled|checked|data-testid|data-test|data-cy|data-qa|aria-(expanded|busy|checked|selected|current|hidden|disabled|haspopup|modal|sort|pressed|live|required|invalid))$/;
  const SKIP = ['SCRIPT', 'STYLE', 'NOSCRIPT', 'LINK', 'META'];
  const cut = (s, n) => (s.length > n ? s.slice(0, n) + '…' : s);

  // URLs carry credentials, tokens and record ids. Keep the shape only: mask userinfo and mail/phone targets,
  // turn numeric, hex and uuid path segments into {id}, keep query parameter names without values, keep hash routes.
  const ids = (p) => p.replace(/\/(?:\d{3,}|[0-9a-f]{16,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?=[/?#]|$)/gi, '/{id}');
  const names = (q) => (q ? '?' + q.split('&').map((kv) => kv.split('=')[0]).filter(Boolean).join('&') : '');
  const safeUrl = (u) => {
    const s = String(u);
    if (/^(mailto|tel|sms):/i.test(s)) return s.split(':')[0] + ':***';
    const m = /^([^?#]*)(?:\?([^#]*))?(?:#([\s\S]*))?$/.exec(s);
    const hash = m[3] && m[3][0] === '/' ? '#' + safeUrl(m[3]) : '';
    return ids(m[1].replace(/\/\/[^/@\s]*@/, '//***@')) + names(m[2]) + hash;
  };
  const opaque = (v) => /^eyJ[\w-]+\.[\w-]+\./.test(v) || /^[a-f0-9]{32,}$/i.test(v);
  const secretField = (el) => el.type === 'password' ||
    SECRET.test([el.name, el.id, el.placeholder, el.getAttribute('aria-label'), el.getAttribute('autocomplete')].join(' '));

  function line(el, o) {
    const quiet = o.text === 0; // structure only: keep what a selector needs, drop what a person typed or a record shows
    let s = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '');
    const cls = Array.from(el.classList);
    if (cls.length) s += '.' + cls.slice(0, o.classes).join('.') + (cls.length > o.classes ? '(+' + (cls.length - o.classes) + ')' : '');
    const attrs = [];
    for (const a of Array.from(el.attributes)) {
      const n = a.name;
      if (!SHOW.includes(n) && !n.startsWith('aria-') && !n.startsWith('data-')) continue;
      let v = a.value;
      if (n === 'href' || n === 'src' || n === 'action') v = safeUrl(v);
      else if (SECRET.test(n) || opaque(v)) v = '***';
      else if (quiet && v !== '' && !STRUCT.test(n)) v = '…';
      attrs.push(v === '' ? n : n + '="' + cut(v, 80) + '"');
    }
    if (!quiet && typeof el.value === 'string' && el.value !== '' && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) {
      attrs.push('value="' + (secretField(el) ? '***' : cut(el.value, 40)) + '"');
    }
    if (attrs.length) s += '[' + attrs.join(' ') + ']';
    if (!quiet) {
      const own = Array.from(el.childNodes).filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ').replace(/\s+/g, ' ').trim();
      if (own) s += ' "' + cut(own, o.text) + '"';
    }
    return s;
  }

  // One line per element, indented by depth: tag#id.classes[attrs] "own text".
  function ser(el, depth, o) {
    const pad = '  '.repeat(depth);
    let host = el.shadowRoot || el, mark = el.shadowRoot ? ' #shadow' : '';
    if (el.tagName === 'IFRAME') { try { host = el.contentDocument.body; mark = ' #document'; } catch (e) { host = el; } }
    const s = pad + line(el, o) + mark;
    if (el.tagName.toLowerCase() === 'svg') return s;
    const kids = Array.from(host.children).concat(el.shadowRoot ? Array.from(el.children) : [])
      .filter((k) => !SKIP.includes(k.tagName.toUpperCase()));
    if (!kids.length) return s;
    if (depth >= o.depth) return s + ' {…' + kids.length + ' children, ' + host.querySelectorAll('*').length + ' descendants}';
    let t = s;
    for (const k of kids.slice(0, o.max)) t += '\n' + ser(k, depth + 1, o);
    return kids.length > o.max ? t + '\n' + pad + '  … +' + (kids.length - o.max) + ' more children' : t;
  }

  // Tool results are cut short, so everything goes to the console in parts headed "TAG# part1/3".
  function out(tag, value) {
    const text = typeof value === 'string' ? value : JSON.stringify(value, null, 1) || String(value);
    const size = 6000, parts = Math.ceil(text.length / size) || 1;
    for (let i = 0; i < parts; i++) console.log(tag + '# part' + (i + 1) + '/' + parts + '\n' + text.slice(i * size, (i + 1) * size));
    return tag + '#: ' + text.length + ' chars, ' + parts + ' part(s)';
  }

  // dump('SV-NAV', 'nav') or dump('SV-ROW', someElement, { depth: 4, max: 5, text: 0 })
  function dump(tag, target, opts) {
    const o = Object.assign({ depth: 8, max: 40, text: 60, classes: 6 }, opts);
    const roots = typeof target === 'string' ? Array.from(document.querySelectorAll(target)) : [target];
    return out(tag, roots.map((r) => ser(r, 0, o)).join('\n=====\n') || '(no match)');
  }

  // Structure without values: { id: 'number', items: [{ name: 'string' }, '×12'] }.
  function shape(v, d) {
    if (v === null || typeof v !== 'object') return v === null ? 'null' : typeof v;
    if (d > 4) return '…';
    if (Array.isArray(v)) return v.length ? [shape(v[0], d + 1), '×' + v.length] : [];
    const r = {};
    for (const k of Object.keys(v).slice(0, 60)) r[k] = SECRET.test(k) ? '***' : shape(v[k], d + 1);
    return r;
  }

  // Record what the app asks its backend from now on: method, path, GraphQL operation text, and the shapes of
  // request and response bodies. This wraps the page's own network functions until the tab is reloaded.
  function hook() {
    if (sv.hooked) return 'already hooked';
    const parse = (b) => { try { return typeof b === 'string' ? JSON.parse(b) : null; } catch (e) { return null; } };
    const gql = (x) => (x && x.operationName ? x : x && x.payload && x.payload.operationName ? x.payload : null);
    const note = (kind, method, u, body) => {
      const j = parse(body), ops = (Array.isArray(j) ? j : [j]).map(gql).filter(Boolean);
      const rec = { kind, method, url: safeUrl(u) };
      if (ops.length) rec.ops = ops.map((g) => ({ op: g.operationName, query: cut(String(g.query || ''), 1500), vars: shape(g.variables, 0) }));
      else if (j) rec.body = shape(j, 0);
      sv.calls.push(rec);
      return rec;
    };
    const f = window.fetch;
    window.fetch = function (input, init) {
      const req = typeof input === 'object' && input !== null && 'url' in input ? input : null;
      const rec = note('fetch', (init && init.method) || (req && req.method) || 'GET', req ? req.url : input, init && init.body);
      const p = f.apply(this, arguments);
      p.then((r) => {
        rec.status = r.status;
        if ((r.headers.get('content-type') || '').includes('json')) return r.clone().json().then((d) => { rec.res = shape(d, 0); });
      }).catch(() => {});
      return p;
    };
    const open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (m, u) { this.__svReq = [m, u]; return open.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function (b) {
      const q = this.__svReq;
      if (q) {
        const rec = note('xhr', q[0], q[1], b);
        this.addEventListener('load', () => {
          rec.status = this.status;
          try { const d = this.responseType === 'json' ? this.response : parse(this.responseText); if (d) rec.res = shape(d, 0); } catch (e) {}
        });
      }
      return send.apply(this, arguments);
    };
    const ws = WebSocket.prototype.send;
    WebSocket.prototype.send = function (d) { note('ws', 'send', this.url, d); return ws.apply(this, arguments); };
    sv.hooked = true;
    return 'hooked';
  }

  // Requests the page made before hook() was installed: paths only, from the browser's own timing log.
  const loaded = () => Array.from(new Set(performance.getEntriesByType('resource')
    .filter((e) => e.initiatorType === 'fetch' || e.initiatorType === 'xmlhttprequest').map((e) => safeUrl(e.name))));

  // Shipped code: list the script files, load one (index or URL) into sv.bundle, then search it in the page.
  const files = () => Array.from(document.scripts).filter((s) => s.src);
  const scripts = () => files().map((s, i) => i + ' ' + safeUrl(s.src));
  const load = (i) => rawFetch(typeof i === 'number' ? files()[i].src : i).then((r) => r.text()).then((t) => { sv.bundle += '\n' + t; return sv.bundle.length; });
  function grep(tag, re, around) {
    const g = new RegExp(re.source, re.flags.replace('g', '') + 'g'), a = around || 0, seen = new Set();
    let more = false;
    for (let m; (m = g.exec(sv.bundle)); ) {
      if (seen.size >= 500) { more = true; break; }
      seen.add(sv.bundle.slice(Math.max(0, m.index - a), m.index + m[0].length + a).replace(/\s+/g, ' '));
      if (m[0] === '') g.lastIndex++;
    }
    // The scripting tool refuses output that looks like URL or query-string data. Two things are rewritten and
    // nothing else: a quoted URL with a query goes through safeUrl, and the browser's URL object prints as LOC.
    const word = new RegExp('\\bloca' + 'tion\\b', 'g');
    const text = Array.from(seen).join('\n')
      .replace(/(["'`])((?:https?:\/\/|\.{0,2}\/)[^"'`\s]*\?[^"'`\s]*)/g, (all, q, url) => q + safeUrl(url))
      .replace(word, 'LOC');
    return out(tag, (text || '(no match)') + (more ? '\n… stopped at 500 matches; narrow the pattern' : ''));
  }

  Object.assign(sv, { dump, out, shape, hook, loaded, scripts, load, grep });
  return 'helpers ready';
})()
```
