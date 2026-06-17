"""Tests for the Markdown → Ghost Lexical converter."""

import json

import pytest

from ghostwriter.lexical import md_to_ghost_lexical


class TestMdToGhostLexical:
    def test_title_extraction(self):
        md = "# My Title\n\nSome content."
        title, lex_json = md_to_ghost_lexical(md)
        assert title == "My Title"

    def test_no_title(self):
        md = "Just a paragraph."
        title, lex_json = md_to_ghost_lexical(md)
        assert title == ""

    def test_paragraph(self):
        md = "A simple paragraph."
        title, lex_json = md_to_ghost_lexical(md)
        data = json.loads(lex_json)
        children = data["root"]["children"]
        assert len(children) == 1
        assert children[0]["type"] == "paragraph"

    def test_heading(self):
        md = "## Section\n\nContent."
        title, lex_json = md_to_ghost_lexical(md)
        data = json.loads(lex_json)
        children = data["root"]["children"]
        assert children[0]["type"] == "extended-heading"
        assert children[0]["tag"] == "h2"

    def test_horizontal_rule(self):
        md = "---\n\nparagraph"
        title, lex_json = md_to_ghost_lexical(md)
        data = json.loads(lex_json)
        children = data["root"]["children"]
        assert children[0]["type"] == "horizontalrule"

    def test_bold_text(self):
        md = "Hello **bold** world."
        title, lex_json = md_to_ghost_lexical(md)
        data = json.loads(lex_json)
        para = data["root"]["children"][0]
        texts = [c for c in para["children"] if c["type"] == "extended-text"]
        assert any(c["format"] == 1 for c in texts)

    def test_inline_code(self):
        md = "Use `print()` function."
        title, lex_json = md_to_ghost_lexical(md)
        data = json.loads(lex_json)
        para = data["root"]["children"][0]
        texts = [c for c in para["children"] if c["type"] == "extended-text"]
        assert any(c["format"] == 8 for c in texts)

    def test_link(self):
        md = "Visit [example](https://example.com)."
        title, lex_json = md_to_ghost_lexical(md)
        data = json.loads(lex_json)
        para = data["root"]["children"][0]
        links = [c for c in para["children"] if c["type"] == "link"]
        assert len(links) == 1
        assert links[0]["url"] == "https://example.com"

    def test_fenced_code_block(self):
        md = "```python\nprint('hello')\n```"
        title, lex_json = md_to_ghost_lexical(md)
        data = json.loads(lex_json)
        children = data["root"]["children"]
        assert children[0]["type"] == "codeblock"
        assert children[0]["language"] == "python"
        assert "print('hello')" in children[0]["code"]

    def test_unordered_list(self):
        md = "- item 1\n- item 2"
        title, lex_json = md_to_ghost_lexical(md)
        data = json.loads(lex_json)
        children = data["root"]["children"]
        assert children[0]["type"] == "list"
        assert children[0]["listType"] == "bullet"

    def test_ordered_list(self):
        md = "1. first\n2. second"
        title, lex_json = md_to_ghost_lexical(md)
        data = json.loads(lex_json)
        children = data["root"]["children"]
        assert children[0]["type"] == "list"
        assert children[0]["listType"] == "number"

    def test_table_as_html_card(self):
        md = (
            "| Name | Age |\n"
            "|------|-----|\n"
            "| Alice| 30  |\n"
        )
        title, lex_json = md_to_ghost_lexical(md)
        data = json.loads(lex_json)
        children = data["root"]["children"]
        assert children[0]["type"] == "html"
        assert "Alice" in children[0]["html"]

    def test_valid_json_output(self):
        md = "# Title\n\nContent."
        title, lex_json = md_to_ghost_lexical(md)
        data = json.loads(lex_json)
        assert "root" in data
        assert "children" in data["root"]

    def test_italic_text(self):
        md = "This is *italic* word."
        title, lex_json = md_to_ghost_lexical(md)
        data = json.loads(lex_json)
        para = data["root"]["children"][0]
        texts = [c for c in para["children"] if c["type"] == "extended-text"]
        assert any(c["format"] == 2 for c in texts)
