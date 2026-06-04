---
name: emby
description: Search, browse, favorite, resume, and inspect media on an Emby server
---

# Emby Skill

Use `emby_client.py` to query and manage an Emby server from Sumi.

## Setup

Either configure scoped env in Sumi:

```toml
[emby]
server = "http://your-emby-server:8096"
username = "your-username"
password = "your-password"
```

Or create `~/.sumi/cookie/emby_config.json`:

```json
{
  "server": "http://your-emby-server:8096",
  "username": "your-username",
  "password": "your-password"
}
```

The access token is cached at `~/.sumi/cookie/emby_token.json` after the first successful login.

## Commands

```bash
# Check server connection
!python3 ~/.sumi/skills/emby/emby_client.py status

# Search media
!python3 ~/.sumi/skills/emby/emby_client.py search "attack on titan" --limit 20

# Search by item type
!python3 ~/.sumi/skills/emby/emby_client.py search "frozen" --type Movie --limit 10

# List libraries
!python3 ~/.sumi/skills/emby/emby_client.py libraries

# List library items
!python3 ~/.sumi/skills/emby/emby_client.py items <library_id> --limit 30

# Show item details
!python3 ~/.sumi/skills/emby/emby_client.py item <item_id>

# List seasons and episodes
!python3 ~/.sumi/skills/emby/emby_client.py seasons <series_id>
!python3 ~/.sumi/skills/emby/emby_client.py episodes <series_id> <season_id>

# Manage favorites
!python3 ~/.sumi/skills/emby/emby_client.py favorite <item_id>
!python3 ~/.sumi/skills/emby/emby_client.py unfavorite <item_id>
!python3 ~/.sumi/skills/emby/emby_client.py is_favorite <item_id>

# List favorite, resumable, watched, or recently added media
!python3 ~/.sumi/skills/emby/emby_client.py favorites --limit 20
!python3 ~/.sumi/skills/emby/emby_client.py resume --limit 20
!python3 ~/.sumi/skills/emby/emby_client.py history --limit 20
!python3 ~/.sumi/skills/emby/emby_client.py latest --limit 20

# Get poster URL
!python3 ~/.sumi/skills/emby/emby_client.py poster <item_id>
!python3 ~/.sumi/skills/emby/emby_client.py poster <item_id> --height 600
```

## Output

All commands print JSON. List commands return an `items` array, and paged commands also return `total`.

Common item fields:

- `id`: Emby item ID
- `name`: item name
- `type`: item type, such as `Movie`, `Series`, `Season`, or `Episode`
- `year`: production year
- `overview`: shortened overview
- `is_favorite`: favorite status
- `played`: watched status
- `playback_pct`: resume progress
- `runtime_min`: runtime in minutes
- `series_name`, `season_name`, `index_number`: episode context
- `image_url`: primary poster URL when available
