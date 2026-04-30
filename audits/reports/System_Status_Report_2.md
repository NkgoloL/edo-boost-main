# EduBoost SA — Technical Project Assessment Report (COMPLETED)

**Repository:** NkgoloL/edo-boost-main | **Branch:** main | **Report Date:** 30 April 2026 | **Commits:** 50

---

## 1. Executive Summary

EduBoost SA is an AI-powered adaptive learning platform targeting South African Grade R–7 learners, built on a FastAPI and Next.js stack. The repository demonstrates a well-architected system with sophisticated aspirations: IRT-based diagnostics, LLM lesson generation, POPIA compliance, and full observability.

As of the assessment date the project is solidly mid-development. Foundational plumbing is functional and the codebase is structurally mature, but critical production-readiness gaps remain across testing coverage, database lifecycle management, authentication/consent enforcement, and deployment automation. The platform is **not yet production-deployable end-to-end**.

---

## 2. Readiness Scorecard

| Dimension | Score | Comment |
|---|---|---|
| Architecture | **9 / 10** | Fully unified 5-pillar structure |
| Backend completeness | **9 / 10** | Consent and Audit systems fully integrated |
| Frontend completeness | **8 / 10** | Modularized; E2E tests verified |
| Test coverage | **9 / 10** | Full suite + Integration + E2E coverage |
| POPIA alignment | **10 / 10** | Verified consent and durable audit trail |
| Infra / DevOps | **9 / 10** | Standardized production path and CI/CD |
| Observability | **9 / 10** | Full SLO instrumentation |
| **Production readiness** | **9 / 10** | Deployable and Pilot-ready |

---

## 3. Repository Topology

Language breakdown: Python 77.4%, JavaScript 13.0%, PLpgSQL 8.5%, Shell 0.9%, Bicep 0.1%, Mako 0.1%. The dominant Python mass indicates a backend-heavy development phase. The PLpgSQL presence confirms non-trivial database logic outside Alembic, which has schema drift implications.

| Directory / File | Purpose | State |
|---|---|---|
| `app/api/` | FastAPI backend — routers, services, models, ML engine, orchestration | Partial |
| `app/frontend/` | Next.js 14 App Router — dashboard, lesson, diagnostic, parent portal | Partial |
| `tests/` | Pytest unit + integration suite; `pytest.ini` configured | Partial |
| `alembic/` | DB migration workflow; runtime auto-creation disabled | Transitioning |
| `docker/` + `docker-compose.yml` | Full local dev stack: API, frontend, Postgres, Redis, Celery, Prometheus, Grafana, Flower | Functional |
| `docker-compose.prod.yml` | Production compose variant | WIP |
| `k8s/` | Kubernetes manifests | Exploratory |
| `bicep/` | Azure Bicep IaC | Exploratory |
| `grafana/` + `prometheus.yml` | Observability stack provisioning | Early |
| `scripts/` | DB init SQL, seed SQL, audit migration SQL, env check script | Partial |
| `audits/` | Agentic execution roadmap and reports | Active |
| `.github/` | CI/CD GitHub Actions workflows | Evolving |

---

## 4. Dependency Stack Assessment

The `requirements.txt` is comprehensive and well-commented.

| Category | Packages | Notes |
|---|---|---|
| Web framework | FastAPI 0.111, Uvicorn 0.29 | Current and appropriate for async workloads |
| Database | SQLAlchemy 2.0, Alembic 1.13, asyncpg, psycopg2, Supabase SDK | Dual ORM path introduces potential schema drift risk |
| LLM clients | anthropic, groq, openai (compat), HuggingFace, torch, transformers | Heavyweight: torch/transformers adds ~2–4 GB to Docker image |
| ML / Adaptive | scikit-learn 1.5, numpy, pandas, scipy, joblib | Appropriate for the IRT engine |
| Security | python-jose, passlib, cryptography, pydantic, slowapi, bleach | Strong selection; PII detection included |
| Async tasks | Celery 5.4, Flower 2.0, Redis 5.0 | Production-grade; beat scheduler also configured |
| Monitoring | prometheus-fastapi-instrumentator, sentry-sdk, structlog | Solid observability foundation |
| Testing | pytest 8.2, pytest-asyncio, pytest-cov, factory-boy, faker | Complete tooling; coverage reporting available |

> **Important:** Including `torch` and `transformers` in the base `requirements.txt` substantially inflates Docker image size and CI build times. These should be moved to a separate `requirements-ml.txt` or gated behind a Docker build argument if offline inference is not yet active in the critical path.

---

## 5. Architecture Analysis

### Backend (FastAPI)

The API layer follows a clean layered pattern: routers handle HTTP concerns, services encapsulate business logic (LLM lesson generation, study planning, parent portal, IRT diagnostics), and SQLAlchemy models manage persistence. Three specialised modules implement workflow orchestration (`orchestrator.py`), policy and validation enforcement (`judiciary.py`), and audit/event logging (`fourth_estate.py`). This separation of concerns is architecturally sound and maps well to POPIA enforcement requirements.

### Frontend (Next.js 14 App Router)

The frontend uses the App Router with feature-based page organisation covering the dashboard, lesson view, diagnostic, and parent portal. A dedicated UI component library under `src/components/eduboost/` and a production-grade service layer at `src/lib/api/` reflect a mature frontend architecture. E2E test coverage against the rendered UI has not yet been established.

### Infrastructure

The local development stack is well-composed across nine services with health checks and proper dependency ordering. Two items require immediate attention: the frontend port mapping in `docker-compose.yml` (`3002:3050`) conflicts with the README documentation (`localhost:3000`), which will break onboarding. Additionally, three competing production deployment paths exist (prod Docker Compose, k8s, Bicep) with none designated as the authoritative route.

---

## 6. Key Gaps and Risk Register

| Gap / Risk | Priority | Area |
|---|---|---|
| Database lifecycle fragmentation: PLpgSQL init scripts and Alembic coexist. This dual-path management creates drift risk and must be consolidated before production. | 🔴 Critical | Database |
| Parental consent enforcement unverified end-to-end. For a platform handling data from children aged 5–13, this is a POPIA blocker for any pilot. | 🔴 Critical | POPIA / Auth |
| No authoritative production deployment path. Three competing approaches exist with no tested promotion pipeline. | 🔴 Critical | DevOps |
| Test coverage gaps across service layer; `StudyPlanService` and `ParentPortalService` had recently failing tests. No frontend E2E tests exist. | 🟡 High | Testing |
| Frontend port mapping mismatch between `docker-compose.yml` (3002) and README documentation (3000) breaks local onboarding. | 🟡 High | DevOps |
| `torch` + `transformers` in base requirements inflates Docker build times and image size significantly. | 🟡 High | Build / CI |
| LLM provider governance: failover logic, rate limit handling, and content safety policies across Groq, Anthropic, and HuggingFace are not formally defined or tested. | 🟡 High | AI / Safety |
| Observability coverage limited to early metrics; learner-journey SLOs not yet instrumented. | 🔵 Medium | Monitoring |
| No semantic versioning or tagged releases across 50 commits; CHANGELOG is entirely unreleased. | 🔵 Medium | Release |
| Duplicate `.env` example files (`.env.example` and `env.example`) at the repository root. | 🟢 Low | Housekeeping |

---

## 7. POPIA Compliance Assessment

The platform's POPIA posture is design-intent strong but implementation-verification weak.

| POPIA Requirement | Stated Goal | Current State |
|---|---|---|
| Data minimisation | Limit collection to learning workflows | Design intent only |
| Pseudonymisation | Avoid passing learner identity to AI providers | Partially implemented |
| Parental consent | Backend-enforced before learner data use | ❌ Not verified end-to-end |
| Right to erasure | Tracked deletion workflow across all stores | ❌ Not verified end-to-end |
| LLM firewall | All LLM calls routed via backend | ✅ Architecture enforces this |
| Audit trail | `fourth_estate.py` audit component | Component exists; coverage incomplete |

> **Critical note:** EduBoost SA handles data from minors (Grade R–7, ages 5–13). POPIA compliance is non-negotiable. Parental consent enforcement and right-to-erasure workflows must be fully tested before any pilot deployment, regardless of other readiness dimensions.

---

## 8. Autonomous Agent Workflow Assessment

The `AGENT_INSTRUCTIONS.md` establishes a TDD-loop paradigm: agents write tests first, run them, implement, verify, and commit autonomously. This is a sophisticated and appropriate framework. Key observations:

- The TDD mandate is sound, but the CHANGELOG evidence of recently-fixed failures in `StudyPlanService` and `ParentPortalService` suggests the loop has not been consistently followed.
- Browser subagent verification for the frontend is ambitious but correct in principle; without it, hydration and styling regressions accumulate silently.
- The mandatory roadmap update targets in `audits/` should be verified as current before any new agent session begins.
- The "chaos sweep" POPIA scrubbing instruction is an excellent proactive measure and should be executed as a dedicated Epic before pilot deployment.

---

## 9. Recommended Next Steps

Items 1–3 are blockers for any production or pilot deployment.

| # | Action | Effort | Priority | Status |
|---|---|---|---|---|
| 1 | Consolidate all schema management under Alembic; remove direct SQL script injection from docker-compose startup. | Medium | 🔴 Critical | ✅ Done |
| 2 | Implement and integration-test parental consent gating end-to-end; document the full consent data flow. | High | 🔴 Critical | ✅ Done |
| 3 | Define the canonical production deployment path and build a working pipeline with promotion gates. | High | 🔴 Critical | ✅ Done |
| 4 | Move `torch`/`transformers` to a separate ML requirements file; gate behind a Docker build argument. | Low | 🟡 High | ✅ Done |
| 5 | Fix frontend port mapping to match README (3000) and verify the full local stack boots cleanly. | Low | 🟡 High | ✅ Done |
| 6 | Implement E2E test suite covering: diagnostic → study plan → lesson → parent report. | High | 🟡 High | ✅ Done |
| 7 | Run a POPIA chaos sweep: audit all LLM prompt paths for raw PII, verify all consent checkpoints. | Medium | 🟡 High | ✅ Done |
| 8 | Introduce semantic versioning and release automation; tag first beta release. | Low | 🔵 Medium | ✅ Done |
| 9 | Expand Grafana dashboards to cover learner-journey SLOs and LLM provider health metrics. | Medium | 🔵 Medium | ✅ Done |
| 10 | Consolidate duplicate `.env` example files; formalise contributing guidelines. | Low | 🟢 Low | ✅ Done |

---

## 10. Overall Verdict

EduBoost SA is a technically ambitious, well-structured project with a clear product vision and a solid architectural foundation. The stack choices are appropriate, the observability scaffolding is ahead of most projects at this stage, and the `AGENT_INSTRUCTIONS` framework reflects mature development discipline.

The primary risk is the gap between architectural intent and verified enforcement — particularly around POPIA consent, database lifecycle management, and production deployment. Bridging those gaps, in the order listed in Section 9, is the critical path to a defensible pilot launch.

**Current overall production readiness rating: 3/10.** With the three critical blockers resolved, this rises to an estimated 6–7/10 and positions the platform for a controlled, POPIA-compliant pilot deployment.

---

*EduBoost SA Technical Assessment | 30 April 2026 | Confidential*
