# BOQ Refinement Loop Implementation Plan

## Objective

Align BOQ item generation with the intended multi-stage refinement flow:

1. Generate an initial BOQ item list with the LLM.
2. Use Model A (`item_predictor.joblib`) to identify additional relevant items.
3. Run a final LLM reconciliation pass over both lists.
4. Apply a BOQ validation layer before downstream RAG, quantity, and pricing stages.

## Current Gap

The current implementation only partially matches the target design.

- The predictor runs before the baseline LLM pass.
- The predictor does not compare its output against the initial LLM list.
- Validation runs after RAG and quantity take-off instead of immediately after final BOQ generation.
- Scope and conflict rules rely too heavily on prompt compliance and are not enforced in code at the correct boundary.

## Desired End State

After implementation, the BOQ flow should be:

`baseline LLM -> predictor additions -> final reconciliation -> BOQ validation -> RAG -> quantities -> pricing`

The generated BOQ item list should also preserve source provenance and be validated for structural integrity, scope fit, and completeness before later stages consume it.

## Scope

### In Scope

- Reordering BOQ item generation stages.
- Adding a predictor wrapper that filters to genuinely additional items.
- Updating LLM prompt and client contracts to match the new stage order.
- Adding a dedicated post-finalization BOQ validation layer.
- Preserving later validation for RAG-enriched and quantity-enriched fields.
- Adding focused tests for orchestration order, rule enforcement, and validation outcomes.

### Out of Scope

- Retraining or replacing `item_predictor.joblib`.
- Changing quantity prediction logic.
- Redesigning the RAG matching process.
- Changing pricing calculations outside validation handoff requirements.

## Implementation Phases

### Phase 1: Reorder Item Generation Flow

**Goal**  
Make the item generation order match the intended refinement loop.

**Changes**

- Update `backend/services/item_gen_process/boq_builder.py` so the first step is `generate_baseline_boq(project_info)`.
- Remove predictor hinting from the baseline generation stage if strict alignment to the intended flow is required.
- Call the predictor after the baseline list is available.
- Pass baseline items and predictor additions into the final reconciliation step.

**Deliverables**

- Updated `build_final_boq_items()` orchestration.
- Clear stage order in logs and progress reporting.

**Exit Criteria**

- BOQ item generation executes in the order `baseline -> predictor -> reconciliation`.

### Phase 2: Add Predictor Addition Wrapper

**Goal**  
Use Model A as an augmentation stage rather than as the initial source of BOQ guidance.

**Changes**

- Keep `predict_boq_items_with_confidence(project_info)` as the low-level adapter in `backend/services/item_gen_process/item_predictor.py`.
- Add a higher-level helper such as `predict_additional_boq_items(project_info, baseline_items)`.
- Normalize baseline descriptions and predictor descriptions before comparison.
- Return only predictor items that are genuinely missing from the baseline list.
- Preserve `source_confidence` and `predicted_category` metadata for later reconciliation and scoring.

**Deliverables**

- New predictor wrapper logic.
- Stable metadata contract for predictor-origin items.

**Exit Criteria**

- Predictor output passed into reconciliation contains additions only, not the full raw prediction set.

### Phase 3: Update LLM Contracts and Prompts

**Goal**  
Make the LLM stages reflect the new orchestration and data contracts.

**Changes**

- Update `backend/services/item_gen_process/llm_client.py` to match the new input flow.
- Update `backend/infrastructure/integrations/prompt_templates/generate_baseline_boq.txt` so baseline generation no longer depends on predictor hints.
- Update `backend/infrastructure/integrations/prompt_templates/gap_fill_boq_items.txt` so it explicitly consumes:
  - project info
  - baseline BOQ items
  - predictor additions
- Keep the reconciliation prompt focused on deduplication, conflict removal, standardization, and gap completion.

**Deliverables**

- Updated LLM client contract.
- Updated prompt templates for baseline and reconciliation stages.

**Exit Criteria**

- Baseline generation works independently.
- Reconciliation receives both input lists using an explicit contract.

### Phase 4: Preserve Provenance and Item Contract

**Goal**  
Ensure final BOQ items retain origin and validation-friendly metadata.

**Changes**

- Normalize source tagging in `backend/services/item_gen_process/boq_builder.py`.
- Preserve whether an item originated from baseline generation, predictor additions, or final reconciliation.
- Keep `preferred_unit`, `work_category`, `material_type`, and `source_confidence` available on the final generated item set.

**Deliverables**

- Stable generated-item contract for validation and downstream scoring.

**Exit Criteria**

- Final BOQ items preserve source provenance and required metadata consistently.

### Phase 5: Add Post-Finalization BOQ Validation Layer

**Goal**  
Validate the generated BOQ immediately after reconciliation and before downstream stages.

**Changes**

- Split responsibilities in `backend/services/validation/boq_validator.py`.
- Add a generated-item validator that runs immediately after final reconciliation and enrichment.
- Validate:
  - `description`
  - `category`
  - `section`
  - `preferred_unit`
  - source metadata
  - scope conflicts
  - completeness heuristics
  - required preliminaries
- Keep the existing later-stage validation for fields that depend on RAG or quantity results.

**Deliverables**

- New post-finalization BOQ validator.
- Clear separation between pre-RAG validation and later-stage validation.

**Exit Criteria**

- Invalid or conflicting BOQ outputs are identified before RAG and quantity take-off begin.

### Phase 6: Wire Validation into the Pipeline

**Goal**  
Move validation to the correct stage boundary without breaking later checks.

**Changes**

- Update `backend/application/pipelines/estimation_pipeline.py`.
- Run the new BOQ validator immediately after `build_final_boq_items()`.
- Keep later validation for RAG-enriched `unit`, quantity anomalies, and pricing-related checks.
- Rename validators if needed so stage responsibilities are explicit.

**Deliverables**

- Updated estimation pipeline with correct validation placement.

**Exit Criteria**

- The pipeline validates BOQ items before Stage 6 RAG matching.

### Phase 7: Encode High-Value Scope Rules in Code

**Goal**  
Reduce reliance on prompt-only enforcement for critical scope decisions.

**Changes**

- Add validator rules for:
  - roof and structure conflicts
  - soil and foundation conflicts
  - commercial versus residential contamination
  - industrial finish exclusions
  - mandatory preliminaries
- Decide the handling policy for each rule:
  - hard-fail for malformed or empty output
  - warn and annotate for recoverable scope or completeness issues

**Deliverables**

- Rule-based validation coverage for critical BOQ conflicts.
- Documented failure and warning policy.

**Exit Criteria**

- Critical BOQ conflicts are no longer enforced only through prompts.

### Phase 8: Add Test Coverage and Verification

**Goal**  
Prove the new flow works and remains stable.

**Changes**

- Add unit tests for orchestration order in `backend/services/item_gen_process/boq_builder.py`.
- Reuse patterns from `backend/tests/unit/test_item_predictor_rules.py` where appropriate.
- Add dedicated tests for:
  - flat slab versus asbestos roofing
  - normal soil versus pile foundation conflicts
  - commercial washroom completeness
  - industrial decorative finish exclusion
  - preliminaries presence
- Add one pipeline-level integration path with mocked LLM and RAG boundaries.

**Deliverables**

- BOQ builder tests.
- Validator tests.
- One integration test for stage sequencing.

**Exit Criteria**

- The new flow is covered by focused unit tests and at least one integration-level verification path.

## Files Affected

- `backend/services/item_gen_process/boq_builder.py`
- `backend/services/item_gen_process/item_predictor.py`
- `backend/services/item_gen_process/llm_client.py`
- `backend/infrastructure/integrations/prompt_templates/generate_baseline_boq.txt`
- `backend/infrastructure/integrations/prompt_templates/gap_fill_boq_items.txt`
- `backend/services/validation/boq_validator.py`
- `backend/application/pipelines/estimation_pipeline.py`
- `backend/tests/unit/test_item_predictor_rules.py`
- Additional BOQ builder and validator tests under `backend/tests/unit/`

## Acceptance Criteria

- The BOQ item generation flow runs in the order `baseline -> predictor additions -> final reconciliation -> validation -> RAG -> quantities`.
- Model A remains integrated through `item_predictor.joblib` without retraining.
- Final BOQ items preserve provenance and validation metadata.
- The generated-item validator runs before RAG matching.
- Critical scope conflicts are caught before quantity take-off.
- Focused unit and integration tests verify the new flow.

## Risks and Constraints

- Prompt changes may temporarily shift LLM output behavior.
- Rule-based validation may need maintenance if project schema values evolve.
- If the business later requires Model A itself to consume the baseline list directly, that will require a separate retraining effort.

## Verification Plan

1. Run a narrow unit test suite for BOQ builder, validator, and predictor behavior.
2. Run one pipeline-level integration path with mocked external dependencies.
3. Confirm flat-slab projects reject asbestos roofing before quantity take-off.
4. Confirm normal-soil projects reject pile foundations before quantity take-off.
5. Confirm generated-item validation uses `preferred_unit` before RAG, while later validation continues to verify `unit` after RAG.