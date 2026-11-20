#!/usr/bin/env python3
"""Private Telegram custom-emoji pack workbench.

Only reads the Bot token from inherited FD 3 (AI Dev Server service_access).
Does not create packs until publish is explicitly invoked.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "data" / "selection.json"
MAX_SET_SIZE = 200


class TelegramError(RuntimeError):
    def __init__(self, method: str, code: int, description: str):
        self.method = method
        self.code = code
        self.description = description
        super().__init__(f"{method}: HTTP/API {code}: {description}")


def read_private_token() -> str:
    """FD 3 is injected by AI Dev Server's protected credential consumer."""
    try:
        token = os.read(3, 4096).decode("ascii").strip()
    except (OSError, UnicodeError):
        raise RuntimeError("Bot credential is unavailable on protected FD 3") from None
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{20,}", token):
        raise RuntimeError("Invalid Telegram bot token format") from None
    return token


class Telegram:
    def __init__(self, token: str):
        self._token = token

    def call(self, method: str, **params):
        # Avoid printing the URL: it includes the credential.
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        req = urllib.request.Request(
            url, data=json.dumps(params).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
                code = body.get("error_code", exc.code)
                desc = body.get("description", "Unknown API error")
            except (ValueError, UnicodeError):
                code, desc = exc.code, "Unparseable API error"
            raise TelegramError(method, code, desc) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # No secret-bearing URL/headers in diagnostics.
            raise RuntimeError(f"{method}: transport failure ({type(exc).__name__})") from None
        if not data.get("ok"):
            raise TelegramError(method, data.get("error_code", 0),
                                data.get("description", "Unknown API error"))
        return data["result"]

    def download(self, file_path: str, destination: Path):
        # file_path always comes from Telegram getFile; prevent arbitrary paths.
        if not file_path or file_path.startswith("/") or ".." in Path(file_path).parts:
            raise RuntimeError("Invalid file path returned by Telegram")
        quoted = urllib.parse.quote(file_path, safe="/")
        url = f"https://api.telegram.org/file/bot{self._token}/{quoted}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                if response.status != 200:
                    raise RuntimeError("Telegram file download failed")
                payload = response.read(22 * 1024 * 1024)
                if len(payload) >= 22 * 1024 * 1024:
                    raise RuntimeError("Telegram file exceeded download bound")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Telegram file download: HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"Telegram file download: {type(exc).__name__}") from None
        atomic_bytes(destination, payload)


def atomic_bytes(path: Path, payload: bytes):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix=".stage-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def state_default():
    return {"owner_id": None, "owner_username": None, "last_update_id": -1,
            "emoji_ids": [], "items": [], "published": None}


def load_state(path=STATE_FILE):
    if not path.exists():
        return state_default()
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def save_state(state, path=STATE_FILE):
    atomic_bytes(path, (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode())


def ids_from_message(msg):
    ids = []
    for key in ("entities", "caption_entities"):
        for entity in msg.get(key, []):
            if entity.get("type") == "custom_emoji" and entity.get("custom_emoji_id"):
                ids.append(entity["custom_emoji_id"])
    sticker = msg.get("sticker") or {}
    if sticker.get("type") == "custom_emoji" and sticker.get("custom_emoji_id"):
        ids.append(sticker["custom_emoji_id"])
    return list(dict.fromkeys(ids))


def process_updates(state, updates):
    new_count = 0
    for update in sorted(updates, key=lambda x: x["update_id"]):
        state["last_update_id"] = max(state["last_update_id"], update["update_id"])
        msg = update.get("message") or {}
        sender = msg.get("from") or {}
        if msg.get("chat", {}).get("type") != "private" or sender.get("is_bot"):
            continue
        user_id = sender.get("id")
        if not user_id:
            continue
        if state["owner_id"] is None:
            if not (msg.get("text") or "").split(maxsplit=1) or (msg.get("text") or "").split(maxsplit=1)[0].split("@")[0] != "/start":
                continue
            state["owner_id"] = user_id
            state["owner_username"] = sender.get("username") or sender.get("first_name", "")
        if user_id != state["owner_id"]:
            continue
        for emoji_id in ids_from_message(msg):
            if emoji_id not in state["emoji_ids"]:
                state["emoji_ids"].append(emoji_id)
                new_count += 1
    return new_count


def hydrate(state, bot):
    ids = state["emoji_ids"]
    # API allows 200 IDs/request. We preserve the selected order.
    received = {}
    for first in range(0, len(ids), 200):
        for item in bot.call("getCustomEmojiStickers", custom_emoji_ids=ids[first:first+200]):
            received[item["custom_emoji_id"]] = item
    items = []
    previous = {x["custom_emoji_id"]: x for x in state.get("items", [])}
    for emoji_id in ids:
        item = received.get(emoji_id)
        if item is None:
            print(f"WARNING: Custom emoji ID unavailable: {emoji_id}", file=sys.stderr)
            continue
        kind = "video" if item.get("is_video") else ("animated" if item.get("is_animated") else "static")
        entry = {
            "custom_emoji_id": emoji_id,
            "file_id": item["file_id"],
            "file_unique_id": item["file_unique_id"],
            "format": kind,
            "emoji": item.get("emoji") or "⭐",
        }
        if previous.get(emoji_id, {}).get("source_set"):
            entry["source_set"] = previous[emoji_id]["source_set"]
        items.append(entry)
    state["items"] = items


def scan(bot, state, path=STATE_FILE):
    before = len(state["emoji_ids"])
    scanned = 0
    for _ in range(80):
        updates = bot.call("getUpdates", offset=state["last_update_id"] + 1,
                           limit=100, timeout=0, allowed_updates=["message"])
        if not updates:
            break
        process_updates(state, updates)
        save_state(state, path)
        scanned += len(updates)
        if len(updates) < 100:
            break
    if state["emoji_ids"]:
        hydrate(state, bot)
        save_state(state, path)
    print(f"Owner: {state['owner_id']} (@{state['owner_username']})")
    print(f"Updates processed: {scanned}, added emojis: {len(state['emoji_ids']) - before}")
    show_selection(state)


def import_packs(bot, state, names, path=STATE_FILE):
    """Collect all Custom Emoji items from source pack short names.

    Does not publish anything. Selection may be trimmed with 'drop' later.
    """
    existing = set(state["emoji_ids"])
    for name in names:
        if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", name):
            raise RuntimeError(f"Invalid sticker set name: {name}")
        source = bot.call("getStickerSet", name=name)
        if source.get("sticker_type") != "custom_emoji":
            raise RuntimeError(f"Not a Custom Emoji sticker set: {name}")
        added = 0
        for sticker in source.get("stickers", []):
            emoji_id = sticker.get("custom_emoji_id")
            if not emoji_id or emoji_id in existing:
                continue
            kind = "video" if sticker.get("is_video") else ("animated" if sticker.get("is_animated") else "static")
            state["emoji_ids"].append(emoji_id)
            state["items"].append({
                "custom_emoji_id": emoji_id,
                "file_id": sticker["file_id"],
                "file_unique_id": sticker["file_unique_id"],
                "format": kind,
                "emoji": sticker.get("emoji") or "⭐",
                "source_set": name,
            })
            existing.add(emoji_id)
            added += 1
        save_state(state, path)
        print(f"Imported {name}: {added} new icons")
    show_selection(state)


def show_selection(state):
    if not state["items"]:
        print("No Custom Emoji selected. Send /start, then a TEXT message containing selected custom emojis.")
        return
    for number, item in enumerate(state["items"], 1):
        print(f"  {number:>3}. {item['emoji']} {item['format']:<8} id={item['custom_emoji_id']} source={item.get('source_set', 'message')}")
    print(f"Total: {len(state['items'])} of {MAX_SET_SIZE} allowed per pack")


def drop(state, indices, path=STATE_FILE):
    try:
        selected = set(int(x.strip()) for x in indices.split(","))
    except ValueError:
        raise RuntimeError("Use comma-separated indices, for example: 2,5,8") from None
    if not selected or any(i < 1 or i > len(state["items"]) for i in selected):
        raise RuntimeError("Selected indices out of range")
    removed = {state["items"][i - 1]["custom_emoji_id"] for i in selected}
    state["emoji_ids"] = [x for x in state["emoji_ids"] if x not in removed]
    state["items"] = [x for x in state["items"] if x["custom_emoji_id"] not in removed]
    save_state(state, path)
    print(f"Removed {len(removed)} items from local selection.")
    show_selection(state)


def pack_name(bot, slug: str):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", slug) or "__" in slug:
        raise RuntimeError("Invalid pack prefix: use English letters, digits, underscores")
    username = bot.call("getMe")["username"]
    name = f"{slug}_by_{username}"
    if len(name) > 64:
        raise RuntimeError("Pack name is too long for Telegram (max 64 characters)")
    return name


def get_pack_or_none(bot, name):
    try:
        return bot.call("getStickerSet", name=name)
    except TelegramError as exc:
        if exc.code == 400 and ("STICKERSET_INVALID" in exc.description
                                or "stickerset not found" in exc.description.lower()):
            return None
        raise


def publish(bot, state, slug, title, confirmed, path=STATE_FILE):
    if not confirmed:
        raise RuntimeError("Publishing requires --yes (explicit approval)")
    if state["owner_id"] is None:
        raise RuntimeError("No pack owner. Send /start to the bot first.")
    if not 1 <= len(state["items"]) <= MAX_SET_SIZE:
        raise RuntimeError(f"Select 1 to {MAX_SET_SIZE} available emojis first.")
    if not 1 <= len(title) <= 64:
        raise RuntimeError("Telegram title must be 1..64 characters")
    name = pack_name(bot, slug)
    existing = get_pack_or_none(bot, name)
    if existing is not None:
        if (state.get("published") or {}).get("name") == name:
            print(f"Existing pack detected: https://t.me/addemoji/{name}")
            print(f"Actual stickers: {len(existing.get('stickers', []))}")
            print("No duplicate creation attempted. Contact operator for reconciliation if incomplete.")
            return
        raise RuntimeError(f"Name already exists: {name}; no changes made.")
    stickers = [
        {"sticker": item["file_id"], "format": item["format"], "emoji_list": [item["emoji"]]}
        for item in state["items"]
    ]
    print(f"Submitting custom emoji pack {name} with {len(stickers)} icons.")
    try:
        bot.call("createNewStickerSet", user_id=state["owner_id"], name=name, title=title,
                 stickers=stickers[:50], sticker_type="custom_emoji")
    except Exception:
        # A timed-out create may actually have succeeded. Never silently retry.
        after = get_pack_or_none(bot, name)
        if after is not None:
            state["published"] = {"name": name, "title": title, "confirmed_count": len(after["stickers"])}
            save_state(state, path)
            raise RuntimeError(f"Creation may have succeeded; check https://t.me/addemoji/{name}. No retry.")
        raise
    pack = get_pack_or_none(bot, name)
    if not pack:
        raise RuntimeError("Telegram acknowledged creation, but pack lookup did not confirm it")
    state["published"] = {"name": name, "title": title, "confirmed_count": len(pack["stickers"])}
    save_state(state, path)
    # Add remaining items only after initial creation is positively verified.
    already = {x.get("file_unique_id") for x in pack["stickers"]}
    for source, entry in zip(state["items"][50:], stickers[50:]):
        if source["file_unique_id"] in already:
            continue
        bot.call("addStickerToSet", user_id=state["owner_id"], name=name, sticker=entry)
        pack = get_pack_or_none(bot, name)
        if not pack:
            raise RuntimeError("Published pack disappeared during expansion")
        already = {x.get("file_unique_id") for x in pack["stickers"]}
        state["published"]["confirmed_count"] = len(pack["stickers"])
        save_state(state, path)
    pack = get_pack_or_none(bot, name)
    count = len(pack["stickers"])
    print(f"Published: https://t.me/addemoji/{name} ({count} Telegram-confirmed items)")
    if count != len(stickers):
        print("WARNING: Sticker count differs from selection; inspect the pack before relying on it.")


def archive(bot, state):
    if not state["items"]:
        raise RuntimeError("No selected icons to download")
    folder = ROOT / "assets" / "imported"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    extensions = {"static": ".webp", "animated": ".tgs", "video": ".webm"}
    written = 0
    for item in state["items"]:
        meta = bot.call("getFile", file_id=item["file_id"])
        original_ext = Path(meta["file_path"]).suffix.lower()
        extension = original_ext if original_ext in (".png", ".webp", ".tgs", ".webm") else extensions[item["format"]]
        destination = folder / (item["custom_emoji_id"] + extension)
        if destination.exists():
            continue
        bot.download(meta["file_path"], destination)
        written += 1
    print(f"Original assets saved at {folder}; downloaded {written} new files.")


def cli(argv=None, bot=None, path=STATE_FILE):
    parser = argparse.ArgumentParser(description="Telegram Custom Emoji selection and publishing workbench")
    subs = parser.add_subparsers(dest="action", required=True)
    subs.add_parser("scan", help="Collect emojis from Telegram private messages")
    importer = subs.add_parser("import-packs", help="Import public Custom Emoji packs by short name")
    importer.add_argument("names", nargs="+", help="Public sticker set names (from t.me/addemoji/NAME)")
    subs.add_parser("list", help="Show locally selected emojis without API access")
    remove = subs.add_parser("drop", help="Remove selected icons by their list indices")
    remove.add_argument("indices", help="Comma-separated 1-based indices")
    pub = subs.add_parser("publish", help="Publish a custom emoji pack after explicit owner approval")
    pub.add_argument("--slug", default="AChIcons")
    pub.add_argument("--title", default="ACh Custom Icons")
    pub.add_argument("--yes", action="store_true")
    subs.add_parser("archive", help="Download original selected emoji files")
    args = parser.parse_args(argv)
    state = load_state(path)
    if args.action == "list":
        show_selection(state)
        return
    if args.action == "drop":
        drop(state, args.indices, path)
        return
    if bot is None:
        bot = Telegram(read_private_token())
    if args.action == "scan":
        scan(bot, state, path)
    elif args.action == "import-packs":
        import_packs(bot, state, args.names, path)
    elif args.action == "archive":
        archive(bot, state)
    elif args.action == "publish":
        publish(bot, state, args.slug, args.title, args.yes, path)


if __name__ == "__main__":
    try:
        cli()
    except (RuntimeError, TelegramError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
