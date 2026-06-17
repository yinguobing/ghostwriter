"""ghostwriter — Markdown → Ghost → WeChat publishing pipeline.

Write Markdown, publish to a Ghost blog, and sync to WeChat drafts.
"""

from .cli import main, sync_article, publish_md_to_ghost, list_posts
from .cleaner import clean_html_for_wechat, WECHAT_SAFE_TAGS
from .config import load_config, set_config_value, show_config, config_path
from .lexical import md_to_ghost_lexical
from .normalize import normalize_title
from .pipeline import process_html

__version__ = "0.1.0"
__all__ = [
    "main",
    "sync_article",
    "publish_md_to_ghost",
    "list_posts",
    "clean_html_for_wechat",
    "WECHAT_SAFE_TAGS",
    "load_config",
    "set_config_value",
    "show_config",
    "config_path",
    "md_to_ghost_lexical",
    "normalize_title",
    "process_html",
]
