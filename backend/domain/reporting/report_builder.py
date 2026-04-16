def build_report(payload: dict) -> dict:
	return {
		"summary": {
			"total": payload.get("costs", {}).get("total"),
			"confidence": payload.get("confidence", {}).get("score"),
		},
		"details": payload,
	}
