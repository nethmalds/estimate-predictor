"""Unit tests for services/floorplan_process/image_cache.py.

Covers:
- BE-TC-090: _extract_extension returns correct lowercase suffix or empty string
- BE-TC-091: _detect_ext_from_magic identifies PNG, JPEG, PDF from magic bytes
- BE-TC-092: download_and_cache rejects non-http/https URL schemes
- BE-TC-093: download_and_cache rejects unsupported explicit extensions (gif, exe)
- BE-TC-094: download_and_cache resolves extension via Content-Type for extensionless URLs
- BE-TC-095: download_and_cache falls back to magic bytes when Content-Type is absent
- BE-TC-096: download_and_cache raises ValueError for unknown format (no ext, no MIME, no magic)
- BE-TC-097: download_and_cache raises RuntimeError on HTTP error status
- BE-TC-098: download_and_cache enforces 50 MB limit via Content-Length header
- BE-TC-099: download_and_cache enforces 50 MB limit via actual body size
- BE-TC-100: download_and_cache is idempotent (second call returns cached path, no re-download)
- BE-TC-101: download_and_cache raises RuntimeError on network error (URLError)
"""
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.floorplan_process.image_cache import (  # noqa: E402
    _detect_ext_from_magic,
    _extract_extension,
    download_and_cache,
)


# ── Helper ────────────────────────────────────────────────────────────────────

def make_mock_response(
    data: bytes,
    content_type: str = "image/png",
    content_length: str | None = None,
    status: int = 200,
) -> MagicMock:
    """Build a mock context-manager response for urllib.request.urlopen."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.read.return_value = data
    # Use a real dict so .get() works without extra setup
    mock_resp.headers = {"Content-Type": content_type}
    if content_length is not None:
        mock_resp.headers["Content-Length"] = content_length
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ── BE-TC-090: _extract_extension ─────────────────────────────────────────────

class TestExtractExtension:
    def test_png_extension(self):
        assert _extract_extension("http://example.com/file.png") == ".png"

    def test_jpg_with_query_string(self):
        assert _extract_extension("http://example.com/file.jpg?foo=bar") == ".jpg"

    def test_no_extension(self):
        assert _extract_extension("http://example.com/uuid-no-ext") == ""

    def test_uploadthing_extensionless_uuid(self):
        assert _extract_extension("https://uploadthing.com/f/abc123def456") == ""

    def test_uppercase_lowercased(self):
        assert _extract_extension("http://example.com/FILE.PNG") == ".png"


# ── BE-TC-091: _detect_ext_from_magic ─────────────────────────────────────────

class TestDetectExtFromMagic:
    def test_png_magic_bytes(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        assert _detect_ext_from_magic(data) == ".png"

    def test_jpeg_magic_bytes(self):
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 20
        assert _detect_ext_from_magic(data) == ".jpg"

    def test_pdf_magic_bytes(self):
        data = b"%PDF-1.4\n" + b"\x00" * 20
        assert _detect_ext_from_magic(data) == ".pdf"

    def test_unknown_returns_empty_string(self):
        data = b"\x00\x01\x02\x03random bytes here"
        assert _detect_ext_from_magic(data) == ""


# ── BE-TC-092: scheme validation ───────────────────────────────────────────────

class TestSchemeValidation:
    def test_ftp_scheme_raises(self):
        with pytest.raises(ValueError, match="scheme"):
            download_and_cache("ftp://example.com/file.png")

    def test_file_scheme_raises(self):
        with pytest.raises(ValueError, match="scheme"):
            download_and_cache("file:///etc/passwd")

    def test_data_scheme_raises(self):
        with pytest.raises(ValueError, match="scheme"):
            download_and_cache("data:image/png;base64,abc123")


# ── BE-TC-093: explicit unsupported extension ──────────────────────────────────

class TestExplicitUnsupportedExtension:
    def test_gif_extension_raises(self):
        with pytest.raises(ValueError, match="gif"):
            download_and_cache("http://example.com/file.gif")

    def test_exe_extension_raises(self):
        with pytest.raises(ValueError):
            download_and_cache("http://example.com/file.exe")


# ── BE-TC-094: extensionless URL resolved via Content-Type ─────────────────────

class TestContentTypeFallback:
    def test_jpeg_content_type_returns_jpg_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "services.floorplan_process.image_cache._CACHE_DIR", tmp_path
        )
        jpeg_data = b"\xff\xd8\xff\xe0" + b"\x00" * 50
        mock_resp = make_mock_response(
            data=jpeg_data,
            content_type="image/jpeg",
        )

        with patch(
            "services.floorplan_process.image_cache.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            result = download_and_cache("https://utfs.io/f/abc123def456")

        assert result.endswith(".jpg")
        assert Path(result).exists()


# ── BE-TC-095: extensionless URL resolved via magic bytes ──────────────────────

class TestMagicBytesFallback:
    def test_png_magic_with_empty_content_type(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "services.floorplan_process.image_cache._CACHE_DIR", tmp_path
        )
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        mock_resp = make_mock_response(
            data=png_data,
            content_type="",  # empty → no MIME mapping → fall back to magic
        )

        with patch(
            "services.floorplan_process.image_cache.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            result = download_and_cache("https://utfs.io/f/abc123def456")

        assert result.endswith(".png")
        assert Path(result).exists()


# ── BE-TC-096: unknown format raises ValueError ────────────────────────────────

class TestUnknownFormat:
    def test_octet_stream_and_unknown_magic_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "services.floorplan_process.image_cache._CACHE_DIR", tmp_path
        )
        random_data = b"\x00\x01\x02\x03\x04\x05garbage"
        mock_resp = make_mock_response(
            data=random_data,
            content_type="application/octet-stream",
        )

        with patch(
            "services.floorplan_process.image_cache.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            with pytest.raises(ValueError, match="Unsupported floorplan format"):
                download_and_cache("https://utfs.io/f/abc123def456")


# ── BE-TC-097: HTTP error status ───────────────────────────────────────────────

class TestHttpError:
    def test_404_raises_runtime_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "services.floorplan_process.image_cache._CACHE_DIR", tmp_path
        )
        mock_resp = make_mock_response(data=b"", status=404)

        with patch(
            "services.floorplan_process.image_cache.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            with pytest.raises(RuntimeError, match="HTTP 404"):
                download_and_cache("http://example.com/plan.png")


# ── BE-TC-098: size limit via Content-Length header ───────────────────────────

class TestSizeLimitContentLength:
    def test_content_length_over_50mb_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "services.floorplan_process.image_cache._CACHE_DIR", tmp_path
        )
        # 50 * 1024 * 1024 = 52428800; one byte over the limit
        mock_resp = make_mock_response(
            data=b"",  # body never read when header check fires
            content_type="image/png",
            content_length="52428801",
        )

        with patch(
            "services.floorplan_process.image_cache.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            with pytest.raises(ValueError, match="too large"):
                download_and_cache("http://example.com/plan.png")


# ── BE-TC-099: size limit via actual body size ────────────────────────────────

class TestSizeLimitBody:
    def test_body_over_limit_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "services.floorplan_process.image_cache._CACHE_DIR", tmp_path
        )
        # Patch the size cap to a small value to avoid allocating 50 MB in tests
        monkeypatch.setattr(
            "services.floorplan_process.image_cache._MAX_FILE_SIZE_BYTES", 100
        )
        # 101 bytes of valid PNG-like data (starts with PNG magic so format is accepted)
        oversized_data = b"\x89PNG" + b"\x00" * 97  # total = 101 bytes > 100

        mock_resp = make_mock_response(
            data=oversized_data,
            content_type="image/png",
            content_length=None,  # no header → rely on body check
        )

        with patch(
            "services.floorplan_process.image_cache.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            with pytest.raises(ValueError, match="too large"):
                download_and_cache("http://example.com/plan.png")


# ── BE-TC-100: idempotent caching ─────────────────────────────────────────────

class TestCachingIdempotent:
    def test_second_call_uses_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "services.floorplan_process.image_cache._CACHE_DIR", tmp_path
        )
        url = "http://example.com/floorplan.png"
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        mock_resp = make_mock_response(data=png_data, content_type="image/png")

        with patch(
            "services.floorplan_process.image_cache.urllib.request.urlopen",
            return_value=mock_resp,
        ) as mock_urlopen:
            first_path = download_and_cache(url)
            second_path = download_and_cache(url)

        assert first_path == second_path
        # urlopen should only have been called once — second call was a cache hit
        mock_urlopen.assert_called_once()


# ── BE-TC-101: network error ──────────────────────────────────────────────────

class TestNetworkError:
    def test_urlerror_raises_runtime_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "services.floorplan_process.image_cache._CACHE_DIR", tmp_path
        )

        with patch(
            "services.floorplan_process.image_cache.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            with pytest.raises(RuntimeError, match="Network error"):
                download_and_cache("http://example.com/plan.png")
