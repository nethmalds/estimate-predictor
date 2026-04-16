from domain.floorplan_processing.pipeline import run_floorplan_pipeline


def execute_floorplan_pipeline(image_path: str) -> dict:
	return run_floorplan_pipeline(image_path)
