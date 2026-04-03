from pipelines.estimation_pipeline import run_estimation_pipeline


def run_estimation_workflow(
    description: str,
    floorplan_image_path: str | None = None,
    provided_parameters: dict | None = None,
) -> dict:
    return run_estimation_pipeline(
        description,
        floorplan_image_path=floorplan_image_path,
        provided_parameters=provided_parameters,
    )
