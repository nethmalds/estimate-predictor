import re
import warnings
from pathlib import Path


_DIMENSION_PATTERNS = [
    r"\b\d+(?:\.\d+)?\s*(?:m|cm|mm)\b",
    r"\b\d+(?:\.\d+)?\s*(?:ft|feet|')\s*(?:\d+(?:\.\d+)?\s*(?:in|\"))?\b",
    r"\b\d+(?:\.\d+)?\s*(?:in|\"|inch|inches)\b",
]


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


def extract_floorplan_text_and_dimensions(image_path: str) -> dict:
    image_file = Path(image_path)
    if not image_file.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

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
            "[OCR] Tesseract binary not found — OCR skipped, dimensions will be empty.",
            stacklevel=2,
        )
        return _ocr_skip_result(image_file, "tesseract_not_found")
    except pytesseract.TesseractError as exc:
        warnings.warn(
            f"[OCR] Tesseract error processing image — OCR skipped: {exc}",
            stacklevel=2,
        )
        return _ocr_skip_result(image_file, "tesseract_error")
    dimensions = _extract_dimensions(text)

    return {
        "image_path": str(image_file.resolve()),
        "text": text,
        "dimensions": dimensions,
        "dimension_count": len(dimensions),
    }
