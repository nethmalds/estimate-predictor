from services.floorplan_process.geometry_extraction.ocr import extract_floorplan_text_and_dimensions


class FloorPlanOCRService:
    def extract_dimensions(self, image_path: str) -> dict:
        return extract_floorplan_text_and_dimensions(image_path)


service = FloorPlanOCRService()
