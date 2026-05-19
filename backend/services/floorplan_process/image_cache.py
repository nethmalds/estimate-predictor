"""Download and cache cloud-hosted floorplan images to a local temp directory.

Supported formats: .png, .jpg, .jpeg, .pdf
The cache is keyed on a SHA-256 hash of the URL so repeated calls are idempotent.

UploadThing CDN URLs have extensionless UUID-like paths — this module handles those
by inspecting the Content-Type response header and file magic bytes as fallback.
"""
from __future__ import annotations

import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse


# Resolve to  <backend_root>/temp/floorplans/
_CACHE_DIR = Path(__file__).resolve().parents[2] / "temp" / "floorplans"

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}

# MIME type → canonical extension mapping (Content-Type header)
_MIME_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".jpg",
    "application/pdf": ".pdf",
    "application/x-pdf": ".pdf",
}

# File magic bytes → canonical extension
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"%PDF", ".pdf"),
]

# Maximum allowed file size: 50 MB
_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


def download_and_cache(url: str) -> str:
    """Download *url* to the local cache directory and return the local file path.

    Handles extensionless UploadThing CDN URLs by reading Content-Type header
    and file magic bytes to determine format.

    Raises
    ------
    ValueError
        If the URL scheme is not http/https, format is unsupported, or file is too large.
    RuntimeError
        If the HTTP request fails (non-2xx) or the network is unreachable.
    """
    # Validate URL scheme — block file://, data:, ftp://, etc.
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed."
        )

    url_ext = _extract_extension(url)

    # If URL has a known extension and it's not allowed, reject early
    if url_ext and url_ext not in _ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported floorplan format '{url_ext}'. "
            f"Accepted formats: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        )

    cache_key = hashlib.sha256(url.encode()).hexdigest()[:24]

    # Fast path: check cache for all possible extensions
    if url_ext:
        candidate = _CACHE_DIR / f"{cache_key}{url_ext}"
        if candidate.exists():
            return str(candidate)
    else:
        for ext in _ALLOWED_EXTENSIONS:
            candidate = _CACHE_DIR / f"{cache_key}{ext}"
            if candidate.exists():
                return str(candidate)

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
            if response.status != 200:
                raise RuntimeError(
                    f"Failed to download floorplan: HTTP {response.status} for url={url}"
                )

            # Size guard via Content-Length header (before reading body)
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > _MAX_FILE_SIZE_BYTES:
                raise ValueError(
                    f"Floorplan file too large "
                    f"({int(content_length) // (1024 * 1024)} MB). "
                    f"Maximum allowed size is {_MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
                )

            # Capture Content-Type for MIME-based extension inference
            content_type = (
                (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            )
            mime_ext = _MIME_TO_EXT.get(content_type)

            data = response.read()

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Network error downloading floorplan url={url}: {exc}"
        ) from exc

    # Enforce size limit on actual content
    if len(data) > _MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"Floorplan file too large ({len(data) // (1024 * 1024)} MB). "
            f"Maximum allowed size is {_MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
        )

    # Determine final extension: URL path > Content-Type MIME > magic bytes
    final_ext = url_ext or mime_ext or _detect_ext_from_magic(data)

    if not final_ext or final_ext not in _ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported floorplan format (detected: '{final_ext or 'unknown'}'). "
            f"Accepted formats: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        )

    cache_path = _CACHE_DIR / f"{cache_key}{final_ext}"
    cache_path.write_bytes(data)
    return str(cache_path)


def _extract_extension(url: str) -> str:
    """Return the lowercased file extension from the URL path portion."""
    path_part = url.split("?")[0].split("#")[0]  # strip query string / fragment
    suffix = Path(path_part).suffix.lower()
    return suffix if suffix else ""


def _detect_ext_from_magic(data: bytes) -> str:
    """Detect file extension from magic bytes (file signature)."""
    for signature, ext in _MAGIC_SIGNATURES:
        if data.startswith(signature):
            return ext
    return ""


def _cache_path_for(url: str, ext: str) -> Path:
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:24]
    return _CACHE_DIR / f"{url_hash}{ext}"
