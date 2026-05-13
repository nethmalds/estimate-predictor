# Frontend and Backend Runtime Stabilization Plan

## Objective

Stabilize frontend and backend execution, compilation, and integration behavior by removing duplicated frontend API environment variables, fixing current frontend diagnostics, implementing Gmail SMTP for forgot-password emails, aligning API contracts and auth ownership between frontend and backend, persisting wizard-generated estimates, and hardening backend startup behavior so runtime failures are explicit and verifiable.

## Scope

This plan covers:

- Frontend environment-variable cleanup and fetch-path normalization.
- Frontend compilation and lint diagnostics currently affecting runtime confidence.
- Frontend-backend API contract alignment for dashboard, estimates, estimate detail, and error responses.
- Auth and ownership alignment between NextAuth frontend sessions and backend estimate/dashboard endpoints.
- Estimate persistence from the wizard flow into the estimates dashboard/detail experience.
- Shared schema/type synchronization for canonical option values and validation constraints.
- Backend Gmail SMTP configuration and password-reset email delivery.
- Backend startup, migration, and readiness verification.
- End-to-end verification of the forgot-password and reset-password flow.

This plan also covers the integration work needed to keep frontend and backend synchronized over time, including response-shape consistency, error-envelope normalization, and contract-verification guardrails.

This plan does not expand into unrelated backlog items such as rate limiting, CSP/HSTS, or sidebar navigation.

## Findings Summary

1. The frontend currently has duplicated backend URL configuration in `frontend/.env.local`.
   - `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
   - `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`
   The codebase is split between both names, which creates drift risk.

2. Frontend fetch logic is inconsistent.
   - `frontend/src/services/estimation.ts` uses `NEXT_PUBLIC_API_BASE_URL`.
   - Several other frontend files still use `NEXT_PUBLIC_BACKEND_URL` directly.

3. The frontend currently has active diagnostics.
   - `frontend/src/app/estimates/[id]/page.tsx` reports a module-resolution error for `./EstimateDetailClient`.
   - `frontend/src/components/wizard/WizardProgress.tsx` has Tailwind shorthand warnings.
   - `frontend/src/components/wizard/steps/ProjectBasicsStep.tsx` has Tailwind shorthand warnings.

4. Backend forgot-password is not production-complete.
   - `backend/app/api/controllers/auth_controller.py` creates and stores password-reset tokens.
   - The actual mail sending path is still a TODO.

5. Backend configuration does not yet support SMTP.
   - `backend/core/config/settings.py` currently has no SMTP settings.
   - `backend/.env.local` currently has no Gmail SMTP configuration.

6. Backend startup readiness has a known risk.
   - `backend/app/api/server.py` starts RAG bootstrap in the background.
   - `backend/services/rag_process/service.py` lazily initializes the vector store.
   Early requests can potentially hit partially initialized services.

7. Backend execution verification must include migrations.
   - `alembic upgrade head` should be part of the verification path before relying on application startup.

8. Dashboard and estimates contracts are currently mismatched.
   - The frontend expects `data.items` from the estimates list endpoint.
   - The backend returns `estimates`.
   - The frontend expects `avg_confidence` and `total_value` from the dashboard summary endpoint.
   - The backend returns `average_confidence` and `total_estimated_value`.

9. Estimate detail and update contracts are not fully aligned.
   - The frontend edit path expects a `user_id` value on the detail payload.
   - The backend detail response does not currently return `user_id`.

10. Frontend and backend still do not share a real auth ownership contract.
   - Estimate and dashboard endpoints still rely on `user_id` query parameters instead of a backend-authenticated user context.

11. Wizard submission is not yet persisted into the estimates database flow.
   - The form controller creates an in-memory session and streams a result.
   - Dashboard and estimates pages read from persisted estimate records.

12. Error envelopes are inconsistent across the boundary.
   - Backend errors are emitted under `error.message`.
   - Frontend service parsing currently looks for `detail`.

13. Canonical wizard option values and validation rules are duplicated.
   - Frontend enum/type definitions and backend clarification/validation values are maintained separately, which invites drift.

## Decisions

- Keep `NEXT_PUBLIC_API_BASE_URL` as the single frontend API origin.
- Remove `NEXT_PUBLIC_BACKEND_URL` from the frontend.
- Use Gmail SMTP with an App Password, not a normal Gmail account password.
- Use `smtp.gmail.com:587` with STARTTLS.
- Preserve forgot-password enumeration protection by always returning the same success message.
- Keep any development-only reset-token echo behavior gated strictly behind `ENV=development`.
- Use one canonical API response shape per endpoint and make frontend consumers conform to it.
- Replace `user_id` query-string ownership with backend-derived authenticated identity.
- Persist wizard-submitted estimates so the estimation flow and dashboard flow operate on the same records.
- Move toward one source of truth for canonical wizard options and validation constraints.

## Implementation Phases (Execution Order)

### Phase 0. Baseline and unblockers

Purpose:

- Establish a clean starting point before cross-cutting changes begin.

Includes:

- Reproduce the current frontend diagnostics and capture the current backend startup/migration blockers.
- Reproduce and inspect the failing `alembic upgrade head` path before deeper backend changes.
- Lock the canonical contract decisions that downstream phases depend on.
- Confirm the target response shapes for dashboard summary, estimates list, estimate detail, and error envelopes.

Exit criteria:

- Current failures are reproducible and understood.
- Canonical response-shape and ownership decisions are fixed.
- The implementation sequence below can proceed without changing the contract target midstream.

### Phase 1. Frontend API boundary cleanup

Purpose:

- Remove obvious frontend drift and make all frontend consumers depend on one consistent API boundary.

Includes:

- Step 1: Normalize frontend API configuration.
- Step 2 frontend-side changes: align dashboard, estimates, and estimate detail consumers to the canonical payload shapes.
- Step 3: Resolve current frontend compilation diagnostics.
- Step 8 frontend-side changes: update frontend parsing for normalized backend error envelopes.

Why this phase comes first:

- The frontend currently has two backend URL variables and multiple response-shape assumptions. Those need to be cleaned up before auth, persistence, and full end-to-end verification are reliable.

Exit criteria:

- `NEXT_PUBLIC_API_BASE_URL` is the only frontend API environment variable.
- Frontend consumers are coded against the canonical payload shapes.
- Current frontend diagnostics are resolved or isolated.

### Phase 2. Backend contract and startup foundation

Purpose:

- Make the backend emit the agreed contracts and start predictably enough for the remaining phases.

Includes:

- Step 2 backend-side changes: align backend estimates and dashboard response shapes with the canonical contract.
- Step 8 backend-side changes: normalize backend error-envelope behavior and validation outputs.
- Step 10 baseline readiness work: resolve or isolate migration/startup blockers, including the current `alembic upgrade head` failure.

Why this phase comes second:

- Frontend alignment is incomplete until the backend emits the same contract, and later auth/persistence work should build on a backend that can start and return stable payloads.

Exit criteria:

- `alembic upgrade head` runs successfully or the blocker is explicitly fixed and verified.
- `uvicorn app.api.server:app` starts with predictable readiness behavior.
- Dashboard, estimates list, estimate detail, and error responses match the agreed contract.

### Phase 3. Auth and ownership alignment

Purpose:

- Replace ad hoc ownership passing with one authenticated ownership model across the stack.

Includes:

- Step 6: Align auth ownership between frontend and backend.

Why this phase comes third:

- Persistence and mutation flows should not be built on top of raw `user_id` query strings. Ownership needs to be settled first.

Exit criteria:

- Estimate and dashboard ownership is derived from backend-authenticated identity.
- Frontend requests no longer rely on raw `user_id` query parameters for access control.
- Cross-user access is blocked consistently.

### Phase 4. Estimate lifecycle persistence

Purpose:

- Unify wizard submission and persisted estimate views into one lifecycle.

Includes:

- Step 7: Persist wizard results into the estimates workflow.

Why this phase comes fourth:

- Persistence should be tied to the finalized ownership model and stable response contracts from earlier phases.

Exit criteria:

- Wizard submission creates or reserves a persisted estimate record.
- Pipeline completion updates the stored estimate with result JSON and summary values.
- Freshly generated estimates appear in dashboard, list, and detail views.

### Phase 5. Password reset delivery

Purpose:

- Complete the real email-delivery path for forgot/reset password.

Includes:

- Step 4: Add backend SMTP configuration for Gmail.
- Step 5: Implement password-reset email delivery.

Why this phase comes fifth:

- SMTP delivery is largely orthogonal, but it still depends on stable backend configuration, startup behavior, and normalized error handling.

Exit criteria:

- Gmail SMTP configuration is wired into backend settings safely.
- Forgot-password sends a real email.
- Reset-password works end to end.

### Phase 6. Shared schema synchronization and contract guardrails

Purpose:

- Prevent the same classes of frontend-backend drift from reappearing.

Includes:

- Step 9: Synchronize shared schema, enums, and validation rules.
- Step 11: Add contract guardrails so sync issues do not recur.

Why this phase comes sixth:

- Guardrails are most valuable once the intended contracts, ownership model, and persistence flow are already settled and can be codified.

Exit criteria:

- Canonical wizard option values and validation rules are sourced consistently.
- Typed response models, generated/shared types, or equivalent guardrails are in place.
- Contract mismatches are detectable before runtime.

### Phase 7. End-to-end verification and sign-off

Purpose:

- Verify the full system against the plan's success criteria.

Includes:

- Step 12: Verify end-to-end behavior.

Why this phase comes last:

- It depends on the implementation phases above and acts as the release gate.

Exit criteria:

- Frontend lint/build and backend migration/startup checks pass.
- Contract-aligned frontend/backend flows work across dashboard, estimates, wizard submission, and password reset.
- All success criteria in this document are satisfied.

## Implementation Plan

### 1. Normalize frontend API configuration

Unify all frontend API calls behind a single environment variable and shared helper.

Actions:

- Keep `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local`.
- Remove `NEXT_PUBLIC_BACKEND_URL` from `frontend/.env.local`.
- Replace direct `process.env.NEXT_PUBLIC_BACKEND_URL` usage across frontend pages and auth config.
- Reuse or extract a shared API base URL helper so server and client fetches resolve through the same base origin.
- Update any inline comments or documentation that still mention the removed variable.

Files in scope:

- `frontend/.env.local`
- `frontend/src/services/estimation.ts`
- `frontend/src/auth.ts`
- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/estimates/page.tsx`
- `frontend/src/app/estimates/[id]/page.tsx`
- `frontend/src/app/estimates/[id]/EstimateDetailClient.tsx`
- `frontend/src/app/forgot-password/page.tsx`
- `frontend/src/app/reset-password/page.tsx`
- `frontend/src/app/register/page.tsx`

### 2. Align frontend-backend API response contracts

Fix concrete payload mismatches so frontend pages and backend endpoints speak the same language.

Actions:

- Align the estimates list contract so both sides use the same collection field name.
- Align dashboard summary field names so frontend summary cards read the backend payload correctly.
- Align detail and patch contracts so the frontend does not depend on fields the backend does not return.
- Standardize pagination parameter names and response metadata between frontend calls and backend endpoints.
- Add explicit typed response models on backend routes that are consumed by the frontend so response drift is caught at the boundary.

Files in scope:

- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/estimates/page.tsx`
- `frontend/src/app/estimates/[id]/page.tsx`
- `frontend/src/app/estimates/[id]/EstimateDetailClient.tsx`
- `backend/app/api/controllers/estimates_controller.py`
- `backend/app/api/schemas/estimate_schemas.py`
- `backend/app/api/routes/router.py`

### 3. Resolve current frontend compilation diagnostics

Fix the concrete frontend issues that can block or weaken local builds.

Actions:

- Revalidate the import path in `frontend/src/app/estimates/[id]/page.tsx`.
- If the sibling import remains unstable, move the client component behind an alias-based shared import from a stable component path.
- Clean the Tailwind shorthand diagnostics in the wizard components.
- Re-run frontend diagnostics after the env cleanup and route fix.

Files in scope:

- `frontend/src/app/estimates/[id]/page.tsx`
- `frontend/src/app/estimates/[id]/EstimateDetailClient.tsx`
- `frontend/src/components/wizard/WizardProgress.tsx`
- `frontend/src/components/wizard/steps/ProjectBasicsStep.tsx`
- `frontend/package.json`

### 4. Add backend SMTP configuration for Gmail

Extend backend configuration so the password-reset flow can send real emails.

Actions:

- Add SMTP host, port, username, password, sender email, sender name, and TLS flags to backend settings.
- Add a frontend application URL used to generate reset links.
- Keep all mail configuration in backend environment files only.
- Do not expose SMTP secrets to the frontend.

Recommended environment variables:

- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USERNAME=your-gmail-address@gmail.com`
- `SMTP_PASSWORD=your-gmail-app-password`
- `SMTP_FROM_EMAIL=your-gmail-address@gmail.com`
- `SMTP_FROM_NAME=CostEstimate AI`
- `SMTP_STARTTLS=true`
- `SMTP_SSL=false`

Files in scope:

- `backend/core/config/settings.py`
- `backend/.env.local`
- `backend/requirements.txt` if the chosen SMTP implementation needs an extra dependency

### 5. Implement password-reset email delivery

Replace the development-only TODO path with real reset email delivery.

Actions:

- Add a dedicated backend mail-sending implementation.
- Build reset URLs that point to the frontend reset page with the token attached.
- Call the mail sender after token creation inside forgot-password.
- Preserve the generic success response whether or not the email exists.
- Keep any `dev_reset_token` response field available only in development if it is still needed for debugging.

Files in scope:

- `backend/app/api/controllers/auth_controller.py`
- Any new backend mail utility module if introduced

### 6. Align auth ownership between frontend and backend

Replace query-parameter ownership with a backend-validated authenticated user context.

Actions:

- Stop using raw `user_id` query parameters for estimate and dashboard ownership.
- Introduce a backend auth dependency that resolves the current user from the authenticated session/token contract.
- Update frontend server and client fetch paths to rely on backend-authenticated ownership instead of passing user identity manually.
- Ensure estimate detail, patch, delete, duplicate, list, and dashboard summary all derive ownership the same way.

Files in scope:

- `frontend/src/auth.ts`
- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/estimates/page.tsx`
- `frontend/src/app/estimates/[id]/page.tsx`
- `frontend/src/app/estimates/[id]/EstimateDetailClient.tsx`
- `backend/app/api/routes/router.py`
- `backend/app/api/controllers/estimates_controller.py`
- New backend auth dependency/module as needed

### 7. Persist wizard results into the estimates workflow

Ensure wizard-generated estimates become first-class persisted records that appear in dashboard and estimate detail views.

Actions:

- Create or reserve an estimate record when a wizard submission starts.
- Update the estimate record when the pipeline completes with status, project info, result JSON, confidence, grand total, and item count.
- Decide whether estimate creation is tied to the authenticated user at submit time and wire it consistently into the persistence path.
- Ensure dashboard and estimate detail views can load freshly generated estimates without relying on transient in-memory session state.

Files in scope:

- `backend/app/api/controllers/form_controller.py`
- `backend/infrastructure/data_layer/database/models/estimate.py`
- `backend/app/api/controllers/estimates_controller.py`
- `frontend/src/app/estimate/new/page.tsx`
- Any repository/data-layer helpers needed for estimate writes

### 8. Normalize error envelopes and validation behavior

Make frontend error handling consume the backend's real error format consistently.

Actions:

- Standardize frontend parsing for backend error payloads emitted under `error.message` and `error.details`.
- Keep backend validation and HTTP errors predictable and documented for frontend consumers.
- Remove assumptions in frontend service code that only FastAPI default `detail` payloads will be returned.
- Verify form validation and submit flows render useful backend validation messages instead of generic failures.

Files in scope:

- `frontend/src/services/estimation.ts`
- `frontend/src/app/login/page.tsx`
- `frontend/src/app/register/page.tsx`
- `frontend/src/app/forgot-password/page.tsx`
- `frontend/src/app/reset-password/page.tsx`
- `backend/core/exceptions/error_handlers.py`
- `backend/app/api/controllers/form_controller.py`
- `backend/app/api/controllers/auth_controller.py`

### 9. Synchronize shared schema, enums, and validation rules

Reduce long-term drift by moving canonical option values and constraints toward one source of truth.

Actions:

- Identify canonical wizard option sets owned by the backend and expose them in a reusable way.
- Align frontend wizard types and selectable values with backend clarification and validation values.
- Align numeric and optional-field validation semantics between frontend form state and backend Pydantic models.
- Prefer generated or shared schema artifacts where practical so UI types are not manually duplicated.

Files in scope:

- `frontend/src/types/wizard.ts`
- `frontend/src/components/wizard/steps/*.tsx`
- `backend/services/clarification_process/clarification_agent.py`
- `backend/app/api/controllers/form_controller.py`
- Shared schema/config module if introduced

### 10. Harden backend execution flow around startup and readiness

Make backend runtime behavior more deterministic during startup.

Actions:

- Validate SMTP configuration at startup or on first mail send with explicit logging.
- Review the Chroma bootstrap path and add a readiness guard or a clear failure mode for early RAG-dependent requests.
- Ensure the application does not appear healthy while required runtime services are partially initialized.
- Verify that database migration succeeds before treating the backend as ready.

Files in scope:

- `backend/app/api/server.py`
- `backend/services/rag_process/service.py`
- Alembic/migration execution path as needed

### 11. Add contract guardrails so sync issues do not recur

Introduce structural checks that make frontend-backend drift visible earlier.

Actions:

- Add response models to frontend-consumed backend routes where missing.
- Consider generating frontend API types from backend OpenAPI or another shared schema source.
- Add focused integration checks around dashboard summary, estimates list/detail, and wizard submission contracts.
- Treat API contract mismatches as verification failures, not just runtime bugs.

Files in scope:

- `backend/app/api/routes/router.py`
- `backend/app/api/schemas/*.py`
- `frontend/src/services/*.ts`
- Frontend and backend test locations as needed

### 12. Verify end-to-end behavior

Run execution and compilation checks for both apps after the changes are made.

Frontend checks:

- Run `npm run lint`.
- Run `npm run build`.
- Confirm the estimate detail route import diagnostic is gone.
- Confirm dashboard, estimates, estimate detail, forgot-password, and reset-password pages all use the unified API base URL.
- Confirm dashboard summary values render from the actual backend field names.
- Confirm estimates list renders from the actual backend list response shape.
- Confirm estimate detail edit/update works without relying on missing payload fields.
- Confirm frontend surfaces backend error messages from the normalized error envelope.

Backend checks:

- Run `alembic upgrade head`.
- Start the API with `uvicorn app.api.server:app`.
- Run a focused backend check such as `pytest tests/unit/test_form_controller_schema.py`.
- Confirm forgot-password creates a token and sends a Gmail message.
- Confirm the reset-password flow accepts the received token and updates the password.
- Confirm login still works with the new password.
- Confirm estimate list, detail, patch, and dashboard summary return contract-aligned payloads.
- Confirm wizard submission creates a persisted estimate and pipeline completion updates it.
- Confirm ownership is enforced through backend-authenticated identity rather than raw query-string user IDs.
- If Chroma bootstrap remains asynchronous, confirm early requests fail deterministically instead of producing partial-initialization errors.

## Relevant Files

### Frontend

- `frontend/.env.local`
- `frontend/package.json`
- `frontend/src/services/estimation.ts`
- `frontend/src/auth.ts`
- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/estimate/new/page.tsx`
- `frontend/src/app/estimates/page.tsx`
- `frontend/src/app/estimates/[id]/page.tsx`
- `frontend/src/app/estimates/[id]/EstimateDetailClient.tsx`
- `frontend/src/app/forgot-password/page.tsx`
- `frontend/src/app/reset-password/page.tsx`
- `frontend/src/app/register/page.tsx`
- `frontend/src/app/login/page.tsx`
- `frontend/src/types/wizard.ts`
- `frontend/src/components/wizard/WizardProgress.tsx`
- `frontend/src/components/wizard/steps/ProjectBasicsStep.tsx`
- `frontend/src/components/wizard/steps/*.tsx`

### Backend

- `backend/.env.local`
- `backend/requirements.txt`
- `backend/core/config/settings.py`
- `backend/core/exceptions/error_handlers.py`
- `backend/app/api/controllers/auth_controller.py`
- `backend/app/api/controllers/form_controller.py`
- `backend/app/api/controllers/estimates_controller.py`
- `backend/app/api/routes/router.py`
- `backend/app/api/schemas/estimate_schemas.py`
- `backend/app/api/server.py`
- `backend/services/rag_process/service.py`
- `backend/services/clarification_process/clarification_agent.py`
- `backend/infrastructure/data_layer/database/models/estimate.py`
- `backend/tests/unit/test_form_controller_schema.py`
- New backend auth dependency/module as needed
- Shared schema/config module as needed

## Verification Commands

### Frontend

```bash
cd frontend
npm run lint
npm run build
```

Additional frontend verification:

```bash
# Verify dashboard, estimates list, estimate detail, forgot-password, reset-password,
# and wizard submission against the running backend.
```

### Backend

```bash
cd backend
source .venv/Scripts/activate
alembic upgrade head
uvicorn app.api.server:app
pytest tests/unit/test_form_controller_schema.py
```

Additional backend verification:

```bash
# Verify persisted estimate creation/update from wizard submission,
# contract-aligned estimate/dashboard payloads, and backend-authenticated ownership.
```

## Risks and Notes

1. The estimate detail import error may be a stale TypeScript server diagnostic rather than a real file-missing problem. Even if it clears after a clean build, use a stable import path if the issue recurs.
2. Gmail SMTP must use an App Password. A normal Gmail account password should not be used.
3. SMTP credentials must remain backend-only and must not be copied into frontend env files.
4. If development still relies on a raw reset token in API responses, that path must remain development-only.
5. If `alembic upgrade head` still fails after the SMTP changes, treat migration startup as a separate backend blocker and inspect the exact Alembic traceback before proceeding.
6. API response-shape changes must be coordinated; changing either frontend or backend alone will keep dashboard and estimates pages broken.
7. Wizard persistence changes must be tied to authenticated ownership, otherwise dashboard synchronization will remain incomplete.
8. If shared schema/type generation is postponed, document the canonical owner for each option set to limit further drift.

## Success Criteria

The plan is complete when all of the following are true:

- The frontend uses only one backend API environment variable.
- Dashboard, estimates list, estimate detail, and error handling use contract-aligned payloads.
- Frontend lint and build succeed.
- Current frontend diagnostics are resolved or proven stale by a clean build.
- The backend accepts Gmail SMTP configuration without exposing secrets.
- Forgot-password sends a real reset email through Gmail SMTP.
- Reset-password works end to end from the frontend.
- Wizard submission creates or updates persisted estimates that appear in dashboard/detail views.
- Ownership is enforced by backend-authenticated identity instead of raw `user_id` query parameters.
- Canonical wizard values and validation rules are synchronized across frontend and backend or clearly sourced from one owner.
- Backend startup and early runtime behavior are explicit and predictable.
- Database migrations and focused backend schema/runtime checks pass.
