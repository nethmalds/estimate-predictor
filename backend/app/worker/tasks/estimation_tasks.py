from application.pipelines.estimation_pipeline import run_estimation_pipeline


def run_estimation_task(description: str) -> dict:
    return run_estimation_pipeline(description)
