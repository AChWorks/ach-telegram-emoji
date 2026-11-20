# Candidate Telegram Custom Emoji packs

The project owner stated that reuse and republication of the following three packs is permitted. This is a **reported permission**, not an independent record of the third-party rights; maintain source attribution where appropriate.

| Pack | Telegram link | Status |
| --- | --- | --- |
| Nikatel Static | https://t.me/addemoji/nikatel_static_by_nikatelshopbot | Source candidate; not yet fetched in a live API test |
| Nikatel Lines | https://t.me/addemoji/nikatel_lines_by_nikatelapp | Source candidate; not yet fetched in a live API test |
| Translucent Pack | https://t.me/addemoji/TranslucentPack | Source candidate; not yet fetched in a live API test |

## Intended workflow

1. Retrieve each **public** set with Telegram Bot API `getStickerSet` and preserve each `custom_emoji_id`, media type and upstream set name.
2. Compare thumbnails, remove undesired icons, avoid duplicate items and verify set size and compatibility.
3. Where Telegram accepts the source media `file_id`, reuse it. If that is rejected, fetch eligible original files with `getFile`, validate them and re-upload through a supported route.
4. Verify the final selected list with the owner before any live publication.
5. Record the published pack link(s) and source provenance in GitHub after successful verification.

A pack's public visibility is not itself a reuse license; the specific permission noted above applies only to these named sources.

Telegram deep links use `t.me/addemoji/<short_name>` for Custom Emoji packs and `t.me/addstickers/<short_name>` for ordinary Sticker packs.
