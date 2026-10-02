---
name: web-ui-automation-components
description: "Use when asked to turn a web UI automation survey report into Puppeteer code: builds strictly typed, drop-in TypeScript models, components and page objects from the report, as source files only, with no project or framework around them."
tags:
  function: [engineering]
  scenario: [ui-automation, test-automation]
  custom: [puppeteer, typescript, page-objects, selectors]
---

# Web UI automation components

Turn a survey report (the kind the `web-ui-automation-survey` skill writes) into TypeScript the person can drop into a Puppeteer project they already have: typed models, one class per component, one class per page. The deliverable is a folder of source files, zipped. It is deliberately not a project and not a framework: no `package.json`, no `tsconfig.json`, no session or facade object, no examples, no test suite, no config. If something beyond components looks worth having (an API client, a reader for the app's client state), say so in the wrap-up and leave it unbuilt.

"Ready to use" means: the folder compiles as it is under strict settings in an ESM or CommonJS project, `new Sidebar(page)` works on a Puppeteer `Page`, every selector traces back to the report, and anything the report only inferred says so in the code.

The shape follows the report's own idea: **Page → (is comprised of) → Components → (are comprised of) → other Components + Elements**. A page is simply the top-level component of its route.

## 1. Read the report

The report is the spec. Build from it, not from memory of the survey.

- §1 (platform facts) decides how components wait and select. §2 gives the shell and the shared primitives. §3 gives each page's tree, properties, routines and readiness signal. §4 says which routines are writes. §7 and §8 say what is Inferred.
- Build everything the report covers unless the person names pages or components.
- Where the report lacks something a component needs (a selector, a readiness signal, where a dropdown's options render), do not invent it. If the app is open in the browser, look it up read-only and tell the person what to correct in the report; otherwise build what is supported and list the gap in the README.
- If the person hands you something other than such a report, say what is missing for components and work from what is there, marking the rest Inferred.

## 2. Layout

```
{app}-components/
├── README.md
├── index.ts          barrel
├── core/             component.ts  errors.ts  wait.ts     (the only shared code)
├── models/           plain data types, one file per domain
├── components/       one class per UI component: shell/ (navigation, header), shared controls, feedback, features
└── pages/            one class per page or tab
```

Copy the three core files from the end of this skill as they are, and add to the base class only what two or more components need.

## 3. Rules

1. **One class per report component.** `static ROOT` (where it normally lives), `static SEL` (element selectors relative to the root, `as const`), the public constructor `(ctx, ref)` every component shares, and methods that return models. Compose with `child()` and `children()`.
2. **A page is a component.** Its root is the element that proves the page rendered. It adds a static `path(...)` for the caller's `page.goto`, `waitForReady()` using the signal the report names, getters for its components, and one method per page routine with the routine id in its JSDoc so code and report can be matched by search.
3. **Models are plain readonly data.** Brand ids that must not be mixed (`type InvoiceId = number & { readonly __brand: 'InvoiceId' }`). Model the state the app renders: `hasNotification` and `notificationCount` belong on a menu item only where items carry badges.
4. **Selectors come from the report.** Use its stable hooks and plain CSS, attribute selectors for ids containing dots, and a scope wherever the report warns of duplicates. Text matching happens in code.
5. **Inferred stays visible.** An inferred selector carries an `Inferred` comment, and its method throws a typed error when the control is missing instead of falling back to a guess.
6. **Roots are resolved on every call and clicks are centred first**, which the base class does. Frameworks re-render and detach nodes, and fixed headers and action bars swallow clicks.
7. **A browser callback is a single arrow with its logic inline.** Inside `evaluate` / `$eval`, a nested `function` or an arrow assigned to a `const` fails at run time with `__name is not defined` when the project runs through `tsx` (or any esbuild setup with `keepNames`), which wraps named functions in a helper the page does not have. Anonymous arrows passed as arguments are fine.
8. **Wait on the report's signals** with `poll`. A fixed delay is acceptable only for a debounce or settle time the report records.
9. **Writes are off until the caller turns them on.** Every action that changes anything on the server starts with `this.assertWritesAllowed(action)`, which throws `SideEffectBlockedError` unless the caller has set `sideEffects.allowWrites = true`. Mark it `WRITE` in the JSDoc, and `no confirmation` where the report says the control acts immediately. The report's §4 decides what is a write; navigation, opening menus and typing into a search box are not. The code will be pointed at a real account, so a mistaken call has to throw rather than act.
10. **Nothing from the surveyed account is baked in.** Host, tenant and record ids are parameters. If the report documents a login form and the person wants it as a component, credentials are arguments the caller supplies. README snippets use made-up values.
11. **Strict typing that travels.** The files must pass `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noUnusedLocals`, `noUnusedParameters`, `noImplicitReturns`, `noFallthroughCasesInSwitch`, `noPropertyAccessFromIndexSignature`, `useUnknownInCatchVariables`, `isolatedModules` and `verbatimModuleSyntax`, with no `any`, no `@ts-ignore` and no non-null `!`. Use `import type` for types, end relative imports in `.js` (that form compiles under both NodeNext and Bundler resolution, in ESM and CommonJS projects), and import Puppeteer only in `core/component.ts`.
12. **Keep it lean.** No abstraction that only one component uses, and no wrapper around something Puppeteer already does well.

## 4. Check it before delivering

The checks run in a scratch harness that is not delivered: a `package.json` with `"type": "module"`, a `tsconfig.json` with the flags above, and `typescript`, `tsx`, `puppeteer` and `@types/node` installed. If a Chromium is already installed, set `PUPPETEER_SKIP_DOWNLOAD=1` for the install and pass its path as `executablePath`; in a container launch with `--no-sandbox`.

1. **Type-check twice**: `tsc --noEmit` with `moduleResolution` Bundler, then again with `--module NodeNext --moduleResolution NodeNext`. Both clean.
2. **Selector syntax**: run the **Selector check** at the end of this skill. It collects every `ROOT` and `SEL` string from the barrel and tries each in a blank page, which catches invalid CSS before the person does.
3. **Behaviour**: build a throwaway `fixture.html` from the report's trees: the shell, one instance of each shared control, and the main component of each page, with invented data and a few lines of script for what components wait on (a dropdown opening, a dialog, a toast). Keep it small: it exists to run the code once, not to mirror the app. Reproduce fixed headers and bottom bars, since they decide whether clicks land. Run each read method once, each write with the switch off (it must reject), and the main writes with it on. A failure here is usually a real selector bug, typically a `ROOT` that also matches a neighbouring panel or table; fix it in the code and tell the person the report needs the same correction.
4. **Live selector counts, when the app is already open in the browser**: on each page, count the matches of every `ROOT` and `SEL` with `querySelectorAll` and compare with the report (one root, N rows). This is read-only and the best evidence short of running Puppeteer against the account. The survey's rules apply: look, don't act, and never sign in for the person. If the browser is not connected, skip this and say so.
5. **Trace and scrub**: every selector in the code appears in the report or carries an `Inferred` comment; every write routine calls the guard first and no read does; no real identifier from the surveyed account (host specific to their tenant, tenant key, ids, names) appears anywhere in the folder.

## 5. Deliver

Write a short `README.md`: which report the kit was built from, how to drop the folder in and construct a component (a few lines of code with made-up values), the writes switch, a table of report section → class → file, and the list of what is Inferred and should be confirmed on a first live run. Zip the folder and send it, or write it into the project folder if the person has pointed you at one.

Close with a few sentences: how many models, components and pages were built, what is Inferred, which checks ran (and whether the live count check did), and that the scratch fixture and smoke test can be included if wanted. No step-by-step recap.

## Core files

`core/errors.ts`

```ts
export type KitErrorCode = 'ELEMENT_NOT_FOUND' | 'TIMEOUT' | 'SIDE_EFFECT_BLOCKED' | 'UNEXPECTED_STATE';

/** Every error carries a `code`, so callers branch on that instead of matching message text. */
export class KitError extends Error {
  readonly code: KitErrorCode;

  constructor(code: KitErrorCode, message: string) {
    super(message);
    this.name = new.target.name;
    this.code = code;
  }
}

export class ElementNotFoundError extends KitError {
  constructor(selectorPath: string) {
    super('ELEMENT_NOT_FOUND', `Element not found: ${selectorPath}`);
  }
}

export class WaitTimeoutError extends KitError {
  constructor(what: string, timeoutMs: number) {
    super('TIMEOUT', `Timed out after ${timeoutMs} ms waiting for ${what}`);
  }
}

export class SideEffectBlockedError extends KitError {
  constructor(action: string) {
    super('SIDE_EFFECT_BLOCKED', `Refusing "${action}": writes are off. Set sideEffects.allowWrites = true to enable them.`);
  }
}

export class UnexpectedStateError extends KitError {
  constructor(message: string) {
    super('UNEXPECTED_STATE', message);
  }
}
```

`core/wait.ts`

```ts
import { WaitTimeoutError } from './errors.js';

export interface WaitOptions {
  readonly timeoutMs?: number;
  readonly intervalMs?: number;
}

/**
 * Poll `probe` until it returns something other than null, undefined or false.
 * An error thrown while the page re-renders counts as "not yet"; the last one is reported on timeout.
 */
export async function poll<T>(what: string, probe: () => Promise<T | null | undefined | false>, options?: WaitOptions): Promise<T> {
  const timeoutMs = options?.timeoutMs ?? 15_000;
  const deadline = Date.now() + timeoutMs;
  let last: unknown = null;
  for (;;) {
    try {
      const value = await probe();
      if (value !== null && value !== undefined && value !== false) return value;
    } catch (error: unknown) {
      last = error;
    }
    if (Date.now() >= deadline) {
      throw new WaitTimeoutError(last instanceof Error ? `${what} (last error: ${last.message})` : what, timeoutMs);
    }
    await new Promise((resolve) => setTimeout(resolve, options?.intervalMs ?? 150));
  }
}
```

`core/component.ts`

```ts
import type { ElementHandle, Frame, Page } from 'puppeteer';
import { ElementNotFoundError, SideEffectBlockedError } from './errors.js';
import { poll, type WaitOptions } from './wait.js';

// The only file that imports Puppeteer: a project on puppeteer-core changes the import above and nothing else.
export type { ElementHandle, Frame, Page };

/** Components change nothing in the account until the caller turns this on. */
export const sideEffects = { allowWrites: false };

export type Context = Page | Frame; // Frame, so components also work inside an iframe
export type RootRef =
  | { readonly kind: 'selector'; readonly selector: string; readonly parent: Component | null }
  | { readonly kind: 'handle'; readonly handle: ElementHandle<Element>; readonly description: string };
export type ComponentCtor<T extends Component> = new (ctx: Context, ref: RootRef) => T;

/** Root a component at a selector, optionally inside a parent component. */
export function at(selector: string, parent: Component | null = null): RootRef {
  return { kind: 'selector', selector, parent };
}

export abstract class Component {
  readonly ctx: Context;
  protected readonly ref: RootRef;

  protected constructor(ctx: Context, ref: RootRef) {
    this.ctx = ctx;
    this.ref = ref;
  }

  /** Selector path for error messages, e.g. `nav >> li[2]`. */
  describe(): string {
    if (this.ref.kind === 'handle') return this.ref.description;
    return this.ref.parent === null ? this.ref.selector : `${this.ref.parent.describe()} >> ${this.ref.selector}`;
  }

  /** Resolved on every call: the framework re-renders and detaches nodes, so a stored handle goes stale. */
  async rootOrNull(): Promise<ElementHandle<Element> | null> {
    if (this.ref.kind === 'handle') return this.ref.handle;
    if (this.ref.parent === null) return this.ctx.$(this.ref.selector);
    const scope = await this.ref.parent.rootOrNull();
    return scope === null ? null : scope.$(this.ref.selector);
  }

  async root(): Promise<ElementHandle<Element>> {
    const handle = await this.rootOrNull();
    if (handle === null) throw new ElementNotFoundError(this.describe());
    return handle;
  }

  async isPresent(): Promise<boolean> {
    return (await this.rootOrNull()) !== null;
  }

  async waitFor(options?: WaitOptions): Promise<ElementHandle<Element>> {
    return poll(`${this.describe()} to appear`, () => this.rootOrNull(), options);
  }

  /** First match inside the root (`null` selector means the root itself), or null. */
  protected async $(selector: string | null): Promise<ElementHandle<Element> | null> {
    const scope = await this.rootOrNull();
    return scope === null || selector === null ? scope : scope.$(selector);
  }

  protected async $$(selector: string): Promise<ElementHandle<Element>[]> {
    const scope = await this.rootOrNull();
    return scope === null ? [] : scope.$$(selector);
  }

  protected async required(selector: string | null): Promise<ElementHandle<Element>> {
    const handle = await this.$(selector);
    if (handle === null) throw new ElementNotFoundError(selector === null ? this.describe() : `${this.describe()} >> ${selector}`);
    return handle;
  }

  /** Whitespace-normalised text, or null when the element is absent. */
  protected async textOf(selector: string | null): Promise<string | null> {
    const handle = await this.$(selector);
    return handle === null ? null : handle.evaluate((el) => (el.textContent ?? '').replace(/\s+/g, ' ').trim());
  }

  protected async attrOf(selector: string | null, name: string): Promise<string | null> {
    const handle = await this.$(selector);
    return handle === null ? null : handle.evaluate((el, attr) => el.getAttribute(attr), name);
  }

  /** Centre first, so a fixed header or action bar cannot swallow the click. */
  protected async clickOn(selector: string | null): Promise<void> {
    const handle = await this.required(selector);
    await handle.evaluate((el) => el.scrollIntoView({ block: 'center', inline: 'nearest' }));
    await handle.click();
  }

  /** Replace the content of a text field. */
  protected async typeInto(selector: string, text: string): Promise<void> {
    const handle = await this.required(selector);
    await handle.evaluate((el) => el.scrollIntoView({ block: 'center', inline: 'nearest' }));
    await handle.click();
    await handle.evaluate((el) => (el as HTMLInputElement).select());
    await handle.press('Backspace');
    await handle.type(text);
  }

  /** First statement of every action that changes anything on the server. */
  protected assertWritesAllowed(action: string): void {
    if (!sideEffects.allowWrites) throw new SideEffectBlockedError(action);
  }

  protected child<T extends Component>(ctor: ComponentCtor<T>, selector: string): T {
    return new ctor(this.ctx, at(selector, this));
  }

  /** One component per match, bound to its element: use them straight away, do not keep them. */
  protected async children<T extends Component>(ctor: ComponentCtor<T>, selector: string): Promise<T[]> {
    const handles = await this.$$(selector);
    return handles.map((handle, i) => new ctor(this.ctx, { kind: 'handle', handle, description: `${this.describe()} >> ${selector}[${i}]` }));
  }
}
```

## Example

A model (`models/navigation.ts`):

```ts
export interface SidebarMenuItemInfo {
  readonly key: string;
  readonly label: string;
  readonly href: string | null;
  readonly isActive: boolean;
  readonly hasNotification: boolean;
  readonly notificationCount: number | null;
}
```

A component with a child component, showing the constructor shape, `ROOT` / `SEL`, composition and an inline browser callback (`components/sidebar.ts`):

```ts
import { at, Component, type Context, type RootRef } from '../core/component.js';
import type { SidebarMenuItemInfo } from '../models/navigation.js';

export class SidebarMenuItem extends Component {
  static readonly SEL = { link: 'a', badge: '.badge' } as const;
  constructor(ctx: Context, ref: RootRef) { super(ctx, ref); } // the same public shape on every component

  async info(): Promise<SidebarMenuItemInfo> {
    const root = await this.root();
    return root.evaluate((el, sel) => { // one arrow with the logic inline
      const link = el.querySelector(sel.link);
      const badge = el.querySelector(sel.badge);
      return {
        key: link?.getAttribute('data-testid') ?? '',
        label: Array.from(link?.childNodes ?? []).filter((n) => n.nodeType === 3).map((n) => n.textContent ?? '').join(' ').replace(/\s+/g, ' ').trim(),
        href: link?.getAttribute('href') ?? null,
        isActive: el.classList.contains('active'),
        hasNotification: badge !== null,
        notificationCount: badge === null ? null : Number.parseInt(badge.textContent ?? '', 10),
      };
    }, SidebarMenuItem.SEL);
  }

  /** Navigation, not a write: no guard. */
  async open(): Promise<void> {
    await this.clickOn(SidebarMenuItem.SEL.link);
  }
}

export class Sidebar extends Component {
  static readonly ROOT = 'nav[aria-label="Primary"]';
  static readonly SEL = { item: 'li' } as const;
  constructor(ctx: Context, ref: RootRef = at(Sidebar.ROOT)) { super(ctx, ref); }

  items(): Promise<SidebarMenuItem[]> {
    return this.children(SidebarMenuItem, Sidebar.SEL.item);
  }
}
```

A page with one child component, showing `path`, the readiness wait, a read routine and a guarded write (`pages/invoices.page.ts`):

```ts
import { at, Component, type Context, type RootRef } from '../core/component.js';
import { poll, type WaitOptions } from '../core/wait.js';

export class InvoicesTable extends Component {
  static readonly SEL = { row: 'tbody tr[data-invoice-id]' } as const;
  constructor(ctx: Context, ref: RootRef) { super(ctx, ref); }

  async rowCount(): Promise<number> {
    return (await this.$$(InvoicesTable.SEL.row)).length;
  }
}

/** Report §3.4 — a page is the top-level component of its route. */
export class InvoicesPage extends Component {
  static readonly ROOT = 'main[data-testid="invoices-page"]';
  static readonly SEL = { table: 'table[aria-label="Invoices"]', search: 'input[name="q"]', payButton: 'button[data-action="pay"]' } as const;
  constructor(ctx: Context, ref: RootRef = at(InvoicesPage.ROOT)) { super(ctx, ref); }

  /** For `page.goto(baseUrl + InvoicesPage.path(tenant))`: host and tenant always come from the caller. */
  static path(tenant: string): string {
    return `/${encodeURIComponent(tenant)}/billing/invoices`;
  }

  get table(): InvoicesTable {
    return this.child(InvoicesTable, InvoicesPage.SEL.table);
  }

  /** The readiness signal the report gives for this page. */
  async waitForReady(options?: WaitOptions): Promise<void> {
    await poll('the invoices table to finish loading', async () => (await this.attrOf(InvoicesPage.SEL.table, 'aria-busy')) === 'false', options);
  }

  /** R-INVOICES-SEARCH: filters in place, changes nothing on the server. */
  async search(text: string): Promise<void> {
    await this.typeInto(InvoicesPage.SEL.search, text);
  }

  /** R-INVOICE-PAY (WRITE): Pay → confirm the dialog → expect the toast. Inferred: not exercised during the survey. */
  async pay(invoiceNumber: string): Promise<void> {
    this.assertWritesAllowed(`pay invoice ${invoiceNumber}`);
    await this.clickOn(InvoicesPage.SEL.payButton);
  }
}
```

## Selector check

Inside the scratch smoke test, after `const page = await browser.newPage()`:

```ts
// at the top of the file
import assert from 'node:assert/strict';
import * as kit from '../{app}-components/index.js';

// every ROOT and SEL string in the kit, tried in a blank page: invalid CSS throws
const selectors = Object.values(kit).flatMap((value) => {
  if (typeof value !== 'function') return [];
  const cls = value as { ROOT?: unknown; SEL?: unknown };
  const sel = typeof cls.SEL === 'object' && cls.SEL !== null ? Object.values(cls.SEL) : [];
  return [cls.ROOT, ...sel].filter((s): s is string => typeof s === 'string');
});
const invalid = await page.evaluate((list) => list.filter((s) => { try { document.querySelector(s); return false; } catch { return true; } }), selectors);
assert.deepEqual(invalid, [], 'invalid CSS selectors');
```
