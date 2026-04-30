## Active Tasks (Agent Execution)

This file is the **authoritative checklist** for the work currently being executed in this repository.  
Each item should be closed only when implemented, verified (tests or runtime validation), and committed.

### Scope: Backend functional verification + dummy data generator

- [x] **Docs scaffolding**
  - [x] Add/maintain this task list (`ACTIVE_TASKS.md`)
  - [x] Add/maintain an implementation log (`audits/recommendations/Implementation_Report.md`)

- [x] **Backend: functional verification**
  - [x] Ensure `pytest` runs in a local venv without Docker and without external LLM keys
  - [x] Make integration tests deterministic by stubbing inference in `APP_ENV=test`
  - [x] Fix any failing routers/services uncovered by tests until suite is green

- [x] **Dummy data generation (post-startup, silent)**
  - [x] Implement generator modules (DB writers) capable of creating up to **10,000** dummy records
  - [x] Ensure generation begins **only after** the API is up (post-startup background task)
  - [x] Make generation **silent** (no noisy logs; only errors should surface)
  - [x] Add idempotency/locking so multiple workers don’t double-generate

- [x] **Persistence floor**
  - [x] Keep **1/3 to 1/2** of generated dummy data persisted at all times
  - [x] Implement cleanup/rotation that never drops below the persistence floor
  - [x] Add configuration knobs (target size, floor ratio, cadence)

- [x] **Commits**
  - [x] Commit in small batches after each milestone (docs → backend green → generator → persistence floor)
  - [x] Implement frontend gamification and state management refactor
  - [x] Sync progress to Redmine

### Scope: EduBoost SA Issues and Solutions remediation

- [x] **Repository and environment hygiene**
  - [x] Removed tracked Celery Beat runtime artifact from the working tree and ignored future schedule files
  - [x] Deduplicated `requirements.txt`, added `aiosqlite`, and moved heavy local ML packages to `requirements-ml.txt`

- [x] **Database lifecycle**
  - [x] Reconciled Alembic into a single revision chain
  - [x] Removed duplicate `study_plans` creation and duplicate diagnostic-session index creation
  - [x] Aligned ORM and migrations for `items_correct`, parent verification tokens, reports, and dummy data points
  - [x] Updated Docker Compose to run Alembic migrations instead of mounting SQL schema init scripts

- [x] **Backend API contracts and POPIA controls**
  - [x] Fixed provider-router imports, fallback stream imports, and `system_prompt` handling
  - [x] Implemented missing `StudyPlanService` and `ParentPortalService` router-facing methods
  - [x] Moved parent report persistence to the canonical `reports` table
  - [x] Switched worker consent checks to the canonical `consent_audit` table
  - [x] Enforced guardian token ownership on parent/consent/deletion/access routes
  - [x] Added token `jti` revocation checks and encrypted guardian full names at registration

- [x] **Frontend, CI, and docs alignment**
  - [x] Updated frontend API client routes for study plans and parent reports
  - [x] Registered the service worker and aligned offline queue/cache routes with backend APIs
  - [x] Added frontend CI, POPIA test path, and smoke test path
  - [x] Updated README, development, architecture, and POPIA docs for ports, migrations, routes, and encryption

### Scope: Fourth Estate Migration & System Status Remediation

- [x] **Durable Audit Trail (Pillar 4)**
  - [x] Migrated Fourth Estate from Redis Streams to RabbitMQ for durable persistence
  - [x] Added `aio-pika` dependency and configured `RABBITMQ_URL`
  - [x] Integrated audit logging into `WorkerAgent` base class (automatic auditing)
  - [x] Implemented lifecycle hooks in `main.py` for RabbitMQ connection management

- [x] **System Status Report 2 Implementation**
  - [x] Consolidated all schema management under a single Alembic baseline
  - [x] Implemented and integration-tested end-to-end parental consent gating
  - [x] Defined canonical production deployment path (`docker-compose.prod.yml` and `nginx.prod.conf`)
  - [x] Fixed frontend port mapping and verified full stack boot
  - [x] Implemented E2E Playwright test suite for key learner journeys
  - [x] Executed POPIA "Chaos Sweep" for PII leakage prevention
  - [x] Introduced semantic versioning and release automation workflows
  - [x] Expanded Grafana dashboards for SLOs and LLM provider health
  - [x] Formalized `CONTRIBUTING.md` and consolidated `.env.example`
