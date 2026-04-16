from application.workflows.floorplan_workflow import run_floorplan_workflow


def run_floorplan_task(image_path: str) -> dict:
    return run_floorplan_workflow(image_path)
