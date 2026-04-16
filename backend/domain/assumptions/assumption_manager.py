def build_assumptions(project_info: dict, floorplan_summary: dict | None = None) -> list[str]:
	assumptions = list(project_info.get("assumptions") or [])
	if not project_info.get("parameters"):
		assumptions.append("Parameters were inferred with minimal context.")
	if not floorplan_summary:
		assumptions.append("No floorplan provided; quantities rely on parametric rules.")
	return assumptions
