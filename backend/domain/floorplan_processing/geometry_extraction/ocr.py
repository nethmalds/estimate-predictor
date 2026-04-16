import re
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
    text = pytesseract.image_to_string(image, config="--psm 6")
    dimensions = _extract_dimensions(text)

    return {
        "image_path": str(image_file.resolve()),
        "text": text,
        "dimensions": dimensions,
        "dimension_count": len(dimensions),
    }
