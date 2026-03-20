#!/bin/bash
# Hook: post-deploy secrets verification
# Trigger: PostToolUse on Bash (reads hook payload to match kubectl/helm commands)
# Checks K8s secrets match Bitwarden after deployment

# Read hook payload from stdin -- only act on deploy commands
PAYLOAD=$(cat)
COMMAND=$(echo "$PAYLOAD" | jq -r '.tool_input.command // empty' 2>/dev/null)

if [[ -z "$COMMAND" ]] || ! echo "$COMMAND" | grep -qE "kubectl apply|helm upgrade|helm install"; then
  exit 0  # Not a deploy command, skip silently
fi

BW_SYNC_SCRIPT="$HOME/projects/infinite-room-labs/<your-infra-repo>/scripts/bw-sync.sh"

if [[ ! -x "$BW_SYNC_SCRIPT" ]]; then
  echo "WARNING: bw-sync.sh not found, skipping verification"
  exit 0
fi

"$BW_SYNC_SCRIPT" --verify-k8s --quiet
EXIT=$?
if [[ $EXIT -ne 0 ]]; then
  echo "SECRET MISMATCH: K8s secrets don't match Bitwarden. Run: bw-sync.sh --target k8s"
fi
exit $EXIT
