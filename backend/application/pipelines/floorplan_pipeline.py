from services.floorplan_process.pipeline import run_floorplan_pipeline


def execute_floorplan_pipeline(image_path: str) -> dict:
	return run_floorplan_pipeline(image_path)
