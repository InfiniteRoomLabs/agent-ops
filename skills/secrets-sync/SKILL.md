---
name: secrets-sync
description: "Sync secrets from Bitwarden to Ansible Vault and Kubernetes"
tags:
  function: [engineering, operations]
  scenario: [secrets-management, infrastructure-automation, security-compliance]
  custom: [bitwarden, rotation-policy, ansible-vault, kubernetes-secrets]
---

# Secrets Sync

Load the Entropy agent and execute a secrets lifecycle operation: sync, rotation check, health report, or service provisioning.

## Triggers

Invoke this skill when the user says any of:
- "sync secrets"
- "rotate secrets"
- "check secret health"
- "provision secrets for"
- "are my secrets up to date"
- "check rotation compliance"
- "verify k8s secrets"

## Agent

This skill delegates to the **Entropy** agent (`agents/engineering/entropy.md`). Load it at skill start.

## Usage

### /secrets-sync

Run a full health check and sync to all targets.

```
/secrets-sync
```

Entropy will:
1. Check BW_SESSION
2. Report current health score and rotation status
3. Run `bw-sync.sh --target both` (dry-run first, then apply on confirmation)
4. Update memory with new sync timestamp and result

### /secrets-sync check

Audit rotation compliance without syncing. No writes to any target.

```
/secrets-sync check
```

Entropy will:
1. Check BW_SESSION
2. Run `bw-sync.sh --check-rotation`
3. Report health score, overdue count, and approaching-window warnings
4. List any anomalies (orphans, unknown-age secrets, policy violations)

### /secrets-sync rotate <service>

Trigger a rotation check and re-sync for a specific service.

```
/secrets-sync rotate infra
/secrets-sync rotate app
```

Entropy will:
1. Look up all secrets tagged for the specified service in Bitwarden
2. Check each against its rotation policy
3. Report which secrets are overdue and by how many days
4. Re-sync the service's secrets to all targets after confirmation

### /secrets-sync provision <service>

Provision all required secrets for a service to all configured targets.

```
/secrets-sync provision scanbridge
/secrets-sync provision dark-matter
```

Entropy will:
1. Look up the service's expected secret manifest in Bitwarden
2. Run `bw-sync.sh --target both` scoped to the service
3. Verify the provisioned set matches the expected manifest
4. Report provisioned secrets by name (never by value) and confirm target state

## Output Expectations

Entropy's output is terse by design. Expect:
- A one-line status header (vault connection, health score)
- A numbered list of anomalies if any exist
- A confirmation line when a sync or provision completes cleanly

If health score drops below 90%, Entropy will prepend a warning before any other output.

## Iron Law

This skill never displays secret values. Names, targets, and timestamps only. If you need to view a secret value, use the Bitwarden CLI directly with appropriate session authentication.
