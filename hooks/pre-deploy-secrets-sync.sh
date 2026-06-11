#!/bin/bash
# Hook: pre-deploy secrets sync
# Trigger: PreToolUse on Bash (reads hook payload from stdin to match ansible-playbook)
# Requires: BW_SESSION, fnox (age-backed BW_SESSION), or the ~/.bw_session cache

# Read hook payload from stdin -- only act on ansible-playbook commands
PAYLOAD=$(cat)
COMMAND=$(echo "$PAYLOAD" | jq -r '.tool_input.command // empty' 2>/dev/null)

if [[ -z "$COMMAND" ]] || ! echo "$COMMAND" | grep -q "ansible-playbook"; then
  exit 0  # Not an ansible-playbook command, skip silently
fi

BW_SYNC_SCRIPT="$HOME/projects/infinite-room-labs/<your-infra-repo>/scripts/bw-sync.sh"
WITH_SECRETS="$HOME/projects/infinite-room-labs/<your-infra-repo>/scripts/with-secrets.sh"

if [[ ! -x "$BW_SYNC_SCRIPT" ]]; then
  echo "WARNING: bw-sync.sh not found at $BW_SYNC_SCRIPT"
  exit 0  # Don't block -- warn only
fi

# Resolve a Bitwarden session: env -> fnox (age) -> fish bw-unlock cache.
if [[ -z "${BW_SESSION:-}" ]] && command -v fnox >/dev/null 2>&1; then
  BW_SESSION="$(fnox get BW_SESSION 2>/dev/null || true)"
fi
if [[ -z "${BW_SESSION:-}" && -f "$HOME/.bw_session" ]]; then
  BW_SESSION="$(cat "$HOME/.bw_session")"
fi
if [[ -z "${BW_SESSION:-}" ]]; then
  echo "WARNING: Bitwarden not unlocked. Secrets may be stale."
  echo "Run: bw-unlock (fish), or seed fnox: fnox set BW_SESSION --provider age -g"
  exit 0  # Don't block -- warn only
fi
export BW_SESSION

# Prefer the fnox-exec wrapper so the sync sees all declared secrets.
if [[ -x "$WITH_SECRETS" ]]; then
  "$WITH_SECRETS" "$BW_SYNC_SCRIPT" --target ansible --quiet
else
  "$BW_SYNC_SCRIPT" --target ansible --quiet
fi
