# Development and operations

## Local prerequisites

- Python 3.10+ (3.13 tested on the Dev Server)
- Render-only dependencies: `Pillow` and `CairoSVG`
- Network access for initial Phosphor SVG downloads
- A separately provisioned Telegram bot only for **live Telegram operations** (not for generating PNG images)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
.venv/bin/python render_icon_pack.py
```

If the OS Python cannot create virtual environments, install your distribution's matching `python3-venv` package or use an independently provisioned Python environment. Do not install packages globally just to run this project.

## Generate a static Custom Emoji family

```bash
.venv/bin/python render_icon_pack.py --icons wallet,gear,credit-card,check-circle
```

Produces `assets/generated/{mono,color,badge}/*.png` (100×100 transparent PNG), an image comparison in `previews/` and provenance manifest. The checked-in example includes 12 icons in 3 styles. The renderer uses a pinned Phosphor revision for reproducibility and stores its MIT license in `assets/sources/phosphor/`.

Do not label the generated output as an official Telegram-published set. Pixel/readability testing on target Telegram clients is still needed.

## Telegram Bot API workbench (experimental)

The Telegram tool is a local CLI with an **external protected credential**. It reads a bot token from inherited **file descriptor 3**, not CLI flags, a checked-in file or the Python process environment. On AI Dev Server an authorized `service_access` credential can be injected through the protected `run_root_command` mechanism (with the existing credential reference); the operator enrolls a real BotFather-issued token through the Agent's private CLI, never in chat or Git. Do not generate substitute random tokens.

Once a dedicated bot has been created and its token enrolled, open its private chat and send `/start` to designate the pack owner. Importing public sets itself does not require chat messages.

The commands below represent CLI subcommands **after** the protected credential has been supplied on FD3:

```bash
python3 emoji_tool.py import-packs nikatel_static_by_nikatelshopbot nikatel_lines_by_nikatelapp TranslucentPack
python3 emoji_tool.py list
python3 emoji_tool.py drop 2,5,8
python3 emoji_tool.py scan
python3 emoji_tool.py archive
```

Only after selection, exact final pack metadata review, explicit approval and a successful owner `/start`, the publish operation can be called:

```bash
python3 emoji_tool.py publish --slug AChIcons --title "ACh Custom Icons" --yes
```

**Do not run the last command until a user has approved that exact public set.** Telegram requires bot-created short names to end in `_by_<bot_username>`. New/changed pack creation must be reconciled against `getStickerSet` after uncertain API responses before any retry. Existing `data/` state and `assets/imported/` downloads are excluded from the public Git repository.

### Known validation gap

The CLI unit tests exercise fake API behavior and publishing deduplication, but **real Telegram publication has not yet been tested**, and source file-id reuse, `getUpdates` delivery with an active webhook, bot-ownership controls and user-facing rendering must be verified. Successful offline tests are not live integration evidence. Imported emoji may require a reupload path when the Telegram API refuses the direct file reference.

The renderer and Telegram workbench are intentionally independent; extending the tool to upload newly generated PNGs is a future stage.

## Types / formats

Read the current official [Telegram Bot API](https://core.telegram.org/bots/api) and [Stickers guide](https://core.telegram.org/stickers) before making format claims. The initial `100×100` PNG path applies to **static custom emoji**, not ordinary stickers. Sticker sizes/formats and animated emoji (TGS/WEBM) have distinct requirements.

## Tests and reviews

- `python3 -m unittest discover -s tests -v`: currently 8 offline tests.
- `python3 -m py_compile emoji_tool.py render_icon_pack.py`: syntax checks.
- Future real Bot API acceptance should use an intentionally separate test bot and must not make irreversible changes to production bots.
- Follow repository scope and the owner's independent review/approval requirements for later substantive changes or releases.

## Handling credentials

This repository does not require or track a token, Telegram user ID, account username, credential reference, chat messages, or API payload logs. Store these only in the authorized protected runtime. The `.gitignore` excludes local selection state, downloaded private media, environment and virtualenv files.
