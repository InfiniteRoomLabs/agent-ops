---
name: render-mermaid
description: >
  Use ONLY when the user explicitly asks to visualize, render, view, open,
  preview, see, or display a mermaid diagram (a `.mmd` file or a fenced
  ```mermaid block) as an image or PDF. Trigger phrases include "show me
  this as a diagram", "render the mermaid", "open the diagram", "can I
  see that visually", "graph it", "visualize this". Do NOT trigger when
  the user is merely writing, editing, pasting, or reviewing mermaid
  syntax in source files -- that work does not need rendering and the
  skill would burn tokens and time for no reason.
allowed-tools: Bash, Write, Read
tags:
  function: [engineering, creative, operations]
  scenario: [diagram-rendering, visualization, dev-experience]
  custom: [mermaid, mmdc, pdf, svg, render]
---

# Render Mermaid

Render a mermaid diagram and open it in the user's default viewer. Defaults to PDF (vector, baked fonts, dark-mode-proof, snap/flatpak-safe).

## When to fire

Trigger ONLY if the user clearly asks to **see** the diagram. "Write a mermaid diagram of X" alone is NOT a render request. "Write it AND show me" IS.

## Quick reference

| Source                                  | Command |
|-----------------------------------------|---------|
| Existing `.mmd` file                    | `uv run ${CLAUDE_PLUGIN_ROOT}/skills/render-mermaid/render_mermaid.py from-file <path>` |
| Fenced ```mermaid block in conversation | Pipe via heredoc to `from-stdin --name <stem>` |
| Want SVG/PNG instead of PDF             | Add `--format svg` or `--format png` |
| Don't auto-open                         | Add `--no-open` |

The renderer writes to `~/Downloads/<stem>.<ext>` (snap-Firefox-readable) and runs `xdg-open` detached so the tool call returns immediately.

## Workflow

1. Locate the mermaid source: a file path the user named, OR the most recent fenced ```mermaid block in the conversation.
2. If the source is a fenced block, write it to a temp `.mmd` (or pipe to `from-stdin --name <stem>`). Choose `<stem>` from context (e.g. the topic of the diagram).
3. Run the script. Default format is PDF. Switch to SVG only if the user explicitly asked for SVG; switch to PNG only for embedding/sharing.
4. The script prints the output path on stdout and detaches the viewer. Tell the user where it landed and what format.

## Format choice

- **PDF (default)** -- viewer-portable, vector, baked fonts. Survives system dark-mode and Linux image viewers that don't parse mermaid's embedded `<style>` block.
- **SVG** -- only when the user wants to drop it in a web page or edit in Inkscape. On Linux, snap Firefox cannot read `/tmp`; the script writes to `~/Downloads/` to avoid that pitfall.
- **PNG** -- only for chat embeds or social posts. Renders at default DPI -- bump width on the CLI if the user wants it big.

## Common mistakes

- **Triggering on plain mermaid authoring.** If the user just pasted a mermaid block to discuss its content, do not render. Wait for an explicit ask.
- **Choosing SVG by default.** SVG looks broken in eog/Loupe because mermaid relies on CSS variables that those viewers do not resolve. Use PDF unless the user names SVG.
- **Putting output in /tmp.** Snap/flatpak browsers cannot read `/tmp`. The script already handles this; don't override `-o`.
- **Forgetting `--no-sandbox`.** On Ubuntu 23.10+ Puppeteer fails with `FATAL: No usable sandbox`. The script already supplies a Puppeteer config; don't bypass it.

## Dependencies

`npx` (Node/npm). The script invokes `npx -y -p @mermaid-js/mermaid-cli mmdc`, which fetches `mmdc` on first run and caches it.
