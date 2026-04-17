from application.pipelines.floorplan_pipeline import execute_floorplan_pipeline


def run_floorplan_task(image_path: str) -> dict:
    return execute_floorplan_pipeline(image_path)
