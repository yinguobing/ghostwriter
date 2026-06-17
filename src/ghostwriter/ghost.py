"""Ghost Admin API client.

Handles JWT authentication, CRUD operations, image upload, and author
lookup via the Ghost Admin and Content APIs.
"""

import json
import time

import jwt
import requests


def get_ghost_token(key_id, key_secret):
    """Create a short-lived JWT for the Ghost Admin API.

    The secret must be the raw hex string from Ghost's integration page.
    It is decoded from hex to bytes before signing.
    """
    secret_bytes = bytes.fromhex(key_secret)
    now = int(time.time())
    payload = {
        "aud": "/admin/",
        "iat": now,
        "exp": now + 300,
        "type": "admin",
    }
    header = {"alg": "HS256", "typ": "JWT", "kid": key_id}
    return jwt.encode(payload, secret_bytes, algorithm="HS256", headers=header)


def _api_request(method, path, config, data=None):
    """Low-level Ghost Admin API request."""
    key_id = config["ghost"]["admin_key_id"]
    key_secret = config["ghost"]["admin_key"]
    api_url = config["ghost"]["api_url"]
    token = get_ghost_token(key_id, key_secret)

    headers = {"Authorization": f"Ghost {token}"}
    kwargs = {"headers": headers, "timeout": 30}

    if data is not None:
        kwargs["headers"]["Content-Type"] = "application/json"
        kwargs["data"] = json.dumps(data, ensure_ascii=False).encode("utf-8")

    url = f"{api_url}{path}"
    r = requests.request(method, url, **kwargs)
    r.raise_for_status()
    return r.json() if r.text else {}


def ghost_api_get(path, config):
    """GET from Ghost Admin API."""
    return _api_request("GET", path, config)


def ghost_api_post(path, data, config):
    """POST to Ghost Admin API."""
    return _api_request("POST", path, config, data=data)


def ghost_api_put(path, data, config):
    """PUT to Ghost Admin API."""
    return _api_request("PUT", path, config, data=data)


def ghost_api_delete(path, config):
    """DELETE from Ghost Admin API."""
    return _api_request("DELETE", path, config)


def upload_image_to_ghost(config, image_path):
    """Upload an image file to Ghost, returning the public URL."""
    import os

    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"封面图片不存在: {image_path}")

    key_id = config["ghost"]["admin_key_id"]
    key_secret = config["ghost"]["admin_key"]
    api_url = config["ghost"]["api_url"]
    token = get_ghost_token(key_id, key_secret)

    with open(image_path, "rb") as f:
        r = requests.post(
            f"{api_url}/ghost/api/admin/images/upload/",
            files={"file": (os.path.basename(image_path), f, "image/png")},
            headers={"Authorization": f"Ghost {token}"},
            timeout=60,
        )
    r.raise_for_status()
    result = r.json()
    return result["images"][0]["url"]


def get_ghost_posts(config, limit=20, status="all"):
    """List Ghost posts via Admin API."""
    return ghost_api_get(f"posts/?limit={limit}&status={status}", config)


def get_ghost_article(article_id, config):
    """Fetch a single Ghost article with HTML rendering."""
    return ghost_api_get(f"posts/{article_id}/?formats=html", config)


def get_ghost_authors(config):
    """Fetch authors via Ghost Content API (no auth needed)."""
    try:
        api_url = config["ghost"]["api_url"]
        r = requests.get(
            f"{api_url}/ghost/api/content/authors/?limit=50",
            timeout=10,
        )
        if r.ok:
            return r.json()
    except Exception:
        pass
    return {"authors": []}
