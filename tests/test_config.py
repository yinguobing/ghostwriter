"""Tests for configuration loading."""

import json
import os
import tempfile

import pytest

from ghostwriter.config import load_config


def test_load_config_from_cwd(monkeypatch):
    """load_config finds config.json in current working directory."""
    # Save original cwd to restore before temp dir cleanup (avoids
    # PermissionError on Windows when cwd is inside the temp dir).
    original_cwd = os.getcwd()
    tmpdir = tempfile.mkdtemp()
    try:
        config_path = os.path.join(tmpdir, "config.json")
        config_data = {
            "wechat": {"appid": "test_id", "secret": "test_secret"},
            "ghost": {
                "api_url": "https://example.com",
                "admin_key_id": "key1",
                "admin_key": "abcdef",
            },
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        monkeypatch.chdir(tmpdir)
        monkeypatch.setattr(
            "ghostwriter.config.os.path.expanduser",
            lambda p: os.path.join(tmpdir, "nonexistent"),
        )

        result = load_config()
        assert result["wechat"]["appid"] == "test_id"
        assert result["ghost"]["api_url"] == "https://example.com"
    finally:
        os.chdir(original_cwd)
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
