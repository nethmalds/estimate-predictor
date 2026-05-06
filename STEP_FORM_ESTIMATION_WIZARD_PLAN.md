# Step Form Estimation Wizard Plan

## Goal

Replace the current chat-based clarification intake with a deterministic multi-step form that is easier for Quantity Surveyors to complete, easier for the frontend to validate, and more reliable for the backend to normalize into estimation inputs.

The new flow must:

- ask for building type first
- ask for floor count second
- collect one area input per floor immediately after floor count
- collect remaining project, construction, and QS-specific details in structured steps
- provide a review screen before estimation starts
- support `residential`, `commercial`, `industrial`, and `mixed_use` projects
- keep the current estimation pipeline working during migration by deriving a compatibility `built_up_area` value from the new floor-by-floor area model

## Why This Change Is Needed

The current intake flow is centered on a chat clarification loop. That creates several problems for structured estimation input:

- the flow is sequential and conversational instead of deterministic
- numeric and enum-heavy data collection is awkward in chat
- floor-by-floor area capture is not a first-class concept
- users cannot easily see overall completion progress
- review and editing are weak because corrections happen by re-answering chat questions or restarting the flow
- the backend clarification logic is currently biased toward residential assumptions
- the current model hides several cost-sensitive defaults instead of surfacing them explicitly
- the prompt layer and runtime enums already drift from each other, which makes the system less reliable as more fields are added

For a QS-oriented workflow, a structured form is a better primary intake surface than chat.

## Locked Product Decisions

The following decisions are already fixed for this plan:

1. The intake experience will be a step-by-step form, not a chat conversation.
2. The first step will always collect building type and floor count.
3. The second step will always collect one area input per floor.
4. The wizard must support all currently declared building types now, not only residential.
5. A review step is required before estimation begins.
6. `built_up_area` will become a derived compatibility field rather than the main source of truth.
7. `floor_areas` will become the richer primary area representation.
8. Explicit user-entered form values must override inferred LLM values.
9. The current chat clarification endpoints may remain temporarily for compatibility, but the new frontend path must not depend on them.
10. Any future post-draft clarification or low-confidence review should also be form-based rather than a return to chat.

## Current Constraints In The Existing Codebase

The current implementation has several constraints that this plan must address explicitly.

### Clarification flow constraints

- `backend/services/clarification_process/clarification_agent.py`
  - currently defines a residential-first question sequence
  - assumes fixed required fields
  - treats `bedrooms` and `bathrooms` as globally required parameters
  - applies several cost-sensitive defaults silently
- `backend/app/api/controllers/clarification_controller.py`
  - is built around session-based, SSE-driven question/answer progression
  - assumes incremental answer submission rather than structured form submission
- `backend/services/clarification_process/llm_client.py`
  - normalizes extracted values, but its schema hints are not fully aligned with runtime dropdown values

### Estimation pipeline constraints

- `backend/application/pipelines/estimation_pipeline.py`
  - expects normalized `project_info`
  - currently receives `built_up_area` as a string-like parameter, not a structured floor-area breakdown
- downstream quantity and validation logic contain residential assumptions
  - `backend/services/quantity_gen_process/rule_based_calculator.py`
  - `backend/services/quantity_gen_process/quantity_validator.py`
  - `backend/services/quantity_gen_process/quantity_calculator.py`
- item generation and reporting also contain residential fallback behavior
  - `backend/services/item_gen_process/item_predictor.py`
  - `backend/services/reporting_process/excel_generator.py`
  - `backend/services/reporting_process/report_builder.py`

### Frontend constraints

- `frontend/src/app/page.tsx`
  - is built around a chat UI, SSE question events, and conversational state
- `frontend/src/services/estimation.ts`
  - exposes chat/session style methods rather than wizard validation/submit methods
- `frontend/src/types/chat.ts`
  - encodes the current chat message contract rather than a form payload contract

## Target User Journey

The new estimation intake should follow a deterministic wizard sequence.

### Step 1 - Project Basics

Collect the following fields first:

- building type
- floor count
- optional project description
- optional floorplan image

This step is mandatory because it determines later branching behavior.

### Step 2 - Floor Areas

Generate one area row per floor based on the floor count from Step 1.

Each row should capture:

- floor label
- area numeric value
- area unit

The system should display a running derived total built-up area.

### Step 3 - Building Program

This step branches by building type.

Residential should ask for fields such as:

- bedrooms
- bathrooms
- key room or space list

Commercial should ask for fields such as:

- primary use type
- number of rentable or functional units where relevant
- washroom count
- service spaces or back-of-house spaces

Industrial should ask for fields such as:

- process or facility type
- loading, storage, utility, and admin area indicators
- operational zones or bays where relevant

Mixed-use should ask for fields such as:

- use mix composition
- approximate split of residential and non-residential usage
- any residential unit counts only if the mixed-use brief includes them

### Step 4 - Construction And Site Details

Collect the high-impact project-wide parameters that currently exist partly as defaults or clarification questions.

Recommended fields:

- finish level
- structural system
- roof type
- ceiling type
- location
- soil condition
- drainage type
- external works scope

### Step 5 - QS Specification Details

Collect estimate-sensitive QS inputs that are more specific than the current clarification flow.

Recommended fields:

- construction scope
- site access constraint
- concrete grade
- wall type
- floor finish specification
- sanitary fitting grade
- electrical scope level
- waterproofing requirement
- optional floor height if required for quantity refinement later

### Step 6 - Review And Submit

Show a review screen before estimation starts.

This screen must:

- summarize all steps
- show the derived total built-up area
- allow editing by section
- surface any remaining assumptions or defaults the backend will apply
- require explicit confirmation before estimation begins

## Target Information Architecture

The wizard should gather structured data in sections rather than as disconnected chat answers.

Recommended top-level grouping:

- project basics
- floor areas
- building program
- construction and site details
- QS specification details
- derived values
- metadata and provenance

This grouping should exist in the frontend state model and be normalized into the backend `project_info` model before the estimation pipeline runs.

## Canonical Wizard Payload

The exact implementation can vary, but the plan should converge on a payload conceptually shaped like this:

```json
{
  "building_type": "residential",
  "floor_count": 2,
  "description": "Optional free-text project description",
  "floorplan_image_url": "https://...",
  "floor_areas": [
    {
      "floor_key": "ground",
      "floor_label": "Ground Floor",
      "area_value": 1200,
      "area_unit": "sqft"
    },
    {
      "floor_key": "first",
      "floor_label": "First Floor",
      "area_value": 1100,
      "area_unit": "sqft"
    }
  ],
  "building_program": {
    "bedrooms": 3,
    "bathrooms": 2,
    "spaces": ["living room", "kitchen", "store", "balcony"]
  },
  "construction_details": {
    "finish_level": "standard",
    "structural_system": "framed",
    "roof_type": "rc_flat_slab",
    "ceiling_type": "gypsum_mineral_fibre",
    "location": "Colombo",
    "soil_condition": "normal",
    "drainage_type": "septic_tank",
    "external_works_scope": "minimal"
  },
  "qs_specifications": {
    "construction_scope": "new_build",
    "site_access_constraint": "normal",
    "concrete_grade": "grade_25",
    "wall_type": "blockwork",
    "floor_finish_spec": "ceramic_tile_standard",
    "sanitary_fitting_grade": "standard",
    "electrical_scope_level": "standard",
    "waterproofing_requirement": "wet_areas_only"
  }
}
```

### Internal normalization target

This should then normalize into a structure compatible with the current pipeline, for example:

- `project_info.building_type`
- `project_info.floors`
- `project_info.parameters.built_up_area`
- `project_info.parameters.finish_level`
- `project_info.parameters.structural_system`
- `project_info.parameters.roof_type`
- `project_info.parameters.ceiling_type`
- `project_info.parameters.location`
- `project_info.parameters.soil_condition`
- `project_info.parameters.drainage_type`
- `project_info.parameters.external_works_scope`
- `project_info.parameters.bedrooms`
- `project_info.parameters.bathrooms`
- `project_info.floor_areas`
- `project_info.qs_specifications`
- `project_info.value_sources`

### Derived compatibility values

The backend should derive:

- total built-up area from all floor rows
- a compatibility string form of `built_up_area` for existing consumers
- normalized area totals for later quantity logic

## Canonical Enum Strategy

The current code already has enum drift between runtime logic and prompts. This must be fixed before the wizard expands the schema.

The plan should standardize on canonical internal enum slugs and map them to display labels in the frontend.

Recommended examples:

- building type
  - `residential`
  - `commercial`
  - `industrial`
  - `mixed_use`
- finish level
  - `standard`
  - `semi_luxury`
  - `luxury`
- structural system
  - `framed`
  - `load_bearing`
  - `hybrid`
- roof type
  - `rc_flat_slab`
  - `clay_tile`
  - `asbestos_sheet`
  - `metal_sheet`
  - `other`
- ceiling type
  - `gypsum_mineral_fibre`
  - `timber`
  - `asbestos_flat`
  - `concrete`
  - `other`
- area unit
  - `sqft`
  - `m2`

The same canonical slugs must be used in:

- runtime validators
- frontend option values
- prompt schema hints
- LLM normalization logic
- reporting and transparency output

## Field Catalog By Step

### Step 1 - Project Basics

Required:

- `building_type`
- `floor_count`

Optional:

- `description`
- `floorplan_image_url`

Validation:

- `building_type` must be one of the supported enum values
- `floor_count` must be an integer greater than or equal to 1
- a sensible upper cap should exist, for example 100, to block invalid inputs

### Step 2 - Floor Areas

Required:

- exactly one floor-area row per floor

Per-row fields:

- `floor_key`
- `floor_label`
- `area_value`
- `area_unit`

Validation:

- number of rows must equal `floor_count`
- each area must be a positive numeric value
- unit must be supported
- if all rows share the same unit, total can be derived directly
- if mixed units are allowed, the backend must normalize them before deriving totals

### Step 3 - Building Program

Residential recommended required fields:

- `bedrooms`
- `bathrooms`

Residential optional fields:

- `spaces`
- `special_rooms`

Commercial recommended fields:

- `primary_use_type`
- `washroom_count`
- `service_space_notes`

Industrial recommended fields:

- `facility_type`
- `bay_or_zone_count` where relevant
- `utility_or_storage_notes`

Mixed-use recommended fields:

- `use_mix_breakdown`
- `residential_component_notes`
- `commercial_component_notes`

Validation:

- do not require `bedrooms` or `bathrooms` for non-residential projects
- enforce only the subset relevant to the selected building type
- allow optional spaces lists for all types if useful to item generation

### Step 4 - Construction And Site Details

Recommended required fields:

- `finish_level`
- `structural_system`
- `roof_type`
- `ceiling_type`
- `location`
- `soil_condition`
- `drainage_type`
- `external_works_scope`

Validation:

- each field must resolve to a canonical enum or validated text value
- avoid silent defaults for these unless the review step makes them visible

### Step 5 - QS Specification Details

Recommended fields:

- `construction_scope`
- `site_access_constraint`
- `concrete_grade`
- `wall_type`
- `floor_finish_spec`
- `sanitary_fitting_grade`
- `electrical_scope_level`
- `waterproofing_requirement`
- optional `typical_floor_height`

Validation:

- each field should be enum-driven wherever possible
- some fields can be conditional, for example waterproofing can be required when wet areas or flat roofs imply it

### Step 6 - Review And Submit

Validation before submit:

- all required fields for the selected building type are complete
- `floor_areas` is complete and valid
- derived total built-up area exists
- any conditional requirements are satisfied
- no unresolved backend validation errors remain

## Backend Architecture Changes

### 1. Re-center `clarification_agent.py` around form rules

`backend/services/clarification_process/clarification_agent.py` should evolve from question-sequence support into the canonical form-rules module.

It should own:

- field definitions
- enum definitions
- conditional requirements
- parsing logic
- validation logic
- derivation logic
- compatibility mapping into existing `project_info`

Recommended responsibilities:

- validate the structured wizard payload
- derive total built-up area from `floor_areas`
- conditionally require residential-only or non-residential program fields
- map canonical enum slugs into downstream-friendly values if needed
- produce field-level validation errors for the frontend

### 2. Add backend request models for form submission

`backend/app/api/controllers/clarification_controller.py` should no longer only handle question/answer sessions.

It should support structured form operations such as:

- validate partial form data
- validate the full form before submit
- normalize the final payload into `project_info`
- trigger estimation using the normalized payload

The current chat routes can remain temporarily, but they should be treated as compatibility endpoints rather than the future contract.

### 3. Keep estimation progress streaming if useful

The wizard replaces chat for intake, but it does not require estimation progress streaming to disappear.

It is valid to keep:

- an estimate-start endpoint
- an estimate-progress SSE stream
- an estimate-completed result payload

The main change is that the pre-estimate clarification loop is removed from the primary frontend path.

### 4. Normalize explicit form values before pipeline entry

`backend/application/pipelines/estimation_pipeline.py` should receive normalized structured data that already represents the resolved user input.

This means:

- the pipeline should not depend on re-asking clarification questions
- `run_estimation_pipeline_from_project_info()` becomes the natural entrypoint for the wizard path
- explicit user data should be preserved as authoritative

### 5. Track provenance of values

The normalized model should distinguish between:

- user-provided values
- derived values
- inferred values
- defaulted values

This provenance is important for:

- confidence scoring
- transparency reporting
- later review workflows

## Suggested Backend API Shape

The final API can vary, but the plan should move toward a contract like this.

### Option A - Backend-driven validation with frontend-managed step state

- `POST /api/estimate-project/form/validate`
  - accepts partial or full wizard payload
  - returns field-level validation errors and any derived values that should be shown immediately
- `POST /api/estimate-project/form/submit`
  - accepts the full validated payload
  - returns an estimation session identifier or immediate estimate start response
- `GET /api/estimate-project/estimate/stream/{session_id}`
  - optional progress stream for estimate execution only

### Option B - Add a schema/config endpoint later

Optional future endpoint:

- `GET /api/estimate-project/form/schema`
  - returns enum options, field groupings, and validation metadata if the frontend should become backend-configurable

For the first implementation, frontend layout can remain hardcoded while backend validation remains authoritative.

## Frontend Architecture Changes

### 1. Replace the chat page with a wizard shell

`frontend/src/app/page.tsx` should stop being a chat-first intake screen and become the wizard entry screen.

It should own:

- step index state
- current form payload state
- per-step validation state
- derived totals shown to the user
- review-step editing triggers
- estimation submission and progress state

### 2. Introduce step-focused components

The implementation can remain in one file initially, but a cleaner long-term split would be:

- `ProjectBasicsStep`
- `FloorAreasStep`
- `BuildingProgramStep`
- `ConstructionDetailsStep`
- `QSSpecificationStep`
- `ReviewSubmitStep`
- optional `WizardProgress`

### 3. Replace chat-centric types

`frontend/src/types/chat.ts` is not the right long-term home for the wizard contract.

The plan should introduce dedicated form types, for example:

- wizard payload types
- step validation error types
- enum option types
- derived totals types

### 4. Replace chat service methods

`frontend/src/services/estimation.ts` should move away from:

- clarification session start
- clarification answer submit
- clarification stream open

and toward:

- form validate
- form submit
- estimate progress stream

### 5. Keep results UI separately from intake UI

The intake wizard and the estimate result display should be treated as separate states.

That avoids coupling the new deterministic intake back to the old chat mental model.

## File-Level Change Plan

### Clarification process

- `backend/services/clarification_process/clarification_agent.py`
  - replace fixed required-field arrays with structured field definitions
  - add floor-area derivation helpers
  - add building-type-specific validation
  - centralize canonical enum definitions
- `backend/services/clarification_process/llm_client.py`
  - align schema hints with canonical enums
  - accept explicit form data as override input when description parsing is still used

### API layer

- `backend/app/api/controllers/clarification_controller.py`
  - add structured validation/submit request models
  - reduce dependence on session-based Q and A flow for the primary path
- `backend/app/api/state/session.py`
  - keep only what is still needed for estimation progress or temporary compatibility

### Pipeline and downstream services

- `backend/application/pipelines/estimation_pipeline.py`
  - accept normalized wizard output
- `backend/services/item_gen_process/boq_builder.py`
  - consume building-type and QS specification data more explicitly
- `backend/services/item_gen_process/item_predictor.py`
  - remove or conditionalize residential fallback mappings
- `backend/services/quantity_gen_process/quantity_calculator.py`
  - ensure building type mapping is not implicitly residential
- `backend/services/quantity_gen_process/rule_based_calculator.py`
  - branch residential heuristics by building type
- `backend/services/quantity_gen_process/quantity_validator.py`
  - remove bedroom/bathroom assumptions for non-residential flows
- `backend/services/reporting_process/excel_generator.py`
  - make summary sections building-type-aware and include floor-area breakdown where appropriate
- `backend/services/reporting_process/report_builder.py`
  - include normalized wizard-derived inputs and provenance in the report payload

### Prompt templates

- `backend/infrastructure/integrations/prompt_templates/extract_project_info.txt`
- `backend/infrastructure/integrations/prompt_templates/extract_with_clarifications.txt`
- `backend/infrastructure/integrations/prompt_templates/generate_baseline_boq.txt`

These templates must align with the canonical internal enums and with the fact that explicit form answers are the authoritative values.

## Migration Strategy

The migration should be staged so the system remains functional throughout.

### Phase 1 - Stabilize schema and enums

Do first:

- define the canonical wizard payload
- define canonical enum slugs
- align prompt and runtime vocabularies
- define derived built-up-area behavior

This phase blocks everything else.

### Phase 2 - Build backend validation and normalization

Do next:

- refactor clarification/form logic into structured validation
- add submit and validate APIs
- normalize wizard payload into `project_info`

This phase should be complete before the frontend fully switches over.

### Phase 3 - Build frontend wizard skeleton

Do next:

- replace chat intake UI with wizard step state
- implement Step 1 through Step 6 visually
- wire local validation and backend validation together

### Phase 4 - Connect estimation run and results

Do next:

- submit normalized payload
- trigger estimation
- keep progress stream if desired
- show results and report download after completion

### Phase 5 - Clean downstream residential assumptions

Do next:

- audit services that assume residential defaults
- make quantity, validation, reporting, and item prediction building-type aware

### Phase 6 - Remove old intake dependence

Do last:

- confirm wizard parity
- stop the new frontend from calling chat clarification endpoints
- eventually retire or minimize the old clarification session path

## Detailed Validation Rules

### Required cross-step validations

- `floor_count` must match the number of floor-area rows
- total built-up area must be derivable
- building-type-specific fields must be complete
- enum values must be canonical
- incompatible combinations must be rejected or flagged early

### Recommended conditional rules

- if `building_type != residential`, do not require `bedrooms` or `bathrooms`
- if `roof_type == rc_flat_slab`, require or strongly recommend a waterproofing-related value
- if `soil_condition` is `rocky`, `expansive`, or `waterlogged`, flag that foundation-related downstream logic will be affected
- if `external_works_scope != none`, surface additional scope review in the review step
- if the project is mixed-use, require some indication of composition instead of generic room counts

### Unit normalization rules

- allow `sqft` and `m2`
- normalize totals internally before quantity logic uses them
- expose a consistent display unit in the review step

## Estimate Accuracy Improvements Expected From The New Model

The form change is not only a UX change. It should improve estimate quality in several concrete ways.

### 1. Better quantity inputs

Floor-by-floor areas are more useful than a single total area string.

They can support:

- better parametric quantity estimation
- floor-aware consistency checks
- clearer derived total area handling

### 2. Better BOQ item generation

Building-type-specific program details and QS specification fields should improve:

- item coverage
- scope relevance
- item description specificity

### 3. Fewer silent assumptions

Promoting current hidden defaults into explicit reviewed form inputs should reduce:

- default-driven estimation drift
- unexplained cost assumptions
- avoidable confidence penalties

### 4. Better transparency

Because values are structured and provenance-aware, the final report can explain:

- what the user provided directly
- what the system derived
- what the system still inferred or defaulted

## Reporting Changes

Reporting should be updated so the final output reflects the new model.

At minimum, reports should be able to show:

- building type
- floor count
- floor-by-floor area breakdown
- total built-up area
- building-type-relevant program details
- key QS specification assumptions
- any defaulted or inferred values

Reports should not assume every project has bedrooms and bathrooms.

## Testing And Verification Plan

### Backend unit tests

Add tests for:

- canonical enum validation
- `floor_count` to `floor_areas` consistency
- built-up-area derivation
- building-type-specific required fields
- conditional validation rules
- normalization from wizard payload to `project_info`

### Frontend tests

Add tests for:

- wizard step order
- step navigation guards
- floor-row generation from floor count
- review-step editing
- submit blocking on missing required values
- building-type field branching

### Integration tests

Add tests for:

- full residential wizard flow
- full commercial wizard flow
- full industrial wizard flow
- full mixed-use wizard flow
- estimate submission from the new form path
- compatibility of derived `built_up_area` with existing pipeline consumers

### Manual validation

Run manual scenarios that verify:

- the form never forces residential-only fields on non-residential projects
- floor areas derive the expected total
- the review step is editable and clear
- the estimate still completes end to end
- downstream reports do not show irrelevant residential placeholders

## Risks And Mitigations

### Risk 1 - Residential assumptions survive downstream

Risk:

- the wizard may support all building types, but downstream logic may still silently treat inputs as residential

Mitigation:

- audit and branch logic in item prediction, quantity rules, validation, and reporting before declaring full multi-type support complete

### Risk 2 - Enum drift continues

Risk:

- frontend values, backend validators, and prompt schemas diverge again

Mitigation:

- define one canonical enum source and make prompts adapt to it rather than invent separate vocabularies

### Risk 3 - The form becomes too long

Risk:

- collecting too many fields could hurt completion rate

Mitigation:

- keep step order fixed but make fields conditional by building type and context

### Risk 4 - Derived area handling breaks compatibility

Risk:

- existing downstream services may still expect a simple `built_up_area` string

Mitigation:

- preserve a derived compatibility value while gradually teaching downstream services to use structured `floor_areas`

### Risk 5 - Free-text description conflicts with explicit form answers

Risk:

- LLM extraction from description or uploads may contradict the form

Mitigation:

- explicit form values must always override inferred values during normalization

## Acceptance Criteria

This plan is complete only when all of the following are true:

1. The primary intake flow is a deterministic wizard, not chat.
2. Building type and floor count are collected in the first step.
3. One area input per floor is collected in the second step.
4. The system derives total built-up area from the floor rows.
5. The review step allows the user to confirm and edit before estimation.
6. Residential-only fields are not required for non-residential projects.
7. The normalized wizard payload can run through the existing estimation pipeline.
8. Reporting reflects the new model without assuming every project is residential.
9. The new frontend path does not depend on the old clarification chat loop.
10. The system still produces an end-to-end estimate and downloadable report.

## Out Of Scope For The First Implementation

The following are useful but should not block the first wizard migration:

- autosave between steps
- resumable drafts backed by database persistence
- multi-user approvals or supervisor review
- a full post-estimate correction form
- a line-item BOQ editor
- a fully backend-driven dynamic form schema

## Recommended Immediate Implementation Order

If execution starts now, the most practical order is:

1. Define canonical enums and the wizard payload contract.
2. Refactor `clarification_agent.py` into the structured validation and derivation layer.
3. Add backend validate and submit endpoints for structured payloads.
4. Replace frontend chat intake with the six-step wizard shell.
5. Wire review and final submit into the estimation pipeline.
6. Audit downstream residential assumptions.
7. Retire the old clarification path from the new frontend.

## Summary

This plan converts project intake from a conversational clarification model into a structured QS-friendly estimation wizard. The first two steps anchor the entire experience around building type, floor count, and per-floor areas. The backend then treats these explicit structured values as the source of truth, while preserving temporary compatibility with the current estimation pipeline through derived `built_up_area` handling.

The success of the plan depends on doing three things in the correct order:

- stabilizing the schema and enum contract first
- replacing the frontend chat intake with a real wizard second
- cleaning downstream residential assumptions before claiming full multi-type support

If those are done in sequence, the system will become easier to use, easier to validate, and more accurate for structured QS estimation.