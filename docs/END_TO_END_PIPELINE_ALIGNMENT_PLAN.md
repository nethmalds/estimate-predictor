# End-to-End Pipeline Alignment Plan

## Objective

Align the current full-stack construction estimation system with the target process described for the project.

The target behavior is treated as the strict implementation spec for this plan. Where the current system behaves differently, this plan treats that difference as implementation work rather than a design alternative.

The aligned system must support the following flow:

1. Collect structured project data through a multi-step wizard.
2. Enforce frontend and backend validation before processing begins.
3. Preprocess and normalize inputs into a stable backend contract.
4. Run optional floorplan CV extraction behind an explicit acceptance boundary.
5. Generate BOQ items using the sequence `baseline LLM -> Model A additions -> final reconciliation`.
6. Validate generated BOQ items before BSR retrieval.
7. Match BOQ items against BSR data and validate the retrieved result before quantity take-off.
8. Estimate quantities using geometry and Model B when floorplans are accepted, or parametric rules and Model B otherwise.
9. Reconcile valid quantity sources using the arithmetic mean, then apply unit-aware rounding and validation.
10. Compute costs with explicit subtotals, preliminaries, contingencies, and external works treatment.
11. Produce a transparent confidence and audit model covering all estimation stages.
12. Generate a backend-owned structured report and downloadable artifact.
13. Persist the enriched result so dashboard and estimate detail surfaces reflect the same data produced by the pipeline.

## Scope

This plan covers the full estimation workflow across frontend and backend.

Included:

- Frontend wizard collection, validation, review, submission, and results rendering.
- Backend request schema, normalization, validation, orchestration, persistence, and reporting.
- Floorplan CV path and fallback behavior.
- BOQ generation, validation, BSR matching, quantity generation, pricing, confidence, and report generation.
- Dashboard and estimate detail alignment with persisted outputs.
- Runtime and verification work needed to prove the aligned flow works end to end.

Excluded:

- Retraining or replacing `item_predictor.joblib`.
- Retraining or replacing `quantity_predictor.joblib`.
- Broad platform work unrelated to the estimation workflow.
- PDF report generation in the first alignment slice unless a real backend generator is added and verified.

## Current Gap Summary

The current implementation already contains the major pipeline pieces, but several parts diverge from the target process.

1. The frontend wizard performs local step validation, but the backend validation endpoint is not used as a first-class pre-submit gate.
2. Normalization and preprocessing preserve some provenance, but not enough to support a full transparency model.
3. The floorplan path computes confidence but does not use a clear accept or reject boundary before downstream estimation.
4. BOQ generation still runs the predictor before the baseline LLM stage.
5. Generated BOQ validation is shallower than the rule set implied by the tests and target process.
6. The pipeline does not have a strong post-RAG validation boundary for BSR-enriched items.
7. Quantity reconciliation currently uses weighted fusion rather than the target arithmetic mean.
8. External works are not surfaced as a clearly traceable subtotal-driven pricing concern.
9. The backend reporting layer is lightweight, while downloadable Excel generation currently lives in the frontend.
10. Persisted estimate surfaces do not yet expose the full audit and transparency data the target process requires.

## Locked Decisions

The following decisions are fixed for this plan:

1. The target narrative is the authoritative behavior.
2. Scope is full stack, not backend-only.
3. The current wizard contract remains focused on `residential`, `commercial`, and `industrial` projects in this slice.
4. `item_predictor.joblib` remains Model A.
5. `quantity_predictor.joblib` remains Model B.
6. Quantity reconciliation must use arithmetic mean across valid sources when two valid sources are available.
7. External works must become explicit BOQ-driven cost items with visible pricing impact.
8. The backend must own the structured report and the first downloadable artifact.
9. Excel is the first required backend-generated downloadable artifact.
10. Existing plan documents for BOQ alignment, floorplan ownership, and runtime stabilization should be reused rather than duplicated.

## Related Existing Plans To Reuse

This plan should absorb and reuse the relevant work already defined in these documents:

- `BOQ_REFINEMENT_LOOP_ALIGNMENT_PLAN.md`
- `FLOORPLAN_PROCESS_BOUNDARY_UPGRADE_PLAN.md`
- `FRONTEND_BACKEND_RUNTIME_STABILIZATION_PLAN.md`

Those plans should be treated as sub-plans that feed this end-to-end alignment effort.

## Implementation Phases

### Phase 0 - Freeze the Canonical Contract

Purpose:

- Prevent drift across frontend, backend, persistence, and reporting before service changes begin.

Work:

- Define the authoritative wizard payload.
- Define the normalized `project_info` structure.
- Define the floorplan audit and acceptance payload.
- Define the generated BOQ item contract.
- Define the BSR-enriched BOQ item contract.
- Define the quantity audit and reconciliation contract.
- Define the cost breakdown and subtotal contract.
- Define the confidence and transparency payload.
- Define the final report payload.
- Define one canonical source of truth for enum values and validation constraints shared by frontend and backend.

Deliverables:

- Stable request and response contracts for the full estimation flow.
- Shared enum and validation reference used by both sides.

Exit criteria:

- Frontend types, backend request models, and persisted result structures all target the same canonical contract.

### Phase 1 - Align Intake, Validation, and Review

Purpose:

- Make the structured wizard behave like the target system before the pipeline is invoked.

Work:

- Keep step-level client validation for responsiveness.
- Add backend validation as an explicit pre-submit gate before estimation begins.
- Surface backend-derived field errors, logical consistency errors, and acceptable-range violations on the review screen.
- Surface defaults and assumptions that will be applied after submission.
- Ensure the review screen reflects exactly what will be sent to the backend.

Primary files:

- `frontend/src/app/estimate/new/page.tsx`
- `frontend/src/components/wizard/steps/ProjectBasicsStep.tsx`
- `frontend/src/components/wizard/steps/ConstructionDetailsStep.tsx`
- `frontend/src/components/wizard/steps/ReviewSubmitStep.tsx`
- `frontend/src/services/estimation.ts`
- `backend/app/api/controllers/form_controller.py`
- `backend/services/clarification_process/clarification_agent.py`

Deliverables:

- Review step with backend-informed validation feedback.
- Stable and consistent validation messages across frontend and backend.

Exit criteria:

- The wizard cannot start estimation with invalid or logically inconsistent data.

### Phase 2 - Strengthen Preprocessing and Normalization

Purpose:

- Ensure downstream services receive complete, explicit, and audit-friendly normalized inputs.

Work:

- Preserve derived totals and compatibility mappings.
- Preserve explicit user input provenance.
- Preserve preprocessing warnings and completeness signals.
- Make normalization failures explicit rather than relying on downstream services to infer around missing inputs.
- Ensure persisted estimate records can store the normalized project context and related audit fields.

Primary files:

- `backend/services/clarification_process/clarification_agent.py`
- `backend/app/api/controllers/form_controller.py`
- `backend/infrastructure/data_layer/database/models/estimate.py`

Deliverables:

- Stable normalized `project_info` contract.
- Preprocessing warnings and provenance fields available for transparency and persistence.

Exit criteria:

- All downstream stages consume one normalized and audit-friendly input model.

### Phase 3 - Add a Floorplan Acceptance Boundary

Purpose:

- Prevent low-quality floorplan extraction from silently contaminating downstream estimation.

Work:

- Reuse the floorplan service boundary direction in the dedicated floorplan plan.
- Add validation for OCR confidence.
- Add validation for detection confidence.
- Add validation for geometric completeness.
- Add validation for dimensional realism.
- Add validation for unit consistency and scale confidence.
- Introduce an explicit `accepted`, `rejected`, or `fallback_to_structured_only` outcome.
- Preserve rejection reasons and confidence breakdown in the final result.

Primary files:

- `backend/services/floorplan_process/service.py`
- `backend/services/floorplan_process/orchestrator.py`
- `backend/services/floorplan_process/confidence_scorer.py`
- `backend/application/pipelines/estimation_pipeline.py`

Deliverables:

- Accepted floorplan geometry contract.
- Rejection and fallback contract with audit reasons.

Exit criteria:

- Downstream BOQ and quantity stages only use floorplan geometry that passed the acceptance boundary.

### Phase 4 - Align BOQ Generation To the Target Refinement Loop

Purpose:

- Make BOQ generation match the intended baseline, Model A augmentation, and reconciliation sequence.

Work:

- Reorder BOQ orchestration to `baseline -> predictor additions -> reconciliation`.
- Keep predictor output as additional-item suggestions, not the initial source of BOQ guidance.
- Preserve provenance metadata for every final BOQ item.
- Update prompts and LLM client contracts to reflect the new stage order.
- Ensure final BOQ items retain validation-friendly metadata.

Primary files:

- `backend/services/item_gen_process/boq_builder.py`
- `backend/services/item_gen_process/item_predictor.py`
- `backend/services/item_gen_process/llm_client.py`
- `backend/infrastructure/integrations/prompt_templates/generate_baseline_boq.txt`
- `backend/infrastructure/integrations/prompt_templates/gap_fill_boq_items.txt`

Deliverables:

- Reordered BOQ generation flow.
- Stable provenance contract for final BOQ items.

Exit criteria:

- BOQ generation executes in the target order and produces validation-ready items.

### Phase 5 - Add Pre-RAG and Post-RAG Validation Boundaries

Purpose:

- Catch invalid generated BOQ items before retrieval and invalid retrieved BOQ items before quantity estimation.

Work:

- Split generated-item validation from later-stage validation responsibilities.
- Add generated BOQ validation immediately after reconciliation.
- Validate description, category, section, preferred unit, provenance, preliminaries presence, completeness heuristics, and scope conflicts.
- Add BSR retrieval validation immediately after RAG matching.
- Validate code, description, unit, rate, and match readiness before quantity take-off.
- Introduce an explicit manual-review path for items that cannot proceed safely.

Primary files:

- `backend/services/validation/boq_validator.py`
- `backend/services/rag_process/service.py`
- `backend/services/rag_process/matcher.py`
- `backend/application/pipelines/estimation_pipeline.py`

Deliverables:

- Pre-RAG generated-item validator.
- Post-RAG retrieval validator.
- Explicit review policy for unmatched or unusable items.

Exit criteria:

- Invalid BOQ items are stopped before BSR lookup, and unusable BSR results are stopped before quantity take-off.

### Phase 6 - Align Quantity Reconciliation To the Target Rule

Purpose:

- Make quantity estimation match the target hybrid method exactly.

Work:

- Replace weighted candidate fusion as the source of final reconciled quantity.
- When floorplan geometry is accepted, use geometry-derived and Model B quantities together.
- When floorplan geometry is unavailable or rejected, use parametric and Model B quantities together.
- When two valid sources exist, compute the arithmetic mean.
- When only one valid source exists, use a documented fallback policy.
- Apply unit-aware rounding for discrete units after reconciliation.
- Retain anomaly and dimensionality validation.
- Update quantity confidence and source summaries to explain source availability and validation outcomes.

Primary files:

- `backend/services/quantity_gen_process/service.py`
- `backend/services/quantity_gen_process/confidence_scoring.py`
- `backend/services/quantity_gen_process/quantity_calculator.py`
- `backend/services/validation/quantity_validator.py`

Deliverables:

- Arithmetic-mean quantity reconciliation.
- Post-mean rounding and validation policy.

Exit criteria:

- Final quantities match the target reconciliation rule and remain unit-safe.

### Phase 7 - Make Pricing and External Works Explicit

Purpose:

- Ensure the pricing layer is traceable and structurally aligned with the target reporting requirements.

Work:

- Keep preliminaries and contingencies as explicit pricing adjustments.
- Make `external_works_scope` produce traceable BOQ-driven items rather than prompt-only behavior.
- Add an explicit external works subtotal.
- Validate line-item cost consistency.
- Validate category subtotal consistency.
- Validate external works subtotal consistency.
- Validate grand total consistency.

Primary files:

- `backend/services/pricing_process/cost_calculator.py`
- `backend/services/item_gen_process/boq_builder.py`
- `backend/application/pipelines/estimation_pipeline.py`

Deliverables:

- Explicit pricing breakdown with external works visibility.
- Final pricing validation stage.

Exit criteria:

- The result contains traceable subtotals and validated totals that match the target process.

### Phase 8 - Rebuild Transparency and Confidence Around a Stage-Level Audit Model

Purpose:

- Produce a transparency layer that explains how the estimate was built and why its confidence score is what it is.

Work:

- Replace the lightweight source summary with a richer audit model.
- Record structured input provenance.
- Record applied defaults and assumptions.
- Record floorplan extraction and acceptance outcomes.
- Record Model A additions and reconciliation provenance.
- Record BSR match type, confidence, and review state.
- Record quantity source pairs, arithmetic-mean reconciliation, and validation outcomes.
- Record pricing validations and final warnings.
- Refactor confidence scoring so bonuses and penalties map to explicit audit facts.

Primary files:

- `backend/services/validation/confidence_scoring.py`
- `backend/services/reporting_process/source_summarizer.py`
- `backend/services/reporting_process/report_builder.py`
- `backend/application/pipelines/estimation_pipeline.py`

Deliverables:

- Stable audit schema.
- Confidence payload with explainable reasons and stage-level evidence.

Exit criteria:

- Every major estimation stage contributes explicit trace data to the final result and report.

### Phase 9 - Move Report Generation To the Backend

Purpose:

- Make reporting a backend responsibility rather than a frontend reconstruction of the pipeline output.

Work:

- Expand the backend reporting package so it owns the structured report payload.
- Add backend-generated Excel report creation as the first downloadable artifact.
- Stop generating the downloadable report directly in the frontend.
- Change the frontend to render backend-supplied report content and consume backend-generated downloads.

Primary files:

- `backend/services/reporting_process/report_builder.py`
- `backend/services/reporting_process/service.py`
- `frontend/src/components/results/ResultsComponents.tsx`
- `frontend/src/app/estimate/new/page.tsx`
- `frontend/src/app/estimates/[id]/EstimateDetailClient.tsx`

Deliverables:

- Backend-owned structured report.
- Backend-generated Excel artifact.
- Frontend report rendering that consumes backend outputs only.

Exit criteria:

- The frontend no longer reconstructs the official report or export on its own.

### Phase 10 - Align Persistence, Dashboard, and Estimate Detail Surfaces

Purpose:

- Make persisted estimate surfaces reflect the enriched output produced by the aligned pipeline.

Work:

- Persist the richer result, audit, and report fields.
- Expose floorplan acceptance status in persisted estimate detail.
- Expose BSR review items and warnings.
- Expose quantity method and confidence summaries.
- Expose pricing breakdown and transparency fields.
- Update dashboard summaries to use persisted aligned outputs.

Primary files:

- `backend/app/api/controllers/estimates_controller.py`
- `backend/infrastructure/data_layer/database/models/estimate.py`
- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/estimates/[id]/EstimateDetailClient.tsx`

Deliverables:

- Persisted estimate contract aligned with the final pipeline output.
- Dashboard and detail pages that reflect the aligned result.

Exit criteria:

- A streamed estimate and a persisted estimate show the same essential data and transparency fields.

### Phase 11 - Add Verification Coverage and Runtime Gates

Purpose:

- Make the aligned system verifiable and releasable.

Work:

- Add unit tests for wizard validation and normalization.
- Add tests for BOQ orchestration order and generated-item validation.
- Add tests for floorplan acceptance and fallback behavior.
- Add tests for arithmetic-mean quantity reconciliation and discrete rounding.
- Add tests for pricing consistency and external works visibility.
- Add tests for backend report generation.
- Run runtime readiness checks including migrations and backend startup.
- Run one no-floorplan end-to-end submission.
- Run one floorplan end-to-end submission.
- Verify SSE completion, persistence, dashboard visibility, estimate detail rendering, and backend-generated report download.

Primary files:

- `backend/tests/unit/test_clarification_agent_validate.py`
- `backend/tests/unit/test_clarification_agent_normalize.py`
- `backend/tests/unit/test_form_controller_schema.py`
- `backend/tests/unit/test_item_predictor_rules.py`
- `backend/tests/unit/test_floorplan_merge.py`
- `backend/tests/unit/test_boq_generated_validator.py`

Deliverables:

- Focused regression coverage for the aligned flow.
- Runtime release gate for the full estimation path.

Exit criteria:

- The aligned flow is covered by focused tests and verified by runtime checks.

## Relevant Files

### Frontend

- `frontend/src/app/estimate/new/page.tsx`
- `frontend/src/components/wizard/steps/ProjectBasicsStep.tsx`
- `frontend/src/components/wizard/steps/ConstructionDetailsStep.tsx`
- `frontend/src/components/wizard/steps/ReviewSubmitStep.tsx`
- `frontend/src/types/wizard.ts`
- `frontend/src/services/estimation.ts`
- `frontend/src/components/results/ResultsComponents.tsx`
- `frontend/src/app/estimates/[id]/EstimateDetailClient.tsx`
- `frontend/src/app/dashboard/page.tsx`

### Backend

- `backend/app/api/controllers/form_controller.py`
- `backend/services/clarification_process/clarification_agent.py`
- `backend/application/pipelines/estimation_pipeline.py`
- `backend/services/floorplan_process/service.py`
- `backend/services/floorplan_process/orchestrator.py`
- `backend/services/floorplan_process/confidence_scorer.py`
- `backend/services/item_gen_process/boq_builder.py`
- `backend/services/item_gen_process/item_predictor.py`
- `backend/services/item_gen_process/llm_client.py`
- `backend/infrastructure/integrations/prompt_templates/generate_baseline_boq.txt`
- `backend/infrastructure/integrations/prompt_templates/gap_fill_boq_items.txt`
- `backend/services/validation/boq_validator.py`
- `backend/services/rag_process/service.py`
- `backend/services/rag_process/matcher.py`
- `backend/services/quantity_gen_process/service.py`
- `backend/services/quantity_gen_process/confidence_scoring.py`
- `backend/services/quantity_gen_process/quantity_calculator.py`
- `backend/services/validation/quantity_validator.py`
- `backend/services/pricing_process/cost_calculator.py`
- `backend/services/validation/confidence_scoring.py`
- `backend/services/reporting_process/report_builder.py`
- `backend/services/reporting_process/source_summarizer.py`
- `backend/app/api/controllers/estimates_controller.py`
- `backend/infrastructure/data_layer/database/models/estimate.py`

### Tests and verification anchors

- `backend/tests/unit/test_clarification_agent_validate.py`
- `backend/tests/unit/test_clarification_agent_normalize.py`
- `backend/tests/unit/test_form_controller_schema.py`
- `backend/tests/unit/test_item_predictor_rules.py`
- `backend/tests/unit/test_floorplan_merge.py`
- `backend/tests/unit/test_boq_generated_validator.py`

## Verification Checklist

1. Confirm the canonical contract is represented consistently across frontend types, backend models, and persisted outputs.
2. Run focused backend validation and normalization tests.
3. Add and run BOQ alignment tests proving the target stage order.
4. Add and run floorplan acceptance and fallback tests.
5. Add and run quantity reconciliation tests proving arithmetic mean and discrete rounding behavior.
6. Add and run pricing and reporting tests proving explicit subtotals and backend-generated export behavior.
7. Run migration and backend startup readiness checks.
8. Execute one full submission without floorplans and one with floorplans.
9. Verify SSE progress and completion behavior.
10. Verify persistence into estimate detail and dashboard surfaces.
11. Verify backend-generated report download behavior.

## Acceptance Criteria

- The wizard enforces both frontend and backend validation before estimation begins.
- Preprocessing and normalization produce one stable backend input contract with provenance and audit fields.
- Floorplan geometry is only used when it passes an explicit acceptance boundary.
- BOQ generation runs in the order `baseline -> Model A additions -> reconciliation -> generated-item validation -> RAG -> retrieval validation`.
- Model A remains integrated through `item_predictor.joblib` without retraining.
- Model B remains integrated through `quantity_predictor.joblib` without retraining.
- Final quantity reconciliation uses arithmetic mean across valid source pairs.
- Discrete units are rounded using documented unit-aware rules after reconciliation.
- External works are traceable through explicit BOQ items and pricing subtotals.
- Confidence and transparency outputs explain methods, assumptions, validation outcomes, and data sources.
- The backend owns the structured report and the first downloadable Excel artifact.
- Persisted estimates expose the same essential outputs shown by the streaming completion flow.
- Focused tests and runtime verification prove the aligned flow works end to end.

## Risk Notes

1. Replacing weighted quantity fusion with arithmetic mean may require downstream confidence and reporting changes to preserve explanation quality.
2. Making external works explicit may require prompt, BOQ, and pricing changes together to avoid double counting.
3. Moving report generation to the backend will affect both streaming and persisted estimate views, so the contract must be frozen before implementation starts.
4. Floorplan acceptance thresholds should be introduced with narrow regression coverage because they change which branch the pipeline takes.
5. The existing runtime stabilization work should be treated as a prerequisite for reliable end-to-end verification.
