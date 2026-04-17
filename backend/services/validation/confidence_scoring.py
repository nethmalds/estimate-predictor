def score_confidence(project_info: dict, floorplan_summary: dict | None = None, warnings: list[str] | None = None) -> dict:
    score = 0.7
    reasons: list[str] = []

    if floorplan_summary:
        score += 0.1
        reasons.append("floorplan_data")
    if project_info.get("parameters"):
        score += 0.1
        reasons.append("parameters_present")
    if warnings:
        score -= min(0.2, 0.05 * len(warnings))
        reasons.append("validation_warnings")

    score = max(0.0, min(score, 1.0))
    return {"score": score, "reasons": reasons}
