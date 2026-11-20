# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import copy
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import emoji_tool as tool


def update(n, uid, username, text=None, entities=None, sticker=None):
    msg = {"chat": {"type": "private"}, "from": {"id": uid, "username": username}}
    if text is not None:
        msg["text"] = text
    if entities is not None:
        msg["entities"] = entities
    if sticker is not None:
        msg["sticker"] = sticker
    return {"update_id": n, "message": msg}


class FakeBot:
    def __init__(self):
        self.calls = []
        self.created = None

    def call(self, method, **params):
        self.calls.append((method, copy.deepcopy(params)))
        if method == "getMe":
            return {"username": "EmojiBuildBot"}
        if method == "getUpdates":
            return [
                update(1, 34, "owner", "/start"),
                update(2, 55, "stranger", "🧪", [{"type": "custom_emoji", "custom_emoji_id": "STRANGER"}]),
                update(3, 34, "owner", "💎😎", [
                    {"type": "custom_emoji", "custom_emoji_id": "111"},
                    {"type": "custom_emoji", "custom_emoji_id": "222"}]),
                update(4, 34, "owner", sticker={"type": "custom_emoji", "custom_emoji_id": "222"}),
            ] if params["offset"] == 0 else []
        if method == "getCustomEmojiStickers":
            return [
                {"custom_emoji_id": value, "file_id": "file_" + value,
                 "file_unique_id": "unique_" + value, "emoji": "⭐",
                 "is_animated": value == "222", "is_video": False}
                for value in params["custom_emoji_ids"]
            ]
        if method == "getStickerSet":
            if self.created is None:
                raise tool.TelegramError(method, 400, "Bad Request: STICKERSET_INVALID")
            return self.created
        if method == "createNewStickerSet":
            self.created = {"name": params["name"], "stickers": [
                {"file_unique_id": "unique_" + s["sticker"].removeprefix("file_")}
                for s in params["stickers"]
            ]}
            return True
        if method == "addStickerToSet":
            self.created["stickers"].append({"file_unique_id": "unique_" + params["sticker"]["sticker"].removeprefix("file_")})
            return True
        raise AssertionError(method)


class EmojiToolTests(unittest.TestCase):
    def test_extract_messages_and_owner_binding(self):
        state = tool.state_default()
        new_count = tool.process_updates(state, [
            update(1, 34, "owner", "/start"),
            update(2, 55, "stranger", "hello", [{"type": "custom_emoji", "custom_emoji_id": "NOT_ALLOWED"}]),
            update(3, 34, "owner", "hi", [{"type": "custom_emoji", "custom_emoji_id": "abc"}]),
            update(4, 34, "owner", sticker={"type": "custom_emoji", "custom_emoji_id": "abc"}),
            update(5, 34, "owner", sticker={"type": "custom_emoji", "custom_emoji_id": "def"}),
        ])
        self.assertEqual(state["owner_id"], 34)
        self.assertEqual(state["emoji_ids"], ["abc", "def"])
        self.assertEqual(new_count, 2)

    def test_no_start_nontext_safe(self):
        state = tool.state_default()
        self.assertEqual(tool.process_updates(state, [update(1, 34, "owner", sticker={"type":"custom_emoji","custom_emoji_id":"abc"})]), 0)
        self.assertIsNone(state["owner_id"])

    def test_scan_drop_publish_and_duplicate_safety(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "selection.json"
            bot = FakeBot()
            state = tool.state_default()
            tool.scan(bot, state, path)
            self.assertEqual(len(state["items"]), 2)
            self.assertEqual(state["owner_id"], 34)
            tool.drop(state, "2", path)
            self.assertEqual(len(state["items"]), 1)
            tool.publish(bot, state, "AChIcons", "ACh Custom Icons", True, path)
            self.assertEqual(len(bot.created["stickers"]), 1)
            self.assertEqual(bot.created["name"], "AChIcons_by_EmojiBuildBot")
            tool.publish(bot, state, "AChIcons", "ACh Custom Icons", True, path)
            self.assertEqual(sum(x[0] == "createNewStickerSet" for x in bot.calls), 1)
            self.assertEqual(tool.load_state(path)["published"]["confirmed_count"], 1)

    def test_publish_requires_yes(self):
        bot = FakeBot()
        with self.assertRaisesRegex(RuntimeError, "--yes"):
            tool.publish(bot, tool.state_default(), "test", "Test", False)
        self.assertEqual(bot.calls, [])

    def test_invalid_name(self):
        with self.assertRaisesRegex(RuntimeError, "Invalid"):
            tool.pack_name(FakeBot(), "bad--name")

    def test_archive_invalid_telegram_path(self):
        bot = tool.Telegram("123:fake")
        with self.assertRaisesRegex(RuntimeError, "Invalid file path"):
            bot.download("../secrets", Path("/tmp/should-not-write"))


class ImportTests(unittest.TestCase):
    def test_source_pack_import_dedup_and_provenance_after_scan(self):
        class PackBot(FakeBot):
            def call(self, method, **params):
                if method == "getStickerSet":
                    return {"sticker_type": "custom_emoji", "stickers": [
                        {"custom_emoji_id": "source-1", "file_id": "file-1",
                         "file_unique_id": "unique-1", "emoji": "💎", "is_animated": False},
                        {"custom_emoji_id": "source-1", "file_id": "file-1",
                         "file_unique_id": "unique-1", "emoji": "💎", "is_animated": False},
                    ]}
                return super().call(method, **params)

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "selected.json"
            state = tool.state_default()
            bot = PackBot()
            tool.import_packs(bot, state, ["SampleSet", "SampleSet"], path)
            self.assertEqual(state["emoji_ids"], ["source-1"])
            self.assertEqual(state["items"][0]["source_set"], "SampleSet")
            tool.hydrate(state, bot)
            self.assertEqual(state["items"][0]["source_set"], "SampleSet")

    def test_invalid_source_name_no_network(self):
        fake = FakeBot()
        with self.assertRaisesRegex(RuntimeError, "Invalid sticker set"):
            tool.import_packs(fake, tool.state_default(), ["bad/name"])
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
