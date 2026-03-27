import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedBSRItem:
    item_no: str
    description: str
    unit: str
    rate: float
    category: str
    work_type: str | None = None
    material_type: str | None = None
    method: str | None = None
    constraints: str | None = None
    metadata: dict | None = None


_WORK_TYPE_KEYWORDS = {
    "excavation": ["excavation", "earth work", "trench", "digging"],
    "concrete": ["concrete", "pcc", "rcc", "mix"],
    "masonry": ["masonry", "brick work", "block work", "stone masonry"],
    "plaster": ["plaster", "rendering"],
    "reinforcement": ["reinforcement", "rebar", "steel bar"],
    "flooring": ["flooring", "tiles", "paving"],
}

_MATERIAL_KEYWORDS = {
    "ordinary soil": ["ordinary soil"],
    "hard soil": ["hard soil"],
    "rock": ["rock", "boulder"],
    "m20 concrete": ["m20"],
    "m25 concrete": ["m25"],
    "brick": ["brick", "class 1 brick", "class i brick"],
}

_METHOD_KEYWORDS = {
    "manual": ["manual", "hand", "labour"],
    "machine": ["machine", "mechanical", "excavator", "jcb"],
    "ready-mix": ["rmc", "ready mix", "ready-mix"],
}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _detect_label(description: str, lookup: dict[str, list[str]]) -> str | None:
    lowered = description.lower()
    for label, keywords in lookup.items():
        if any(keyword in lowered for keyword in keywords):
            return label
    return None


def _extract_constraints(description: str) -> str | None:
    parts: list[str] = []

    depth_match = re.search(r"depth\s*(?:of|up to|exceeding)?\s*([\d.]+\s*(?:m|mm|cm))", description, re.IGNORECASE)
    if depth_match:
        parts.append(f"depth:{depth_match.group(1)}")

    thickness_match = re.search(r"thickness\s*(?:of)?\s*([\d.]+\s*(?:m|mm|cm))", description, re.IGNORECASE)
    if thickness_match:
        parts.append(f"thickness:{thickness_match.group(1)}")

    floor_match = re.search(r"(ground floor|first floor|basement|upper floor)", description, re.IGNORECASE)
    if floor_match:
        parts.append(f"floor:{floor_match.group(1).lower()}")

    return ", ".join(parts) if parts else None


def _parse_row(raw_row: list[str]) -> ParsedBSRItem | None:
    cells = [_clean_text(cell) for cell in raw_row if cell and _clean_text(cell)]
    if len(cells) < 5:
        return None

    item_no = cells[0]
    unit = cells[-2]
    rate_token = cells[-1].replace(",", "")

    try:
        rate = float(re.findall(r"[\d.]+", rate_token)[0])
    except (ValueError, IndexError):
        return None

    description = " ".join(cells[1:-2])
    work_type = _detect_label(description, _WORK_TYPE_KEYWORDS)
    material_type = _detect_label(description, _MATERIAL_KEYWORDS)
    method = _detect_label(description, _METHOD_KEYWORDS)

    category = work_type or "general"

    return ParsedBSRItem(
        item_no=item_no,
        description=description,
        unit=unit,
        rate=rate,
        category=category,
        work_type=work_type,
        material_type=material_type,
        method=method,
        constraints=_extract_constraints(description),
        metadata={"parser": "pdf_table"},
    )


def parse_bsr_pdf(pdf_path: str) -> list[dict]:
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("pdfplumber is required for parsing PDF. Install with: pip install pdfplumber") from exc

    parsed_items: list[ParsedBSRItem] = []

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    parsed = _parse_row(row or [])
                    if parsed:
                        parsed_items.append(parsed)

    dedup: dict[str, ParsedBSRItem] = {}
    for item in parsed_items:
        dedup[item.item_no] = item

    return [
        {
            "item_no": item.item_no,
            "description": item.description,
            "unit": item.unit,
            "rate": item.rate,
            "category": item.category,
            "work_type": item.work_type,
            "material_type": item.material_type,
            "method": item.method,
            "constraints": item.constraints,
            "metadata": item.metadata,
        }
        for item in dedup.values()
    ]
