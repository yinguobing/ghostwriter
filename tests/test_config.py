"""Tests for configuration loading and management."""

import json
import os
import tempfile

import pytest

from ghostwriter.config import (
    _nested_get,
    _nested_set,
    load_config,
    set_config_value,
    show_config,
    config_path,
    _CONFIG_DIR,
    _CONFIG_PATH,
)


class TestNestedGet:
    def test_simple_key(self):
        d = {"ghost": {"api_url": "https://example.com"}}
        assert _nested_get(d, "ghost.api_url") == "https://example.com"

    def test_missing_key(self):
        d = {"ghost": {}}
        assert _nested_get(d, "ghost.api_url") is None

    def test_missing_section(self):
        d = {}
        assert _nested_get(d, "ghost.api_url") is None

    def test_non_dict_intermediate(self):
        d = {"ghost": "not_a_dict"}
        assert _nested_get(d, "ghost.api_url") is None


class TestNestedSet:
    def test_sets_nested_value(self):
        d = {"ghost": {}, "wechat": {}}
        _nested_set(d, "ghost.api_url", "https://example.com")
        assert d["ghost"]["api_url"] == "https://example.com"

    def test_creates_intermediate_dicts(self):
        d = {}
        _nested_set(d, "ghost.api_url", "https://example.com")
        assert d["ghost"]["api_url"] == "https://example.com"


class TestLoadConfigFromEnv:
    def test_all_env_vars_set(self, monkeypatch):
        monkeypatch.setenv("GHOSTWRITER_GHOST_API_URL", "https://example.com")
        monkeypatch.setenv("GHOSTWRITER_GHOST_ADMIN_KEY_ID", "key123")
        monkeypatch.setenv("GHOSTWRITER_GHOST_ADMIN_KEY", "secret123")
        monkeypatch.setenv("GHOSTWRITER_WECHAT_APPID", "wx123")
        monkeypatch.setenv("GHOSTWRITER_WECHAT_SECRET", "wxsecret")

        config = load_config()
        assert config["ghost"]["api_url"] == "https://example.com"
        assert config["ghost"]["admin_key_id"] == "key123"
        assert config["wechat"]["appid"] == "wx123"

    def test_partial_env_vars_falls_back_to_file(self, monkeypatch, tmp_path):
        # Only set one env var — should fall through to file
        monkeypatch.setenv("GHOSTWRITER_GHOST_API_URL", "https://env.example.com")
        # Ensure no other env vars are set
        for v in ["GHOSTWRITER_GHOST_ADMIN_KEY_ID", "GHOSTWRITER_GHOST_ADMIN_KEY",
                   "GHOSTWRITER_WECHAT_APPID", "GHOSTWRITER_WECHAT_SECRET"]:
            monkeypatch.delenv(v, raising=False)

        # Create a config file
        config_dir = tmp_path / "ghostwriter"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        file_config = {
            "ghost": {
                "api_url": "https://file.example.com",
                "admin_key_id": "file_key_id",
                "admin_key": "file_key_secret",
            },
            "wechat": {
                "appid": "file_appid",
                "secret": "file_secret",
            },
        }
        config_file.write_text(json.dumps(file_config))
        monkeypatch.setattr("ghostwriter.config._CONFIG_PATH", str(config_file))

        config = load_config()
        # Env is partial, should use file fallback
        assert config["ghost"]["api_url"] == "https://file.example.com"


class TestLoadConfigFromFile:
    def test_valid_file_loads(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.json")
            config_data = {
                "ghost": {
                    "api_url": "https://example.com",
                    "admin_key_id": "key1",
                    "admin_key": "secret",
                },
                "wechat": {
                    "appid": "wx1",
                    "secret": "wxsecret",
                },
            }
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f)

            monkeypatch.setattr("ghostwriter.config._CONFIG_PATH", config_file)
            # Remove all env vars
            for v in ["GHOSTWRITER_GHOST_API_URL", "GHOSTWRITER_GHOST_ADMIN_KEY_ID",
                       "GHOSTWRITER_GHOST_ADMIN_KEY", "GHOSTWRITER_WECHAT_APPID",
                       "GHOSTWRITER_WECHAT_SECRET"]:
                monkeypatch.delenv(v, raising=False)

            config = load_config()
            assert config["ghost"]["api_url"] == "https://example.com"


class TestConfigValidation:
    def test_missing_ghost_key_exits(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.json")
            config_data = {
                "ghost": {
                    "api_url": "https://example.com",
                    # missing admin_key_id and admin_key
                },
                "wechat": {
                    "appid": "wx1",
                    "secret": "wxsecret",
                },
            }
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f)

            monkeypatch.setattr("ghostwriter.config._CONFIG_PATH", config_file)
            for v in ["GHOSTWRITER_GHOST_API_URL", "GHOSTWRITER_GHOST_ADMIN_KEY_ID",
                       "GHOSTWRITER_GHOST_ADMIN_KEY", "GHOSTWRITER_WECHAT_APPID",
                       "GHOSTWRITER_WECHAT_SECRET"]:
                monkeypatch.delenv(v, raising=False)

            with pytest.raises(SystemExit):
                load_config()


class TestSetConfigValue:
    def test_set_new_key_creates_file(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.json")
            monkeypatch.setattr("ghostwriter.config._CONFIG_PATH", config_file)
            monkeypatch.setattr("ghostwriter.config._CONFIG_DIR", tmpdir)

            set_config_value("ghost.api_url", "https://example.com")

            assert os.path.exists(config_file)
            with open(config_file) as f:
                data = json.load(f)
            assert data["ghost"]["api_url"] == "https://example.com"

    def test_set_preserves_existing_keys(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.json")
            monkeypatch.setattr("ghostwriter.config._CONFIG_PATH", config_file)
            monkeypatch.setattr("ghostwriter.config._CONFIG_DIR", tmpdir)

            set_config_value("ghost.api_url", "https://example.com")
            set_config_value("ghost.admin_key_id", "key123")

            with open(config_file) as f:
                data = json.load(f)
            assert data["ghost"]["api_url"] == "https://example.com"
            assert data["ghost"]["admin_key_id"] == "key123"

    def test_invalid_key_exits(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.json")
            monkeypatch.setattr("ghostwriter.config._CONFIG_PATH", config_file)
            monkeypatch.setattr("ghostwriter.config._CONFIG_DIR", tmpdir)

            with pytest.raises(SystemExit):
                set_config_value("invalid.key", "value")


class TestConfigPath:
    def test_returns_expanded_path(self):
        path = config_path()
        assert "ghostwriter" in path
        assert path.endswith("config.json")
