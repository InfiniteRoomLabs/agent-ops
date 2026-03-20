# Daily Secrets Rotation Check

Add this to the homelab server crontab:

```bash
# Check secret rotation compliance daily at 6am
0 6 * * * /usr/local/bin/bw-sync.sh --check-rotation >> /var/log/irl/secrets-rotation.log 2>&1
```

Or add to the Ansible cron playbook for automated deployment.
