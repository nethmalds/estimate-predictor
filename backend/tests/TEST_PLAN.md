# Backend Test Plan

**Project:** Construction Cost Estimation Platform  
**Module:** FastAPI Backend  
**Version:** Current (`refactor/flow` branch)  
**Prepared by:** nethmalds  
**Date:** 2026-05-15  
**Environment:** Python 3.10.11, pytest 9.0.3, Windows 11

---

## Scope

This test plan covers the backend REST API, estimation pipeline, RAG matching service, BOQ generation, quantity calculation, cost calculation, and authentication middleware of the construction cost estimation platform.

---

## Test Environment Setup

| Requirement | Value |
|-------------|-------|
| Runtime | Python 3.10.11 |
| Framework | FastAPI + Uvicorn |
| Database | PostgreSQL (mocked in automated tests) |
| Vector DB | ChromaDB (mocked in automated tests) |
| LLM | Ollama (mocked in automated tests) |
| Run command | `pytest tests/ -v -m integration` |

---

## 1. Authentication & Authorization

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| BE-TC-001 | Authentication | Valid authenticated request accesses protected endpoint | 1. Obtain a valid JWT token. 2. Send `GET /api/estimates` with `Authorization: Bearer <token>` header. 3. Observe response. | Valid JWT token for an existing user | HTTP 200 with estimate list payload | HTTP 200 returned | ✅ Pass | |
| BE-TC-002 | Authentication | Request without Authorization header is rejected | 1. Send `GET /api/estimates` with no Authorization header. 2. Observe response. | No token | HTTP 401 Unauthorized | HTTP 401 returned | ✅ Pass | |
| BE-TC-003 | Authentication | Request with malformed token is rejected | 1. Send `GET /api/estimates` with `Authorization: Bearer invalid.token.here`. 2. Observe response. | Invalid JWT string | HTTP 401 Unauthorized | HTTP 401 returned | ✅ Pass | |
| BE-TC-004 | Authorization | User can only access their own estimates | 1. Authenticate as User A. 2. Create an estimate as User A. 3. Authenticate as User B. 4. Attempt `GET /api/estimates/{estimateId}` using User B's token. | Two distinct user accounts | HTTP 404 or HTTP 403 (estimate not visible across users) | Not Tested | ⚠️ Not Tested | Requires live DB with two seeded users |

---

## 2. Form Validation API — `POST /api/estimate-project/form/validate`

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| BE-TC-005 | Form Validation | Valid residential payload returns `valid: true` | 1. Send `POST /validate` with a complete residential payload. 2. Inspect `valid` and `errors` fields in response. | `building_type: residential`, `floor_count: 2`, `floor_areas: [{120 sqft}, {110 sqft}]`, `bedrooms: 3`, `bathrooms: 2`, all construction details filled | HTTP 200, `valid: true`, `errors: {}` | HTTP 200 returned but `valid: false` | ❌ Fail | Validation service appears to require additional fields not present in test fixture (schema drift) |
| BE-TC-006 | Form Validation | Missing required construction detail fields return errors | 1. Send `POST /validate` with payload omitting `finish_level` and `structural_system`. 2. Inspect response body. | Residential payload with `finish_level` and `structural_system` removed | HTTP 200, `valid: false`, errors list contains both missing field names | HTTP 200, `valid: false`, errors returned | ✅ Pass | |
| BE-TC-007 | Form Validation | `floor_count` below minimum triggers schema rejection | 1. Send `POST /validate` with `floor_count: 0`. 2. Observe response code. | `floor_count: 0` (violates `ge=1` constraint) | HTTP 422 Unprocessable Entity | HTTP 422 returned | ✅ Pass | |
| BE-TC-008 | Form Validation | `floor_count` above maximum triggers schema rejection | 1. Send `POST /validate` with `floor_count: 101`. 2. Observe response code. | `floor_count: 101` (violates `le=100` constraint) | HTTP 422 Unprocessable Entity | Not Tested | ⚠️ Not Tested | Schema constraint exists; not yet covered by a dedicated test case |
| BE-TC-009 | Form Validation | Commercial building without `primary_use_type` returns invalid | 1. Send `POST /validate` with `building_type: commercial`, all other fields filled, but `primary_use_type` omitted. 2. Inspect `valid` field. | `building_type: commercial`, `washroom_count: 2`, no `primary_use_type` | HTTP 200, `valid: false`, error references `primary_use_type` | HTTP 200, `valid: false` returned | ✅ Pass | |
| BE-TC-010 | Form Validation | Unknown building type triggers schema rejection | 1. Send `POST /validate` with `building_type: warehouse`. 2. Observe response code. | `building_type: "warehouse"` (not in allowed enum) | HTTP 422 Unprocessable Entity | HTTP 422 returned | ✅ Pass | |

---

## 3. Form Submission API — `POST /api/estimate-project/form/submit`

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| BE-TC-011 | Form Submission | Unauthenticated submit request is rejected | 1. Send `POST /submit` with a valid payload but no Authorization header. 2. Observe response. | Valid residential payload, no token | HTTP 401 Unauthorized | HTTP 401 returned | ✅ Pass | |
| BE-TC-012 | Form Submission | Payload with missing required fields returns 422 | 1. Send `POST /submit` with only `building_type` and `floor_count`, omitting `floor_areas`. 2. Observe response. | `{building_type: residential, floor_count: 1}` | HTTP 422 Unprocessable Entity | HTTP 422 returned | ✅ Pass | |
| BE-TC-013 | Form Submission | Valid payload starts pipeline and returns session ID | 1. Authenticate. 2. Send `POST /submit` with a complete residential payload. 3. Inspect response for `session_id` and `status`. | Complete residential payload with all required fields | HTTP 200, `session_id` present, `status: processing`, `estimate_id` present | HTTP 422 returned instead of 200 | ❌ Fail | Submit payload fixture is missing a newly required field. Inspect 422 response body to identify the field. |
| BE-TC-014 | Form Submission | Business validation failure on submit returns 422 | 1. Send `POST /submit` with a payload that passes Pydantic schema but fails business rules (e.g. residential with zero bedrooms). 2. Inspect response. | Residential payload with `bedrooms: 0` | HTTP 422, response body contains validation error detail | HTTP 422 returned | ✅ Pass | |
| BE-TC-015 | Form Submission | Duplicate submission within active session is handled | 1. Submit a valid form to get a session. 2. Immediately submit the same form again. 3. Observe whether the second submission is rejected or creates a new session. | Same valid payload submitted twice in quick succession | Second submission either returns 409 Conflict or creates a new independent session | Not Tested | ⚠️ Not Tested | Requires live async environment |

---

## 4. SSE Streaming API — `GET /api/estimate-project/form/stream/{session_id}`

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| BE-TC-016 | SSE Streaming | Unknown session ID returns 404 | 1. Authenticate. 2. Send `GET /stream/nonexistent-session-id`. 3. Observe response code. | `session_id: "nonexistent-session-id"` | HTTP 404 Not Found | HTTP 404 returned | ✅ Pass | |
| BE-TC-017 | SSE Streaming | Stream emits `progress` events during pipeline execution | 1. Submit a valid form to get a session ID. 2. Connect to the SSE stream for that session. 3. Collect all events until stream closes. | Valid session from a submitted form | Stream emits multiple `event: progress` messages with stage names and percentages | Not Tested | ⚠️ Not Tested | Requires live pipeline execution |
| BE-TC-018 | SSE Streaming | Stream emits `completed` event on pipeline success | 1. Submit a form. 2. Connect to SSE stream. 3. Wait for the final event. | Valid session | Final event is `event: completed` with full estimate data in payload | Not Tested | ⚠️ Not Tested | Requires live pipeline execution |
| BE-TC-019 | SSE Streaming | Stream emits `error` event on pipeline failure | 1. Submit a form that will cause a pipeline error. 2. Connect to SSE stream. 3. Observe events. | Payload triggering a pipeline exception | Stream emits `event: error` with an error message | Not Tested | ⚠️ Not Tested | Requires live pipeline |

---

## 5. Estimates Management API

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| BE-TC-020 | Estimates — List | Authenticated user retrieves their estimate list | 1. Authenticate. 2. Send `GET /api/estimates`. 3. Inspect response. | Valid auth token | HTTP 200, response body is an array (may be empty) | HTTP 200 with list returned | ✅ Pass | |
| BE-TC-021 | Estimates — List | Unauthenticated list request is rejected | 1. Send `GET /api/estimates` without a token. 2. Observe response. | No token | HTTP 401 Unauthorized | HTTP 401 returned | ✅ Pass | |
| BE-TC-022 | Estimates — List | Pagination parameters are respected | 1. Authenticate. 2. Send `GET /api/estimates?page=1&page_size=5`. 3. Verify no more than 5 items are returned. | `page=1`, `page_size=5` | HTTP 200, at most 5 estimate objects | HTTP 200 with correct count | ✅ Pass | |
| BE-TC-023 | Estimates — Detail | Existing estimate is returned by ID | 1. Authenticate. 2. Send `GET /api/estimates/{id}` for a known estimate. 3. Inspect the response body. | Valid `estimate_id` belonging to the authenticated user | HTTP 200, response includes `boq_items`, `costs`, `confidence` | HTTP 200 with full detail | ✅ Pass | |
| BE-TC-024 | Estimates — Detail | Non-existent estimate ID returns 404 | 1. Authenticate. 2. Send `GET /api/estimates/00000000-0000-0000-0000-000000000000`. 3. Observe response. | UUID that does not exist in the database | HTTP 404 Not Found | HTTP 404 returned | ✅ Pass | |
| BE-TC-025 | Estimates — Patch | Estimate fields can be updated | 1. Authenticate. 2. Send `PATCH /api/estimates/{id}` with `{"title": "Updated Title"}`. 3. Verify response contains updated value. | Valid estimate ID, `{"title": "Updated Title"}` | HTTP 200, response body reflects the updated title | HTTP 200 returned | ✅ Pass | |
| BE-TC-026 | Estimates — Patch | Patching a non-existent estimate returns 404 | 1. Authenticate. 2. Send `PATCH /api/estimates/00000000-0000-0000-0000-000000000000` with any body. | Non-existent UUID | HTTP 404 Not Found | HTTP 404 returned | ✅ Pass | |
| BE-TC-027 | Estimates — Delete | Authenticated user can delete their estimate | 1. Authenticate. 2. Send `DELETE /api/estimates/{id}` for an existing estimate. 3. Verify the estimate is gone. | Valid estimate ID belonging to the authenticated user | HTTP 204 No Content | HTTP 204 returned | ✅ Pass | |
| BE-TC-028 | Estimates — Delete | Deleting a non-existent estimate returns 404 | 1. Authenticate. 2. Send `DELETE /api/estimates/00000000-0000-0000-0000-000000000000`. | Non-existent UUID | HTTP 404 Not Found | HTTP 404 returned | ✅ Pass | |
| BE-TC-029 | Estimates — Dashboard | Dashboard endpoint returns summary statistics | 1. Authenticate. 2. Send `GET /api/estimates/dashboard`. 3. Inspect response for summary fields. | Valid auth token | HTTP 200, response includes aggregate statistics (total count, avg confidence, etc.) | HTTP 200 with summary returned | ✅ Pass | |
| BE-TC-030 | Estimates — Dashboard | Dashboard handles empty dataset gracefully | 1. Authenticate as a user with no estimates. 2. Send `GET /api/estimates/dashboard`. | User with zero estimates | HTTP 200, numeric fields default to 0 or null | HTTP 200 returned | ✅ Pass | |

---

## 6. BOQ Generation

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| BE-TC-031 | BOQ Generation | Residential project produces a non-empty BOQ item list | 1. Call `build_final_boq_items` with a standard residential `project_info`. 2. Assert the returned list has items. | `building_type: residential`, `floors: 2`, `built_up_area: 250 sqm` | List contains at least one BOQ item with `description`, `unit`, and `section` | Items generated as expected | ✅ Pass | Verified via `test_boq_builder.py` |
| BE-TC-032 | BOQ Generation | All generated BOQ items have required fields | 1. Generate a BOQ for a standard project. 2. Iterate over each item. 3. Assert `description`, `unit`, and `section` are non-null. | Standard residential input | Every item has `description`, `unit`, and `section` populated | All items have required fields | ✅ Pass | |
| BE-TC-033 | BOQ Generation | BOQ validator flags items with missing units | 1. Pass a BOQ item list where one item has `unit: null` to the validator. 2. Check the validation result. | `[{description: "Brick wall", unit: null, section: "Masonry"}]` | Validation result marks the item as invalid | Validation correctly flags item | ✅ Pass | Verified via `test_boq_generated_validator.py` |
| BE-TC-034 | BOQ Generation | Item predictor generates section-specific items for finish level | 1. Run the item predictor rule engine with `finish_level: luxury`. 2. Verify high-spec finish items are included. | `finish_level: luxury`, `building_type: residential` | BOQ includes luxury finish items not present in standard finish output | Not Tested | ⚠️ Not Tested | Rule logic exists but comparative test not written |

---

## 7. RAG BSR Matching

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| BE-TC-035 | RAG Matching | Regular BOQ item is matched against BSR database | 1. Call `match_boq_items_batch` with a standard BOQ item list. 2. Inspect each returned item for `bsr_item_no` and `match_confidence`. | `[{description: "Brick masonry wall", unit: "m2"}]` | Each non-contractual item has `bsr_item_no`, `rate`, and `match_confidence` ≥ 0 | Match fields present on all items | ✅ Pass | Verified via `test_rag_matcher.py` |
| BE-TC-036 | RAG Matching | Contractual items are excluded from rate matching | 1. Include an item with `category: preliminary_and_general` in the batch. 2. Call `match_boq_items_batch`. 3. Inspect the contractual item in the result. | `[{description: "Preliminaries", category: "preliminary_and_general"}]` | Contractual item is flagged but not assigned a BSR rate; `is_contractual: true` | Contractual items skipped correctly | ✅ Pass | Verified via `test_rag_matcher.py` |
| BE-TC-037 | RAG Matching | Query normalisation lowercases and strips special characters | 1. Call `normalize_query` with a mixed-case string containing punctuation. 2. Assert the output is lowercase with punctuation removed. | `"Brick Masonry (M25) @ Ground Floor!"` | `"brick masonry m25 ground floor"` | Normalisation correct | ✅ Pass | Verified via `test_rag_retriever.py` |
| BE-TC-038 | RAG Matching | Scorer assigns higher score to items with matching work type | 1. Score two candidates against a query with `work_type: masonry`. 2. Candidate A has `work_type: masonry`, Candidate B has `work_type: concrete`. | Work type matches for candidate A only | Candidate A score > Candidate B score | Scoring differential correct | ✅ Pass | Verified via `test_rag_scorer.py` |
| BE-TC-039 | RAG Matching | Confidence score is bounded between 0 and 1 | 1. Run the scorer on multiple candidate pairs. 2. Assert every `final_score` is in [0.0, 1.0]. | Various candidate inputs with extreme weights | All scores in range [0.0, 1.0] | All scores within bounds | ✅ Pass | Verified via `test_rag_scorer.py` |

---

## 8. Quantity Estimation

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| BE-TC-040 | Quantity Estimation | Quantities are derived from floor area inputs | 1. Run `compute_quantities` with a project having `built_up_area: 250 sqm`. 2. Inspect returned quantities. | `built_up_area: 250`, `floors: 2` | Each BOQ item has a `quantity` value proportional to the floor area | Not Tested | ⚠️ Not Tested | Unit not yet written for `quantity_calculator.py` |
| BE-TC-041 | Quantity Estimation | Quantity reconciliation resolves conflicts between sources | 1. Call the reconciliation function with overlapping quantities from two sources. 2. Inspect which value is retained. | Two sources providing different quantities for the same item | Conflict resolved using defined priority rule (e.g. CV source > rule-based) | Reconciliation works correctly | ✅ Pass | Verified via `test_quantity_reconciliation.py` |
| BE-TC-042 | Quantity Estimation | Anomalous quantities are flagged in validation | 1. Pass a quantity list where one item has `quantity: -5` to the validator. 2. Inspect the validation output. | `[{quantity: -5, unit: "m2"}]` | Validation flags the item as anomalous | Not Tested | ⚠️ Not Tested | `quantity_validator.py` has 9% coverage |

---

## 9. Cost Calculation

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| BE-TC-043 | Cost Calculation | Total cost includes base, preliminaries, and contingencies | 1. Call `calculate_costs` with a priced BOQ. 2. Verify `total = base_total + preliminaries + contingencies`. | BOQ with known rates and quantities | `total` = sum of all cost components | Not Tested | ⚠️ Not Tested | `cost_calculator.py` has 8% coverage |
| BE-TC-044 | Cost Calculation | Cost subtotals are provided per section | 1. Call `calculate_costs` with items in at least two sections. 2. Inspect `subtotals` in the result. | Items in `Masonry` and `Concrete` sections | `subtotals` dict contains an entry per section with a non-zero sum | Not Tested | ⚠️ Not Tested | |
| BE-TC-045 | Cost Calculation | Zero-quantity item contributes zero cost | 1. Include an item with `quantity: 0` in the BOQ. 2. Verify its `cost` in the output. | `{quantity: 0, rate: 2500}` | `cost: 0` for that item | Not Tested | ⚠️ Not Tested | |

---

## 10. Full Estimation Pipeline

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| BE-TC-046 | Pipeline | Pipeline output contains all required top-level keys | 1. Run `run_estimation_pipeline_from_project_info` with all external services mocked. 2. Inspect the returned dict. | Standard residential `project_info`, empty `floorplan_urls` | Output contains `boq_items`, `costs`, `confidence`, `report`, `floorplan` | All keys present in output | ✅ Pass | |
| BE-TC-047 | Pipeline | Confidence score in output is within valid range | 1. Run pipeline with mocked services returning `confidence.score: 0.83`. 2. Assert value is in [0.0, 1.0]. | Mocked `score: 0.83` | `confidence.score` between 0.0 and 1.0 | `0.83` returned, within range | ✅ Pass | |
| BE-TC-048 | Pipeline | No BOQ item in output has null description or unit | 1. Run pipeline. 2. Iterate over `boq_items`. 3. Assert `description` and `unit` are non-null for each. | Standard residential input | All items have non-null `description` and `unit` | No null fields found | ✅ Pass | |
| BE-TC-049 | Pipeline | `costs.total` is present and positive | 1. Run pipeline with mocked costing returning a known total. 2. Assert `total > 0`. | Mocked costs with `total: 113000` | `costs.total` is present and > 0 | `costs.total` correct | ✅ Pass | |
| BE-TC-050 | Pipeline | `floorplan.available` is false when no URLs supplied | 1. Run pipeline with `floorplan_urls: []`. 2. Check `floorplan.available` in output. | `floorplan_urls: []` | `floorplan.available: false` | `floorplan.available: false` returned | ✅ Pass | |
| BE-TC-051 | Pipeline | Pre-set cancel event raises `PipelineCancelledError` | 1. Create a `threading.Event` and set it. 2. Pass it as `cancel_event` to the pipeline. 3. Expect `PipelineCancelledError` to be raised. | Cancel event set before pipeline starts | `PipelineCancelledError` raised, pipeline does not complete | `PipelineCancelledError` raised correctly | ✅ Pass | |
| BE-TC-052 | Pipeline | Progress callback receives all major stage events | 1. Run pipeline with a callback that records `(stage, status)` tuples. 2. Assert key stages are present in the collected list. | Standard residential input, empty callback list | Callback called with `baseline_boq`, `bsr_matching`, `cost_calculation` stages | All three stage events received | ✅ Pass | |

---

## Known Failures

| Test Case ID | Failure Description | Root Cause | Action |
|---|---|---|---|
| BE-TC-005 | Validate endpoint returns `valid: false` for a complete residential payload | Validation service added new required fields after the test fixture was written | Run the endpoint manually with `-s` flag, inspect which fields are now enforced, update the fixture |
| BE-TC-013 | Submit endpoint returns 422 for a valid payload | Submit Pydantic schema was extended with a new required field not present in the fixture | Inspect the 422 response `detail` array to find the missing field name |

---

## Summary

| Category | Total Cases | Pass | Fail | Not Tested |
|---|---|---|---|---|
| Authentication | 4 | 3 | 0 | 1 |
| Form Validation API | 6 | 4 | 1 | 1 |
| Form Submission API | 5 | 3 | 1 | 1 |
| SSE Streaming API | 4 | 1 | 0 | 3 |
| Estimates Management API | 11 | 11 | 0 | 0 |
| BOQ Generation | 4 | 3 | 0 | 1 |
| RAG BSR Matching | 5 | 5 | 0 | 0 |
| Quantity Estimation | 3 | 1 | 0 | 2 |
| Cost Calculation | 3 | 0 | 0 | 3 |
| Full Estimation Pipeline | 7 | 7 | 0 | 0 |
| **Total** | **52** | **38** | **2** | **12** |
