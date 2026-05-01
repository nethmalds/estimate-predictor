from services.floorplan_process.service import run_pipeline


def run_floorplan_task(image_path: str) -> dict:
    return run_pipeline(image_path)
