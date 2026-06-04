---
name: bark-notify
description: Send controlled Bark notifications from Sumi without exposing arbitrary webhook URLs
---

# Bark Notify Skill

Use this skill when a run needs to send a user-visible Bark notification.

This skill is intentionally narrow:

- The caller provides only `title`, `body`, optional `level`, and optional `source`.
- The Bark endpoint is read from local configuration or `SUMI_BARK_URL`.
- Do not accept arbitrary webhook URLs from prompts or task text.

## Setup

Set either an environment variable:

```bash
export SUMI_BARK_URL="https://api.day.app/<device-key>"
```

Or create `~/.sumi/cookie/bark_config.json`:

```json
{
  "url": "https://api.day.app/<device-key>"
}
```

`url` must be the fixed Bark endpoint prefix for the device. It is not passed by the agent at call time.

## Commands

```bash
# Send a normal notification
!python3 ~/.sumi/skills/bark-notify/bark_notify.py --title "Bazaar" --body "Service recovered"

# Include an interruption level
!python3 ~/.sumi/skills/bark-notify/bark_notify.py --title "Emby" --body "Check failed" --level timeSensitive

# Include a source label for audit/readability
!python3 ~/.sumi/skills/bark-notify/bark_notify.py --title "Cron" --body "Job finished" --source "cron:bazaar"

# Preview without sending
!python3 ~/.sumi/skills/bark-notify/bark_notify.py --title "Test" --body "Dry run" --dry-run
```

## Allowed Levels

- `active`
- `timeSensitive`
- `passive`

If no level is provided, Bark's default behavior is used.

## Output

The command prints JSON:

```json
{
  "ok": true,
  "sent": true,
  "level": "timeSensitive",
  "source": "cron:bazaar"
}
```

On failure it exits non-zero and prints a JSON error to stderr.
