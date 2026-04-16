from application.pipelines.estimation_pipeline import run_estimation_pipeline


def run_estimation_workflow(
    description: str,
    floorplan_image_url: str | None = None,
) -> dict:
    return run_estimation_pipeline(
        description,
        floorplan_image_url=floorplan_image_url,
    )
