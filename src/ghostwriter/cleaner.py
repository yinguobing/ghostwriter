"""HTML cleaner for WeChat draft compatibility.

WeChat's rich-text editor only supports a limited subset of HTML tags,
attributes, and CSS properties. This module provides a three-level
whitelist filter that strips everything else while preserving text content.

Level 1: Tag whitelist  — strip unknown tags, keep their inner text
Level 2: Attribute whitelist — keep only safe attributes
Level 3: Style whitelist — keep only safe CSS properties
"""

import html.parser
import re
from html import escape as _html_escape


# ── 微信安全标签白名单 ──────────────────────────────────────
WECHAT_SAFE_TAGS = {
    "p", "br", "strong", "em", "b", "i", "u", "a", "img", "span",
    "div", "h2", "h3", "h4", "blockquote", "pre", "code", "ul", "ol", "li",
}
WECHAT_SAFE_ATTRS = {"href", "src", "alt", "title"}
WECHAT_SAFE_STYLES = {
    "color", "font-size", "font-weight", "font-family", "text-align",
    "line-height", "margin", "margin-bottom", "margin-left", "margin-right",
    "padding", "padding-left", "padding-right", "background", "background-color",
    "border", "border-left", "border-bottom", "border-right", "border-collapse",
    "border-radius", "width", "height", "max-width",
    "white-space", "word-break", "overflow", "vertical-align",
    "display",
}


def _filter_style(style_value):
    """Keep only whitelisted CSS properties from a style attribute value."""
    props = []
    for decl in style_value.split(";"):
        decl = decl.strip()
        if not decl or ":" not in decl:
            continue
        prop, val = decl.split(":", 1)
        prop = prop.strip().lower()
        if prop in WECHAT_SAFE_STYLES:
            props.append(f"{prop}: {val.strip()}")
    return "; ".join(props)


class _WeChatCleaner(html.parser.HTMLParser):
    """HTMLParser-based three-level whitelist filter.

    Strips non-whitelisted tags (preserving inner text), filters
    attributes and inline styles to only what WeChat supports.
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self._skip_depth = 0

    # HTML void elements (self-closing, no end tag)
    _VOID_ELEMENTS = frozenset((
        "area", "base", "br", "col", "embed", "hr", "img",
        "input", "link", "meta", "param", "source", "track", "wbr",
    ))

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self._skip_depth > 0:
            if tag not in self._VOID_ELEMENTS:
                self._skip_depth += 1
            return
        if tag not in WECHAT_SAFE_TAGS:
            self._skip_depth = 1
            return
        keep = []
        for name, val in attrs:
            nl = name.lower().strip()
            if nl in WECHAT_SAFE_ATTRS:
                keep.append(f'{name}="{_html_escape(val)}"')
            elif nl == "style" and val.strip():
                filtered = _filter_style(val)
                if filtered:
                    keep.append(f'style="{_html_escape(filtered)}"')
        attr_str = " " + " ".join(keep) if keep else ""
        self.out.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in WECHAT_SAFE_TAGS:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        self.out.append(data)

    def handle_entityref(self, name):
        self.out.append(f"&{name};")

    def handle_charref(self, name):
        self.out.append(f"&#{name};")

    def handle_comment(self, data):
        pass  # comments removed entirely


def clean_html_for_wechat(html):
    """Apply three-level whitelist filtering for WeChat compatibility.

    1. Remove <script>/<style> tags and their content
    2. Replace data-src with src
    3. Run the tag/attribute/style whitelist filter
    """
    # Remove script/style
    html = re.sub(
        r'<(script|style)[^>]*>.*?</\1>', '', html,
        flags=re.DOTALL | re.I
    )
    # Replace data-src with src (before parser, to avoid attr filtering)
    html = re.sub(r'\s*data-src="([^"]+)"', r' src="\1"', html)
    # Three-level filter
    cleaner = _WeChatCleaner()
    cleaner.feed(html)
    return "".join(cleaner.out)


def clean_ghost_comments(html):
    """Remove Ghost-specific HTML comments (<!--kg-card-*--> etc.)."""
    return re.sub(r'<!--[\s\S]*?-->', '', html)
