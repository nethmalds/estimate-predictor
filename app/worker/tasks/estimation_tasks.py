from orchestration.estimation_workflow import run_estimation_workflow


def run_estimation_task(description: str) -> dict:
    return run_estimation_workflow(description)
