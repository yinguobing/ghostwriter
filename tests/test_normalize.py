"""Tests for Unicode title normalization."""

import pytest

from ghostwriter.normalize import normalize_title


def test_curly_double_quotes():
    assert normalize_title('He said “hello”') == 'He said "hello"'


def test_curly_single_quotes():
    # ‘ (left) and ’ (right) both map to straight '
    assert normalize_title("It‘s a test’") == "It's a test'"


def test_em_dash():
    assert normalize_title("foo—bar") == "foo-bar"


def test_en_dash():
    assert normalize_title("foo–bar") == "foo-bar"


def test_fullwidth_space():
    assert normalize_title("hello　world") == "hello world"


def test_mixed_characters():
    result = normalize_title(
        '“Title” — subtitle　with‘quotes’'
    )
    assert result == '"Title" - subtitle with\'quotes\''


def test_no_special_chars_is_noop():
    assert normalize_title("Hello World") == "Hello World"


def test_empty_string():
    assert normalize_title("") == ""
