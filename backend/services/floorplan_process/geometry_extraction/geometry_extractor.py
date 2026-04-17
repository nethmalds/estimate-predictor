def preprocess_image(image_path: str) -> dict:
    return {"image_path": image_path, "method": "basic_preprocess", "notes": "placeholder"}


def detect_openings(image_path: str) -> dict:
    return {"doors": 0, "windows": 0, "method": "placeholder"}


def extract_room_boundaries(image_path: str) -> dict:
    return {"rooms": [], "method": "placeholder"}
