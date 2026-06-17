# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

ghostwriter is a Python CLI that implements a **Markdown → Ghost → WeChat** publishing pipeline. Write Markdown, publish to a Ghost blog, and sync to a WeChat Official Account draft.

## Commands

```bash
# Install (from PyPI)
pip install ghostwriter-cli

# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# CLI
ghostwriter list                              # list Ghost posts
ghostwriter publish article.md                # publish Markdown to Ghost
ghostwriter publish article.md --draft --wechat
ghostwriter <article-id>                      # sync Ghost→WeChat
ghostwriter --preview <article-id>            # preview HTML, no draft
ghostwriter config                            # show config (secrets masked)
ghostwriter config set <key> <value>          # write config key
ghostwriter config path                       # print config file path
```

## Configuration architecture

Two-tier system, env vars take priority:

1. **Environment variables** (primary, CI/Docker):
   `GHOSTWRITER_GHOST_API_URL`, `GHOSTWRITER_GHOST_ADMIN_KEY_ID`,
   `GHOSTWRITER_GHOST_ADMIN_KEY`, `GHOSTWRITER_WECHAT_APPID`,
   `GHOSTWRITER_WECHAT_SECRET`

2. **Config file** (fallback): `~/.config/ghostwriter/config.json`,
   managed via `ghostwriter config set <key> <value>`

`load_config()` validates all 5 required keys are present, exits with helpful
error if any are missing. See `src/ghostwriter/config.py`.

## Package structure

```
src/ghostwriter/
├── __init__.py     # public API re-exports
├── __main__.py     # python -m ghostwriter
├── cli.py          # CLI dispatch: main(), sync_article, publish_md_to_ghost, _cmd_publish
├── config.py       # load_config(), set_config_value(), show_config()
├── ghost.py        # Ghost Admin API: JWT auth, CRUD, image upload, author lookup
├── wechat.py       # WeChat API: token cache, material upload, draft creation
├── cleaner.py      # _WeChatCleaner HTML parser + whitelists + clean_html_for_wechat
├── pipeline.py     # process_html() + 14 transform stages (hr, table, links, lists, etc.)
├── lexical.py      # md_to_ghost_lexical(): Markdown → Ghost Lexical JSON
└── normalize.py    # normalize_title(): Unicode → ASCII for WeChat compatibility
```

## Architecture

### 1. Ghost API layer (`ghost.py`)
JWT auth (`get_ghost_token`) → generic `_api_request` helper used by
`ghost_api_get/post/put/delete`. All Admin API calls go through path
normalization: `{api_url.rstrip('/')}/{path.lstrip('/')}`.
`upload_image_to_ghost` and `get_ghost_authors` build their own URLs (Content API).

### 2. WeChat API layer (`wechat.py`)
Token management with disk cache (`/tmp/wechat_token.json`), permanent
material upload for images, draft creation. Token is cached until 60s
before expiry.

### 3. HTML processing pipeline (`pipeline.py`)
**Core of Ghost→WeChat conversion.** Order is strict — reordering breaks things:

1. Replace image URLs with WeChat CDN URLs
2. Strip Ghost HTML comments (`<!--kg-card-*-->`)
3. Convert `<hr>` → styled `<div>` (before whitelist)
4. Convert `<table>` → inline-block `<span>` layout (before whitelist)
5. Extract code blocks to placeholders (protect from filter)
6. Three-level whitelist filter: tags → attributes → CSS properties
7. Restore code blocks with WeChat-safe `<pre>` styling
8. Apply default styles (heading sizes, inline code, blockquote)
9. Flatten nested blockquotes
10. Paragraph/image spacing
11. Convert links to `text [url]`
12. Convert `<ol>` → numbered `<p>`, `<ul>` → bullet `<p>`

Whitelists live in `cleaner.py`: `WECHAT_SAFE_TAGS`, `WECHAT_SAFE_ATTRS`,
`WECHAT_SAFE_STYLES`.

### 4. Markdown → Ghost Lexical (`lexical.py`)
Converts Markdown to Ghost Lexical JSON (not mobiledoc). Tables become
`html` cards. Supports headings, code blocks, lists, hr, inline formatting
(bold, italic, code, links).

### 5. CLI (`cli.py`)
Commands: `list`, `publish`, `config`, sync (by article ID or `--preview`).
`main()` handles dispatch. `sync_article()` is the Ghost→WeChat flow.
`publish_md_to_ghost()` handles Markdown→Ghost with author lookup fallback.

## Key design decisions

- **Code block protection:** Extracted to `__CODE_BLOCK_PLACEHOLDER__N__` before
  the whitelist filter, restored afterward. Prevents filter from stripping tags.
- **Author fallback chain:** Ghost Content API → hardcoded IDs for known slugs.
- **WeChat constraints:** Author ≤8 bytes, digest ≤120 bytes, titles must not
  contain Unicode special characters (normalized via `normalize_title()`).
- **Preview mode skips WeChat:** `--preview` only reads Ghost article and saves
  HTML to `/tmp`, no WeChat credentials needed.
