"""Tests for the HTML whitelist cleaner."""

import pytest

from ghostwriter.cleaner import (
    WECHAT_SAFE_TAGS,
    WECHAT_SAFE_ATTRS,
    WECHAT_SAFE_STYLES,
    _filter_style,
    clean_html_for_wechat,
    clean_ghost_comments,
)


class TestFilterStyle:
    def test_whitelisted_properties_kept(self):
        result = _filter_style("color: red; font-size: 14px;")
        assert "color: red" in result
        assert "font-size: 14px" in result

    def test_non_whitelisted_properties_stripped(self):
        result = _filter_style("position: absolute; color: red;")
        assert "position" not in result
        assert "color: red" in result

    def test_empty_style(self):
        assert _filter_style("") == ""

    def test_only_non_whitelisted(self):
        result = _filter_style("display-flex: 1; unknown-prop: value;")
        assert result == ""


class TestCleanHtmlForWechat:
    def test_safe_tags_preserved(self):
        html = "<p>Hello</p><br><strong>Bold</strong>"
        result = clean_html_for_wechat(html)
        assert "<p>" in result
        assert "<br>" in result
        assert "<strong>" in result

    def test_unsafe_tags_stripped_text_preserved(self):
        html = "<script>alert(1)</script><p>Keep me</p>"
        result = clean_html_for_wechat(html)
        assert "alert" not in result
        assert "script" not in result
        assert "<p>Keep me</p>" in result

    def test_style_tags_removed(self):
        html = "<style>body { color: red; }</style><p>text</p>"
        result = clean_html_for_wechat(html)
        assert "body" not in result
        assert "color:" not in result
        assert "<p>text</p>" in result

    def test_non_whitelisted_attrs_stripped(self):
        html = '<p class="foo" data-x="1" id="bar">text</p>'
        result = clean_html_for_wechat(html)
        assert "class=" not in result
        assert "data-x" not in result
        assert "id=" not in result

    def test_style_filtering_on_tag(self):
        html = '<p style="color: red; position: absolute;">text</p>'
        result = clean_html_for_wechat(html)
        assert "color: red" in result
        assert "position" not in result

    def test_data_src_converted_to_src(self):
        html = '<img data-src="https://example.com/img.png">'
        result = clean_html_for_wechat(html)
        assert 'src="https://example.com/img.png"' in result
        assert "data-src" not in result

    def test_comments_removed(self):
        html = "<!-- a comment --><p>text</p>"
        result = clean_html_for_wechat(html)
        assert "<!--" not in result

    def test_nested_non_whitelisted_text_preserved(self):
        html = "<foo><bar>nested text</bar></foo>"
        result = clean_html_for_wechat(html)
        assert "nested text" in result
        assert "<foo>" not in result
        assert "<bar>" not in result


class TestCleanGhostComments:
    def test_kg_card_comments_removed(self):
        html = "<!--kg-card-begin: html--><p>text</p><!--kg-card-end: html-->"
        result = clean_ghost_comments(html)
        assert "<!--" not in result
        assert "<p>text</p>" in result

    def test_multiple_comments_removed(self):
        html = "<!-- a --><p>1</p><!-- b --><p>2</p>"
        result = clean_ghost_comments(html)
        assert "<!--" not in result
        assert "<p>1</p>" in result
        assert "<p>2</p>" in result
