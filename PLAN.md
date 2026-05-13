# Industry-Grade Hardening Plan — Backend + Frontend (v2, with shipped DevOps)

> **Status: Phases 1–5 ✅ SHIPPED · H11 ✅ SHIPPED · Phase 6 pending.**
> **What changed in v2**: Phase 5 (DevOps) is fully specified with concrete artifacts — backend Dockerfile, frontend Dockerfile, `docker-compose.prod.yml`, `run.sh`, `Caddyfile`, `.env.example`. Phase 6 gains a Chrome MCP install subsection (6.9) so future sessions can drive audits autonomously. H11 (email verification) was added from the gap analysis and shipped alongside Phase 5.

---

## Context

This is a **construction cost estimation platform** built around a RAG pipeline: BOQ (Bill of Quantities) line-items are matched to official BSR (Building Standard Rate) codes via vector + keyword fusion, with an 11-stage estimation pipeline (floorplan CV → LLM BOQ generation → ML item prediction → RAG matching → quantity take-off → pricing → validation → reporting).

- **Backend**: FastAPI 0.115 + SQLAlchemy 2.0 (sync ORM) + Alembic + PostgreSQL 16 + ChromaDB 0.5.5 + Sentence Transformers + Ollama Cloud LLM
- **Frontend**: Next.js 16 (App Router) + React 19 (Compiler enabled) + TypeScript strict + shadcn/ui + Tailwind 4 + Zustand + React Query + NextAuth v5

**Goal**: Bring this to industry-grade standards suitable for a **single-server VPS/Docker production deployment**, prioritizing security correctness first, then quality, then performance/observability — and provide a **one-command production runner** (`./run.sh up`) so the full stack boots cleanly on a fresh VPS.

**Out of scope** (per user direction):
- Async SQLAlchemy migration (keep sync + `asyncio.to_thread()` pattern)
- Kubernetes / Helm (stay on Docker Compose)
- Replacing NextAuth v5 (harden config only)
- Local Ollama container (keep using **Ollama Cloud** at `https://ollama.com` via `OLLAMA_API_KEY`)

**Deployment target**: single VPS, Docker Compose, Caddy reverse proxy + auto-TLS, no K8s.

---

## Codebase snapshot (from exploration)

### Backend layout
```
backend/
├── app/api/         controllers, routes, schemas, middleware, services
├── application/     pipelines/estimation_pipeline.py (11-stage flow)
├── core/            config/settings.py, exceptions/error_handlers.py
├── infrastructure/  data_layer/{database,vector_db}, integrations/ollama_client.py,
│                    ai/models/** (object detection + ML predictors, ~35 MB)
├── services/        rag_process, item_gen_process, quantity_gen_process,
│                    pricing_process, floorplan_process, clarification_process,
│                    validation, reporting_process
├── tests/           unit (11 files, ~1.8k LOC), integration (1 file, 309 LOC)
└── docker/          Dockerfile, Dockerfile.dockerignore, docker-compose.yml
```

Architecture pattern: **clean / layered** — Controllers → Services → Repositories → ORM. Dependency injection via FastAPI `Depends()`.

### Frontend layout
```
frontend/src/
├── app/             App Router routes; (auth) public, /dashboard protected
├── components/      shadcn primitives + wizard steps + layout + results
├── services/        auth.service.ts, estimates.service.ts, floorplan.service.ts
├── lib/             api-client.ts (custom fetch wrapper), utils, uploadthing
├── hooks/           use-auth, use-estimates (React Query w/ smart polling)
├── store/           wizard-store.ts (Zustand + localStorage persist)
├── types/           barrel-exported domain types
├── auth.ts          NextAuth v5 Credentials provider, JWT, 7-day session
└── middleware.ts    protected route enforcement
```

### Runtime facts

| Concern | Current state | Source |
|---|---|---|
| Backend entrypoint | `uvicorn app.api.server:app --host 0.0.0.0 --port 8000` | [backend/app/api/server.py](backend/app/api/server.py) |
| Backend health | `GET /health` returns `{status, env, smtp_configured}` | [backend/app/api/server.py](backend/app/api/server.py) |
| Migrations | Auto-run on startup via `init_db()` in startup hook | [backend/app/api/server.py](backend/app/api/server.py) |
| Python version | 3.10 (3.10.11 in dev) | `backend/.venv/pyvenv.cfg` |
| Native deps | `tesseract-ocr`, `libgl1-mesa-glx`, `libglib2.0-0` (PyMuPDF, ultralytics, pytesseract, PIL) | [backend/requirements.txt](backend/requirements.txt) |
| ML model assets | `backend/infrastructure/ai/models/**` (~35 MB) | local files; baked into image |
| BSR seed PDF | `backend/infrastructure/data_layer/storage/bsr_wp_2025.pdf` (5 MB) | mounted as volume |
| HF cache | `all-MiniLM-L6-v2` to `~/.cache/huggingface/` first run | persistent volume `hf_cache` |
| Backend env vars | `POSTGRES_*`, `CHROMA_*`, `OLLAMA_*`, `API_SECRET_KEY`, `EMBEDDING_MODEL`, `SMTP_*`, `CORS_ALLOW_ORIGINS`, `ENV` | [backend/core/config/settings.py](backend/core/config/settings.py) |
| Ollama client | External Cloud at `${OLLAMA_HOST:-https://ollama.com}` with `OLLAMA_API_KEY` | [backend/infrastructure/integrations/ollama_client.py](backend/infrastructure/integrations/ollama_client.py) |
| Frontend build/start | `next build` / `next start`; npm; Node 20+ | [frontend/package.json](frontend/package.json) |
| Frontend Next.js | 16.x, App Router, React Compiler enabled; `output: "standalone"` **now set** | [frontend/next.config.ts](frontend/next.config.ts) |
| Frontend env vars | Build: `NEXT_PUBLIC_API_BASE_URL`. Runtime: `AUTH_SECRET`, `UPLOADTHING_TOKEN` | [frontend/src/lib/api-client.ts](frontend/src/lib/api-client.ts), [frontend/src/auth.ts](frontend/src/auth.ts) |
| Existing dev compose | postgres + chroma only — kept untouched as the dev workflow | [backend/docker/docker-compose.yml](backend/docker/docker-compose.yml) |

---

## Findings — prioritized by severity

### 🔴 CRITICAL (security / correctness)

| # | Finding | Location | Status |
|---|---------|----------|--------|
| C1 | **Secrets committed in git**: `OLLAMA_API_KEY`, `API_SECRET_KEY`, SMTP password live in tracked `backend/.env.local` | `backend/.env.local` | ✅ **SHIPPED** |
| C2 | **No rate limiting** on login, password reset, `/match-boq`, registration — brute-force / DoS exposure | `app/api/routes/router.py` | ✅ **SHIPPED** |
| C3 | **Overly permissive CORS** in production (`allow_methods=["*"]`, `allow_headers=["*"]`, `allow_credentials=True`) | `app/api/server.py` | ✅ **SHIPPED** |
| C4 | **No security headers** anywhere (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy) | `next.config.ts`, `app/api/server.py` | ✅ **SHIPPED** |
| C5 | **Print statement leaking timing data** in production code path | `services/item_gen_process/llm_client.py:35` | ✅ **SHIPPED** |
| C6 | **Frontend wizard data in localStorage** (project details persist unencrypted; minor risk on shared machines) | `src/store/wizard-store.ts` | ✅ **SHIPPED** |

### 🟠 HIGH (production blockers)

| # | Finding | Location | Status |
|---|---------|----------|--------|
| H1 | **Frontend has zero tests** — no Vitest/Jest, no Playwright | `frontend/package.json` | ✅ **SHIPPED** |
| H2 | **No CI/CD pipeline** anywhere — no GitHub Actions, no pre-commit | repo root | ✅ **SHIPPED** |
| H3 | **`pytest` not in `requirements.txt`** — backend tests can't be installed cleanly | `backend/requirements.txt` | ✅ **SHIPPED** |
| H4 | **Backend logging is anemic** (only 8 logger calls; no audit log for auth/estimates/RAG; no structured JSON logs) | scattered | ✅ **SHIPPED** |
| H5 | **No error tracking** (no Sentry on either side) — production failures invisible | both | ✅ **SHIPPED** |
| H6 | **Raw `<img>` in wizard** instead of `next/image` — unoptimized LCP, bandwidth | `src/components/wizard/steps/ProjectBasicsStep.tsx:291` | ✅ **SHIPPED** |
| H7 | **No code quality tooling on backend** — no ruff, black, mypy, pre-commit | repo root | ✅ **SHIPPED** |
| H8 | **JWT lifetime = 7 days, no refresh tokens** — long blast radius if leaked | `app/api/services/auth_service.py`, `src/auth.ts` | ✅ **SHIPPED** (TTL → 24 h) |
| H9 | **No connection pool tuning** — defaults to `pool_size=5, max_overflow=10` | `infrastructure/data_layer/database/session.py:11` | ✅ **SHIPPED** |
| H10 | **Wizard form validation is manual** — no zod/RHF, no shared FE/BE schema | `src/app/dashboard/estimate/new/page.tsx:55-89` | ✅ **SHIPPED** |
| H11 | **No email verification on registration** — accounts go active immediately; password reset unsafe on unverified address | `backend/app/api/services/auth_service.py`, `backend/infrastructure/data_layer/database/models/user.py` | ✅ **SHIPPED** |

### 🟡 MEDIUM (quality / DX)

| # | Finding | Location | Status |
|---|---------|----------|--------|
| M1 | **No API versioning** — single `/api/` prefix, breaks future clients on changes | `app/api/routes/router.py` | ⏳ Phase 5b |
| M2 | **No `X-Request-ID` correlation** across logs/responses | backend middleware | ✅ **SHIPPED** |
| M3 | **Potential N+1 in RAG matching** — items fetched in loop | `services/rag_process/service.py:92-95` | ✅ **SHIPPED** |
| M4 | **Migrations run synchronously on startup** — slow cold-start, race risk on multi-instance | `app/api/server.py` startup hook | ⏳ Phase 5b |
| M5 | **No caching layer** (Redis) for BSR lookups, sessions, dashboard summaries | n/a | ✅ **SHIPPED** (Redis session store; BSR cache deferred) |
| M6 | **Frontend: no SEO metadata beyond root layout**, no dynamic `generateMetadata`, no OG tags, no sitemap/robots | `src/app/layout.tsx` | ✅ **SHIPPED** |
| M7 | **Accessibility unverified** — no automated audit, no skip links, no explicit focus management observed | various | ⚠️ Phase 6 (static fixes shipped; live aXe audit pending) |
| M8 | **Inconsistent migration naming** — mix of descriptive + auto-generated revision IDs | `infrastructure/data_layer/database/migrations/versions/` | ⏳ Phase 5b |
| M9 | **No bundle analysis** — Recharts/Sonner/UploadThing not measured | `next.config.ts` | ✅ **SHIPPED** |
| M10 | **Session cleanup is in-process** (`ProcessSessionStore`) — won't survive restart, doesn't scale beyond 1 worker | `app/api/state/session.py` | ✅ **SHIPPED** |

### 🟢 LOW (polish)

| # | Finding | Location | Status |
|---|---------|----------|--------|
| L1 | No README documentation of `/docs` (FastAPI auto-OpenAPI) | `backend/README.md` | ⏳ Phase 5b |
| L2 | `AGENTS.md` / `CLAUDE.md` are near-empty | both | ⏳ Phase 5b |
| L3 | No Prettier config / format script | `frontend/package.json` | ⏳ Phase 5b |
| L4 | Hardcoded embedding text strategy | `services/rag_process/service.py:70` | ⏳ Phase 5b |
| L5 | No `.editorconfig` | repo root | ⏳ Phase 5b |

---

## Phased roadmap

### Phase 1 — Security & correctness ✅ SHIPPED
Make the app safe to expose.

- Resolve C1–C6, H3, H8 partial (shorten JWT TTL)
- Rotate secrets, purge from git history, hard-fail in prod when defaults used
- Add `slowapi` rate limiting on auth/RAG endpoints
- Lock CORS in prod via env-driven allowlist
- Ship security headers middleware (backend) + `next.config.ts` headers (frontend)
- Replace print → logger; remove leaked SMTP creds from `.env.local`

**Key files:**
- `backend/.env.local` — delete from tracking, replace with `.env.example`
- `backend/app/api/server.py` — CORS, security headers middleware, rate limiter wiring
- `backend/core/config/settings.py` — hard-fail in prod when secrets absent
- `backend/app/api/services/auth_service.py` — shorten JWT TTL, add refresh
- `backend/services/item_gen_process/llm_client.py:35` — print → logger
- `frontend/next.config.ts` — security headers in `headers()`
- `frontend/src/auth.ts` — align session maxAge with backend

**Phase 1 smoke test:**
- Hit `/api/auth/login` with invalid creds 20× rapidly → confirm 429
- `curl -I` on any endpoint → confirm CSP/HSTS/X-Frame-Options headers present

---

### Phase 2 — Quality gates & testing ✅ SHIPPED
Never regress what you fixed.

- H1, H2, H3, H7, H10
- Backend: add `pytest`, `pytest-cov`, `ruff`, `black`, `mypy` to requirements; `pyproject.toml` config; pre-commit hooks
- Frontend: add Vitest + RTL for unit/component tests, Playwright for E2E (login → wizard → estimate detail)
- GitHub Actions CI: lint + typecheck + test on PR; build images on main
- Form validation: introduce `zod` schema reused across wizard steps; share schema shapes via OpenAPI codegen (`openapi-typescript`) so backend Pydantic is the source of truth

**Key files:**
- `backend/requirements.txt` + new `backend/pyproject.toml`
- `backend/.pre-commit-config.yaml` (new)
- `.github/workflows/ci.yml` (new)
- `frontend/package.json` (add vitest, @testing-library/react, playwright, prettier)
- `frontend/vitest.config.ts`, `frontend/playwright.config.ts` (new)
- `frontend/src/lib/schemas/` (new — zod schemas)

**Phase 2 smoke test:**
- `pytest --cov` ≥ 80% backend
- `npm test` + `npm run test:e2e` green
- CI green on a throwaway PR

---

### Phase 3 — Observability ✅ SHIPPED
See what's happening in prod.

- H4, H5, M2
- Backend: structured JSON logging (loguru or stdlib + `python-json-logger`); audit log for login / password reset / estimate mutate; Sentry SDK; `X-Request-ID` middleware (uuid4 if absent, echo back, attach to logs)
- Frontend: Sentry browser SDK with session replay (privacy-masked); web-vitals reporting
- Add `/healthz` and `/readyz` endpoints (DB ping, Chroma ping)
- (Optional) Posthog client-side (already in deps)

**Key files:**
- `backend/core/logging/__init__.py` (new — structured logger setup)
- `backend/app/api/middleware/request_id.py` (new)
- `backend/app/api/middleware/audit_log.py` (new)
- `backend/core/observability/sentry.py` (new)
- `frontend/src/lib/sentry.ts` (new), `frontend/sentry.{client,server,edge}.config.ts` (new)

**Phase 3 smoke test:**
- Trigger error → confirm Sentry receives it on both sides
- Tail logs → confirm JSON shape + `request_id` correlation

---

### Phase 4 — Performance & resilience ✅ SHIPPED
Handle real load.

- H6, H9, M3, M4, M5, M9, M10
- Backend: connection pool tuning (`pool_size=20, max_overflow=10, pool_recycle=3600`); fix RAG N+1 with batch `BSRItem.id.in_()`; move migrations out of startup hook into `alembic upgrade head` entrypoint step; introduce Redis for session store + BSR cache
- Frontend: replace `<img>` with `next/image`; bundle analysis (`@next/bundle-analyzer`); React.memo / useMemo on hot wizard re-renders; add `loading="lazy"` for below-fold media

**Key files:**
- `backend/infrastructure/data_layer/database/session.py:11` (pool config)
- `backend/services/rag_process/service.py:92` (batch fetch)
- `backend/infrastructure/cache/redis_client.py` (new)
- `backend/app/api/state/session.py` (Redis-backed implementation)
- `frontend/src/components/wizard/steps/ProjectBasicsStep.tsx:291` (next/image)
- `frontend/next.config.ts` (bundle analyzer)

**Phase 4 smoke test:**
- Lighthouse perf score ≥ 90 (desktop)
- `pg_stat_activity` shows pool reuse
- RAG matching p95 latency drop

---

### Phase 5 — DevOps & production polish ✅ SHIPPED

One-command production deployment.

**Shipped artifacts:**

| File | Description |
|------|-------------|
| [backend/docker/Dockerfile](backend/docker/Dockerfile) | 2-stage Python 3.10-slim build; non-root user `app`; HEALTHCHECK on `/health` |
| [backend/docker/Dockerfile.dockerignore](backend/docker/Dockerfile.dockerignore) | Dockerfile-specific ignore rules for `.venv/`, `__pycache__/`, `.env*`, `tests/`, uploads |
| [frontend/docker/Dockerfile](frontend/docker/Dockerfile) | 3-stage Node 20-alpine build; standalone output; non-root user `nextjs` |
| [frontend/docker/Dockerfile.dockerignore](frontend/docker/Dockerfile.dockerignore) | Dockerfile-specific ignore rules for `node_modules/`, `.next/`, `.env*`, coverage |
| [frontend/next.config.ts](frontend/next.config.ts) | Added `output: "standalone"` |
| [docker-compose.prod.yml](docker-compose.prod.yml) | 5-service stack: postgres → chroma → backend → frontend → caddy on `estimator_net` |
| [Caddyfile](Caddyfile) | Auto-TLS; routes `/api/*`, `/health`, `/docs` → backend; all else → frontend |
| [.env.example](.env.example) | Template for all required env vars |
| [run.sh](run.sh) | `up / down / logs / rebuild / status / migrate` with env validation |
| [.gitignore](.gitignore) | Root-level; gitignores `.env`, `.env.local`, `audits/`, `.claude/` |

**Unchanged (intentional):**
- [backend/docker/docker-compose.yml](backend/docker/docker-compose.yml) — kept as the **dev** compose (Postgres + Chroma only). Devs continue: `docker compose up -d` from `backend/docker/` + `uvicorn ... --reload` + `npm run dev`.

**Deferred to Phase 5b:**
- Automated DB backups (`backend/scripts/backup.sh` — pg_dump cron sidecar)
- API versioning (`/api/v1/`)
- M1, M6, M8, L1–L5

#### Quick start (production)

```bash
cp .env.example .env         # fill in all values (production env)
chmod +x run.sh
./run.sh up                  # builds images, starts all 5 services
./run.sh status              # check all services are healthy
./run.sh logs                # tail live logs
./run.sh migrate             # run alembic upgrade head manually
./run.sh down                # stop everything
```

#### Phase 5 verification checklist

1. **Service health** — `./run.sh status` shows all five services `healthy`.
2. **Backend** — `curl http://localhost/health` returns `{"status":"ok","env":"production","smtp_configured":true|false}`.
3. **Migrations** — `./run.sh logs | grep -i alembic` shows `Running upgrade -> ...` lines.
4. **Frontend SSR** — `curl -I http://localhost/` returns `200` and `x-powered-by: Next.js`.
5. **Round-trip** — open `http://localhost/login`, register a user, log in. Network tab shows `/api/...` proxied by Caddy.
6. **Wizard smoke** — start estimate → upload floorplan → submit → SSE stream visible → estimate detail renders.
7. **Persistence** — `./run.sh down && ./run.sh up`; existing user + estimate survive.
8. **Resources** — `docker stats` shows backend ≤ 2 GB, frontend ≤ 250 MB at idle.
9. **Image size** — backend ≤ 4 GB (PyTorch is large), frontend ≤ 400 MB.
10. **TLS (prod only)** — `curl -I https://$DOMAIN` returns `200` with Let's Encrypt cert.

**Likely failure modes:**
- Backend OOM → bump host RAM or add `mem_limit: 2g` in compose.
- Frontend build fails → confirm `NEXT_PUBLIC_API_BASE_URL` is in `.env` and passed via `args:`.
- Caddy can't get cert → check ports 80/443 are reachable and `DOMAIN` matches DNS.

---

### H11 — Email verification ✅ SHIPPED

Shipped alongside Phase 5. Accounts now require email verification before login is allowed.

**What was added:**

**Backend:**
| File | Change |
|------|--------|
| [backend/infrastructure/data_layer/database/models/user.py](backend/infrastructure/data_layer/database/models/user.py) | Added `is_verified`, `verification_token`, `verification_sent_at` columns |
| [backend/infrastructure/data_layer/database/migrations/versions/0003_add_email_verification_to_users.py](backend/infrastructure/data_layer/database/migrations/versions/0003_add_email_verification_to_users.py) | New Alembic migration |
| [backend/infrastructure/data_layer/database/repositories/user_repository.py](backend/infrastructure/data_layer/database/repositories/user_repository.py) | Added `find_by_verification_token`, `set_verification_token`, `mark_verified` |
| [backend/app/api/services/auth_service.py](backend/app/api/services/auth_service.py) | `register` sends verification email; `login` gated on `is_verified`; `forgot_password` gated on `is_verified`; new `verify_email()` + `resend_verification_email()` |
| [backend/app/api/controllers/auth_controller.py](backend/app/api/controllers/auth_controller.py) | New `verify_email` and `resend_verification` route handlers |
| [backend/app/api/routes/router.py](backend/app/api/routes/router.py) | `GET /api/auth/verify-email` and `POST /api/auth/resend-verification` |
| [backend/app/api/schemas/auth_schemas.py](backend/app/api/schemas/auth_schemas.py) | Added `ResendVerificationRequest`, `VerifyEmailResponse` |

**Frontend:**
| File | Change |
|------|--------|
| [frontend/src/auth.ts](frontend/src/auth.ts) | Throws `EmailNotVerifiedError` (code: `"email_not_verified"`) when backend returns 403 |
| [frontend/src/types/auth.ts](frontend/src/types/auth.ts) | Extended `RegisterResponse`; added `ResendVerificationRequest/Response`, `VerifyEmailResponse` |
| [frontend/src/services/auth.service.ts](frontend/src/services/auth.service.ts) | Added `verifyEmail()` and `resendVerification()` |
| [frontend/src/app/(auth)/register/page.tsx](frontend/src/app/(auth)/register/page.tsx) | Redirects to `/register/check-email?email=...` after success |
| [frontend/src/app/(auth)/register/check-email/page.tsx](frontend/src/app/(auth)/register/check-email/page.tsx) | **NEW** — "Check your inbox" page with resend button |
| [frontend/src/app/verify-email/page.tsx](frontend/src/app/verify-email/page.tsx) | **NEW** — reads `?token=`, calls backend, auto-redirects to login on success |
| [frontend/src/app/(auth)/login/page.tsx](frontend/src/app/(auth)/login/page.tsx) | Detects `email_not_verified` code; shows "Resend verification email" button inline |

**Behavior:**
- Register → verification email sent → `is_verified = false` until link clicked
- Login with unverified account → HTTP 403 `email_not_verified` → login page shows resend button
- Forgot password with unverified account → silently returns same 200 message (no token issued)
- Verification tokens expire after 24 hours; resend rate-limited to 1 per hour per email

---

### Phase 6 — Browser audits ⏳ partially complete (static audit done; live audits pending)

Run after Phase 1 (so security headers don't distort numbers) and before Phase 4 (so perf work targets real problems). Capture outputs to `audits/` at repo root.

#### 6.0 — Static code audit results (2026-05-13)

**Fixed in this session:**

| Category | Finding | File | Status |
|----------|---------|------|--------|
| SEO | Missing `generateMetadata` / OG tags on all pages | all pages | ✅ Fixed |
| SEO | Missing `robots.txt` | `public/robots.txt` | ✅ Fixed |
| SEO | Missing sitemap | `src/app/sitemap.ts` | ✅ Fixed |
| A11y | Error alerts missing `role="alert"` + `aria-live` | login, register, check-email | ✅ Fixed |
| A11y | Decorative glow divs not `aria-hidden` | CtaSection, HeroSection, auth layout, estimate detail | ✅ Fixed |
| A11y | Terms/Privacy `<span>` not keyboard accessible | login, register | ✅ Fixed |
| A11y | WizardProgress missing `role="progressbar"` + aria attrs | `WizardProgress.tsx` | ✅ Fixed |
| Perf | `ResultsComponents` (Recharts + XLSX) not code-split | `EstimateDetailClient.tsx` | ✅ Fixed (`dynamic()`) |
| Tailwind | `h-[500px]`/`w-[500px]`/`w-[400px]`/`h-[250px]` not canonical | auth layout, estimate detail | ✅ Fixed |

**Deferred — needs live stack (Lighthouse/aXe):**

| Category | Finding | Severity |
|----------|---------|----------|
| A11y | Skip-link absent (keyboard navigation to main content) | Medium |
| A11y | No focus trap in modals/sheets | Medium |
| A11y | `aria-live` region on SSE stream progress missing | Medium |
| A11y | Icon-only dashboard card action lacks `aria-label` | High |
| Perf | Lighthouse perf score unknown — run §6.1 to baseline | — |
| A11y | aXe audit score unknown — run §6.2 to baseline | — |

---

#### 6.0b — Stack-up for local audits

```powershell
# Terminal 1 — infra
cd backend\docker
docker compose up -d

# Terminal 2 — backend
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.api.server:app --reload --port 8000

# Terminal 3 — frontend
cd frontend
npm run dev
```

For production-realistic audits (post-Phase 5):
```bash
./run.sh up
```

#### 6.1 — Lighthouse (perf, a11y, best-practices, SEO)

```powershell
npm i -g lighthouse
$routes = @(
  @{ name="landing";        url="http://localhost:3000/" },
  @{ name="login";          url="http://localhost:3000/login" },
  @{ name="register";       url="http://localhost:3000/register" },
  @{ name="dashboard";      url="http://localhost:3000/dashboard" },
  @{ name="wizard-new";     url="http://localhost:3000/dashboard/estimate/new" },
  @{ name="estimate-detail";url="http://localhost:3000/dashboard/estimate/<replace-with-real-id>" }
)
mkdir audits\lighthouse -Force | Out-Null
foreach ($r in $routes) {
  lighthouse $r.url `
    --output=html --output=json `
    --output-path="audits\lighthouse\$($r.name)" `
    --chrome-flags="--headless=new" `
    --only-categories=performance,accessibility,best-practices,seo `
    --form-factor=desktop --throttling-method=simulate
}
```

**What to look for:**
- **Performance < 90** → check LCP element, TBT, JS bundle size, unoptimized images → Phase 4 H6/M9
- **Accessibility < 95** → record each violation with rule id + selector → Phase 6 fix list
- **Best Practices < 95** → CSP, HTTPS, browser console errors → Phase 1 C4
- **SEO < 95** → metadata gaps → Phase 5b M6

#### 6.2 — Accessibility deep-dive (aXe)

```powershell
npm i -g @axe-core/cli
axe http://localhost:3000/ --save audits\axe\landing.json
axe http://localhost:3000/login --save audits\axe\login.json
```

Triage by impact: **critical** and **serious** must be fixed before "industry grade".

#### 6.3 — Console & runtime errors

For each route: DevTools → Console → Preserve log → hard refresh → interact → save Errors/Warnings to `audits\console\<route>.txt`.

Watch for: React hydration mismatches, missing key warnings, deprecated API warnings, uncaught promise rejections.

#### 6.4 — Network audit

DevTools → Network → record login → wizard submit → SSE stream → estimate-detail polling → Save as HAR to `audits\network\<flow>.har`.

**Triage:** requests > 1 MB, requests > 1s on localhost, missing `Cache-Control`, CORS preflight issues, `Bearer undefined`.

#### 6.5 — Coverage (dead CSS / JS)

DevTools → Cmd-Shift-P → "Show Coverage" → walk wizard end-to-end → stop → sort by Unused Bytes. Save to `audits\coverage\`.

- CSS > 60% unused → Tailwind purge issue
- JS > 60% unused on first load → candidate for `dynamic()` import

#### 6.6 — Bundle analysis

```powershell
cd frontend
npm i -D @next/bundle-analyzer
$env:ANALYZE="true"; npm run build; Remove-Item Env:\ANALYZE
```

Look for: Recharts on chart-free routes, duplicate dependencies, Moment.js / full Lodash.

#### 6.7 — Backend perf sanity

```powershell
# RAG match latency under load (install: choco install hey)
hey -n 100 -c 10 -m POST `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer <jwt>" `
  -d '{"boq_text":"Excavation in ordinary soil up to depth 1.5m by manual means","top_k":5}' `
  http://localhost:8000/api/match-boq
```

Record p50/p95/p99 in `audits\backend-load\rag.txt`. p95 > 1s on warm cache → Phase 4 M3/M5.

#### 6.8 — Folding results back into the plan

After each audit, append findings under the relevant phase as `[Phase 6] <issue>`.

#### 6.9 — Optional: Chrome DevTools MCP

```powershell
npm i -g chrome-devtools-mcp
```

Add to `.mcp.json` at repo root:

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest"]
    }
  }
}
```

Restart Claude Code. Tools `mcp__chrome-devtools__navigate_page`, `mcp__chrome-devtools__list_console_messages`, `mcp__chrome-devtools__list_network_requests`, etc. become available.

- **6.1 Lighthouse** → use `performance_start_trace` per route
- **6.3 Console errors** → use `list_console_messages` after each navigation
- **6.4 Network** → use `list_network_requests` + filter by size/latency

---

## Reuse opportunities (don't reinvent)

- **`apiClient`** at [frontend/src/lib/api-client.ts](frontend/src/lib/api-client.ts) — extend with retry logic + Sentry breadcrumb hook; don't replace.
- **`AppError` + error_handlers** at `backend/core/exceptions/error_handlers.py` — extend with audit log emit; response shape is already consistent.
- **Repository pattern** at `backend/infrastructure/data_layer/database/repositories/` — Phase 4 batch fixes go here, not in services.
- **NextAuth JWT callback** at [frontend/src/auth.ts](frontend/src/auth.ts) — refresh token rotation hooks here.
- **Existing Pydantic schemas** at `backend/app/api/schemas/` — source of truth for `openapi-typescript` codegen feeding `frontend/src/lib/schemas/`.
- **Wizard step validation** at `frontend/src/app/dashboard/estimate/new/page.tsx:55-89` — refactor into zod schemas, keep step-by-step UX.
- **Cooperative cancel via `threading.Event`** at `application/pipelines/estimation_pipeline.py:73-77` — keep; works correctly with sync-pipeline-in-thread model.
- **Health endpoint** at `backend/app/api/server.py` — Docker `HEALTHCHECK` and Caddy upstream both rely on it.
- **Auto-migrate on startup** at `backend/app/api/server.py` — no separate migration container needed; `./run.sh migrate` is a manual escape hatch.
- **Frontend API URL fallback** at [frontend/src/lib/api-client.ts](frontend/src/lib/api-client.ts) — `?? "http://localhost:8000"` means dev still works without env injection.

---

## Recommended next steps

1. **Phase 1** — security & correctness. Fixes C1–C6, H3, H8. Run Phase 6 audits afterward to baseline numbers.
2. **Phase 2** — quality gates. Add pytest, Vitest, Playwright, CI.
3. **Phase 3** — observability. Structured logs, Sentry, request-ID correlation.
4. **Phase 4** — performance. Pool tuning, RAG batch fix, Redis, next/image.
5. **Phase 5b** (optional) — API versioning, pg_dump backup sidecar, polish items M1/M6/M8/L1–L5.
6. **Phase 6** — browser audits after Phase 1 ships; fold findings back into Phase 4.
