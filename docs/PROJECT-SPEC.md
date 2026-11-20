# Project specification — ACh Telegram Emoji

**Status:** Accepted project scope; Telegram publishing and Sticker support are future delivery stages.

## Purpose

ACh Telegram Emoji is the single repository for an ACh-branded design and production workflow for Telegram **Custom Emoji** and, later, **Sticker** packs. It is a curated library and reproducible set of tools, not an attempt to rehost every icon catalogue.

## Accepted scope

- Preserve references and terms for potentially useful external icon libraries.
- Select or import licensed assets, avoiding unnecessary manual re-creation where existing Telegram media can be reused.
- Support multiple consistent variants of the same visual family, e.g. monochrome, colored/duotone, and colored-background badges.
- Keep source provenance and license/permission records alongside outputs.
- Prepare, preview, validate, and eventually publish Telegram Custom Emoji packs owned by ACh.
- Extend to Telegram stickers later without migrating the project to another repository.
- Keep work, evidence, future decisions and incomplete tasks in the repository and Issues rather than relying on chat history.

## Product and engineering boundaries

- **Publishing is an external action.** Present the exact title, short name, owner, assets and target Telegram account for owner approval before publishing or changing live packs.
- **Credential and personal data boundaries:** Use an approved protected service credential/runtime mechanism; never store secrets or real-user messages/selection state in public Git.
- **Source rights:** The owner reported permission to reuse the three referenced Telegram emoji packs. Record their provenance; do not assume this gives permission for arbitrary other sets.
- **Project license:** ACh-authored source code, tools, tests, and project documentation use [MPL-2.0](../LICENSE). Third-party artwork and derived icon outputs are not relicensed by the repository-wide license.
- **Third-party library terms:** Follow each set's license as applied to specific files; not every “free” icon is redistributable. Preserve required notices/attribution.
- **Style consistency:** Each generated pack should have a coherent source, weight, scale, padding and palette, even if the wider project hosts many families.
- Do not invent restrictions unrelated to real Telegram format/API contracts. Keep import, transformation and publishing separate so experiments do not imply publication.

## Implemented and independently verifiable so far

- `render_icon_pack.py` creates `100×100` PNG emoji in three styles from Phosphor Core SVG; a 12-icon, 36-output example and manifest have been generated.
- `emoji_tool.py` supports importing public sets with `getStickerSet` and selecting, removing and preparing custom emoji sets using Bot API.
- Python offline unit tests cover ownership selection, deduplication, importing, removal and publish safety; they do **not** establish real Telegram Bot API acceptance.
- Three pre-existing Telegram packs and icon discovery references are documented.

## Not yet established

- The Telegram bot's token is not present in Git and must be enrolled by the operator separately; do not claim account readiness without checking it.
- Real `getStickerSet` import for the three supplied packs, reuse of source `file_id` in a new set, actual Telegram publication, and end-user rendering remain unverified.
- Full sticker (non-emoji) generation/export and video/TGS animation are future scope, not implemented.
- Which source library, art direction, published names and palettes to use long term are not final decisions. The ACh project license is settled as MPL-2.0; upstream assets retain their own licenses.

## Success criteria (next active milestone)

1. Operator can securely provision a dedicated bot; tool validates `getMe` without exposing the token.
2. Relevant source emoji can be listed with provenance, visually inspected, selected and excluded.
3. Telegram-ready assets are validated against official type/format requirements and appropriately attributed.
4. A proposed pack can be previewed and approved before a single publication attempt.
5. Publication, if approved, is verified by rereading the resulting Telegram sticker set (name, item count, types and actual appearance).
6. Accepted outputs and technical evidence are recorded in GitHub, not just in chat.

Future Sticker support should have its own outcome and acceptance contract before beginning implementation.

## Primary references

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Telegram sticker creation and formats](https://core.telegram.org/stickers)
- [Icon sources](ICON-SOURCES.md)
- [Candidate Telegram packs](TELEGRAM-PACKS.md)
- [Developer / operation guide](DEVELOPMENT.md)
