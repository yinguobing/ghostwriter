"""Tests for the HTML processing pipeline."""

import pytest

from ghostwriter.pipeline import (
    convert_hr,
    convert_table_to_div,
    convert_code_blocks,
    restore_code_blocks,
    convert_links,
    convert_ordered_list,
    convert_unordered_list,
    flatten_nested_blockquotes,
    replace_images,
    extract_images,
    apply_wechat_styles,
    process_html,
)


class TestConvertHr:
    def test_hr_converted_to_div(self):
        result = convert_hr("<hr>")
        assert "<div" in result
        assert "border-top" in result

    def test_hr_with_attrs_converted(self):
        result = convert_hr('<hr class="foo">')
        assert "<div" in result
        assert "<hr" not in result


class TestFlattenNestedBlockquotes:
    def test_double_nesting_flattened(self):
        html = "<blockquote><blockquote>deep</blockquote></blockquote>"
        result = flatten_nested_blockquotes(html)
        assert result.count("<blockquote>") == 1
        assert result.count("</blockquote>") == 1

    def test_single_blockquote_unchanged(self):
        html = "<blockquote>shallow</blockquote>"
        result = flatten_nested_blockquotes(html)
        assert result == html


class TestCodeBlocks:
    def test_extract_and_restore_roundtrip(self):
        html = '<pre><code class="language-python">print("hello")\nprint("world")</code></pre>'
        extracted = convert_code_blocks(html)
        assert "print" not in extracted  # code content is hidden
        restored = restore_code_blocks(extracted)
        assert "print" in restored
        assert "python" in restored.lower()
        assert '<pre style=' in restored

    def test_pre_without_code_tag(self):
        html = "<pre>plain text</pre>"
        extracted = convert_code_blocks(html)
        assert "plain text" not in extracted
        restored = restore_code_blocks(extracted)
        assert "plain" in restored


class TestConvertLinks:
    def test_link_converted_to_text_url(self):
        html = '<a href="https://example.com">Click here</a>'
        result = convert_links(html)
        assert "Click here [https://example.com]" in result
        assert "<a " not in result

    def test_link_where_text_is_url(self):
        html = '<a href="https://example.com">https://example.com</a>'
        result = convert_links(html)
        assert "[https://example.com]" not in result  # no redundant URL

    def test_single_quote_href(self):
        html = "<a href='https://example.com'>link</a>"
        result = convert_links(html)
        assert "link [https://example.com]" in result


class TestConvertOrderedList:
    def test_ol_converted_to_paragraphs(self):
        html = "<ol><li>First</li><li>Second</li></ol>"
        result = convert_ordered_list(html)
        assert "<ol>" not in result
        assert "1. First" in result
        assert "2. Second" in result
        assert "<p" in result


class TestConvertUnorderedList:
    def test_ul_converted_to_bullet_paragraphs(self):
        html = "<ul><li>Item A</li><li>Item B</li></ul>"
        result = convert_unordered_list(html)
        assert "<ul>" not in result
        assert "• Item A" in result
        assert "• Item B" in result
        assert "<p" in result


class TestExtractImages:
    def test_extracts_src_urls(self):
        html = '<img src="https://example.com/a.png"><img src="https://example.com/b.jpg">'
        urls = extract_images(html)
        assert len(urls) == 2
        assert urls[0] == "https://example.com/a.png"

    def test_no_images_returns_empty(self):
        assert extract_images("<p>text</p>") == []


class TestReplaceImages:
    def test_replaces_urls(self):
        html = '<img src="https://old.com/img.png">'
        image_map = {"https://old.com/img.png": "https://new.com/img.png"}
        result = replace_images(html, image_map)
        assert "https://new.com/img.png" in result
        assert "https://old.com/img.png" not in result


class TestApplyWechatStyles:
    def test_h2_gets_default_style(self):
        result = apply_wechat_styles("<h2>Title</h2>")
        assert "font-size: 20px" in result

    def test_h3_gets_default_style(self):
        result = apply_wechat_styles("<h3>Title</h3>")
        assert "font-size: 18px" in result

    def test_inline_code_gets_background(self):
        result = apply_wechat_styles("<code>var</code>")
        assert "background: #f0f0f0" in result

    def test_blockquote_gets_border(self):
        result = apply_wechat_styles("<blockquote>quote</blockquote>")
        assert "border-left: 4px solid #ddd" in result

    def test_existing_style_not_overwritten(self):
        result = apply_wechat_styles(
            '<h2 style="font-size: 24px;">Custom</h2>'
        )
        assert 'style="font-size: 24px;"' in result


class TestConvertTableToDiv:
    def test_table_converted_to_div(self):
        html = (
            "<table>"
            "<tr><th>Name</th><th>Age</th></tr>"
            "<tr><td>Alice</td><td>30</td></tr>"
            "</table>"
        )
        result = convert_table_to_div(html)
        assert "<table>" not in result
        assert "<div" in result
        assert "Alice" in result
        assert "30" in result


class TestProcessHtml:
    def test_basic_pipeline(self):
        html = "<p>Hello World</p>"
        result = process_html(html, {})
        assert "Hello World" in result
        assert "<p" in result

    def test_pipeline_replaces_images(self):
        html = '<img src="https://old.com/img.png">'
        result = process_html(
            html, {"https://old.com/img.png": "https://new.com/img.png"}
        )
        assert "https://new.com/img.png" in result

    def test_pipeline_removes_ghost_comments(self):
        html = "<!--kg-card-begin--><p>text</p><!--kg-card-end-->"
        result = process_html(html, {})
        assert "<!--" not in result
        assert "text" in result
        assert "<p" in result

    def test_pipeline_converts_links(self):
        html = '<a href="https://example.com">click</a>'
        result = process_html(html, {})
        assert "click [https://example.com]" in result
