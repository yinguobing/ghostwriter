"""HTML processing pipeline for Ghost → WeChat conversion.

Transforms Ghost article HTML into WeChat-draft-compatible HTML through
a fixed sequence of transformations. Order matters — many steps must
run before or after the whitelist filter to work correctly.
"""

import re
from html import escape as _html_escape

from .cleaner import clean_ghost_comments, clean_html_for_wechat

# Code block placeholder marker
_CODE_PLACEHOLDER = "__CODE_BLOCK_PLACEHOLDER__"
_code_blocks_cache = []


# ── Code block protection ────────────────────────────────────

def convert_code_blocks(html):
    """Extract <pre><code> blocks to placeholders to protect from the whitelist filter.

    Returns HTML with placeholders inserted. Call restore_code_blocks()
    after filtering to restore the code blocks with WeChat-safe styling.
    """
    global _code_blocks_cache
    _code_blocks_cache = []

    def _extract(match):
        full = match.group(0)
        lang_match = re.search(r'class="language-(\w+)"', full)
        lang = lang_match.group(1) if lang_match else ""
        code_match = re.search(
            r'<code[^>]*>(.*?)</code>', full, re.DOTALL
        )
        code_content = code_match.group(1) if code_match else match.group(1)
        idx = len(_code_blocks_cache)
        _code_blocks_cache.append({"lang": lang, "content": code_content})
        return f"{_CODE_PLACEHOLDER}{idx}{_CODE_PLACEHOLDER}"

    html = re.sub(
        r'<pre><code[^>]*>(.*?)</code></pre>', _extract, html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'<pre>(.*?)</pre>', _extract, html,
        flags=re.DOTALL,
    )
    return html


def restore_code_blocks(html):
    """Restore code block placeholders with WeChat-safe styled HTML."""
    global _code_blocks_cache

    def _restore(match):
        idx = int(match.group(1))
        block = _code_blocks_cache[idx]
        content = block["content"]
        lang = block["lang"]

        lang_html = ""
        if lang:
            lang_html = (
                f'<div style="font-size: 12px; color: #999; '
                f'margin-bottom: 6px; line-height: 1.4;">'
                f'{_html_escape(lang)}'
                f'</div>'
            )

        # WeChat doesn't reliably support white-space: pre-wrap,
        # so we explicitly convert newlines to <br>
        content_with_br = content.replace('\n', '<br>')

        return (
            '<pre style="background: #f5f5f5; padding: 12px 16px; '
            'border-radius: 4px; font-size: 14px; line-height: 1.7; '
            'overflow-x: auto; margin-bottom: 16px; '
            'word-break: break-all; border: 1px solid #e0e0e0;">'
            f'{lang_html}'
            '<code style="font-family: Consolas, Monaco, \'Courier New\', '
            'monospace; color: #333;">'
            f'{content_with_br}'
            '</code></pre>'
        )

    return re.sub(
        rf'{_CODE_PLACEHOLDER}(\d+){_CODE_PLACEHOLDER}',
        _restore,
        html,
    )


# ── Element transformers ─────────────────────────────────────

def convert_hr(html):
    """Convert <hr> to a styled divider <div>."""
    return re.sub(
        r'<hr[^>]*>',
        r'<div style="border-top: 1px solid #ddd; margin: 24px 0;"></div>',
        html,
    )


def flatten_nested_blockquotes(html):
    """Flatten nested <blockquote> tags (WeChat doesn't handle them)."""
    while "<blockquote><blockquote>" in html:
        html = html.replace("<blockquote><blockquote>", "<blockquote>")
    while "</blockquote></blockquote>" in html:
        html = html.replace("</blockquote></blockquote>", "</blockquote>")
    return html


def convert_table_to_div(html):
    """Convert <table> to WeChat-compatible inline-block layout.

    WeChat drafts don't support <table>, <tr>, <td>, flex, or
    table-cell display. This uses <span> + display:inline-block +
    percentage widths to simulate a table. Must run before the
    whitelist filter since <table> is not in WECHAT_SAFE_TAGS.
    """
    def _convert(match):
        table_html = match.group(0)
        rows = re.findall(
            r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL
        )
        if not rows:
            return ''

        max_cols = max(
            len(re.findall(
                r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL
            ))
            for row in rows
        )
        if max_cols == 0:
            return ''

        cell_width_pct = f"{100.0 / max_cols:.2f}%"

        parts = []
        parts.append(
            '<div style="margin-bottom: 16px; border-top: 1px solid #e0e0e0; '
            'border-bottom: 1px solid #e0e0e0; overflow: hidden; '
            'font-size: 14px; line-height: 1.6;">'
        )

        for row_idx, row in enumerate(rows):
            cells = re.findall(
                r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL
            )
            if not cells:
                continue

            is_header = '<th' in row or row_idx == 0
            bg = '#f5f5f5' if is_header else 'transparent'
            fw = 'bold' if is_header else 'normal'
            border_bottom = (
                '1px solid #e0e0e0' if row_idx < len(rows) - 1
                else 'none'
            )

            row_cells = []
            for ci, cell in enumerate(cells):
                cell_content = cell.strip()
                row_cells.append(
                    f'<span style="display:inline-block; width:{cell_width_pct}; '
                    f'padding: 8px 12px; font-weight: {fw}; '
                    f'box-sizing:border-box; vertical-align:middle; '
                    f'color: #333;">{cell_content}</span>'
                )

            parts.append(
                f'<p style="margin:0; padding:0; line-height:1.6; '
                f'overflow:hidden; background:{bg}; border-bottom:{border_bottom}">'
                f'{"".join(row_cells)}'
                f'</p>'
            )

        parts.append('</div>')
        return '\n'.join(parts)

    return re.sub(
        r'<table[^>]*>.*?</table>', _convert, html,
        flags=re.DOTALL,
    )


def apply_wechat_styles(html):
    """Add default WeChat-compatible styles to various elements.

    Handles: h2/h3/h4 font sizes, inline code background, blockquote
    border, and code font styles. Only applies to elements without
    existing style attributes.
    """
    # h2
    html = re.sub(
        r'<h2(\b(?!\s+[^>]*style=)[^>]*)>',
        r'<h2 style="font-size: 20px; font-weight: bold; '
        r'margin-bottom: 12px; margin-top: 24px;"\1>',
        html,
    )
    # h3
    html = re.sub(
        r'<h3(\b(?!\s+[^>]*style=)[^>]*)>',
        r'<h3 style="font-size: 18px; font-weight: bold; '
        r'margin-bottom: 10px; margin-top: 20px;"\1>',
        html,
    )
    # h4
    html = re.sub(
        r'<h4(\b(?!\s+[^>]*style=)[^>]*)>',
        r'<h4 style="font-size: 16px; font-weight: bold; '
        r'margin-bottom: 8px; margin-top: 16px;"\1>',
        html,
    )
    # inline code
    html = re.sub(
        r'<code(\b(?!\s+[^>]*style=)[^>]*)>',
        r'<code style="background: #f0f0f0; padding: 2px 4px; '
        r'border-radius: 3px; font-size: 14px; '
        r'font-family: Consolas, Monaco, \'Courier New\', monospace; '
        r'color: #333;"\1>',
        html,
    )
    # blockquote
    html = re.sub(
        r'<blockquote(\b(?!\s+[^>]*style=)[^>]*)>',
        r'<blockquote style="border-left: 4px solid #ddd; '
        r'padding: 8px 16px; margin: 16px 0; '
        r'color: #666; background: #fafafa;"\1>',
        html,
    )
    return html


def extract_images(html):
    """Return all image src URLs found in the HTML."""
    return re.findall(r'<img[^>]+src="([^"]+)"', html)


def replace_images(html, image_map):
    """Replace original image URLs with WeChat CDN URLs."""
    for old_url, wechat_url in image_map.items():
        html = html.replace(f'src="{old_url}"', f'src="{wechat_url}"')
    return html


def convert_links(html):
    """Convert <a href="url">text</a> to text [url] format.

    WeChat drafts may strip or lose styling on <a> tags.
    Converting to plain text + URL is more reliable.
    """
    def _replace_link(match):
        href = match.group(1)
        text = match.group(2).strip()
        if href == text or href.endswith(text):
            return text
        return f'{text} [{href}]'

    html = re.sub(
        r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        _replace_link, html, flags=re.DOTALL,
    )
    html = re.sub(
        r"<a\s+[^>]*href='([^']+)'[^>]*>(.*?)</a>",
        _replace_link, html, flags=re.DOTALL,
    )
    return html


def convert_ordered_list(html):
    """Convert <ol> to <p> + number prefix paragraphs.

    WeChat doesn't render <ol> list-style — convert to explicit numbering.
    """
    def _convert(match):
        items = re.findall(
            r'<li>(.*?)</li>', match.group(0), re.DOTALL
        )
        lines = []
        for i, item in enumerate(items, 1):
            item = item.strip()
            lines.append(
                f'<p style="margin-bottom: 8px; padding-left: 16px;">'
                f'{i}. {item}</p>'
            )
        return '\n'.join(lines)

    return re.sub(r'<ol>.*?</ol>', _convert, html, flags=re.DOTALL)


def convert_unordered_list(html):
    """Convert <ul> to <p> + bullet prefix paragraphs.

    WeChat doesn't render <ul> list-style — convert to explicit bullets.
    """
    def _convert(match):
        items = re.findall(
            r'<li>(.*?)</li>', match.group(0), re.DOTALL
        )
        lines = []
        for item in items:
            item = item.strip()
            lines.append(
                f'<p style="margin-bottom: 8px; padding-left: 16px;">'
                f'• {item}</p>'
            )
        return '\n'.join(lines)

    return re.sub(r'<ul>.*?</ul>', _convert, html, flags=re.DOTALL)


# ── Main pipeline ────────────────────────────────────────────

def process_html(html_content, image_map):
    """Full HTML processing pipeline: Ghost HTML → WeChat-compatible HTML.

    Pipeline stages (order is critical):
     1. Replace image URLs with WeChat CDN URLs
     2. Remove Ghost-specific HTML comments (<!--kg-card-*-->)
     3. Convert <hr> to styled <div> (before whitelist filter)
     4. Convert <table> to inline-block layout (before whitelist filter)
     5. Protect code blocks with placeholders
     6. Three-level whitelist filter (tags → attrs → styles)
     7. Restore code blocks with WeChat-safe styling
     8. Apply default styles (headings, code, blockquote)
     9. Flatten nested blockquotes
    10. Add paragraph spacing
    11. Add image spacing
    12. Convert links to text [url] format
    13. Convert ordered lists to numbered <p>
    14. Convert unordered lists to bulleted <p>

    Returns HTML suitable for WeChat draft creation.
    """
    # 1. Replace image URLs
    html = replace_images(html_content, image_map)

    # 2. Remove Ghost comments
    html = clean_ghost_comments(html)

    # 3. Convert <hr> (before whitelist — <hr> not in safe tags)
    html = convert_hr(html)

    # 4. Convert <table> (before whitelist — <table> not in safe tags)
    html = convert_table_to_div(html)

    # 5. Protect code blocks
    html = convert_code_blocks(html)

    # 6. Three-level whitelist filter
    html = clean_html_for_wechat(html)

    # 7. Restore code blocks
    html = restore_code_blocks(html)

    # 8. Default styles
    html = apply_wechat_styles(html)

    # 9. Flatten nested blockquotes
    html = flatten_nested_blockquotes(html)

    # 10. Paragraph spacing
    html = re.sub(
        r'<p\b(?!\s+[^>]*style=)([^>]*)>',
        r'<p style="margin-bottom: 16px;">', html,
    )

    # 11. Image spacing
    html = re.sub(
        r'<img([^>]*)>',
        r'<img style="margin-bottom: 16px;"\1>', html,
    )

    # 12. Links → text [url]
    html = convert_links(html)

    # 13. Ordered lists → numbered <p>
    html = convert_ordered_list(html)

    # 14. Unordered lists → bullet <p>
    html = convert_unordered_list(html)

    return html
