# Floorplan Process Boundary Upgrade Plan

## Goal

Consolidate all backend floorplan processing under `backend/services/floorplan_process` while keeping `backend/services/floorplan_process/service.py` as a strict communication facade only.

The service file exists only to communicate with other processes and delegate inward. It must not contain orchestration, OCR coordination, geometry heuristics, scale resolution, confidence scoring, result assembly, or any other floorplan business logic.

All floorplan business rules should live in dedicated internal modules inside `backend/services/floorplan_process`.

This plan intentionally overrides the earlier floorplan ownership direction in `HYBRID_QUANTITY_AND_FLOORPLAN_REFACTOR_PLAN.md`.

## Target Architecture

### Public boundary

- `backend/services/floorplan_process/service.py`
  - Only supported cross-package import surface for floorplan processing.
  - Only responsible for communication with other processes and delegation into internal floorplan modules.
  - Must not be used as a place to accumulate floorplan logic.

### Internal floorplan modules

- `backend/services/floorplan_process/orchestrator.py`
  - Owns the end-to-end floorplan flow.
- `backend/services/floorplan_process/confidence_scorer.py`
  - Owns geometry-confidence rules.
- `backend/services/floorplan_process/image_cache.py`
  - Internal adapter for remote floorplan download and caching.
- `backend/services/floorplan_process/geometry_extraction/ocr.py`
  - Internal OCR adapter.
- `backend/services/floorplan_process/geometry_extraction/*`
  - Internal extraction adapters only.
- Optional focused helper modules when needed:
  - `scale_resolution.py`
  - `geometry_aggregation.py`
  - `result_builder.py`
  - `validation.py`

These helpers should be added only when they clearly reduce coupling or keep the orchestrator from becoming another monolith.

## Core Architectural Rules

1. `service.py` is a communication boundary only.
2. `service.py` may expose stable public entrypoints, but it must delegate immediately.
3. Internal floorplan modules must never route business logic back through `service.py`.
4. External callers must not import `image_cache.py`, `geometry_extraction/*`, or other internal floorplan modules directly.
5. Compatibility wrappers may exist temporarily during migration, but they must contain no business logic.
6. Prefer a few purposeful internal modules over one large orchestrator, but do not over-split trivial helpers.

## Current Situation

The floorplan process is currently split across layers:

- `backend/application/floorplan/orchestrator.py`
  - Contains the main floorplan orchestration logic.
- `backend/application/floorplan/confidence_scorer.py`
  - Contains geometry-confidence logic.
- `backend/services/floorplan_process/service.py`
  - Public facade, but still tied to the old application-layer implementation.
- `backend/services/floorplan_process/pipeline.py`
  - Compatibility alias that still re-exports application-owned logic.
- `backend/application/pipelines/floorplan_pipeline.py`
  - Extra wrapper entrypoint.
- `backend/application/pipelines/estimation_pipeline.py`
  - Still imports `image_cache` directly, which breaks the intended service boundary.

There is also a circular import workaround pattern where the old application orchestrator reaches back into the service file only to access OCR functionality. That contract should be removed instead of preserved.

## Migration Plan

### Phase 1 - Freeze the public floorplan contract

Keep `backend/services/floorplan_process/service.py` as the only supported import surface for cross-package callers.

The service layer should exist only to communicate with other processes, expose the canonical processing entrypoint, and delegate inward.

Do not let callers import these directly:

- `backend/services/floorplan_process/pipeline.py`
- `backend/services/floorplan_process/image_cache.py`
- `backend/services/floorplan_process/geometry_extraction/*`

Only keep a raw OCR public surface if an import audit proves it is still required.

Depends on none.

### Phase 2 - Remove the circular-import workaround

The current `service = FloorPlanOCRService()` singleton exists only to support the old application orchestrator.

Replace that dependency with a direct internal OCR adapter call so no floorplan implementation module imports the public service facade.

After this step:

- no floorplan business-logic module should import `backend/services/floorplan_process/service.py`
- the service singleton should be removed unless a real external dependency is discovered

Depends on Phase 1.

### Phase 3 - Create the canonical internal module split

Add or formalize the internal floorplan modules under `backend/services/floorplan_process`.

Recommended ownership:

- `orchestrator.py`
  - end-to-end floorplan flow
- `confidence_scorer.py`
  - geometry confidence calculation
- `scale_resolution.py`
  - dimension parsing and scale source decisions when needed
- `geometry_aggregation.py`
  - area, perimeter, wall-length, room normalization, and heuristic flags when needed
- `result_builder.py`
  - response shaping when the returned geometry payload becomes too large for the orchestrator

Keep the split pragmatic. Only add these helpers if they reduce real complexity.

Depends on Phase 2.

### Phase 4 - Migrate application-owned floorplan logic into service-owned internals

Move the logic from these files into the internal floorplan modules:

- `backend/application/floorplan/orchestrator.py`
- `backend/application/floorplan/confidence_scorer.py`

As part of the move:

- strip application-layer ownership wording from docstrings
- make `backend/services/floorplan_process` self-contained
- ensure floorplan-specific computation resolves entirely within the service package internals

Depends on Phase 3.

### Phase 5 - Simplify the public facade

After the move, `backend/services/floorplan_process/service.py` should exist only for outward communication and inward delegation to internal modules.

If raw OCR must remain publicly reachable, expose it as a thin delegated function instead of preserving a service object or singleton unless that shape is required by a real external caller.

Depends on Phase 4.

### Phase 6 - Rewire all callers to the canonical service boundary

Update these callers so they depend only on `backend/services/floorplan_process/service.py`:

- `backend/app/api/controllers/project_controller.py`
- `backend/app/worker/tasks/floorplan_tasks.py`
- `backend/application/pipelines/estimation_pipeline.py`

In particular:

- remove the direct `image_cache` import from `backend/application/pipelines/estimation_pipeline.py`
- let floorplan URL resolution happen inside the floorplan package

Depends on Phase 5.

### Phase 7 - Convert old entrypoints into compatibility wrappers only

Keep `backend/application/pipelines/floorplan_pipeline.py` as a short-lived deprecated alias to the service facade while validation is running.

Only keep wrappers under `backend/application/floorplan` if import audits show they are still required. Otherwise remove them.

These wrappers must contain no business logic.

Depends on Phase 6.

### Phase 8 - Preserve external behavior while cleaning internals

Keep the external route, request model, and response shape stable during the refactor.

The floorplan response should continue to expose the existing geometry and confidence fields unless a separate contract change is approved, including fields such as:

- `total_floor_area_m2`
- `perimeter_m`
- `wall_length_m`
- `opening_count`
- `room_count`
- `rooms`
- `dimensions_raw`
- `method`
- `geometry_confidence`
- `scale_source`
- `dimensions_confidence`
- `openings_confidence`
- `coverage_confidence`
- `heuristic_flags`
- `inferred_area_flag`
- current compatibility fields still consumed elsewhere

Depends on Phases 4 and 6.

Can run in parallel with Phase 7.

### Phase 9 - Remove obsolete application-owned floorplan implementation

Once import audits and smoke checks are clean:

- delete or reduce `backend/application/floorplan` to temporary compatibility stubs
- remove those stubs when no callers remain
- retire `backend/services/floorplan_process/pipeline.py` if no callers remain

The end state should have one obvious public floorplan entrypoint.

Depends on Phases 7 and 8.

### Phase 10 - Add focused verification coverage before final cleanup

Because backend test files are not currently visible in the workspace, budget explicit time for narrow regression coverage or smoke checks around:

- the public facade
- the floorplan API path
- the worker path
- the estimation pipeline floorplan branch

Depends on Phases 6 through 9.

## Relevant Files

- `backend/services/floorplan_process/service.py`
  - Communication-only facade.
- `backend/services/floorplan_process/pipeline.py`
  - Temporary alias at most.
- `backend/services/floorplan_process/image_cache.py`
  - Internal adapter.
- `backend/services/floorplan_process/geometry_extraction/ocr.py`
  - Internal OCR adapter.
- `backend/application/floorplan/orchestrator.py`
  - Current implementation source to migrate out.
- `backend/application/floorplan/confidence_scorer.py`
  - Current scoring source to migrate out.
- `backend/application/pipelines/floorplan_pipeline.py`
  - Temporary compatibility wrapper.
- `backend/application/pipelines/estimation_pipeline.py`
  - Caller cleanup required.
- `backend/app/api/controllers/project_controller.py`
  - API caller rewiring.
- `backend/app/worker/tasks/floorplan_tasks.py`
  - Worker caller rewiring.
- `backend/app/api/routes/router.py`
  - Route behavior should remain stable.
- `HYBRID_QUANTITY_AND_FLOORPLAN_REFACTOR_PLAN.md`
  - Earlier direction now superseded for floorplan ownership.

## Verification Checklist

1. Confirm no floorplan implementation module imports `backend/services/floorplan_process/service.py`.
2. Confirm no external caller imports `backend/services/floorplan_process/image_cache.py` or `backend/services/floorplan_process/geometry_extraction/*` directly.
3. Verify `backend/services/floorplan_process/service.py` contains no orchestration, heuristics, score computation, OCR coordination, or payload shaping.
4. Run backend diagnostics after each migration slice to catch unresolved imports or circular-dependency regressions.
5. Smoke-test the API path through `backend/app/api/controllers/project_controller.py`.
6. Smoke-test the worker path through `backend/app/worker/tasks/floorplan_tasks.py`.
7. Smoke-test the estimation path in `backend/application/pipelines/estimation_pipeline.py` with a floorplan URL.
8. If tests are added, keep them narrow:
   - one facade delegation test
   - one internal orchestration test
   - one caller-level smoke test

## Decisions

- In scope:
  - backend-only floorplan consolidation
  - caller rewiring
  - estimation pipeline cleanup
  - staged compatibility wrappers
  - behavior-preserving validation
- In scope:
  - `backend/services/floorplan_process` is the permanent home for floorplan business logic
  - `service.py` is only the communication boundary to other processes
- In scope:
  - remove the current `FloorPlanOCRService` singleton unless a real external dependency is discovered
- In scope:
  - preserve the current external floorplan API contract unless a separate request changes it
- Excluded:
  - frontend work unless a later approved API change requires it
- Excluded:
  - broader quantity-pipeline refactors unrelated to floorplan ownership

## Final End State

At the end of this refactor:

- all floorplan business logic lives under `backend/services/floorplan_process` internal modules
- `backend/services/floorplan_process/service.py` exists only to communicate with other processes and delegate inward
- external callers use one stable floorplan boundary
- old application-layer floorplan implementations and wrapper indirections are removed
- the API, worker, and estimation flows keep the same observable behavior