"""WeChat Official Account API client.

Handles access token management (with disk caching), permanent material
upload for images, and draft creation.
"""

import json
import os
import re
import time

import requests


TOKEN_CACHE = "/tmp/wechat_token.json"


def get_wechat_token(appid, secret):
    """Get a WeChat access token, caching it to disk.

    Returns a cached token if it has more than 60 seconds remaining.
    Otherwise requests a new one from the WeChat API.
    """
    cached = None
    if os.path.exists(TOKEN_CACHE):
        with open(TOKEN_CACHE, encoding="utf-8") as f:
            cached = json.load(f)
        if cached.get("expires_at", 0) > time.time() + 60:
            return cached["access_token"]

    url = (
        f"https://api.weixin.qq.com/cgi-bin/token"
        f"?grant_type=client_credential&appid={appid}&secret={secret}"
    )
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    if "access_token" not in data:
        raise Exception(f"获取token失败: {data}")

    token = data["access_token"]
    with open(TOKEN_CACHE, "w", encoding="utf-8") as f:
        json.dump({
            "access_token": token,
            "expires_at": data.get("expires_in", 7200) + time.time(),
        }, f)
    return token


def upload_permanent_material(token, image_url, material_type="image"):
    """Upload an image to WeChat permanent material storage.

    Returns (media_id, url) tuple. Both are None on failure.
    """
    try:
        img_data = requests.get(image_url, timeout=30)
        img_data.raise_for_status()
    except Exception as e:
        print(f"  [警告] 下载图片失败 {image_url}: {e}")
        return None, None

    ext = re.search(r'\.(jpg|jpeg|png|gif|webp)', image_url, re.I)
    ext = ext.group(1) if ext else "jpg"
    mime = f"image/{ext.replace('jpg', 'jpeg')}"

    files = {"media": (f"image.{ext}", img_data.content, mime)}
    url = (
        f"https://api.weixin.qq.com/cgi-bin/material/add_material"
        f"?access_token={token}&type={material_type}"
    )
    r = requests.post(url, files=files, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "media_id" in data:
        return data["media_id"], data.get("url")
    print(f"  [警告] 上传永久素材失败: {data}")
    return None, None


def create_wechat_draft(token, title, author, content, thumb_media_id,
                        digest=""):
    """Create a draft in WeChat's draft box.

    Args:
        token: WeChat access token.
        title: Article title.
        author: Author name (max 8 bytes).
        content: HTML content for the article body.
        thumb_media_id: Cover image media_id (empty string if none).
        digest: Article summary (max 120 bytes, auto-truncated).

    Returns:
        (success: bool, message: str)
    """
    if not digest:
        digest = "查看全文"
    elif len(digest.encode("utf-8")) > 120:
        digest = digest.encode("utf-8")[:119].decode("utf-8", errors="ignore")

    articles = [{
        "title": title,
        "author": author,
        "content": content,
        "content_source_url": "",
        "digest": digest,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
    }]

    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
    payload_bytes = json.dumps(
        {"articles": articles}, ensure_ascii=False
    ).encode("utf-8")
    r = requests.post(
        url, data=payload_bytes,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    if data.get("errcode") == 0 or "media_id" in data:
        return True, f"草稿创建成功，media_id={data.get('media_id')}"
    return False, f"创建草稿失败: {data}"
