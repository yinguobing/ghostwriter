# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

ghostwriter is a single-file Python CLI that implements a **Markdown → Ghost → WeChat** publishing pipeline. Write Markdown, publish to a Ghost blog, and sync to a WeChat Official Account draft — all from the command line.

## Commands

```bash
# List Ghost posts
python3 ghostwriter.py list

# Publish Markdown to Ghost
python3 ghostwriter.py publish article.md
python3 ghostwriter.py publish article.md --title "标题" --slug my-slug --tags tag1,tag2
python3 ghostwriter.py publish article.md --author guobing --draft
python3 ghostwriter.py publish article.md --cover cover.png --wechat

# Sync Ghost post to WeChat draft
python3 ghostwriter.py <article-id>

# Preview WeChat HTML (saves to /tmp, no draft created)
python3 ghostwriter.py --preview <article-id>
```

**Dependencies:** `pip install requests PyJWT`

**Configuration:** Create `config.json` (gitignored) with Ghost Admin API key and WeChat appid/secret. See README for schema.

**No tests, no linting, no build system.** This is a single-script tool.

## Architecture

Everything lives in `ghostwriter.py` (~1215 lines). The file is organized into distinct layers:

### 1. Ghost API layer
JWT-based auth (`get_ghost_token`) → generic `ghost_api_get/post/put/delete` helpers. Also `upload_image_to_ghost` for image uploads and `get_ghost_authors` via Content API.

### 2. WeChat API layer
Token management with disk caching (`/tmp/wechat_token.json`), permanent material upload (`upload_permanent_material`), and draft creation (`create_wechat_draft`). The WeChat token is cached to avoid hitting rate limits.

### 3. HTML processing pipeline (`process_html`)
This is the **core of the Ghost→WeChat conversion**. The pipeline runs in a strict order — reordering steps will break things:

1. Replace image URLs with WeChat CDN URLs
2. Strip Ghost-specific HTML comments (`<!--kg-card-*-->`)
3. Convert `<hr>` → styled `<div>` (must happen before whitelist filtering)
4. Convert `<table>` → inline-block `<span>` layout (must happen before whitelist filtering, since `<table>` is not in the safe tags whitelist)
5. **Extract code blocks** to placeholders to protect them from the next step
6. **Three-level whitelist filter** (`_WeChatCleaner` + `clean_html_for_wechat`): tags → attributes → CSS properties. Non-whitelisted tags are stripped but their text content is preserved.
7. Restore code blocks with WeChat-safe styling
8. Apply default styles (heading sizes, inline code background, blockquote)
9. Flatten nested blockquotes (WeChat can't render them)
10. Add paragraph/image spacing
11. Convert `<a>` links to `text [url]` format
12. Convert `<ol>` → numbered `<p>` paragraphs, `<ul>` → bullet `<p>` paragraphs

The three whitelists are module-level constants: `WECHAT_SAFE_TAGS`, `WECHAT_SAFE_ATTRS`, `WECHAT_SAFE_STYLES`.

### 4. Unicode title normalization
Before sending to WeChat, titles go through character replacement: curly quotes → straight quotes, em dashes → hyphens, fullwidth space → regular space. This avoids WeChat error code 45003.

### 5. Markdown → Ghost Lexical converter (`md_to_ghost_lexical`)
Converts Markdown to Ghost's Lexical JSON format (not Ghost's older mobiledoc). The conversion is lossy by design — it produces Lexical nodes that Ghost's editor can open and edit. Tables become `html` cards (inline HTML). Fenced code blocks, headings (h1-h6), horizontal rules, ordered/unordered lists, and inline formatting (bold, italic, code, links) are all supported.

### 6. CLI entry point
Simple `sys.argv` parsing at the bottom. Three commands: `list`, `publish`, and sync (by article ID or `--preview`).

## Key design decisions

- **Single file by design.** No package structure — the tool is meant to be cloned and run directly.
- **Code block protection pattern:** Code blocks are extracted to `__CODE_BLOCK_PLACEHOLDER__N__` tokens before the whitelist filter runs, then restored afterward. This prevents the filter from stripping `<pre>`/`<code>` tags or their content.
- **Author fallback chain:** When publishing, author lookup tries Ghost Content API → hardcoded author IDs for known slugs (`xiaohei`, `guobing`). The hardcoded IDs are Ghost instance-specific.
- **WeChat constraints:** Author field max 8 bytes, digest max 120 bytes, titles must not contain Unicode special characters. These are enforced throughout the sync logic.
