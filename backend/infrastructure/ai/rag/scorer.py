from infrastructure.ai.rag.retriever import QueryFeatures


def _keyword_score(query: QueryFeatures, candidate) -> tuple[float, list[str]]:
    score = 0.0
    matched_fields: list[str] = []

    description = candidate.description.lower()

    if query.material and query.material in description:
        score += 3
        matched_fields.append(f"material:{query.material}")

    if query.work_type and candidate.work_type and query.work_type == candidate.work_type.lower():
        score += 2
        matched_fields.append(f"work_type:{query.work_type}")

    if query.method and candidate.method and query.method == candidate.method.lower():
        score += 2
        matched_fields.append(f"method:{query.method}")

    if query.constraints and candidate.constraints:
        candidate_constraints = candidate.constraints.lower()
        if any(fragment.split(":", 1)[-1] in candidate_constraints for fragment in query.constraints):
            score += 1
            matched_fields.append("constraints")

    token_overlap = sum(1 for token in query.tokens if token in description)
    if token_overlap >= 3:
        score += 1
        matched_fields.append("partial_overlap")

    return score, matched_fields


def score_candidate(
    query: QueryFeatures,
    candidate,
    vector_score: float,
    vector_weight: float = 0.65,
    keyword_weight: float = 0.35,
) -> dict:
    raw_keyword, matched_fields = _keyword_score(query, candidate)
    keyword_score = min(raw_keyword / 9.0, 1.0)
    final_score = (vector_weight * vector_score) + (keyword_weight * keyword_score)

    return {
        "vector_score": round(vector_score, 4),
        "keyword_score": round(keyword_score, 4),
        "final_score": round(final_score, 4),
        "matched_fields": matched_fields,
    }
