"""Configuration loading.

Looks for config.json in these locations (first found wins):
1. Current working directory (./config.json)
2. User config directory (~/.config/ghostwriter/config.json)
3. Package directory (alongside this source file)
"""

import json
import os
import sys
import textwrap


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config():
    """Load config.json, searching multiple locations.

    Returns the parsed config dict. Exits with an error message if no
    config file is found.
    """
    search_paths = [
        os.path.join(os.getcwd(), "config.json"),
        os.path.expanduser("~/.config/ghostwriter/config.json"),
        os.path.join(os.path.dirname(__file__), "config.json"),
    ]

    found = None
    for p in search_paths:
        if os.path.exists(p):
            found = p
            break

    if not found:
        print(f"[!] 配置不存在，已搜索:")
        for p in search_paths:
            print(f"    {p}")
        print("[!] 请创建 config.json，参考:")
        print(textwrap.dedent("""\
        {
          "wechat": {
            "appid": "your_appid",
            "secret": "your_secret"
          },
          "ghost": {
            "api_url": "https://yinguobing.com",
            "admin_key_id": "xxx",
            "admin_key": "hex_secret"
          }
        }"""))
        sys.exit(1)

    with open(found, encoding="utf-8") as f:
        return json.load(f)
