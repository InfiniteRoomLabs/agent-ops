---
name: tmux-session-capture
description: "Ingest the user's pre-agent terminal context by capturing tmux pane scrollback with tdump. Use when the user says 'catch up on what I was doing', 'look at my terminal', 'see my shell history', references commands or output from before the agent session started, or hands you a scrollback dump file."
tags:
  function: [engineering]
  scenario: [session-bootstrap, context-ingestion]
  custom: [tmux, tdump, shell-context]
---

# tmux Session Capture

Capture the user's tmux scrollback so the agent can read their pre-session shell work instead of asking them to copy-paste it.

## The mechanism

`tdump` is a fish function (`~/.config/fish/functions/tdump.fish`):

```fish
tmux capture-pane -p -S - -J > $out   # full scrollback, wrapped lines joined
echo $out                              # echoes path, so (tdump) composes inline
```

- Default output: `/tmp/tmux-session.txt`; optional arg overrides the path.
- From bash (agent Bash tool): `fish -c tdump`, then Read the printed path.
- User-side idiom: `claude "read (tdump) and catch up on what I was doing"`.
- If tdump is missing on the machine, fall back to the raw command: `tmux capture-pane -p -S - -J > /tmp/tmux-session.txt`.

## When to use

- The user references shell work you didn't witness: "as you can see", "that error above", "what I was just doing".
- Bootstrapping an agent session on top of an active terminal workflow.
- Debugging something the user ran interactively before invoking the agent.

## Critical limitation -- the TUI repaint trap

Claude Code (and most TUI agents) repaint the screen in place. **Agent conversation history never lands in tmux scrollback.** A capture taken mid-session yields only:

1. Scrollback from *before* the agent session started, and
2. A snapshot of the *current viewport* (which will include the live spinner and statusline, mid-render).

Consequences:

- Capture is most valuable **before** entering the agent session -- that is the intended workflow.
- Never treat a mid-session capture as a session transcript. The real record is the transcript JSONL under `~/.claude/projects/<project-dir>/`, searchable via `aichat "query"`.
- `capture-pane` grabs the **current pane only**. Multi-pane workflows need one capture per pane (`tmux capture-pane -p -S - -J -t <pane-id>`).

## Recipe

1. Run `fish -c tdump` (or the raw tmux command).
2. Read the output file. It may be large; prefer tail-first if you only need recent context.
3. Mine it for: commands run, errors hit, files touched, versions printed.
4. Do not echo the whole dump back at the user -- summarize what you learned.
