from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import threading
import time
import warnings
from pathlib import Path
from typing import Any


_log = logging.getLogger(__name__)


_DIMENSION_PATTERNS = [
    r"\b\d+(?:\.\d+)?\s*(?:m|cm|mm)\b",
    r"\b\d+(?:\.\d+)?\s*(?:ft|feet|')\s*(?:\d+(?:\.\d+)?\s*(?:in|\"))?\b",
    r"\b\d+(?:\.\d+)?\s*(?:in|\"|inch|inches)\b",
]


# ---------------------------------------------------------------------------
# Vision-API fallback — configuration and module-level state
# ---------------------------------------------------------------------------

_VISION_TIMEOUT_SECONDS = 15.0
_VISION_CACHE_DIR = Path(__file__).resolve().parents[3] / "temp" / "vision_ocr_cache"

# Circuit breaker: open after 5 failures within 5 minutes, stay open for 60 s.
_CIRCUIT_THRESHOLD = 5
_CIRCUIT_WINDOW_SECONDS = 5 * 60
_CIRCUIT_OPEN_SECONDS = 60

_circuit_lock = threading.Lock()
_vision_failure_timestamps: list[float] = []
_circuit_open_until: float = 0.0


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _extract_dimensions(text: str) -> list[str]:
    matches: list[str] = []
    for pattern in _DIMENSION_PATTERNS:
        matches.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return _dedupe_preserve_order([match.strip() for match in matches if match.strip()])


def _ocr_skip_result(image_file: Path, reason: str) -> dict:
    return {
        "image_path": str(image_file.resolve()),
        "text": "",
        "dimensions": [],
        "dimension_count": 0,
        "ocr_skipped": True,
        "ocr_skip_reason": reason,
    }


# ---------------------------------------------------------------------------
# Vision fallback helpers
# ---------------------------------------------------------------------------

def _circuit_state() -> tuple[bool, float]:
    """Return (is_open, seconds_remaining_until_close)."""
    now = time.monotonic()
    with _circuit_lock:
        if now < _circuit_open_until:
            return True, _circuit_open_until - now
        return False, 0.0


def _record_vision_failure() -> None:
    """Track a vision-API failure; open the breaker once threshold reached."""
    global _circuit_open_until  # noqa: PLW0603
    now = time.monotonic()
    with _circuit_lock:
        cutoff = now - _CIRCUIT_WINDOW_SECONDS
        _vision_failure_timestamps[:] = [
            t for t in _vision_failure_timestamps if t >= cutoff
        ]
        _vision_failure_timestamps.append(now)
        if len(_vision_failure_timestamps) >= _CIRCUIT_THRESHOLD:
            _circuit_open_until = now + _CIRCUIT_OPEN_SECONDS
            _vision_failure_timestamps.clear()
            _log.warning(
                "[OCR] Vision circuit breaker OPEN for %ss after %s consecutive failures.",
                _CIRCUIT_OPEN_SECONDS, _CIRCUIT_THRESHOLD,
            )


def _record_vision_success() -> None:
    with _circuit_lock:
        _vision_failure_timestamps.clear()


def _vision_cache_path(image_bytes: bytes) -> Path:
    cache_key = hashlib.sha256(image_bytes).hexdigest()[:24]
    return _VISION_CACHE_DIR / f"{cache_key}.json"


def _load_vision_cache(cache_path: Path) -> dict | None:
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_vision_cache(cache_path: Path, payload: dict) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        _log.warning("[OCR] Could not write vision cache %s: %s", cache_path, exc)


def _call_llm_vision(b64: str, mime: str, prompt: str) -> str:
    """Call the configured Ollama vision model with a base64 image and text prompt.

    Returns the raw text content of the model response. Raises on transport
    errors so the caller can route to the circuit breaker / skip fallback.
    """
    # Local imports keep test patches lightweight and avoid hard-failing module
    # import when Ollama infrastructure is unavailable.
    from infrastructure.integrations.ollama_client import _get_client  # type: ignore[import]
    import os

    client = _get_client()
    model_name = (
        os.getenv("OLLAMA_VISION_MODEL")
        or os.getenv("OLLAMA_MODEL")
        or "gpt-oss:120b-cloud"
    )

    messages = [
        {
            "role": "user",
            "content": prompt,
            # Ollama's chat API accepts a list of base64-encoded images on each
            # message; the data: URI prefix is not used.
            "images": [b64],
        }
    ]
    response = client.chat(
        model=model_name,
        messages=messages,
        stream=False,
        options={"temperature": 0.0, "num_ctx": 4096},
    )
    # Mirror ollama_client._extract_message_content but local to avoid circular deps
    message = response.get("message") if isinstance(response, dict) else getattr(response, "message", None)
    if isinstance(message, dict):
        content = message.get("content") or ""
    else:
        content = getattr(message, "content", "") or ""
    return str(content)


_VISION_PROMPT = (
    "You are analyzing a floor plan image. For every labelled room return a "
    "JSON array with one object per room of the form:\n"
    '[{"name": "Bedroom 1", "dimension_label": "11\'3\\" x 8\'11\\"", '
    '"bbox": [x1, y1, x2, y2]}]\n'
    "bbox values must be pixel coordinates of the room label inside the image. "
    "If you cannot infer a bbox use null. Return only the JSON array — no commentary."
)


def _parse_vision_response(raw_text: str) -> tuple[list[str], list[dict]]:
    """Parse the LLM vision response into (dimension_tokens, ocr_labels).

    Tries JSON first; on failure falls back to running the dimension regexes
    across the raw text so we still recover usable tokens from prose output.
    """
    dimensions: list[str] = []
    ocr_labels: list[dict] = []

    text = raw_text.strip()
    # Vision models sometimes wrap JSON in ``` fences — strip those.
    fence_match = re.search(r"\[[\s\S]*\]", text)
    json_blob = fence_match.group(0) if fence_match else text

    parsed: Any = None
    try:
        parsed = json.loads(json_blob)
    except (json.JSONDecodeError, ValueError):
        parsed = None

    if isinstance(parsed, list):
        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            dim_label = entry.get("dimension_label") or ""
            bbox = entry.get("bbox")

            if isinstance(dim_label, str) and dim_label:
                dimensions.extend(_extract_dimensions(dim_label))

            if isinstance(name, str) and name.strip():
                label_entry: dict = {"name": name.strip()}
                if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                    try:
                        label_entry["bbox"] = [float(v) for v in bbox]
                    except (TypeError, ValueError):
                        pass
                ocr_labels.append(label_entry)

    if not dimensions:
        # Non-JSON or empty JSON — fall back to running regexes on raw text.
        dimensions = _extract_dimensions(raw_text)

    return _dedupe_preserve_order(dimensions), ocr_labels


def _extract_dimensions_via_vision(image_path: str) -> dict:
    """Fallback OCR using the configured LLM vision API.

    Raises ``TimeoutError`` when the call exceeds ``_VISION_TIMEOUT_SECONDS``.
    """
    image_file = Path(image_path)
    image_bytes = image_file.read_bytes()
    cache_path = _vision_cache_path(image_bytes)

    cached = _load_vision_cache(cache_path) if cache_path.exists() else None
    if cached is not None:
        cached.setdefault("image_path", str(image_file.resolve()))
        cached.setdefault("vision_source", True)
        cached.setdefault("vision_cache_hit", True)
        return cached

    ext = image_file.suffix.lstrip(".").lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "webp": "image/webp"}.get(ext, "image/png")
    b64 = base64.b64encode(image_bytes).decode()

    # Run the call on a worker thread so we can enforce a hard timeout.
    container: dict[str, Any] = {}

    def _worker() -> None:
        try:
            container["text"] = _call_llm_vision(b64, mime, _VISION_PROMPT)
        except Exception as exc:  # noqa: BLE001
            container["error"] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(_VISION_TIMEOUT_SECONDS)
    if thread.is_alive():
        raise TimeoutError(
            f"Vision OCR call exceeded {_VISION_TIMEOUT_SECONDS:.0f}s timeout"
        )
    if "error" in container:
        raise container["error"]  # type: ignore[misc]

    raw_text = container.get("text") or ""
    dimensions, ocr_labels = _parse_vision_response(raw_text)

    result = {
        "image_path":      str(image_file.resolve()),
        "text":            raw_text,
        "dimensions":      dimensions,
        "dimension_count": len(dimensions),
        "ocr_labels":      ocr_labels,
        "vision_source":   True,
    }
    _save_vision_cache(cache_path, result)
    return result


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_floorplan_text_and_dimensions(
    image_path: str,
    original_path: str | None = None,
) -> dict:
    """Run Tesseract OCR, falling back to an LLM vision call when unavailable.

    Parameters
    ----------
    image_path
        Path passed to Tesseract — typically the preprocessed binarised image.
    original_path
        Optional path of the original (un-binarised) image. The vision API
        fallback prefers this richer source when supplied; defaults to
        ``image_path``.
    """
    image_file = Path(image_path)
    if not image_file.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    vision_source_path = original_path or image_path

    try:
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        raise ImportError(
            "pytesseract and Pillow are required for OCR. Install with: pip install pytesseract Pillow"
        ) from exc

    try:
        image = Image.open(image_file)
    except OSError as exc:
        raise ValueError(f"Invalid image file: {image_path}") from exc

    image = image.convert("L")
    try:
        text = pytesseract.image_to_string(image, config="--psm 6")
    except pytesseract.TesseractNotFoundError:
        warnings.warn(
            "[OCR] Tesseract not found — trying vision API fallback.",
            stacklevel=2,
        )
        return _run_vision_fallback(vision_source_path, "tesseract_not_found")
    except pytesseract.TesseractError as exc:
        warnings.warn(
            f"[OCR] Tesseract error processing image — trying vision API fallback: {exc}",
            stacklevel=2,
        )
        return _run_vision_fallback(vision_source_path, "tesseract_error")

    dimensions = _extract_dimensions(text)

    return {
        "image_path": str(image_file.resolve()),
        "text": text,
        "dimensions": dimensions,
        "dimension_count": len(dimensions),
    }


def _run_vision_fallback(image_path: str, tesseract_reason: str) -> dict:
    """Invoke the vision fallback with circuit breaker and timeout handling."""
    image_file = Path(image_path)
    is_open, remaining = _circuit_state()
    if is_open:
        _log.info(
            "[OCR] Vision circuit open (%.1fs remaining) — returning skip result.",
            remaining,
        )
        return _ocr_skip_result(image_file, "vision_circuit_open")

    try:
        result = _extract_dimensions_via_vision(image_path)
    except TimeoutError:
        warnings.warn("[OCR] Vision fallback timed out.", stacklevel=2)
        _record_vision_failure()
        return _ocr_skip_result(image_file, "vision_timeout")
    except Exception as vision_exc:  # noqa: BLE001
        warnings.warn(
            f"[OCR] Vision fallback failed ({tesseract_reason}): {vision_exc}",
            stacklevel=2,
        )
        _record_vision_failure()
        return _ocr_skip_result(image_file, "tesseract_not_found_vision_failed")

    _record_vision_success()
    return result
