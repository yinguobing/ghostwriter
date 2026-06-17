"""Markdown to Ghost Lexical JSON converter.

Converts Markdown text to Ghost's Lexical editor format (JSON). The output
can be posted directly to the Ghost Admin API and is editable in Ghost's
editor afterward.

Supported Markdown:
  - Headings (h1-h6)
  - Paragraphs, bold (**), italic (*), inline code (`)
  - Links [text](url)
  - Fenced code blocks with language tags
  - Tables (converted to html-card nodes)
  - Ordered and unordered lists
  - Horizontal rules (---, ***, ___)
"""

import json
import re

# Lexical format constants
_LEXICAL_FORMATS = {1: "bold", 2: "italic", 8: "code"}


def _lex_text(text, fmt=0):
    return {
        "type": "extended-text", "text": text, "format": fmt,
        "version": 1, "detail": 0, "style": "", "mode": "normal",
    }


def _lex_link(text, url):
    return {
        "type": "link", "url": url,
        "children": [_lex_text(text)],
        "format": 0, "version": 1, "detail": 0, "style": "",
        "mode": "normal", "rel": None, "target": None, "title": None,
    }


def _lex_para(children):
    return {
        "type": "paragraph", "children": children,
        "format": "", "indent": 0, "version": 1, "direction": "ltr",
    }


def _lex_heading(tag, children):
    return {
        "type": "extended-heading", "tag": tag, "children": children,
        "format": "", "indent": 0, "version": 1, "direction": "ltr",
    }


def _lex_codeblock(code, lang=""):
    return {
        "type": "codeblock", "code": code, "language": lang,
        "caption": "", "version": 1,
    }


def _lex_hr():
    return {"type": "horizontalrule", "version": 1}


def _lex_listitem(children):
    return {
        "type": "listitem", "children": children,
        "format": "", "indent": 0, "value": 1, "version": 1,
        "direction": "ltr",
    }


def _lex_list(items, ordered=False):
    return {
        "type": "list",
        "listType": "number" if ordered else "bullet",
        "start": 1, "children": items,
        "format": "", "indent": 0, "version": 1, "direction": "ltr",
    }


def _lex_html_card(html):
    return {"type": "html", "html": html, "version": 1}


def _extract_fenced_codes(md_text):
    """Extract fenced code blocks to placeholders.

    Returns (processed_text, code_map) where code_map maps placeholder
    keys to {"lang": ..., "code": ...} dicts.
    """
    code_map = {}
    idx = 0

    def _save(m):
        nonlocal idx
        lang = m.group(1) or ""
        code = m.group(2).rstrip("\n")
        code_map[f"__CB_{idx}__"] = {"lang": lang, "code": code}
        r = f"\n__CB_{idx}__\n"
        idx += 1
        return r

    text = re.sub(
        r'```(\w*)\n(.*?)```', _save, md_text,
        flags=re.DOTALL,
    )
    return text, code_map


def _parse_inline(text):
    """Parse inline formatting: **bold**, `code`, *italic*, [links](url)."""
    children = []
    last = 0
    pattern = (
        r'\*\*(.+?)\*\*|'
        r'(`[^`]+`)|'
        r'(\*(.+?)\*)|'
        r'(\[([^\]]+)\]\(([^)]+)\))'
    )
    for m in re.finditer(pattern, text):
        s, e = m.start(), m.end()
        if s > last:
            children.append(_lex_text(text[last:s]))
        if m.group(1):       # **bold**
            children.append(_lex_text(m.group(1), 1))
        elif m.group(2):     # `code`
            children.append(_lex_text(m.group(2).strip('`'), 8))
        elif m.group(3):     # *italic*
            children.append(_lex_text(m.group(4), 2))
        elif m.group(5):     # [text](url)
            children.append(_lex_link(m.group(6), m.group(7)))
        last = e
    if last < len(text):
        children.append(_lex_text(text[last:]))
    return children if children else [_lex_text("")]


def _table_to_html(raw):
    """Convert a Markdown table to an HTML <table> string."""
    rows = [
        r for r in raw.split('\n')
        if r.strip() and not re.match(r'^\|[\s:-]+\|', r)
    ]
    parts = ['<table>']
    for i, row in enumerate(rows):
        tag = 'th' if i == 0 else 'td'
        cells = [c.strip() for c in row.split('|')[1:-1]]
        parts.append('<tr>')
        for cell in cells:
            ch = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', cell)
            ch = re.sub(r'`([^`]+)`', r'<code>\1</code>', ch)
            parts.append(f'<{tag}>{ch}</{tag}>')
        parts.append('</tr>')
    parts.append('</table>')
    return '\n'.join(parts)


def md_to_ghost_lexical(md_text):
    """Convert Markdown text to Ghost Lexical JSON.

    Supported Markdown elements:
      - Headings (h1-h6 via # prefix)
      - Paragraphs
      - Fenced code blocks (```lang ... ```)
      - Tables (pipe syntax)
      - Ordered and unordered lists
      - Horizontal rules (---, ***, ___)
      - Inline: bold, italic, code, links

    Returns:
        (title: str, lexical_json: str) — title extracted from the first
        h1 heading (or empty), and a JSON string of the Lexical document.
    """
    lines = md_text.split('\n')
    title = ""
    if lines and lines[0].startswith('# '):
        title = lines[0][2:].strip()
        lines = lines[1:]
    content = '\n'.join(lines)

    content, code_map = _extract_fenced_codes(content)
    raw_blocks = re.split(r'\n{2,}', content)

    children = []
    for raw in raw_blocks:
        raw = raw.strip()
        if not raw:
            continue

        cm = re.match(r'^__CB_(\d+)__$', raw)
        if cm:
            cb = code_map.get(raw)
            if cb:
                children.append(_lex_codeblock(cb["code"], cb["lang"]))
            continue

        if re.match(r'^[-*_]{3,}\s*$', raw):
            children.append(_lex_hr())
            continue

        hm = re.match(r'^(#{1,6})\s+(.+)$', raw)
        if hm:
            children.append(
                _lex_heading(f"h{len(hm.group(1))}",
                             _parse_inline(hm.group(2)))
            )
            continue

        if '|' in raw and raw.count('|') >= 4:
            children.append(_lex_html_card(_table_to_html(raw)))
            continue

        lines_list = raw.split('\n')
        if all(
            re.match(r'^(\s*[-*+]\s+|\s*\d+[.)]\s+)', l)
            for l in lines_list if l.strip()
        ):
            items, ordered = [], None
            for line in lines_list:
                m = re.match(r'^\s*([-*+]|\d+[.)])\s+(.*)$', line)
                if not m:
                    continue
                marker, content_i = m.group(1), m.group(2)
                is_ordered = (
                    marker.endswith(')') or marker.endswith('.')
                    or marker.isdigit()
                )
                if ordered is None:
                    ordered = bool(
                        is_ordered and marker not in ['-', '*', '+']
                    )
                items.append(
                    _lex_listitem(_parse_inline(content_i.strip()))
                )
            if items:
                children.append(_lex_list(items, ordered or False))
            continue

        children.append(_lex_para(_parse_inline(raw)))

    lexical_tree = {
        "root": {
            "children": children,
            "direction": None,
            "format": "",
            "indent": 0,
            "type": "root",
            "version": 1,
        }
    }
    return title, json.dumps(lexical_tree, ensure_ascii=False)
