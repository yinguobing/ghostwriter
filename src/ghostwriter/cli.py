"""CLI entry point and high-level command implementations.

Provides the `ghostwriter` console script and the three main commands:
  - list:      List Ghost posts
  - publish:   Publish Markdown to Ghost (and optionally sync to WeChat)
  - sync:      Sync a Ghost article to a WeChat draft
"""

import json
import os
import sys

import requests

from .config import load_config, set_config_value, show_config, config_path
from .ghost import (
    ghost_api_get,
    ghost_api_post,
    get_ghost_article,
    get_ghost_authors,
    get_ghost_posts,
    upload_image_to_ghost,
)
from .lexical import md_to_ghost_lexical
from .normalize import normalize_title
from .pipeline import extract_images, process_html
from .wechat import (
    create_wechat_draft,
    get_wechat_token,
    upload_permanent_material,
)


# ── Sync: Ghost article → WeChat draft ───────────────────────

def sync_article(article_id, preview_only=False):
    """Sync a Ghost article to a WeChat draft.

    Args:
        article_id: Ghost post ID.
        preview_only: If True, save HTML to /tmp instead of creating a draft.

    Returns:
        True on success, False on failure.
    """
    config = load_config()

    action = "预览" if preview_only else "同步"
    print(f"[*] 开始{action} Ghost 文章 {article_id} → 微信草稿")

    # 1. Get Ghost article
    print("[*] 获取 Ghost 文章...")
    ghost_data = get_ghost_article(article_id, config)
    posts = ghost_data.get("posts", [])
    if not posts:
        print(f"[!] 未找到文章: {article_id}")
        return False
    article = posts[0]

    title = normalize_title(article.get("title", "无标题"))
    author = article.get("primary_author", {}).get("name", "")
    html_content = article.get("html", "")
    feature_image = article.get("feature_image")
    custom_excerpt = (
        article.get("custom_excerpt") or article.get("excerpt", "")
    )

    print(f"[+] 标题: {title}")
    print(f"[+] 状态: {article.get('status')}")

    # In preview mode, skip all WeChat API calls
    if not preview_only:
        wc = config["wechat"]
        print("[*] 获取微信 access_token...")
        token = get_wechat_token(wc["appid"], wc["secret"])
        print(f"[+] token: {token[:20]}...")

        # Author field: max 8 bytes for WeChat
        author_for_wechat = "国冰"
        if author and len(author.encode("utf-8")) <= 8:
            author_for_wechat = author

        # Upload cover image (permanent material)
        thumb_media_id = ""
        if feature_image:
            print(f"[*] 上传封面图（永久素材）...")
            thumb_media_id, _ = upload_permanent_material(token, feature_image)
            if thumb_media_id:
                print(f"[+] 封面图 media_id: {thumb_media_id}")
            else:
                print(f"[!] 封面上传失败，将创建无封面草稿")

        # Extract and upload content images
        images = extract_images(html_content)
        image_map = {}
        if images:
            print(f"[*] 发现 {len(images)} 张内容图片，开始上传...")
            for img_url in images:
                media_id, wechat_url = upload_permanent_material(token, img_url)
                if wechat_url:
                    image_map[img_url] = wechat_url
                    print(f"  [+] {img_url[:60]}... → {wechat_url[:60]}...")
    else:
        # Preview: no WeChat token needed, keep original image URLs
        author_for_wechat = author if author else "国冰"
        thumb_media_id = ""
        image_map = {}

    # Run HTML processing pipeline
    final_html = process_html(html_content, image_map)

    # Output result
    print(
        f"[*] 标题字节: {len(title.encode('utf-8'))} | "
        f"作者: {author_for_wechat!r}"
    )
    print(f"[*] 最终 HTML 预览:\n{final_html[:500]}...")
    print(f"[*] HTML 总长: {len(final_html)} 字符")

    if preview_only:
        preview_path = f"/tmp/wechat_preview_{article_id}.html"
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(final_html)
        print(f"\n[+] 完整 HTML 已保存到: {preview_path}")
        print(f"[+] 用浏览器打开即可预览效果")
        return True

    print("[*] 创建微信草稿...")
    digest = custom_excerpt
    if not digest:
        digest = article.get('excerpt', '')[:200]

    success, msg = create_wechat_draft(
        token, title, author_for_wechat, final_html,
        thumb_media_id, digest,
    )
    print(f"[+] {msg}")
    return success


# ── List posts ───────────────────────────────────────────────

def list_posts(limit=20):
    """List Ghost posts via the Admin API.

    Args:
        limit: Max number of posts to show (default 20, use 'all' for unlimited).
    """
    config = load_config()
    data = get_ghost_posts(config, limit=limit, status="all")
    posts = data.get("posts", [])
    print(f"共 {len(posts)} 篇:\n")
    for p in posts:
        tag = "📝" if p.get("status") == "published" else "📄"
        print(
            f"{tag} [{p.get('status')}] {p.get('title')} | "
            f"id={p.get('id')}"
        )


# ── Publish: Markdown → Ghost ────────────────────────────────

def publish_md_to_ghost(md_path, config,
                        title=None,
                        slug=None,
                        tags=None,
                        cover_image=None,
                        author_slug="xiaohei",
                        status="published"):
    """Publish a Markdown file to a Ghost blog.

    Args:
        md_path: Path to the Markdown file.
        config: Config dict from load_config().
        title: Override title (default: first h1 in the file).
        slug: Custom post slug.
        tags: List of tag name strings.
        cover_image: Local path to cover image (uploaded to Ghost).
        author_slug: Ghost author slug (default "xiaohei").
        status: "published" or "draft".

    Returns:
        (success: bool, result: str) — URL of the published post on
        success, or an error message on failure.
    """
    if not os.path.exists(md_path):
        return False, f"文件不存在: {md_path}"

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    extracted_title, lexical_json = md_to_ghost_lexical(md_text)
    if not title:
        title = (
            extracted_title
            or os.path.splitext(os.path.basename(md_path))[0]
        )
    if not title:
        return False, "无法确定标题，请用 --title 指定"

    # Extract first paragraph as excerpt
    excerpt = ""
    lex_data = json.loads(lexical_json)
    for child in lex_data["root"]["children"]:
        if child.get("type") == "paragraph":
            texts = [
                c.get("text", "")
                for c in child.get("children", [])
                if c.get("type") == "extended-text"
            ]
            excerpt = "".join(texts)[:200]
            break

    # Look up author (Content API → hardcoded fallback)
    author_id = None
    try:
        authors_data = get_ghost_authors(config)
        for a in authors_data.get("authors", []):
            if a.get("slug") == author_slug:
                author_id = a["id"]
                break
        if not author_id:
            author_id = authors_data.get("authors", [{}])[0].get("id")
    except Exception:
        pass
    # Fallback: authors map from config file
    if not author_id:
        authors_map = config.get("authors", {})
        author_id = authors_map.get(author_slug)
    if not author_id:
        return False, f"无法找到作者: {author_slug}"

    tag_objects = [{"name": t} for t in (tags or [])]

    post = {
        "title": title,
        "lexical": lexical_json,
        "status": status,
        "visibility": "public",
        "authors": [{"id": author_id}],
        "tags": tag_objects,
        "excerpt": excerpt,
    }

    # Upload cover image
    if cover_image:
        try:
            feature_image_url = upload_image_to_ghost(config, cover_image)
            post["feature_image"] = feature_image_url
            print(f"[+] 封面图片已上传: {feature_image_url}")
        except Exception as e:
            print(f"[!] 封面图片上传失败: {e}")

    if slug:
        post["slug"] = slug
    # Ghost API uses custom_excerpt, not excerpt
    if excerpt:
        post["custom_excerpt"] = excerpt
        del post["excerpt"]

    post_data = {"posts": [post]}

    try:
        result = ghost_api_post(
            "/ghost/api/admin/posts/", post_data, config,
        )
        post = result.get("posts", [{}])[0]
        post_url = (
            f"{config['ghost']['api_url']}/{post.get('slug', '')}/"
        )
        return True, post_url
    except requests.HTTPError as e:
        try:
            detail = e.response.json()
        except Exception:
            detail = str(e)
        return False, f"Ghost API 错误: {detail}"


def _cmd_publish(args):
    """Parse `publish` subcommand arguments and execute."""
    # Check for help before loading config
    if args and args[0] in ("--help", "-h", "help"):
        print("""publish 用法:
  ghostwriter publish <file.md> [选项]

  选项:
    --title "标题"       - 指定标题（默认取文件第一个 # 标题）
    --slug "my-slug"     - 指定 slug（默认从标题自动生成）
    --cover "image.jpg"  - 封面图片路径（本地文件，自动上传到 Ghost）
    --tags tag1,tag2     - 逗号分隔的标签
    --author slug        - 作者 slug（默认 xiaohei）
    --draft              - 保存为草稿（默认直接发布）
    --wechat             - 发布后自动同步到微信草稿箱
    --help, -h           - 显示此帮助信息
""")
        return True

    config = load_config()

    md_path = args[0]
    title = None
    tags = []
    author = "xiaohei"
    status = "published"
    do_wechat = False
    slug = None
    cover_image = None

    i = 1
    while i < len(args):
        if args[i] in ("--help", "-h", "help"):
            print("""publish 用法:
  ghostwriter publish <file.md> [选项]

  选项:
    --title "标题"       - 指定标题（默认取文件第一个 # 标题）
    --slug "my-slug"     - 指定 slug（默认从标题自动生成）
    --cover "image.jpg"  - 封面图片路径（本地文件，自动上传到 Ghost）
    --tags tag1,tag2     - 逗号分隔的标签
    --author slug        - 作者 slug（默认 xiaohei）
    --draft              - 保存为草稿（默认直接发布）
    --wechat             - 发布后自动同步到微信草稿箱
    --help, -h           - 显示此帮助信息
""")
            return True
        elif args[i] == "--title" and i + 1 < len(args):
            title = args[i + 1]
            i += 2
        elif args[i] == "--slug" and i + 1 < len(args):
            slug = args[i + 1]
            i += 2
        elif args[i] == "--cover" and i + 1 < len(args):
            cover_image = args[i + 1]
            i += 2
        elif args[i] == "--tags" and i + 1 < len(args):
            tags = [t.strip() for t in args[i + 1].split(",")]
            i += 2
        elif args[i] == "--author" and i + 1 < len(args):
            author = args[i + 1]
            i += 2
        elif args[i] == "--draft":
            status = "draft"
            i += 1
        elif args[i] == "--wechat":
            do_wechat = True
            i += 1
        else:
            print(f"[!] 未知参数: {args[i]}")
            return False

    print(f"[*] 发布 {md_path} → Ghost...")
    success, result = publish_md_to_ghost(
        md_path, config,
        title=title, slug=slug, tags=tags,
        cover_image=cover_image,
        author_slug=author, status=status,
    )

    if success:
        print(f"[+] ✅ 发布成功: {result}")
        if do_wechat:
            print("[*] 开始同步到微信...")
            post_slug = result.rstrip("/").split("/")[-1]
            try:
                posts_data = ghost_api_get(
                    f"/ghost/api/admin/posts/?filter=slug:{post_slug}",
                    config,
                )
                for p in posts_data.get("posts", []):
                    if p.get("slug") == post_slug:
                        return sync_article(p["id"])
            except Exception as e:
                print(f"[!] 微信同步失败: {e}")
                return False
        return True
    else:
        print(f"[!] ❌ 发布失败: {result}")
        return False


# ── Config ───────────────────────────────────────────────────

def _cmd_config(args):
    """Handle `ghostwriter config` subcommand."""
    if not args or args[0] in ("show",):
        show_config()
    elif args[0] == "set" and len(args) >= 3:
        set_config_value(args[1], " ".join(args[2:]))
    elif args[0] == "path":
        print(config_path())
    elif args[0] in ("--help", "-h", "help"):
        print("""config 用法:
  ghostwriter config                显示当前配置（密钥已脱敏）
  ghostwriter config set <key> <value>
                                    设置单个配置项
  ghostwriter config path           显示配置文件路径

  有效的 <key>:
    ghost.api_url          Ghost 博客地址
    ghost.admin_key_id     Ghost Admin API Key ID
    ghost.admin_key        Ghost Admin API Key Secret
    wechat.appid           微信公众号 AppID
    wechat.secret          微信公众号 AppSecret
    authors.<slug>         (可选) 作者 slug → Ghost 作者 ID 映射
""")
    else:
        print(f"[!] 未知的 config 子命令: {' '.join(args)}")
        print("[!] 使用 'ghostwriter config --help' 查看用法")


# ── Main ─────────────────────────────────────────────────────

def main(args=None):
    """Main CLI entry point.

    Args:
        args: List of command-line arguments (default: sys.argv[1:]).
    """
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h", "help"):
        print("""用法:
  ghostwriter list [--limit <n>|all]   - 列出 Ghost 文章
  ghostwriter sync <article-id>        - 同步 Ghost 文章到微信草稿
  ghostwriter sync --preview <id>      - 预览微信 HTML（不创建草稿）
  ghostwriter publish <file.md>        - 发布 Markdown 到 Ghost 博客
  ghostwriter config                   - 查看/设置配置

  publish 选项:
    --title "标题"       - 指定标题（默认取文件第一个 # 标题）
    --slug "my-slug"     - 指定 slug（默认从标题自动生成）
    --cover "image.jpg"  - 封面图片路径（本地文件，自动上传）
    --tags tag1,tag2     - 标签
    --author slug        - 作者 slug（默认 xiaohei）
    --draft              - 保存为草稿（默认直接发布）
    --wechat             - 发布后同步到微信

  示例:
  ghostwriter publish article.md
  ghostwriter publish article.md --title "我的文章" --slug my-article --cover cover.png --tags Ghost,开源 --draft
  ghostwriter publish article.md --wechat
  ghostwriter sync 123abc
  ghostwriter sync --preview 123abc
""")
        sys.exit(1)

    if args[0] == "list":
        limit = 20
        if len(args) > 1 and args[1] == "--limit" and len(args) > 2:
            limit = args[2]
        list_posts(limit=limit)
    elif args[0] == "config":
        _cmd_config(args[1:])
    elif args[0] == "publish":
        if len(args) < 2:
            print("[!] 请指定 Markdown 文件路径")
            sys.exit(1)
        try:
            _cmd_publish(args[1:])
        except Exception as e:
            print(f"[!] 错误: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    elif args[0] == "sync":
        preview_only = False
        article_id = None
        i = 1
        while i < len(args):
            if args[i] == "--preview" and i + 1 < len(args):
                preview_only = True
                article_id = args[i + 1]
                i += 2
            elif not args[i].startswith("--"):
                article_id = args[i]
                i += 1
            else:
                print(f"[!] 未知参数: {args[i]}")
                sys.exit(1)
        if not article_id:
            print("[!] 请指定文章 ID")
            print("[!] 用法: ghostwriter sync [--preview] <article-id>")
            sys.exit(1)
        try:
            sync_article(article_id, preview_only=preview_only)
        except Exception as e:
            print(f"[!] 错误: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print(f"[!] 未知命令: {args[0]}")
        print("[!] 使用 --help 查看可用命令")
        sys.exit(1)


if __name__ == "__main__":
    main()
