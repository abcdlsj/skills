#!/usr/bin/env python3
"""Small Emby CLI client for Sumi skills."""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

import httpx

CONFIG_PATH = Path("~/.sumi/cookie/emby_config.json").expanduser()
TOKEN_PATH = Path("~/.sumi/cookie/emby_token.json").expanduser()

CLIENT_NAME = "Sumi"
DEVICE_NAME = "Python"
DEVICE_ID = "sumi-python-001"
VERSION = "1.0.0"

ITEM_FIELDS = "Overview,MediaSources,ProductionYear,UserData"
VIDEO_TYPES = "Movie,Series,Episode"
PLAYABLE_TYPES = "Movie,Episode"


class EmbyClient:
    def __init__(self, server, token=None, user_id=None):
        self.server = server.rstrip("/")
        self.token = token
        self.user_id = user_id

    def auth_header(self):
        parts = [
            f'Client="{CLIENT_NAME}"',
            f'Device="{DEVICE_NAME}"',
            f'DeviceId="{DEVICE_ID}"',
            f'Version="{VERSION}"',
        ]
        if self.token:
            parts.append(f'Token="{self.token}"')
        return "MediaBrowser " + ", ".join(parts)

    def request(self, method, path, body=None, params=None):
        url = self.url(path, params)
        headers = {"X-Emby-Authorization": self.auth_header()}
        content = json.dumps(body).encode() if body is not None else None
        if body is not None:
            headers["Content-Type"] = "application/json"

        try:
            resp = httpx.request(method, url, content=content, headers=headers, timeout=15)
            resp.raise_for_status()
            raw = resp.content
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"HTTP {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            raise RuntimeError(str(e)) from e

        return json.loads(raw) if raw else {}

    def url(self, path, params=None):
        qs = urlencode(params or {}, doseq=True)
        return f"{self.server}{path}?{qs}" if qs else f"{self.server}{path}"

    def login(self, username, password):
        resp = self.request(
            "POST",
            "/emby/Users/AuthenticateByName",
            {"Username": username, "Pw": password},
        )
        self.user_id = resp["User"]["Id"]
        self.token = resp["AccessToken"]
        self.save_token()
        return resp

    def load_token(self):
        if not TOKEN_PATH.exists():
            return False
        data = read_json(TOKEN_PATH)
        self.user_id = data.get("user_id")
        self.token = data.get("token")
        return bool(self.user_id and self.token)

    def save_token(self):
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(
            json.dumps({"user_id": self.user_id, "token": self.token}, indent=2),
            encoding="utf-8",
        )

    def verify_token(self):
        try:
            self.request("GET", f"/emby/Users/{self.user_id}")
            return True
        except RuntimeError:
            return False

    def item_params(self, limit, **extra):
        params = {
            "Limit": limit,
            "Fields": ITEM_FIELDS,
            "ImageTypeLimit": 3,
            "EnableImageTypes": "Primary,Thumb,Backdrop",
        }
        params.update({k: v for k, v in extra.items() if v not in (None, "", [])})
        return params

    def items(self, path, params=None):
        resp = self.request("GET", path, params=params)
        return resp if isinstance(resp, list) else resp.get("Items", [])

    def libraries(self):
        return self.items(f"/emby/Users/{self.user_id}/Views")

    def latest(self, limit=20):
        return self.items(
            f"/emby/Users/{self.user_id}/Items/Latest",
            self.item_params(limit),
        )

    def library_items(self, parent_id, start=0, limit=50):
        resp = self.request(
            "GET",
            f"/emby/Users/{self.user_id}/Items",
            params=self.item_params(
                limit,
                Recursive="true",
                SortBy="SortName",
                SortOrder="Ascending",
                StartIndex=start,
                ParentId=parent_id,
            ),
        )
        return page(resp)

    def search(
        self,
        query,
        item_types=None,
        limit=50,
        start=0,
        played=None,
        favorite_only=False,
        year=0,
    ):
        filters = []
        if played == "played":
            filters.append("IsPlayed")
        if played == "unplayed":
            filters.append("IsUnplayed")
        if favorite_only:
            filters.append("IsFavorite")

        resp = self.request(
            "GET",
            f"/emby/Users/{self.user_id}/Items",
            params=self.item_params(
                limit,
                Recursive="true",
                StartIndex=start,
                SearchTerm=query,
                IncludeItemTypes=",".join(item_types) if item_types else None,
                Filters=",".join(filters),
                Years=str(year) if year else None,
            ),
        )
        return page(resp)

    def item(self, item_id):
        return self.request(
            "GET",
            f"/emby/Users/{self.user_id}/Items/{item_id}",
            params={"Fields": "MediaSources,Overview,UserData"},
        )

    def seasons(self, series_id):
        return self.items(
            f"/emby/Shows/{series_id}/Seasons",
            {"UserId": self.user_id},
        )

    def episodes(self, series_id, season_id):
        return self.items(
            f"/emby/Shows/{series_id}/Episodes",
            {
                "UserId": self.user_id,
                "SeasonId": season_id,
                "Fields": "MediaSources,Overview",
            },
        )

    def add_favorite(self, item_id):
        return self.request("POST", f"/emby/Users/{self.user_id}/FavoriteItems/{item_id}")

    def remove_favorite(self, item_id):
        path = f"/emby/Users/{self.user_id}/FavoriteItems/{item_id}"
        try:
            return self.request("DELETE", path)
        except RuntimeError as e:
            if "HTTP 404" in str(e) or "HTTP 405" in str(e):
                return self.request("POST", f"{path}/Delete")
            raise

    def is_favorite(self, item_id):
        items = self.items(
            f"/emby/Users/{self.user_id}/Items",
            {
                "Ids": item_id,
                "Limit": 1,
                "Recursive": "true",
                "Filters": "IsFavorite",
            },
        )
        return bool(items)

    def favorites(self, limit=50):
        return self.filtered_items("IsFavorite", VIDEO_TYPES, limit)

    def resume(self, limit=50):
        return self.filtered_items("IsResumable", PLAYABLE_TYPES, limit)

    def history(self, limit=20, start=0):
        resp = self.request(
            "GET",
            f"/emby/Users/{self.user_id}/Items",
            params=self.filter_params("IsPlayed", PLAYABLE_TYPES, limit, StartIndex=start),
        )
        return page(resp)

    def filtered_items(self, filters, item_types, limit):
        return self.items(
            f"/emby/Users/{self.user_id}/Items",
            self.filter_params(filters, item_types, limit),
        )

    def filter_params(self, filters, item_types, limit, **extra):
        return self.item_params(
            limit,
            Recursive="true",
            Filters=filters,
            SortBy="DatePlayed",
            SortOrder="Descending",
            IncludeItemTypes=item_types,
            **extra,
        )

    def poster_url(self, item, height=400):
        tag = (item.get("ImageTags") or {}).get("Primary")
        if not tag:
            return ""
        return self.url(
            f"/emby/Items/{item.get('Id')}/Images/Primary",
            {"height": height, "tag": tag},
        )


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def page(resp):
    return resp.get("Items", []), resp.get("TotalRecordCount", 0)


def fail(message):
    print(json.dumps({"error": message}, ensure_ascii=False))
    sys.exit(1)


def emit(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def output(client, items, total=None):
    data = {"items": [simplify(client, item) for item in items]}
    if total is not None:
        data["total"] = total
    emit(data)


def simplify(client, item):
    user = item.get("UserData") or {}
    ticks = item.get("RunTimeTicks") or 0
    pos = user.get("PlaybackPositionTicks") or 0
    sources = item.get("MediaSources") or []

    return {
        "id": item.get("Id"),
        "name": item.get("Name"),
        "type": item.get("Type"),
        "year": item.get("ProductionYear"),
        "overview": (item.get("Overview") or "")[:200],
        "is_favorite": user.get("IsFavorite", False),
        "played": user.get("Played", False),
        "playback_pct": round(pos / ticks * 100, 1) if ticks and pos else 0,
        "runtime_min": ticks // 60_000_000 if ticks else 0,
        "series_name": item.get("SeriesName"),
        "season_name": item.get("SeasonName"),
        "index_number": item.get("IndexNumber"),
        "series_id": item.get("SeriesId"),
        "season_id": item.get("SeasonId"),
        "container": sources[0].get("Container") if sources else None,
        "image_url": client.poster_url(item),
    }


def client_from_config():
    if not CONFIG_PATH.exists():
        fail(f"Config file not found: {CONFIG_PATH}")

    config = read_json(CONFIG_PATH)
    server = config.get("server")
    if not server:
        fail("Missing 'server' in config file")

    client = EmbyClient(server)
    if client.load_token() and client.verify_token():
        return client

    username = config.get("username")
    password = config.get("password")
    if not username or not password:
        fail("Login required. Add 'username' and 'password' to the config file")

    try:
        client.login(username, password)
    except Exception as e:
        fail(f"Login failed: {e}")

    return client


def cmd_status(client, args):
    try:
        resp = client.request("GET", "/emby/System/Info/Public")
        emit(
            {
                "ok": True,
                "server_name": resp.get("ServerName"),
                "version": resp.get("Version"),
                "user_id": client.user_id,
            }
        )
    except Exception as e:
        emit({"ok": False, "error": str(e)})


def cmd_search(client, args):
    items, total = client.search(
        args.query,
        item_types=[args.type] if args.type else None,
        limit=args.limit,
        start=args.start or 0,
        played=args.played,
        favorite_only=args.favorite_only,
        year=args.year or 0,
    )
    output(client, items, total)


def cmd_libraries(client, args):
    output(client, client.libraries())


def cmd_items(client, args):
    items, total = client.library_items(args.parent_id, args.start or 0, args.limit)
    output(client, items, total)


def cmd_item(client, args):
    emit(simplify(client, client.item(args.item_id)))


def cmd_seasons(client, args):
    output(client, client.seasons(args.series_id))


def cmd_episodes(client, args):
    output(client, client.episodes(args.series_id, args.season_id))


def cmd_favorite(client, args):
    try:
        client.add_favorite(args.item_id)
        emit({"ok": True, "action": "favorited", "item_id": args.item_id})
    except Exception as e:
        emit({"ok": False, "error": str(e)})


def cmd_unfavorite(client, args):
    try:
        client.remove_favorite(args.item_id)
        emit({"ok": True, "action": "unfavorited", "item_id": args.item_id})
    except Exception as e:
        emit({"ok": False, "error": str(e)})


def cmd_is_favorite(client, args):
    try:
        emit({"item_id": args.item_id, "is_favorite": client.is_favorite(args.item_id)})
    except Exception as e:
        emit({"error": str(e)})


def cmd_favorites(client, args):
    output(client, client.favorites(args.limit))


def cmd_resume(client, args):
    output(client, client.resume(args.limit))


def cmd_history(client, args):
    items, total = client.history(args.limit, args.start or 0)
    output(client, items, total)


def cmd_latest(client, args):
    output(client, client.latest(args.limit))


def cmd_poster(client, args):
    item = client.item(args.item_id)
    url = client.poster_url(item, args.height)
    if not url:
        emit({"error": "No poster found", "item_id": args.item_id})
        return
    emit({"item_id": args.item_id, "name": item.get("Name"), "poster_url": url})


def parser():
    p = argparse.ArgumentParser(description="Emby CLI for Sumi")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("status", help="Check server connection")

    q = sub.add_parser("search", help="Search media")
    q.add_argument("query", nargs="?", default="")
    q.add_argument("--type", help="Item type: Movie, Series, Episode")
    q.add_argument("--limit", type=int, default=50)
    q.add_argument("--start", type=int)
    q.add_argument("--played", choices=["played", "unplayed"])
    q.add_argument("--favorite-only", action="store_true")
    q.add_argument("--year", type=int)

    sub.add_parser("libraries", help="List media libraries")

    q = sub.add_parser("items", help="List library items")
    q.add_argument("parent_id", help="Library or folder ID")
    q.add_argument("--limit", type=int, default=50)
    q.add_argument("--start", type=int)

    q = sub.add_parser("item", help="Show item details")
    q.add_argument("item_id")

    q = sub.add_parser("seasons", help="List seasons")
    q.add_argument("series_id")

    q = sub.add_parser("episodes", help="List season episodes")
    q.add_argument("series_id")
    q.add_argument("season_id")

    q = sub.add_parser("favorite", help="Add item to favorites")
    q.add_argument("item_id")

    q = sub.add_parser("unfavorite", help="Remove item from favorites")
    q.add_argument("item_id")

    q = sub.add_parser("is_favorite", help="Check favorite status")
    q.add_argument("item_id")

    q = sub.add_parser("poster", help="Get item poster URL")
    q.add_argument("item_id")
    q.add_argument("--height", type=int, default=400)

    q = sub.add_parser("favorites", help="List favorite media")
    q.add_argument("--limit", type=int, default=50)

    q = sub.add_parser("resume", help="List resumable media")
    q.add_argument("--limit", type=int, default=50)

    q = sub.add_parser("history", help="List watch history")
    q.add_argument("--limit", type=int, default=20)
    q.add_argument("--start", type=int)

    q = sub.add_parser("latest", help="List recently added media")
    q.add_argument("--limit", type=int, default=20)

    return p


def main():
    p = parser()
    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(1)

    commands = {
        "status": cmd_status,
        "search": cmd_search,
        "libraries": cmd_libraries,
        "items": cmd_items,
        "item": cmd_item,
        "seasons": cmd_seasons,
        "episodes": cmd_episodes,
        "favorite": cmd_favorite,
        "unfavorite": cmd_unfavorite,
        "is_favorite": cmd_is_favorite,
        "poster": cmd_poster,
        "favorites": cmd_favorites,
        "resume": cmd_resume,
        "history": cmd_history,
        "latest": cmd_latest,
    }
    commands[args.command](client_from_config(), args)


if __name__ == "__main__":
    main()
