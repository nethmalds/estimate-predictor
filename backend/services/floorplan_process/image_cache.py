"""Download and cache cloud-hosted floorplan images to a local temp directory.

Supported formats: .png, .jpg, .jpeg, .pdf
The cache is keyed on a SHA-256 hash of the URL so repeated calls are idempotent.
"""
from __future__ import annotations

import hashlib
import urllib.request
import urllib.error
from pathlib import Path



# Resolve to  <backend_root>/temp/floorplans/
_CACHE_DIR = Path(__file__).resolve().parents[2] / "temp" / "floorplans"

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}


def download_and_cache(url: str) -> str:
    """Download *url* to the local cache directory and return the local file path.

    Raises
    ------
    ValueError
        If the URL extension is not in the supported set.
    RuntimeError
        If the HTTP request fails (non-2xx) or the network is unreachable.
    """
    ext = _extract_extension(url)
    if ext not in _ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported floorplan format '{ext}'. "
            f"Accepted formats: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        )

    cache_path = _cache_path_for(url, ext)

    if cache_path.exists():
        return str(cache_path)

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
            if response.status != 200:
                raise RuntimeError(
                    f"Failed to download floorplan: HTTP {response.status} for url={url}"
                )
            data = response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error downloading floorplan url={url}: {exc}") from exc

    cache_path.write_bytes(data)
    return str(cache_path)


def _extract_extension(url: str) -> str:
    """Return the lowercased file extension from the URL path portion."""
    path_part = url.split("?")[0].split("#")[0]  # strip query string / fragment
    suffix = Path(path_part).suffix.lower()
    return suffix if suffix else ""


def _cache_path_for(url: str, ext: str) -> Path:
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:24]
    return _CACHE_DIR / f"{url_hash}{ext}"
