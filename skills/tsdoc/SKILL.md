---
name: tsdoc
description: "Write or fix doc comments in TypeScript using TSDoc conventions. Use when adding JSDoc/docblocks to .ts files, cleaning up AI-generated or wordy comments, documenting interfaces/types/functions, or when a comment uses @property or {Type} annotations that should be TSDoc instead."
argument-hint: "<file or symbol to document>"
tags:
  function: [engineering]
  scenario: [documentation]
  custom: [tsdoc, typescript, jsdoc, doc-comments]
---

# /tsdoc

Write TypeScript doc comments the way the TS toolchain actually reads them.

## Why TSDoc, not classic JSDoc

In a `.ts` codebase the things that consume doc comments are:

- **The IDE** (VS Code, IntelliJ) via the TypeScript language server. It shows
  the doc comment **attached to each declaration** on hover.
- **TypeDoc**, the standard TS doc-site generator. Same model -- per-declaration
  TSDoc comments.

Neither reads `@property` tags in an interface header, and both **ignore the
`{Type}` in `@param {Type} name`** -- TypeScript already has the type. The only
tool that reads `@property`/`{Type}` is the legacy `jsdoc` CLI, which TS projects
don't use. So a tidy consolidated `@property` header documents nothing the IDE
will ever show on the member you hover.

## Rules

1. **One doc comment per declaration.** Put a `/** ... */` on the interface/type/
   function/class **and** on every member -- not a single `@property` block in the
   header. Member hover only shows the comment on that member.
2. **No `@property` tags.** Replace them with a `/** */` above each field.
3. **No `{Type}` annotations** anywhere (`@param`, `@returns`, members). TS supplies
   the type; the brace form is redundant and ignored.
4. **Methods/functions:** `@param name - description` and `@returns description`.
   Hyphen after the param name, no brace types.
5. **Cross-reference with `{@link Symbol}`** or `{@link Symbol.member}` -- TSDoc-native,
   clickable in-IDE and in TypeDoc.
6. **Lead with substance.** First sentence says what it *is* and any non-obvious
   invariant (e.g. "exactly one of `a`/`b` is set"). Cut generic filler like
   "Represents a structure that encapsulates...".
7. **ASCII only** (repo convention): `--` not em dash, `->` not arrow, straight quotes.
8. Optional tags when they earn their place: `@see`, `@example`, `@defaultValue`,
   `@deprecated`. Skip `@interface`/`@typedef` -- TS infers the kind.

## Convert: before -> after

Wordy / classic-JSDoc header (does **not** surface on member hover):

```ts
/**
 * Represents the capabilities of a surface, indicating the operations
 * that are permitted for the surface.
 * @interface
 * @property {boolean} read - Indicates if reading is allowed.
 * @property {boolean} write - Indicates if writing is allowed.
 */
export interface SurfaceCaps {
  read: boolean;
  write: boolean;
}
```

Proper TSDoc (each member documents itself):

```ts
/** Capability flags advertising which operations a surface permits. */
export interface SurfaceCaps {
  /** The surface can read/fetch items. */
  read: boolean;
  /** The surface can persist items. */
  write: boolean;
}
```

Method, TSDoc form:

```ts
/**
 * Fetch and build the canonical item for `ref`.
 *
 * @param ref - Reference (typically from {@link SourceSurface.list}) to read.
 * @returns The neutral-interchange payload for the item.
 */
read(ref: ItemRef): Promise<CanonicalItem>;
```

## Workflow

1. **Diff first** if the file was already touched (`git diff -- <file>`). AI tools
   and the JetBrains "Write Documentation" intention often overwrite good comments
   with generic prose -- recover the substance from the `-` lines before rewriting.
2. Apply the rules above, member by member.
3. **Verify clean**: get IDE diagnostics for the file (no broken `{@link}` targets,
   no syntax errors). Build (`tsc`) stays green -- comments don't change types.
4. Don't touch types or logic. Docs only.

## Enforcing it (optional)

To catch malformed TSDoc on lint, add `eslint-plugin-tsdoc` and enable
`tsdoc/syntax`. Only suggest this if the user wants the convention enforced
repo-wide -- it flags syntax, not coverage.
