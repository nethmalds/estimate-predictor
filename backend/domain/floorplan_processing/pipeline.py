from domain.floorplan_processing.geometry_extraction.geometry_extractor import (
    detect_openings,
    extract_room_boundaries,
    preprocess_image,
)
from domain.floorplan_processing.service import service


def run_floorplan_pipeline(image_path: str) -> dict:
    preprocess = preprocess_image(image_path)
    ocr_result = service.extract_dimensions(image_path)
    openings = detect_openings(image_path)
    rooms = extract_room_boundaries(image_path)
    dimensions = ocr_result.get("dimensions") or []
    summary = {
        "dimension_count": len(dimensions),
        "method": "ocr_dimensions" if dimensions else "ocr_text_only",
    }
    return {
        "preprocess": preprocess,
        "ocr": ocr_result,
        "openings": openings,
        "rooms": rooms,
        "summary": summary,
    }
