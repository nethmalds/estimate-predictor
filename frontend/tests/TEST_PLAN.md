# Frontend Test Plan

**Project:** Construction Cost Estimation Platform  
**Module:** Next.js Frontend  
**Version:** Current (`refactor/flow` branch)  
**Prepared by:** nethmalds  
**Date:** 2026-05-15  
**Environment:** Node.js LTS, Vitest 2.1.9, Playwright, Windows 11

---

## Scope

This test plan covers the wizard multi-step form, SSE streaming progress display, estimation results UI, estimates management screens, API client error handling, and authentication flows of the construction cost estimation frontend.

---

## Test Environment Setup

| Requirement | Value |
|-------------|-------|
| Runtime | Node.js LTS |
| Framework | Next.js 15 + React + TypeScript |
| Unit test runner | Vitest 2.1.9 + JSDOM |
| E2E test runner | Playwright (mocked API via `page.route()`) |
| Dev server | `npm run dev` (required for E2E only) |
| Unit run command | `npm run test:ci` |
| E2E run command | `npx playwright test` |

---

## 1. Authentication & Access Control

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-001 | Authentication | Unauthenticated user is redirected to login from wizard | 1. Open browser in incognito (no session). 2. Navigate to `/wizard`. 3. Observe the page rendered. | No active session | Browser redirected to `/login` | Redirect to `/login` confirmed | ✅ Pass | Verified via E2E (`wizard.spec.ts`) |
| FE-TC-002 | Authentication | Unauthenticated user is redirected to login from estimates | 1. Open browser in incognito. 2. Navigate to `/estimates`. 3. Observe. | No active session | Browser redirected to `/login` | Redirect to `/login` confirmed | ✅ Pass | Verified via E2E (`estimates.spec.ts`) |
| FE-TC-003 | Authentication | Authenticated user can access the wizard page | 1. Log in with valid credentials. 2. Navigate to `/wizard`. 3. Observe the wizard renders. | Valid user session (mocked via `page.route`) | Wizard step 1 is displayed | Wizard page renders correctly | ✅ Pass | Verified via E2E (`wizard.spec.ts`) |
| FE-TC-004 | Authentication | Session token is sent in Authorization header on all API calls | 1. Log in. 2. Trigger any API call (e.g. fetch estimates list). 3. Inspect outgoing request headers. | Valid session token | All outgoing API requests contain `Authorization: Bearer <token>` | Authorization header sent correctly | ✅ Pass | Verified via unit test (`api-client.test.ts`) |
| FE-TC-005 | Authentication | API call without a token does not send Authorization header | 1. Render a component that calls the API while the session token is absent. 2. Inspect the outgoing request. | No token in session store | Request is sent without an Authorization header | No header sent | ✅ Pass | Verified via unit test (`api-client.test.ts`) |

---

## 2. Wizard Step Navigation

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-006 | Wizard Navigation | Progress bar shows correct step number | 1. Load the wizard. 2. Inspect the `aria-valuenow` attribute on the `progressbar` element at each step. | Steps 1 through 5 | `aria-valuenow` matches the current step number | `aria-valuenow` correct at each step | ✅ Pass | Verified via unit test (`WizardProgress.test.tsx`) |
| FE-TC-007 | Wizard Navigation | Progress bar range attributes are correct | 1. Render the `WizardProgress` component. 2. Check `aria-valuemin` and `aria-valuemax`. | 5-step wizard | `aria-valuemin="1"`, `aria-valuemax="5"` | Attributes correct | ✅ Pass | Verified via unit test |
| FE-TC-008 | Wizard Navigation | Current step title appears in the progress bar label | 1. Render progress at step 2 ("Floor Areas"). 2. Read the `aria-label` of the progressbar. | `currentStep: 2` | `aria-label` contains "Floor Areas" | Label contains step title | ✅ Pass | Verified via unit test |
| FE-TC-009 | Wizard Navigation | Completed steps show a screen-reader label | 1. Render progress at step 3. 2. Check that steps 1 and 2 have an sr-only "— completed" label. | `currentStep: 3` | "Project Basics — completed" and "Floor Areas — completed" visible in DOM | Completed labels present | ✅ Pass | Verified via unit test |
| FE-TC-010 | Wizard Navigation | Current step does not show completed label | 1. Render progress at step 2. 2. Assert "Floor Areas — completed" is NOT in the DOM. | `currentStep: 2` | "Floor Areas — completed" absent | Completed label absent for current step | ✅ Pass | Verified via unit test |
| FE-TC-011 | Wizard Navigation | `nextStep` increments step counter | 1. Mount the wizard at step 1. 2. Dispatch `nextStep`. 3. Assert `currentStep` is 2. | Store state starting at step 1 | `currentStep: 2` | Step increments correctly | ✅ Pass | Verified via store unit test |
| FE-TC-012 | Wizard Navigation | `nextStep` does not exceed step 5 | 1. Set `currentStep: 5`. 2. Dispatch `nextStep`. 3. Assert `currentStep` is still 5. | Store state at step 5 | `currentStep` remains 5 | Boundary clamped correctly | ✅ Pass | Verified via store unit test |
| FE-TC-013 | Wizard Navigation | `prevStep` does not go below step 1 | 1. Set `currentStep: 1`. 2. Dispatch `prevStep`. 3. Assert `currentStep` is still 1. | Store state at step 1 | `currentStep` remains 1 | Boundary clamped correctly | ✅ Pass | Verified via store unit test |
| FE-TC-014 | Wizard Navigation | Advancing with valid data shows the next step form | 1. Fill step 1 with a valid building type and floor count. 2. Click "Next". 3. Observe rendered form. | `building_type: residential`, `floor_count: 2` | Step 2 (Floor Areas) form is displayed | Step 2 form rendered | ✅ Pass | Verified via E2E (`wizard.spec.ts`) |

---

## 3. Step 1 — Project Basics

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-015 | Project Basics | Building type selection is validated as required | 1. Leave building type unselected. 2. Attempt to proceed to next step. 3. Observe error state. | Empty building type | Error message displayed, step does not advance | Validation error shown | ✅ Pass | Verified via schema unit test (`wizard.test.ts`) |
| FE-TC-016 | Project Basics | `floor_count` of 0 triggers validation error | 1. Enter `floor_count: 0`. 2. Trigger validation. 3. Observe error. | `floor_count: 0` | Error message: floor count must be at least 1 | Validation error shown | ✅ Pass | Verified via schema unit test |
| FE-TC-017 | Project Basics | `floor_count` above 100 triggers validation error | 1. Enter `floor_count: 101`. 2. Trigger validation. 3. Observe error. | `floor_count: 101` | Error message: floor count must not exceed 100 | Validation error shown | ✅ Pass | Verified via schema unit test |
| FE-TC-018 | Project Basics | Valid residential payload passes step 1 validation | 1. Enter `building_type: residential`, `floor_count: 2`. 2. Trigger validation. | `building_type: residential`, `floor_count: 2` | `validateStep(1, data)` returns no errors | No validation errors | ✅ Pass | Verified via schema unit test |

---

## 4. Step 2 — Floor Areas

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-019 | Floor Areas | Empty floor areas array fails validation | 1. Set `floor_areas: []`. 2. Trigger step 2 validation. | `floor_areas: []` | Validation error: at least one floor area is required | Validation error shown | ✅ Pass | Verified via schema unit test |
| FE-TC-020 | Floor Areas | Area value of zero fails validation | 1. Enter `area_value: 0` for a floor. 2. Trigger validation. | `area_value: 0` | Validation error on the area field | Validation error shown | ✅ Pass | Verified via schema unit test |
| FE-TC-021 | Floor Areas | String area value is coerced to number | 1. Pass `area_value: "150"` as a string to the schema. 2. Check the parsed value type. | `area_value: "150"` | Parsed value is the number `150` | Coercion correct | ✅ Pass | Verified via schema unit test |
| FE-TC-022 | Floor Areas | Valid single-floor entry passes validation | 1. Enter a single floor with `area_value: 150`, `area_unit: sqm`. 2. Trigger validation. | `floor_areas: [{floor_label: "G/F", area_value: 150, area_unit: "sqm"}]` | No validation errors | No errors | ✅ Pass | Verified via schema unit test |

---

## 5. Step 3 — Building Program

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-023 | Building Program | Residential schema validates bedrooms range | 1. Enter `bedrooms: 0`. 2. Trigger validation. | `bedrooms: 0` | Validation error: bedrooms must be at least 1 | Validation error shown | ✅ Pass | Verified via schema unit test |
| FE-TC-024 | Building Program | Residential schema rejects `bedrooms > 50` | 1. Enter `bedrooms: 51`. 2. Trigger validation. | `bedrooms: 51` | Validation error: exceeds maximum | Validation error shown | ✅ Pass | Verified via schema unit test |
| FE-TC-025 | Building Program | Commercial schema validates `washroom_count` | 1. Enter `washroom_count: 0`. 2. Trigger validation. | `washroom_count: 0` | Validation error: must be at least 1 | Validation error shown | ✅ Pass | Verified via schema unit test |
| FE-TC-026 | Building Program | Industrial schema accepts all optional fields absent | 1. Submit step 3 for an industrial project with no optional fields. 2. Trigger validation. | `building_type: industrial`, no optional fields | No validation errors | No errors | ✅ Pass | Verified via schema unit test |

---

## 6. Step 4 — Construction Details

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-027 | Construction Details | Missing `finish_level` triggers validation error | 1. Omit `finish_level` from step 4 data. 2. Trigger validation. | All fields except `finish_level` | Validation error on `finish_level` | Validation error shown | ✅ Pass | Verified via schema unit test |
| FE-TC-028 | Construction Details | Valid construction details payload passes validation | 1. Fill all required fields in step 4. 2. Trigger validation. | `finish_level: standard`, `structural_system: framed`, `roof_type: clay_tile`, `ceiling_type: plastered` | No validation errors | No errors | ✅ Pass | Verified via schema unit test |

---

## 7. Step 5 — Review & Submit

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-029 | Review & Submit | Step 5 has no client-side validation of its own | 1. Call `validateStep(5, data)` with any data. 2. Inspect the result. | Any form data | No errors returned (review step is read-only) | No validation errors | ✅ Pass | Verified via schema unit test |
| FE-TC-030 | Review & Submit | Submit calls `submitWizardForm` with the full payload | 1. Fill all wizard steps. 2. Submit the form on step 5. 3. Inspect the arguments passed to the service call. | Complete residential payload | `submitWizardForm` called once with the combined form payload | Service called with correct payload | ✅ Pass | Verified via hook unit test (`use-wizard.test.ts`) |
| FE-TC-031 | Review & Submit | Submit endpoint is called when the form is submitted via UI | 1. Fill all 5 steps via the E2E wizard flow. 2. Click submit. 3. Verify the intercepted POST request to `/api/estimate-project/form/submit`. | Complete wizard form (mocked backend) | POST request made to submit endpoint | Submit endpoint called | ✅ Pass | Verified via E2E (`wizard.spec.ts`) |
| FE-TC-032 | Review & Submit | `isSubmitting` flag prevents duplicate submission | 1. Trigger submit. 2. While the first submission is in progress, trigger submit again. 3. Observe whether a second call is made. | First submission pending | Second submit call is ignored; `submitWizardForm` called only once | Duplicate call blocked | ✅ Pass | Verified via hook unit test |

---

## 8. SSE Streaming Progress

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-033 | SSE Streaming | Successful submit opens an SSE stream | 1. Submit the wizard form. 2. Observe that `openFormEstimateStream` is called. 3. Check that an EventSource connection is established. | Valid submission payload | SSE stream opened with the correct session ID | Stream opened after submit | ✅ Pass | Verified via hook unit test |
| FE-TC-034 | SSE Streaming | Store session is set after successful submit | 1. Submit the form. 2. Inspect the Zustand store after the submit resolves. | Valid submission, mock returns `session_id: "sess-123"` | `store.sessionId === "sess-123"` and `store.estimateId` are set | Store session set correctly | ✅ Pass | Verified via hook unit test |
| FE-TC-035 | SSE Streaming | Progress events are appended to the store | 1. Open a stream. 2. Dispatch a `progress` event from the fake EventSource. 3. Inspect `store.streamEvents`. | `{event: "progress", data: {stage: "boq"}}` | `streamEvents` array contains the dispatched event | Event appended to store | ✅ Pass | Verified via hook unit test |
| FE-TC-036 | SSE Streaming | Completed event triggers `onComplete` callback and sets status | 1. Open a stream. 2. Dispatch a `completed` event. 3. Observe callback and store status. | `{event: "completed", data: {boq_items: [...]}}` | `onComplete` called once, `store.status === "completed"` | Callback called, status set | ✅ Pass | Verified via hook unit test |
| FE-TC-037 | SSE Streaming | Error event triggers `onError` callback and sets error status | 1. Open a stream. 2. Dispatch an `error` event. 3. Observe callback and store status. | `{event: "error", data: {message: "Pipeline failed"}}` | `onError` called once, `store.status === "error"` | Callback called, error status set | ✅ Pass | Verified via hook unit test |
| FE-TC-038 | SSE Streaming | Network error during submit sets error status | 1. Mock `submitWizardForm` to throw. 2. Trigger submit. 3. Inspect store status. | `submitWizardForm` rejects with a network error | `store.status === "error"` | Error status set | ✅ Pass | Verified via hook unit test |
| FE-TC-039 | SSE Streaming | Cancellation closes the stream and resets session | 1. Open a stream. 2. Call `cancel()`. 3. Inspect the EventSource state and store. | Active stream | EventSource `close()` called, `store.sessionId === null`, `store.status === "idle"` | Stream closed, session reset | ✅ Pass | Verified via hook unit test |
| FE-TC-040 | SSE Streaming | Prior stream events are cleared on new session start | 1. Dispatch two events. 2. Call `setSession("new-s", "new-e")`. 3. Inspect `streamEvents`. | Two events appended before `setSession` | `streamEvents` is empty after `setSession` | Events cleared | ✅ Pass | Verified via store unit test |

---

## 9. Results — BOQ Table

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-041 | BOQ Table | Item count is displayed in the card title | 1. Render `FullBoqTable` with 3 items. 2. Inspect the card heading. | `boq_items` array with 3 entries | Card heading contains "3" | Item count shown | ✅ Pass | Verified via component unit test |
| FE-TC-042 | BOQ Table | One row is rendered per BOQ item | 1. Render `FullBoqTable` with 5 items. 2. Count the table rows. | 5 BOQ items | 5 data rows in the table | Row count matches | ✅ Pass | Verified via component unit test |
| FE-TC-043 | BOQ Table | Grand total is displayed in the table footer | 1. Render `FullBoqTable` with known cost values. 2. Inspect the footer row. | Items with calculable totals | Grand total value visible in the footer | Grand total shown | ✅ Pass | Verified via component unit test |
| FE-TC-044 | BOQ Table | Section label is visible for each item | 1. Render items with distinct `section` values. 2. Inspect visible text. | `section: "Masonry"` and `section: "Concrete"` | Section names visible in the rendered table | Sections visible | ✅ Pass | Verified via component unit test |
| FE-TC-045 | BOQ Table | Filter input narrows displayed rows by description | 1. Render the table with 3 items of distinct descriptions. 2. Type a description substring into the filter input. 3. Count visible rows. | Filter text matching only 1 of 3 items | Only the matching row is visible | Filter works correctly | ✅ Pass | Verified via component unit test |
| FE-TC-046 | BOQ Table | Pagination controls appear when items exceed page size | 1. Render `FullBoqTable` with 30 items (page size = 25). 2. Check for pagination controls in the DOM. | 30 items | Pagination controls rendered | Pagination visible | ✅ Pass | Verified via component unit test |
| FE-TC-047 | BOQ Table | No pagination for fewer items than page size | 1. Render with 10 items. 2. Check for pagination controls. | 10 items (< 25 page size) | No pagination controls rendered | No pagination | ✅ Pass | Verified via component unit test |
| FE-TC-048 | BOQ Table | Empty items array renders without crashing | 1. Render `FullBoqTable` with `boq_items: []`. 2. Observe rendered output. | `boq_items: []` | Component renders, empty state shown, no JS error | Renders without error | ✅ Pass | Verified via component unit test |
| FE-TC-049 | BOQ Table | `bsr_description` is used as fallback when `description` is absent | 1. Render an item with `description: undefined` and `bsr_description: "Brick wall"`. 2. Inspect the row. | `{bsr_description: "Brick wall", description: undefined}` | Row displays "Brick wall" | Fallback text shown | ✅ Pass | Verified via component unit test |

---

## 10. Results — Confidence & Cost Breakdown

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-050 | Confidence Card | Confidence score is displayed as a percentage | 1. Render `ConfidenceBreakdownCard` with `score: 0.87`. 2. Inspect visible text. | `score: 0.87` | "87%" visible on the card | "87%" displayed | ✅ Pass | Verified via component unit test |
| FE-TC-051 | Confidence Card | Breakdown entries are rendered when provided | 1. Render with a `breakdown` object containing two entries. 2. Count visible entries. | `breakdown: {quantity_coverage: 0.1, match_rate: 0.05}` | Both entries visible | Both entries rendered | ✅ Pass | Verified via component unit test |
| FE-TC-052 | Confidence Card | Section confidence bars are rendered for each section | 1. Render with a `section_breakdown` of two sections. 2. Count progress bar elements. | Two sections in `section_breakdown` | Two section bars visible | Section bars rendered | ✅ Pass | Verified via component unit test |
| FE-TC-053 | Confidence Card | Zero confidence score does not crash the component | 1. Render with `score: 0`. 2. Observe component renders. | `score: 0` | Component renders "0%", no error | Renders without crash | ✅ Pass | Verified via component unit test |
| FE-TC-054 | Cost Chart | Cost breakdown bar chart renders with data | 1. Render `CostBreakdownChart` with a `subtotals` map. 2. Check that the chart container is in the DOM. | `subtotals: {Masonry: 50000, Concrete: 30000}` | Chart container rendered | Chart rendered | ✅ Pass | Verified via component unit test (Recharts mocked) |
| FE-TC-055 | Cost Chart | Empty subtotals renders without crashing | 1. Render `CostBreakdownChart` with `subtotals: {}`. 2. Observe output. | `subtotals: {}` | Component renders without a JS error | Renders without crash | ✅ Pass | Verified via component unit test |

---

## 11. Estimates Management

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-056 | Estimates List | Project names from API response are displayed | 1. Navigate to `/estimates` with mocked API returning two estimates. 2. Check visible project names. | Mocked estimates: `[{title: "House A"}, {title: "Office B"}]` | "House A" and "Office B" visible on the page | Project names shown | ✅ Pass | Verified via E2E (`estimates.spec.ts`) |
| FE-TC-057 | Estimates List | Status badges are displayed per estimate | 1. Navigate to `/estimates` with one `completed` and one `in_progress` estimate. 2. Check badge labels. | Mixed status estimates | "completed" and "in_progress" badge labels visible | Status badges shown | ✅ Pass | Verified via E2E |
| FE-TC-058 | Estimates List | Empty state is shown when no estimates exist | 1. Mock the list API to return an empty array. 2. Navigate to `/estimates`. 3. Observe. | `[]` from API | Empty state message or placeholder is displayed | Empty state rendered | ✅ Pass | Verified via E2E |
| FE-TC-059 | Estimates List | `useEstimateList` does not fetch without a token | 1. Render the hook without a session token. 2. Observe whether a network request is made. | No session token | No fetch request made | No fetch called | ✅ Pass | Verified via hook unit test (`use-estimates.test.ts`) |
| FE-TC-060 | Estimates List | `useEstimateList` passes page and pageSize to service | 1. Render hook with `page=2, pageSize=10`. 2. Inspect the service call arguments. | `page: 2`, `pageSize: 10` | Service called with `(token, page=2, pageSize=10)` | Correct args passed | ✅ Pass | Verified via hook unit test |
| FE-TC-061 | Estimates Detail | Detail page shows project name and a BOQ item | 1. Navigate to `/estimates/{id}` with a mocked detail response. 2. Check visible content. | Mocked detail: `{title: "House A", boq_items: [{description: "Excavation"}]}` | "House A" and "Excavation" visible | Detail content shown | ✅ Pass | Verified via E2E |
| FE-TC-062 | Estimates Detail | `useEstimateDetail` does not fetch when estimate ID is absent | 1. Render hook with `estimateId: undefined`. 2. Observe fetches. | No estimate ID | No fetch request made | No fetch called | ✅ Pass | Verified via hook unit test |
| FE-TC-063 | Estimates — Delete | `useDeleteEstimate` calls the delete service on mutate | 1. Trigger `useDeleteEstimate.mutate(id)`. 2. Inspect service call. | Valid estimate ID | `deleteEstimate` service called with the correct ID | Service called | ✅ Pass | Verified via hook unit test |
| FE-TC-064 | Estimates — Patch | `usePatchEstimate` calls the patch service and surfaces errors | 1. Mock `patchEstimate` to reject. 2. Trigger mutate. 3. Observe the error state. | Service rejection | Mutation error is surfaced to the caller | Error surfaced | ✅ Pass | Verified via hook unit test |

---

## 12. API Client & Error Handling

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-065 | API Client | Successful GET request returns parsed JSON | 1. Call `apiClient.get` against a mocked 200 response. 2. Inspect the return value. | Response: `{id: 1, title: "Test"}` | Resolved value equals `{id: 1, title: "Test"}` | JSON parsed correctly | ✅ Pass | Verified via unit test (`api-client.test.ts`) |
| FE-TC-066 | API Client | 204 No Content response returns `undefined` | 1. Call `apiClient.get` against a mocked 204 response. 2. Inspect the return value. | HTTP 204 with no body | Return value is `undefined` | `undefined` returned | ✅ Pass | Verified via unit test |
| FE-TC-067 | API Client | FastAPI `detail` string is extracted as error message | 1. Call `apiClient.get` against a 400 response with body `{detail: "Not found"}`. 2. Inspect the thrown error. | `{detail: "Not found"}` | Thrown `ApiError` has `message === "Not found"` | Message extracted correctly | ✅ Pass | Verified via unit test |
| FE-TC-068 | API Client | FastAPI array `detail` extracts first item message | 1. Mock a 422 response with `{detail: [{msg: "field required"}]}`. 2. Trigger a request. 3. Inspect the error. | Pydantic 422 error shape | `ApiError.message` contains the first item's message | First item extracted | ✅ Pass | Verified via unit test |
| FE-TC-069 | API Client | Non-JSON error body falls back to HTTP status string | 1. Mock a 500 response with plain text body. 2. Trigger a request. 3. Inspect the error message. | Plain text 500 body | `ApiError.message` contains the HTTP status description | Status string used as fallback | ✅ Pass | Verified via unit test |
| FE-TC-070 | API Client | Network failure propagates as a rejected promise | 1. Mock `fetch` to reject with a network error. 2. Call `apiClient.get`. 3. Observe the error. | `fetch` rejects with `TypeError: Failed to fetch` | Promise rejects with the original network error | Error propagated | ✅ Pass | Verified via unit test |
| FE-TC-071 | API Client | `POST` sets `Content-Type: application/json` | 1. Call `apiClient.post` with a JSON body. 2. Inspect the outgoing request headers. | `{key: "value"}` as body | `Content-Type: application/json` header present | Header set correctly | ✅ Pass | Verified via unit test |
| FE-TC-072 | API Client | `postForm` does not set `Content-Type` | 1. Call `apiClient.postForm` with a `FormData` object. 2. Inspect headers. | `FormData` body | No `Content-Type` header set (browser sets multipart boundary automatically) | Header absent | ✅ Pass | Verified via unit test |

---

## 13. Excel Export

| Test Case ID | Feature | Test Scenario | Test Steps | Test Data | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|---|
| FE-TC-073 | Excel Export | Report contains Summary, Bill of Quantities, and Cost Breakdown sheets | 1. Call `generateExcelReport` with a full estimate result. 2. Inspect the sheet names passed to `book_append_sheet`. | Full estimate with `boq_items`, `costs`, `confidence` | Three sheets appended: "Summary", "Bill of Quantities", "Cost Breakdown" | All three sheets appended | ✅ Pass | Verified via unit test (`chat-utils.test.ts`) |
| FE-TC-074 | Excel Export | `generateExcelReport` returns an `ArrayBuffer` | 1. Call `generateExcelReport` with any data. 2. Inspect the return type. | Any valid estimate data | Return value is an `ArrayBuffer` | `ArrayBuffer` returned | ✅ Pass | Verified via unit test |
| FE-TC-075 | Excel Export | Empty estimate data does not throw during export | 1. Call `generateExcelReport({})`. 2. Observe whether an exception is thrown. | `{}` (empty estimate) | Function completes without throwing | No error thrown | ✅ Pass | Verified via unit test |

---

## Summary

| Category | Total Cases | Pass | Fail | Not Tested |
|---|---|---|---|---|
| Authentication & Access Control | 5 | 5 | 0 | 0 |
| Wizard Navigation | 9 | 9 | 0 | 0 |
| Step 1 — Project Basics | 4 | 4 | 0 | 0 |
| Step 2 — Floor Areas | 4 | 4 | 0 | 0 |
| Step 3 — Building Program | 4 | 4 | 0 | 0 |
| Step 4 — Construction Details | 2 | 2 | 0 | 0 |
| Step 5 — Review & Submit | 4 | 4 | 0 | 0 |
| SSE Streaming Progress | 8 | 8 | 0 | 0 |
| Results — BOQ Table | 9 | 9 | 0 | 0 |
| Results — Confidence & Cost | 6 | 6 | 0 | 0 |
| Estimates Management | 9 | 9 | 0 | 0 |
| API Client & Error Handling | 8 | 8 | 0 | 0 |
| Excel Export | 3 | 3 | 0 | 0 |
| **Total** | **75** | **75** | **0** | **0** |
