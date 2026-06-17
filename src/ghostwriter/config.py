"""Configuration management.

Configuration is read from two sources, in priority order:
1. Environment variables (GHOSTWRITER_GHOST_*, GHOSTWRITER_WECHAT_*)
2. Config file (~/.config/ghostwriter/config.json)

Use `ghostwriter config set <key> <value>` to manage the config file.
"""

import json
import os
import sys
import textwrap

# All required config keys mapped to their env var names.
_REQUIRED_KEYS = {
    "ghost.api_url":      "GHOSTWRITER_GHOST_API_URL",
    "ghost.admin_key_id": "GHOSTWRITER_GHOST_ADMIN_KEY_ID",
    "ghost.admin_key":    "GHOSTWRITER_GHOST_ADMIN_KEY",
    "wechat.appid":       "GHOSTWRITER_WECHAT_APPID",
    "wechat.secret":      "GHOSTWRITER_WECHAT_SECRET",
}

# Keys that should be masked when displayed.
_SECRET_KEYS = {
    "ghost.admin_key_id",
    "ghost.admin_key",
    "wechat.appid",
    "wechat.secret",
}

_CONFIG_DIR = os.path.expanduser("~/.config/ghostwriter")
_CONFIG_PATH = os.path.join(_CONFIG_DIR, "config.json")


def _nested_get(d, key_path):
    """Get a nested dict value by dot-separated key path.

    Example: _nested_get(d, "ghost.api_url") → d["ghost"]["api_url"]
    """
    parts = key_path.split(".")
    for part in parts:
        if not isinstance(d, dict) or part not in d:
            return None
        d = d[part]
    return d


def _nested_set(d, key_path, value):
    """Set a nested dict value by dot-separated key path.

    Example: _nested_set(d, "ghost.api_url", "https://...")
    """
    parts = key_path.split(".")
    for part in parts[:-1]:
        if part not in d:
            d[part] = {}
        d = d[part]
    d[parts[-1]] = value


def _load_from_env():
    """Try to build a config dict from environment variables.

    Returns a config dict if ALL required env vars are set, otherwise None.
    """
    config = {"ghost": {}, "wechat": {}}
    for key_path, env_var in _REQUIRED_KEYS.items():
        value = os.environ.get(env_var)
        if not value:
            return None
        _nested_set(config, key_path, value)
    return config


def _load_from_file():
    """Load config from the JSON file.

    Returns the parsed dict, or None if the file doesn't exist or is invalid.
    """
    if not os.path.exists(_CONFIG_PATH):
        return None
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _validate_config(config, source):
    """Check that all required keys are present.

    Prints a helpful error and exits if any keys are missing.
    """
    missing = []
    for key_path, env_var in _REQUIRED_KEYS.items():
        if not _nested_get(config, key_path):
            missing.append((key_path, env_var))

    if not missing:
        return

    lines = [f"[!] 配置不完整 ({source})，缺少以下字段:"]
    for key_path, env_var in missing:
        lines.append(f"    {key_path}  (env: {env_var})")
    lines.append("")
    lines.append("设置方法:")
    lines.append("  # 环境变量（推荐用于 CI/Docker）:")
    for _, env_var in missing:
        lines.append(f"  export {env_var}=<value>")
    lines.append("")
    lines.append("  # 或使用 CLI 写入配置文件:")
    for key_path, _ in missing:
        lines.append(f"  ghostwriter config set {key_path} <value>")
    lines.append("")
    lines.append(f"  # 配置文件位置: {_CONFIG_PATH}")

    print("\n".join(lines))
    sys.exit(1)


def load_config():
    """Load configuration, preferring env vars over the config file.

    Returns a dict with shape:
        {"ghost": {"api_url", "admin_key_id", "admin_key"},
         "wechat": {"appid", "secret"}}

    Exits with an error message if required keys are missing.
    """
    config = _load_from_env()
    if config is not None:
        return config

    config = _load_from_file()
    if config is not None:
        _validate_config(config, f"文件 {_CONFIG_PATH}")
        return config

    # No config source available
    print(f"[!] 未找到配置")
    print(f"")
    print(f"配置文件路径: {_CONFIG_PATH}")
    print(f"")
    print(f"请选择一种方式配置:")
    print(f"")
    print(f"  方式 1 — 环境变量（适合 CI/Docker）:")
    for _, env_var in _REQUIRED_KEYS.items():
        print(f"    export {env_var}=<value>")
    print(f"")
    print(f"  方式 2 — 配置文件（适合本地使用）:")
    msg = "  ghostwriter config set {key} <value>"
    print(f"    {msg.format(key='ghost.api_url')}")
    print(f"    {msg.format(key='ghost.admin_key_id')}")
    print(f"    {msg.format(key='ghost.admin_key')}")
    print(f"    {msg.format(key='wechat.appid')}")
    print(f"    {msg.format(key='wechat.secret')}")
    sys.exit(1)


# ── CLI config management ──────────────────────────────────────

def config_path():
    """Return the path to the config file."""
    return _CONFIG_PATH


def show_config():
    """Print the current effective configuration.

    Secrets (admin_key, appid, secret) are masked.
    """
    print(f"配置文件: {_CONFIG_PATH}")

    # Show env vars if they're set (primary source)
    env_config = _load_from_env()
    if env_config:
        print("来源: 环境变量")
        source = "env"
        config = env_config
    else:
        config = _load_from_file()
        if config:
            print("来源: 配置文件")
            source = "file"
        else:
            print("来源: (无)")
            print("")
            print("未设置任何配置。使用以下命令开始:")
            print("  ghostwriter config set ghost.api_url <url>")
            return

    print("")
    for key_path in _REQUIRED_KEYS:
        value = _nested_get(config, key_path)
        if value and key_path in _SECRET_KEYS:
            # Mask secret values: show first 4 + last 4 chars
            if len(value) > 8:
                value = value[:4] + "***" + value[-4:]
            else:
                value = "***"
        elif not value:
            value = "(未设置)"
        print(f"  {key_path} = {value}")

    # Show optional authors map
    authors = config.get("authors", {})
    if authors:
        print("")
        for slug, author_id in authors.items():
            print(f"  authors.{slug} = {author_id}")


def set_config_value(key_path, value):
    """Write a single key to the config file.

    Creates the config directory and file if they don't exist.
    Preserves any existing keys in the file.
    """
    if key_path not in _REQUIRED_KEYS and not key_path.startswith("authors."):
        valid = "\n".join(f"  {k}" for k in _REQUIRED_KEYS)
        valid += "\n  authors.<slug>     (可选) 作者 slug → ID 映射"
        print(f"[!] 未知的配置键: {key_path}")
        print(f"有效的键:\n{valid}")
        sys.exit(1)

    # Load existing or start fresh
    config = _load_from_file()
    if config is None:
        config = {"ghost": {}, "wechat": {}}

    _nested_set(config, key_path, value)

    # Write back
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    display = value
    if key_path in _SECRET_KEYS and len(value) > 8:
        display = value[:4] + "***" + value[-4:]
    print(f"[+] {key_path} = {display}")
