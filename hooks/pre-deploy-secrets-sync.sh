#!/bin/bash
# Hook: pre-deploy secrets sync
# Trigger: PreToolUse on Bash (reads hook payload from stdin to match ansible-playbook)
# Requires: BW_SESSION or ~/.secrets/bw-session

# Read hook payload from stdin -- only act on ansible-playbook commands
PAYLOAD=$(cat)
COMMAND=$(echo "$PAYLOAD" | jq -r '.tool_input.command // empty' 2>/dev/null)

if [[ -z "$COMMAND" ]] || ! echo "$COMMAND" | grep -q "ansible-playbook"; then
  exit 0  # Not an ansible-playbook command, skip silently
fi

BW_SYNC_SCRIPT="$HOME/projects/infinite-room-labs/<your-infra-repo>/scripts/bw-sync.sh"

if [[ ! -x "$BW_SYNC_SCRIPT" ]]; then
  echo "WARNING: bw-sync.sh not found at $BW_SYNC_SCRIPT"
  exit 0  # Don't block -- warn only
fi

# Check if BW is available
if [[ -z "${BW_SESSION:-}" ]] && [[ ! -f "$HOME/.secrets/bw-session" ]]; then
  echo "WARNING: Bitwarden not unlocked. Secrets may be stale."
  echo "Run: bw unlock --raw > ~/.secrets/bw-session"
  exit 0  # Don't block -- warn only
fi

"$BW_SYNC_SCRIPT" --target ansible --quiet
