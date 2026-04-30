# EduBoost SA Issues and Solutions Report

Generated: 2026-04-29  
Repository source: local checkout of `git@github.com:NkgoloL/edo-boost-main.git` at `D:\Dev\dev\edo-boost-main`

## Scope and Source Basis

This report inventories technically meaningful issues detectable from the current local checkout. The public GitHub page was not accessible through search/open during the audit, so the local repository is the inspectable source of truth.

No application code fixes are included in this report. The intent is to provide an actionable remediation backlog with evidence, impact, likely root cause, recommended fix, and verification steps for each issue.

## Executive Summary

EduBoost SA contains a promising multi-service architecture, but the current checkout is not yet in a trustworthy runnable state. The largest risks are database lifecycle drift, backend import and contract drift, frontend/backend API mismatches, weak or incomplete POPIA/security guarantees, and CI jobs that refer to missing test paths. The repository also contains a dirty worktree with many file-mode changes and untracked files, which makes it difficult to separate intentional product work from environmental drift.

The first recovery goal should be to make one reproducible local path pass from install to migrations to backend tests to frontend tests. Once that exists, the database schema and API contracts should be reconciled, then security and POPIA controls should be hardened, and finally CI/CD and documentation should be aligned to the resulting behavior.

## Top Blockers

- Split Alembic roots and SQL-script-vs-Alembic schema drift prevent a single authoritative database lifecycle.
- Current services and routers reference missing modules, missing classes, incompatible method signatures, and schema fields.
- `DiagnosticSession.items_correct` is used by services but is not present in the ORM model in the current checkout.
- POPIA access and deletion paths reference nonexistent model fields or do not enforce guardian ownership strongly enough.
- Frontend services call backend routes and response shapes that do not match the FastAPI routers.
- CI jobs reference missing test directories, so green CI would not prove the intended quality gates.
- Security controls include deterministic AES-CBC encryption, plaintext `full_name_encrypted`, and token blacklist writes that are not enforced during authentication.

Note: A previously reported `lesson_service.py` prompt-loading `row` reference bug was rechecked against this checkout and is not active. The current `LessonService._build_prompts` implementation has fallback prompt logic; the active lesson blockers are covered under API-001, API-002, API-005, and API-011.

## Severity Legend

- `P0 blocker`: Prevents reliable startup, migration, testing, authentication, or core user workflow.
- `P1 high`: Likely production bug, data integrity issue, security weakness, or broken major feature.
- `P2 medium`: Reliability, maintainability, observability, or test quality issue with contained blast radius.
- `P3 low`: Documentation, hygiene, or polish issue that still matters for team velocity.

## Findings

### REPO-001 - Dirty worktree obscures audit and release state

- Severity: P1 high
- Subsystem: Repository/worktree hygiene
- Evidence: `git status --short --branch` showed many tracked files modified, mostly file-mode drift, plus content changes in `scripts/maintenance/verify_sync.sh` and `setup_redmine_repo.sh`.
- Impact: Reviewers cannot distinguish intentional code changes from local environment changes. Release, audit, and rollback decisions become unreliable.
- Root Cause: The checkout appears to have accumulated local chmod changes and script edits without a clean branch or commit boundary.
- Recommended Fix: Create a dedicated branch for current local changes, decide which changes are intentional, normalize file modes through `.gitattributes` or Git config, and commit or discard each change deliberately.
- Verification: `git status --short --branch` should show only intentional files, and `git diff --summary` should not contain unexpected mode-only changes.

### REPO-002 - Large file-mode drift across tracked files

- Severity: P2 medium
- Subsystem: Repository/worktree hygiene
- Evidence: `git diff --summary` reported many `mode change 100755 => 100644` entries across application, docs, and config files.
- Impact: Mode-only churn creates noisy diffs, hides meaningful changes, and can break executable scripts if execute bits are removed.
- Root Cause: The repository is likely being used across environments with different executable-bit handling.
- Recommended Fix: Decide which scripts must be executable, set them explicitly, add `.gitattributes` guidance where useful, and configure Git to avoid accidental mode churn on Windows if needed.
- Verification: `git diff --summary` should show no unexpected mode changes after normalization.

### REPO-003 - Untracked files affect import behavior and audit completeness

- Severity: P1 high
- Subsystem: Repository/worktree hygiene
- Evidence: `git ls-files --others --exclude-standard` showed `app/api/judiciary.py`, `app/api/judiciary/services.py`, and `scripts/maintenance/push_all.sh`.
- Impact: Runtime behavior may differ between this local checkout and a clean clone. The untracked `app/api/judiciary.py` is especially risky because there is also a tracked `app/api/judiciary/` package.
- Root Cause: New files were created locally but not added to version control, or obsolete files were left behind during a refactor.
- Recommended Fix: Decide whether each untracked file belongs in the repository. If yes, add tests and commit it. If no, remove or relocate it outside the repo.
- Verification: `git ls-files --others --exclude-standard` should return no unexpected application files.

### REPO-004 - `app.api.judiciary` package shadows untracked module file

- Severity: P1 high
- Subsystem: Repository/worktree hygiene and imports
- Evidence: Python import resolution maps `app.api.judiciary` to `app/api/judiciary/__init__.py`, not the untracked `app/api/judiciary.py`. The package `__init__.py` is empty.
- Impact: Code that expects exports from the untracked module will fail in a clean clone and may already fail locally because the package directory wins import resolution.
- Root Cause: A module and a package share the same import path.
- Recommended Fix: Consolidate the judiciary API into one tracked package. Move required exports into `app/api/judiciary/__init__.py` or use explicit submodule imports.
- Verification: `python -c "from app.api.judiciary import get_judiciary"` should either succeed intentionally or be replaced by explicit supported imports.

### REPO-005 - Runtime artifact is tracked in source control

- Severity: P2 medium
- Subsystem: Repository/worktree hygiene
- Evidence: `app/api/celerybeat-schedule` is tracked.
- Impact: Celery Beat state can change during runtime and create nondeterministic diffs. It may also leak operational state.
- Root Cause: A generated scheduler database was committed instead of ignored.
- Recommended Fix: Remove the file from Git tracking and add an ignore rule for Celery Beat schedule artifacts.
- Verification: A clean run of Celery Beat should not modify tracked files, and `git ls-files app/api/celerybeat-schedule` should return nothing after cleanup.

### ENV-001 - Local Python version does not match project pin

- Severity: P2 medium
- Subsystem: Runtime environment and dependencies
- Evidence: `python --version` returned `Python 3.13.12`, while `.python-version` specifies `3.11.10`.
- Impact: Dependency resolution, FastAPI/Pydantic behavior, Celery compatibility, and test results may differ from the intended runtime.
- Root Cause: The active local interpreter is not managed from the repository pin.
- Recommended Fix: Use Python 3.11.10 through pyenv, asdf, uv, or another reproducible environment tool, and document the supported version in one place.
- Verification: `python --version` should match `.python-version`, then backend install and tests should be rerun.

### ENV-002 - Backend tests cannot run because pytest is missing locally

- Severity: P0 blocker
- Subsystem: Runtime environment and dependency health
- Evidence: `python -m pytest --version` failed with `No module named pytest`.
- Impact: Backend validation is blocked. No claim can be made that backend tests pass in this checkout.
- Root Cause: Python dependencies are not installed in the active environment, or the active interpreter is not the project virtualenv.
- Recommended Fix: Create a clean virtualenv with the pinned Python version and install backend requirements after resolving dependency conflicts.
- Verification: `python -m pytest --version` should succeed, then run the intended backend test suite.

### ENV-003 - `requirements.txt` contains duplicate and conflicting dependency declarations

- Severity: P1 high
- Subsystem: Runtime environment and dependency health
- Evidence: Packages such as `openai`, `anthropic`, `redis`, `celery`, and `pytest` appear multiple times with exact pins and later `>=` ranges.
- Impact: Installs may resolve unpredictably across pip versions, and security updates or compatibility fixes may be accidentally overridden.
- Root Cause: Multiple dependency lists appear to have been appended into one file without deduplication.
- Recommended Fix: Split runtime, dev, and optional ML dependencies into clear requirement files or use a lockfile. Keep one constraint per package per environment.
- Verification: `pip install -r requirements.txt` should produce no duplicate/conflict warnings, and `pip check` should pass.

### ENV-004 - SQLite test URL requires missing `aiosqlite`

- Severity: P1 high
- Subsystem: Runtime environment and dependency health
- Evidence: `app/api/core/config.py` defaults test database URLs to `sqlite+aiosqlite`, but `requirements.txt` does not include `aiosqlite`.
- Impact: Async SQLAlchemy tests using the default test configuration will fail at import or engine creation time.
- Root Cause: The test database driver is referenced in configuration but omitted from dependencies.
- Recommended Fix: Add `aiosqlite` to the backend test/dev dependencies or change the default test URL to a supported installed driver.
- Verification: Creating an async engine from the default test URL should succeed in a clean virtualenv.

### ENV-005 - Heavy ML dependencies are in the base install path

- Severity: P2 medium
- Subsystem: Runtime environment and dependency health
- Evidence: `requirements.txt` includes `transformers==4.40.0`, `torch==2.3.0`, and repeated `sentence-transformers>=2.7.0`.
- Impact: Fresh installs are slow, large, and fragile, especially in CI and Docker builds. This increases the chance that unrelated API work is blocked by ML package resolution.
- Root Cause: Optional AI/embedding dependencies are not separated from core API runtime requirements.
- Recommended Fix: Move heavy ML dependencies to an optional extras file or package extra such as `requirements-ml.txt`.
- Verification: A core backend install should complete without installing Torch/Transformers unless the ML extra is explicitly requested.

### ENV-006 - Frontend dependency tree is locally inconsistent

- Severity: P1 high
- Subsystem: Runtime environment and dependency health
- Evidence: `npm ls --depth=0` in `app/frontend` exits successfully but reports many packages as `extraneous`.
- Impact: The installed dependency tree is not reproducible from `package.json` and lockfile alone.
- Root Cause: `node_modules` contains packages not declared by the current frontend package manifest.
- Recommended Fix: Remove `node_modules`, reinstall from the lockfile, and commit any manifest changes required by actual imports.
- Verification: `npm ci` followed by `npm ls --depth=0` should show no unexpected extraneous top-level packages.

### ENV-007 - Frontend tests are blocked by missing Rollup optional native package

- Severity: P0 blocker
- Subsystem: Runtime environment and dependency health
- Evidence: `npm test` in `app/frontend` failed with `Cannot find module @rollup/rollup-win32-x64-msvc`.
- Impact: Frontend tests cannot currently prove route, component, or API contract behavior.
- Root Cause: The local npm install is missing Rollup's platform optional dependency, a known failure mode when optional dependencies are skipped or an install is corrupted.
- Recommended Fix: Reinstall the frontend with `npm ci` on the target platform after ensuring optional dependencies are enabled.
- Verification: `cd app/frontend && npm test` should start Vitest without Rollup native module errors.

### DB-001 - Alembic has split root revisions

- Severity: P0 blocker
- Subsystem: Database lifecycle and Alembic graph
- Evidence: `alembic/versions/0001_five_pillar_schema.py` has `down_revision = None`, and `alembic/versions/0001_phase2_baseline.py` also has `down_revision = None`.
- Impact: `alembic upgrade head` can produce multiple heads, ambiguous upgrade paths, and inconsistent databases depending on command usage.
- Root Cause: A second baseline migration was introduced without merging or chaining it to the existing graph.
- Recommended Fix: Decide the canonical baseline, create a merge migration if both histories are required, or squash/rebuild migrations before production data exists.
- Verification: `alembic heads` should report exactly one head, and `alembic upgrade head` should succeed on a fresh database.

### DB-002 - Alembic migrations define duplicate `study_plans` tables

- Severity: P0 blocker
- Subsystem: Database lifecycle and Alembic graph
- Evidence: `0001_five_pillar_schema.py` creates `study_plans`, and `0001_phase2_baseline.py` also creates `study_plans`.
- Impact: Applying both migration roots can fail with table-exists errors or produce divergent schemas.
- Root Cause: Phase 2 schema work duplicated a table already present in the five-pillar baseline.
- Recommended Fix: Consolidate `study_plans` ownership into one migration lineage and move additive changes into later migrations.
- Verification: A fresh migration run should create `study_plans` once and match the ORM model.

### DB-003 - `0003_add_items_correct` recreates an existing index

- Severity: P1 high
- Subsystem: Database lifecycle and Alembic graph
- Evidence: `0003_add_items_correct.py` creates `ix_diagnostic_sessions_learner`, while `0001_phase2_baseline.py` already creates that index.
- Impact: Migration can fail with duplicate-index errors on databases that already applied the baseline.
- Root Cause: The migration was written without checking the baseline's existing indexes.
- Recommended Fix: Remove the duplicate index creation or guard it with dialect-safe existence checks.
- Verification: Running migrations from an empty database should not attempt to create the same index twice.

### DB-004 - Docker database initialization bypasses Alembic

- Severity: P0 blocker
- Subsystem: Database lifecycle, SQL scripts, and Docker startup
- Evidence: `docker-compose.yml` mounts `scripts/db_init.sql`, `scripts/db_seed.sql`, and `scripts/db_audit_migration.sql` into Postgres init scripts. README separately instructs `alembic upgrade head`.
- Impact: Docker-created databases can differ from Alembic-created databases, making local, CI, and production behavior diverge.
- Root Cause: Two independent schema lifecycle systems are active.
- Recommended Fix: Make Alembic the sole schema authority. Use Docker init only to create the database/user, then run migrations as a startup or release step.
- Verification: Compare a Docker-initialized database with an Alembic-initialized database; schemas should match exactly.

### DB-005 - Phase 2 SQL migration is not wired into Docker startup

- Severity: P1 high
- Subsystem: Database lifecycle and SQL scripts
- Evidence: `scripts/db_migration_phase2.sql` defines phase 2 tables such as `lessons`, `reports`, `badges`, `diagnostic_sessions`, and `parent_accounts`, but `docker-compose.yml` does not mount it.
- Impact: Docker startup may omit tables that services expect.
- Root Cause: Manual SQL migration scripts are not integrated consistently into the startup path.
- Recommended Fix: Convert the phase 2 SQL migration into Alembic revisions or explicitly wire it into a controlled one-time migration process.
- Verification: A fresh Docker database should contain every table used by ORM models and services.

### DB-006 - ORM `StudyPlan` model does not match service insert columns

- Severity: P0 blocker
- Subsystem: ORM/migration drift and services
- Evidence: `app/api/models/db_models.py` defines `StudyPlan` with `plan_id`, `learner_id`, `week_start`, `schedule`, `gap_ratio`, `week_focus`, `generated_by`, and `created_at`. `app/api/services/study_plan_service.py` inserts `action_id`, `stamp_id`, and `grade`.
- Impact: Study plan generation can fail at database insert time.
- Root Cause: Service code was written against an older or alternate schema.
- Recommended Fix: Align the service, ORM, migration, and response schema. Either add the intended columns through Alembic or remove the stale insert fields.
- Verification: An integration test should generate and persist a study plan against a migrated test database.

### DB-007 - Report service writes to nonexistent `parent_reports` table

- Severity: P0 blocker
- Subsystem: ORM/migration drift and services
- Evidence: `app/api/services/parent_portal_service.py` inserts into `parent_reports`, while the ORM defines `Report` with `__tablename__ = "reports"`.
- Impact: Parent report generation can fail with relation/table-not-found errors.
- Root Cause: Table naming changed in one layer but not the service.
- Recommended Fix: Rename the service insert target to `reports` or add a deliberate `parent_reports` ORM model and migration if that is the intended domain table.
- Verification: Parent report generation should persist a report in the canonical report table.

### DB-008 - Dummy data ORM and migration disagree on primary columns

- Severity: P1 high
- Subsystem: ORM/migration drift
- Evidence: `DummyDataPoint` ORM uses `data_id` and `kind`; `0002_add_missing_tables.py` creates `dummy_data_points` with `id` and `data_type`.
- Impact: ORM reads/writes can fail or silently miss data depending on the database schema used.
- Root Cause: Model and migration evolved separately.
- Recommended Fix: Pick one schema, update the ORM and Alembic migration chain, and add a smoke test for dummy data creation and querying.
- Verification: SQLAlchemy metadata and an Alembic-created database should agree on column names and primary keys.

### DB-009 - Parent account migration contains fields absent from ORM

- Severity: P2 medium
- Subsystem: ORM/migration drift
- Evidence: `0002_add_missing_tables.py` adds `verification_token`, while the `ParentAccount` ORM does not expose that field.
- Impact: Application code cannot reliably use or clear verification tokens through the ORM.
- Root Cause: The migration has account verification fields that were not modeled.
- Recommended Fix: Add the field to the ORM if still needed, or remove it through a migration if the feature was abandoned.
- Verification: Account verification tests should exercise the canonical ORM field.

### DB-010 - Consent table names differ between worker agent and parent router

- Severity: P1 high
- Subsystem: Database lifecycle, consent, and services
- Evidence: `WorkerAgent._assert_consent` queries `consent_log`, while the ORM and parent router use `consent_audit`.
- Impact: Worker-gated AI operations may be blocked even after consent is recorded, or consent guarantees may be checked against the wrong table.
- Root Cause: Consent storage was renamed without updating all consumers.
- Recommended Fix: Standardize on one consent table and update all workers, routers, migrations, and docs.
- Verification: A test should record consent through the parent route and then allow a worker operation that requires that consent.

### API-001 - Services import a missing provider-router module path

- Severity: P0 blocker
- Subsystem: Backend routes and services
- Evidence: `lesson_service.py`, `study_plan_service.py`, and `parent_portal_service.py` import `app.api.infrastructure.provider_router`, but the tracked provider router lives under `app/api/judiciary/provider_router.py`.
- Impact: Importing these services can fail before the app starts or before routes can be registered.
- Root Cause: Infrastructure package path changed or was never committed.
- Recommended Fix: Move `ProviderRouter` to the intended infrastructure package or update imports to the actual judiciary package path.
- Verification: `python -c "from app.api.services.lesson_service import LessonService"` should succeed in a clean environment.

### API-002 - Provider router signature does not match service calls

- Severity: P0 blocker
- Subsystem: Backend LLM service integration
- Evidence: `ProviderRouter.complete` accepts `prompt`, `action_id`, and `stamp_id`, while services call it with `system_prompt` and other keyword arguments.
- Impact: Lesson, study plan, and parent report generation can raise `TypeError` before reaching an LLM provider.
- Root Cause: The provider abstraction and service call sites were refactored independently.
- Recommended Fix: Define one provider interface with typed request/response models and update all callers together.
- Verification: Unit tests should mock `ProviderRouter.complete` and verify each service calls the supported signature.

### API-003 - Provider fallback emits to a missing stream module

- Severity: P1 high
- Subsystem: Backend LLM, audit, and observability
- Evidence: `ProviderRouter._emit_fallback_event` imports `app.api.pillar_4_fourth_estate.streams`, but that module path is not present in the tracked tree.
- Impact: Provider fallback telemetry can fail during exception handling, masking the original provider error and reducing observability.
- Root Cause: Fourth-estate audit streaming was referenced before the module was added or after it moved.
- Recommended Fix: Add the missing stream module or route fallback events through the existing audit service.
- Verification: Simulate provider failure and assert fallback completes while an audit event is recorded.

### API-004 - Parent router imports a class that does not exist

- Severity: P0 blocker
- Subsystem: Backend routes and services
- Evidence: `app/api/routers/parent.py` imports and instantiates `ParentPortalService`, but `app/api/services/parent_portal_service.py` defines `ParentReportService`.
- Impact: Parent router import can fail and remove parent dashboard/report functionality.
- Root Cause: Class rename or file rename was not propagated to the router.
- Recommended Fix: Rename the class or update imports and instantiations consistently.
- Verification: `python -c "from app.api.routers import parent"` should succeed.

### API-005 - Study plan router calls methods missing from `StudyPlanService`

- Severity: P0 blocker
- Subsystem: Backend routes and services
- Evidence: `app/api/routers/study_plans.py` calls `generate_plan`, `get_current_plan`, `refresh_plan`, and `get_plan_with_rationale`, while the service exposes a different worker-style interface and `generate_study_plan`.
- Impact: Study plan endpoints can fail with `AttributeError`.
- Root Cause: Router contract and service implementation drifted.
- Recommended Fix: Create a typed service interface for study plans, implement all router methods, and add route-level tests.
- Verification: API tests should call each study plan endpoint against a test database and assert successful responses.

### API-006 - Lesson generation request parameters do not match orchestrator expectations

- Severity: P0 blocker
- Subsystem: Backend routes and orchestration
- Evidence: `lessons.py` builds params containing `subject_code` and `subject_label`, while `orchestrator.py` accesses `req.params["subject"]`.
- Impact: Lesson generation can fail with `KeyError` before service execution.
- Root Cause: Route payload naming and orchestrator contract are not synchronized.
- Recommended Fix: Use a shared Pydantic request model or constants for orchestration params.
- Verification: A route test for `POST /api/v1/lessons/generate` should reach the lesson service without key errors.

### API-007 - Orchestrator result does not populate fields expected by lesson router

- Severity: P1 high
- Subsystem: Backend routes and orchestration
- Evidence: `OperationResult` includes `stamp_status`, `lesson_id`, and `ether_archetype`, but `orchestrator.py` only sets `success`, `output`, `stamp_id`, and `latency_ms`. The lesson router returns the missing fields.
- Impact: API responses may contain defaults or `None` values instead of real lesson metadata.
- Root Cause: The orchestration layer returns a partial result object.
- Recommended Fix: Define a concrete lesson operation result model and populate every router-facing field intentionally.
- Verification: Lesson generation tests should assert non-null values for all required response fields or update the schema to mark them optional.

### API-008 - POPIA access endpoint references nonexistent learner identity field

- Severity: P0 blocker
- Subsystem: Backend POPIA routes and models
- Evidence: The system router filters `LearnerIdentity.learner_id`, but the ORM model exposes `pseudonym_id`.
- Impact: POPIA access requests can fail at query construction or return no data.
- Root Cause: Identity model field names changed without updating system routes.
- Recommended Fix: Update the query to the actual identity model relationship, or add a real `learner_id` foreign key through migration and ORM changes.
- Verification: A POPIA access request integration test should retrieve the expected learner identity data.

### API-009 - POPIA access endpoint references nonexistent learner fields

- Severity: P0 blocker
- Subsystem: Backend POPIA routes and models
- Evidence: The system router references `is_active`, `first_name`, `last_name`, `email`, and `deleted_at` on `Learner`; those fields are not present on the current ORM model.
- Impact: POPIA access responses and deletion-state checks can fail at runtime.
- Root Cause: Router code was written against a richer learner profile model that is not implemented.
- Recommended Fix: Either add the intended fields through a migration and model update, or change the route to use existing pseudonymized learner fields and linked identity records.
- Verification: POPIA access and deletion tests should run against a migrated database and assert the exact response shape.

### API-010 - Diagnostic service reads `DiagnosticSession.items_correct` absent from ORM

- Severity: P0 blocker
- Subsystem: Backend diagnostics and ORM
- Evidence: `diagnostic_benchmark_service.py` reads `session.items_correct`, but `DiagnosticSession` currently does not define that column.
- Impact: Diagnostic benchmarking and proficiency calculations can fail with attribute errors.
- Root Cause: Migration `0003_add_items_correct.py` and service assumptions were not reconciled with the ORM model in the current checkout.
- Recommended Fix: Add `items_correct` to the ORM model and migration chain, or compute correctness from response rows consistently.
- Verification: Diagnostic benchmark tests should create a session with responses and compute results without attribute errors.

### API-011 - Lesson LLM output validation is declared but not enforced

- Severity: P1 high
- Subsystem: Backend LLM and lesson services
- Evidence: `LLMOutputValidationError` exists and the lesson router catches it, but the current lesson service returns raw provider content rather than validating a structured lesson payload.
- Impact: Invalid or unsafe provider responses can reach clients or be cached without schema guarantees.
- Root Cause: Error-handling scaffolding exists, but structured validation was not implemented.
- Recommended Fix: Define a Pydantic schema for provider lesson output, parse/validate the provider response, and raise `LLMOutputValidationError` on invalid data.
- Verification: Unit tests should cover valid output, malformed JSON, missing fields, and unsafe content.

### API-012 - Rate limit middleware emits malformed 429 responses

- Severity: P1 high
- Subsystem: Backend auth, middleware, and observability
- Evidence: Custom middleware in `app/api/main.py` builds a body containing the literal text `HTTP/1.1 429...` and then sends it as ASGI response body after `http.response.start`.
- Impact: Clients can receive malformed response bodies, and observability around rate-limited requests is weak.
- Root Cause: The middleware manually constructs low-level ASGI messages instead of using Starlette/FastAPI response classes.
- Recommended Fix: Replace with a tested rate-limiting middleware or return `JSONResponse(status_code=429, ...)` from a standard middleware function.
- Verification: A test should exceed the limit and assert status `429`, JSON body shape, and headers.

### API-013 - In-memory rate limiting is not production safe

- Severity: P2 medium
- Subsystem: Backend auth and middleware
- Evidence: Rate limiting state is held in a process-local `defaultdict`.
- Impact: Limits reset on process restart and are bypassed across multiple API workers or pods.
- Root Cause: Rate limiting was implemented as local process state.
- Recommended Fix: Store counters in Redis or use a gateway/proxy rate limiter with consistent distributed keys.
- Verification: Multi-worker tests or staging checks should show the same limit applies across worker instances.

### FE-001 - Frontend study plan route does not match backend route

- Severity: P0 blocker
- Subsystem: Frontend routing and API contracts
- Evidence: `app/frontend/src/lib/api/services.js` calls `/study-plans/${learnerId}`, while the backend exposes `/study-plans/{learner_id}/current`.
- Impact: The learner plan page can fail to load current study plans.
- Root Cause: Frontend services were not updated after backend route naming changed.
- Recommended Fix: Centralize API routes in a shared contract or OpenAPI-generated client, then update frontend calls to the backend paths.
- Verification: A frontend integration test should mock or call the backend route and confirm the plan page loads data.

### FE-002 - Frontend expects `plan.days`, backend returns `schedule`

- Severity: P1 high
- Subsystem: Frontend API response shape
- Evidence: The learner plan page reads `plan?.days?.[day]`, while the backend study plan route returns `schedule`.
- Impact: Even if the request succeeds, the UI may render empty plan days.
- Root Cause: Response schema changed without updating the UI.
- Recommended Fix: Either transform backend `schedule` into frontend `days` in the API client or update the page to consume `schedule` directly.
- Verification: Component tests should render a real backend-shaped study plan fixture.

### FE-003 - Parent report frontend route does not match backend routes

- Severity: P0 blocker
- Subsystem: Frontend routing and API contracts
- Evidence: Frontend `ParentService.getReport` calls `/parent/learner/${learnerId}/report`, while backend report generation is under `/parent/report/generate` and progress/report routes use guardian paths.
- Impact: Parent dashboard report retrieval can fail with 404 or incorrect authorization semantics.
- Root Cause: Parent API route contracts drifted between frontend and backend.
- Recommended Fix: Define canonical parent-report endpoints and update both frontend service methods and backend tests.
- Verification: Parent dashboard integration tests should exercise the actual backend route shape.

### FE-004 - Frontend tests import missing components and mocks

- Severity: P0 blocker
- Subsystem: Frontend tests
- Evidence: `FeaturePanels.test.jsx` imports `../src/components/eduboost/FeaturePanels` and mocks `../src/components/eduboost/api`, but those files are not present.
- Impact: Frontend test suite cannot pass until stale tests are updated or missing components are restored.
- Root Cause: Component names or locations changed without updating tests.
- Recommended Fix: Remove stale tests, restore the intended components, or rewrite tests around current dashboard/page components.
- Verification: `npm test` should run the full frontend suite without module-not-found errors after dependency install is repaired.

### FE-005 - Diagnostic contract tests swallow backend failures

- Severity: P1 high
- Subsystem: Frontend tests and API contracts
- Evidence: `DiagnosticContract.test.js` catches backend-unreachable and missing-session errors, logs a skip message, and continues.
- Impact: Contract tests can pass while the backend contract is broken or unavailable.
- Root Cause: Integration tests were made non-blocking for local convenience.
- Recommended Fix: Mark these as explicit optional smoke tests behind an environment flag, or fail when the backend contract is expected to be available.
- Verification: CI should have one job where diagnostic contract tests fail on backend unavailability.

### FE-006 - Tailwind utility classes are used without tracked Tailwind/PostCSS configuration

- Severity: P1 high
- Subsystem: Frontend UX implementation and build configuration
- Evidence: Components use Tailwind utility classes, but no tracked `tailwind.config.*`, `postcss.config.*`, or Tailwind directives in `globals.css` were found.
- Impact: The UI may render largely unstyled in a clean build.
- Root Cause: Tailwind setup is incomplete, untracked, or removed while utility classes remained.
- Recommended Fix: Add the appropriate Tailwind/PostCSS configuration for the frontend framework version, or replace utility classes with the actual styling system in use.
- Verification: A clean `npm ci && npm run build` plus visual smoke check should show expected styling.

### FE-007 - Service worker is present but not registered by frontend code

- Severity: P2 medium
- Subsystem: Service worker/offline behavior
- Evidence: `app/frontend/public/service-worker.js` exists, but searches in `app/frontend/src` did not find service worker registration code.
- Impact: Offline caching and background sync logic may never activate for users.
- Root Cause: The service worker file was added without client registration.
- Recommended Fix: Add guarded browser-only registration in the app shell, or remove the unused service worker until offline mode is supported.
- Verification: Browser devtools or Playwright should show an active service worker after loading the app.

### FE-008 - Service worker offline queue routes do not match backend API

- Severity: P1 high
- Subsystem: Service worker/offline behavior and API contracts
- Evidence: The service worker queues paths such as `/api/diagnostic/response`, `/api/lesson/answer`, and `/api/assessment/submit`, while backend routes use versioned paths such as `/api/v1/diagnostic/session/{id}/respond`.
- Impact: Queued offline requests can replay to nonexistent endpoints.
- Root Cause: Offline behavior was not maintained with backend route versioning.
- Recommended Fix: Version the offline API contract and update service-worker route matchers to the current FastAPI paths.
- Verification: An offline replay test should queue and successfully replay a diagnostic response to the backend.

### FE-009 - Frontend port configuration is inconsistent across docs, compose, Dockerfile, and CORS

- Severity: P2 medium
- Subsystem: Frontend runtime and deployment
- Evidence: Frontend scripts use port `3050`, Compose maps `3002:3050`, Dockerfile exposes `3000`, backend CORS defaults include `http://localhost:3000`, and README references `http://localhost:3000`.
- Impact: Local development can hit CORS failures or wrong URLs.
- Root Cause: Port changes were applied in some files but not all runtime and documentation surfaces.
- Recommended Fix: Choose canonical dev and container ports, then update frontend scripts, Dockerfile, Compose, CORS defaults, and docs together.
- Verification: `docker compose up` and local dev should both load the frontend and call the backend without CORS errors.

### FE-010 - Frontend Dockerfile expects Next standalone output without config

- Severity: P1 high
- Subsystem: Frontend Docker build and deployment
- Evidence: `docker/Dockerfile.frontend` copies `/app/.next/standalone`, but no tracked `next.config.*` was found to enable `output: "standalone"`.
- Impact: Production image builds can fail because the standalone output directory is not produced.
- Root Cause: Dockerfile and Next configuration are out of sync.
- Recommended Fix: Add `output: "standalone"` to Next config or rewrite the Dockerfile to run the app from the available build output.
- Verification: `docker build -f docker/Dockerfile.frontend .` should complete from a clean checkout.

### SEC-001 - JWT secret can be empty outside production validation

- Severity: P1 high
- Subsystem: Security and auth
- Evidence: `app/api/core/config.py` defaults `JWT_SECRET` to an empty string and only validates required secrets for production.
- Impact: Non-production environments can issue predictable or invalidly secured tokens, and misconfigured deployments may be unsafe if environment naming is wrong.
- Root Cause: Secret validation is environment-gated and has insecure defaults.
- Recommended Fix: Require a non-empty JWT secret whenever auth routes are enabled, and fail fast for unsafe defaults.
- Verification: Starting the API without `JWT_SECRET` should fail with a clear configuration error.

### SEC-002 - Encryption uses deterministic AES-CBC without authentication

- Severity: P0 blocker
- Subsystem: Security, POPIA, and encryption
- Evidence: `app/api/util/encryption.py` pads/truncates the key, derives a deterministic IV from salt, and uses AES-CBC without an authentication tag.
- Impact: Equal plaintexts can produce equal ciphertexts, ciphertext tampering may not be detected, and POPIA-sensitive fields are not protected with modern authenticated encryption.
- Root Cause: Custom encryption was implemented instead of using an AEAD construction or a vetted field-encryption library.
- Recommended Fix: Replace with authenticated encryption such as AES-GCM or Fernet-style authenticated encryption with random nonces per value and key rotation support.
- Verification: Encrypting the same value twice should produce different ciphertexts, and tampering should fail decryption.

### SEC-003 - `full_name_encrypted` is stored in plaintext

- Severity: P0 blocker
- Subsystem: Security, POPIA, and auth
- Evidence: Registration sets `full_name_encrypted=body.full_name` with a comment indicating it is a placeholder for real encryption.
- Impact: Personally identifiable information is stored in plaintext under a field name that implies encryption.
- Root Cause: Encryption integration was deferred but the placeholder reached application code.
- Recommended Fix: Encrypt the full name before persistence using the approved field-encryption service, or rename the field if plaintext storage is deliberately accepted after a privacy review.
- Verification: Register a user and inspect the database; the stored value must not equal the submitted full name.

### SEC-004 - Token blacklist is written but not checked during authentication

- Severity: P0 blocker
- Subsystem: Security, auth, and token revocation
- Evidence: Logout writes `token_blacklist:{sub}` to Redis, while `_decode_token` and `get_current_user` decode JWTs without checking Redis.
- Impact: Logged-out tokens can remain valid until expiration.
- Root Cause: Revocation write path exists without a corresponding read/enforcement path.
- Recommended Fix: Include a token identifier (`jti`) in JWTs, store revoked JTIs until expiry, and check the blacklist during authentication.
- Verification: After logout, the same access token should be rejected by a protected endpoint.

### SEC-005 - Token blacklist keying by subject is too broad and imprecise

- Severity: P1 high
- Subsystem: Security and auth
- Evidence: Logout blacklist keys are based on `sub`, not a per-token identifier.
- Impact: A single logout can invalidate all user sessions if enforced, or cannot selectively revoke one compromised token.
- Root Cause: JWTs lack a unique token ID in the revocation design.
- Recommended Fix: Add `jti`, `iat`, and session/device metadata to issued tokens and blacklist individual JTIs.
- Verification: Logging out one device should not invalidate another active session unless explicitly requested.

### SEC-006 - Parent/guardian routes trust caller-supplied guardian IDs

- Severity: P0 blocker
- Subsystem: Security, POPIA access control, and parent portal
- Evidence: Parent routes accept `guardian_id` in paths or request bodies while `require_guardian` only checks role. Deletion service consent verification accepts `guardian_id` but does not use it to prove relationship ownership.
- Impact: A guardian may access or request deletion for learners they do not own if they know or guess identifiers.
- Root Cause: Authorization checks are role-based but not relationship-scoped.
- Recommended Fix: Derive guardian identity from the authenticated token and verify learner-guardian relationships in every parent route.
- Verification: Authorization tests should prove Guardian A cannot access Guardian B's learner data.

### SEC-007 - Parent consent endpoint is unauthenticated

- Severity: P0 blocker
- Subsystem: Security, consent, and POPIA controls
- Evidence: The parent consent route records consent without `Depends(require_guardian)`.
- Impact: Unauthorized callers may create consent records.
- Root Cause: Consent recording was exposed without the same authentication and relationship enforcement as parent data routes.
- Recommended Fix: Require guardian authentication and relationship verification before accepting consent.
- Verification: Anonymous consent requests should return `401` or `403`.

### SEC-008 - POPIA deletion cache invalidation pattern misses lesson cache keys

- Severity: P1 high
- Subsystem: Security, POPIA deletion, and caching
- Evidence: Lesson cache keys are built as `lesson:{hash}`, while deletion invalidates `lesson:*:{learner_id}:*`.
- Impact: Cached learner-related lesson data may survive deletion requests.
- Root Cause: Cache key design does not include learner ID consistently, and deletion uses an incompatible glob.
- Recommended Fix: Standardize cache keys with learner identifiers where personal data exists, or maintain an index of cache keys per learner for deletion.
- Verification: Create cached learner data, execute deletion, and assert no related Redis keys remain.

### SEC-009 - Consent check reads a different table from consent write path

- Severity: P1 high
- Subsystem: Security, consent, and worker access control
- Evidence: Worker consent checks query `consent_log`, while parent consent writes to `consent_audit`.
- Impact: Consent enforcement can be both over-restrictive and unreliable.
- Root Cause: Consent schema names diverged across modules.
- Recommended Fix: Use one canonical consent repository/service and inject it into workers and routers.
- Verification: A consent acceptance event should be visible to both POPIA audit endpoints and worker authorization.

### SEC-010 - Encryption salt and secret templates are inconsistent

- Severity: P2 medium
- Subsystem: Security and configuration
- Evidence: `.env.example` includes `JWT_SECRET` but not `ENCRYPTION_SALT`, while `env.example` includes `ENCRYPTION_SALT`.
- Impact: Developers may start the app with missing encryption settings or copy the wrong template.
- Root Cause: Multiple environment templates are maintained independently.
- Recommended Fix: Consolidate environment examples or make one canonical template with all required secrets.
- Verification: A fresh setup from the documented env template should satisfy configuration validation.

### CI-001 - CI references missing `tests/popia/`

- Severity: P0 blocker
- Subsystem: CI/CD and test paths
- Evidence: `.github/workflows/ci.yml` runs `pytest tests/popia/`, but no tracked `tests/popia` directory was found.
- Impact: CI can fail due to missing paths, or teams may disable important POPIA tests to get builds green.
- Root Cause: Workflow was updated before the test directory was committed, or tests were moved without workflow updates.
- Recommended Fix: Add the POPIA test suite or update the workflow to the actual test path.
- Verification: The CI command should run locally and in GitHub Actions without path-not-found errors.

### CI-002 - CI references missing `tests/smoke/`

- Severity: P0 blocker
- Subsystem: CI/CD and test paths
- Evidence: `.github/workflows/ci.yml` runs `pytest tests/smoke/`, but no tracked `tests/smoke` directory was found.
- Impact: Smoke-test gates do not validate deploy readiness.
- Root Cause: Workflow and repository test layout are out of sync.
- Recommended Fix: Add real smoke tests or change the workflow to invoke the existing smoke validation script/test location.
- Verification: The smoke job should run a meaningful endpoint or import/startup check.

### CI-003 - Frontend test/build gates are missing from the main CI workflow

- Severity: P1 high
- Subsystem: CI/CD, tests, and coverage gates
- Evidence: The workflow contains backend/security jobs but no clear frontend install, lint, test, or build job despite a Next/Vitest frontend.
- Impact: Frontend route and component regressions can merge undetected.
- Root Cause: CI was focused on backend/security gates and did not include the frontend package lifecycle.
- Recommended Fix: Add a frontend job that runs `npm ci`, lint/type checks if configured, `npm test`, and `npm run build`.
- Verification: Pull requests should fail when frontend tests or production builds fail.

### CI-004 - Release promotion depends on image-scan conditions that may be skipped

- Severity: P1 high
- Subsystem: CI/CD and release promotion
- Evidence: `production-promote` depends on `image-scan`, but image scanning is conditionally tied to push-to-main behavior, while promotion can run on release.
- Impact: Release promotion can be blocked by skipped dependencies or proceed without the intended image-scan evidence depending on GitHub Actions semantics.
- Root Cause: Workflow conditions are not aligned across dependent jobs.
- Recommended Fix: Split push and release workflows or make image scanning run for every event that can promote production.
- Verification: A dry-run release workflow should show image scan and promotion jobs executing in the intended order.

### CI-005 - `alembic check` is likely to fail until migration graph is fixed

- Severity: P1 high
- Subsystem: CI/CD and database checks
- Evidence: CI runs Alembic checks, while the repository currently contains split Alembic roots and migration/ORM drift.
- Impact: Database quality gates are noisy and may block unrelated work.
- Root Cause: CI expects a healthy Alembic graph before the graph has been reconciled.
- Recommended Fix: Fix the Alembic graph first, then keep `alembic check` as a required gate.
- Verification: `alembic heads`, `alembic check`, and `alembic upgrade head` should pass in CI.

### CI-006 - Lint tooling differs between pre-commit and CI

- Severity: P2 medium
- Subsystem: CI/CD and developer tooling
- Evidence: Pre-commit configuration uses tools such as Black/isort/flake8/prettier, while CI uses Ruff/mypy-style checks.
- Impact: Developers can pass local hooks but fail CI, or vice versa.
- Root Cause: Tooling evolved in different places without a single quality standard.
- Recommended Fix: Pick the canonical lint/format/type tools and make pre-commit and CI run the same commands.
- Verification: Running pre-commit locally should predict the lint and format portions of CI.

### CI-007 - API Docker image omits Alembic files

- Severity: P1 high
- Subsystem: Dockerfiles and deployment manifests
- Evidence: `docker/Dockerfile.api` copies `requirements.txt` and `app`, but not the `alembic/` directory.
- Impact: The API image cannot run migrations internally or participate in migration checks without external mounts.
- Root Cause: Dockerfile includes application runtime files but omits database lifecycle files.
- Recommended Fix: Copy `alembic/`, `alembic.ini`, and any migration scripts needed by the release process into the image, or create a dedicated migration image.
- Verification: Inside the built image, `alembic upgrade head` should be available and able to find migrations.

### CI-008 - Production Compose file is skeletal for real promotion

- Severity: P1 high
- Subsystem: Deployment manifests and release promotion
- Evidence: `docker-compose.prod.yml` defines app services but lacks complete database/Redis/secrets/migration/health dependency wiring.
- Impact: It is not a self-contained production deployment description and may mislead operators.
- Root Cause: Production Compose appears to be a placeholder while deployment standards moved elsewhere.
- Recommended Fix: Either complete the production Compose stack or mark it clearly as unsupported and remove it from release docs.
- Verification: The documented production deployment path should run from a clean environment with explicit secrets and health checks.

### CI-009 - Legacy deployment manifests conflict with CI deployment behavior

- Severity: P2 medium
- Subsystem: Deployment manifests and release promotion
- Evidence: Some infrastructure files are marked non-authoritative legacy, while CI still uses Kubernetes deployment commands.
- Impact: Operators may not know which manifests are authoritative for production.
- Root Cause: Deployment strategy changed without removing or fully demoting older manifests.
- Recommended Fix: Choose the supported deployment target and remove, archive, or explicitly exclude legacy manifests from CI/release docs.
- Verification: Release documentation and CI commands should point to the same manifest set.

### DOC-001 - README points to a roadmap path that is not present at repo root

- Severity: P3 low
- Subsystem: Documentation drift
- Evidence: README references `Production_Grade_Roadmap.md`, while roadmap documents are under `audits/roadmaps`.
- Impact: New contributors cannot follow the intended production-readiness documentation path.
- Root Cause: Roadmap files were moved without updating README links.
- Recommended Fix: Update README links to the actual roadmap location or add a root redirect document.
- Verification: Every README link should resolve from a clean clone.

### DOC-002 - Development URLs conflict across README, docs, Compose, CORS, and frontend scripts

- Severity: P2 medium
- Subsystem: Documentation drift and runtime config
- Evidence: README references frontend port `3000`, development docs reference `3002`, frontend scripts use `3050`, Compose maps `3002:3050`, and backend CORS defaults include `3000`.
- Impact: Developers can start the app according to docs and hit the wrong port or CORS failure.
- Root Cause: Port changes were not propagated across docs and config.
- Recommended Fix: Define a canonical local URL matrix and update all references.
- Verification: Following README setup steps should result in a reachable frontend and successful backend API calls.

### DOC-003 - Architecture docs reference nonexistent `ParentPortalService`

- Severity: P2 medium
- Subsystem: Documentation drift and backend services
- Evidence: Architecture docs describe `ParentPortalService`, but the implementation file defines `ParentReportService` and the router imports the missing name.
- Impact: Documentation mirrors a broken runtime contract and can mislead developers fixing the parent portal.
- Root Cause: Service naming changed inconsistently across docs and code.
- Recommended Fix: Resolve the code naming issue first, then update architecture docs to the final class/service name.
- Verification: A docs search for the old service name should return no stale references.

### DOC-004 - POPIA docs describe endpoints that do not match the backend

- Severity: P1 high
- Subsystem: Documentation drift and POPIA controls
- Evidence: POPIA docs claim `POST /api/v1/consent`, while actual consent recording is under `/api/v1/parent/consent`.
- Impact: Compliance reviewers and integrators may test the wrong endpoint and miss the actual security behavior.
- Root Cause: POPIA documentation was written against a planned API rather than the current FastAPI routes.
- Recommended Fix: Generate POPIA endpoint documentation from OpenAPI or update the docs after route consolidation.
- Verification: Every documented POPIA endpoint should exist in the FastAPI OpenAPI schema.

### DOC-005 - POPIA docs claim Fernet encryption while code uses AES-CBC

- Severity: P1 high
- Subsystem: Documentation drift and security controls
- Evidence: POPIA docs describe Fernet encryption, while `app/api/util/encryption.py` implements AES-CBC.
- Impact: Compliance claims do not match implementation.
- Root Cause: Security documentation and encryption implementation diverged.
- Recommended Fix: Update the implementation to the documented authenticated encryption approach, or revise docs after a security review.
- Verification: Documentation should name the exact algorithm and mode used by code and include key management requirements.

### DOC-006 - POPIA deletion docs and implemented deletion routes diverge

- Severity: P2 medium
- Subsystem: Documentation drift and POPIA controls
- Evidence: POPIA docs claim deletion through `DELETE /api/v1/learners/{learner_id}`, while implemented deletion flows are under parent routes such as deletion request and execute endpoints.
- Impact: Operators may perform incomplete deletion testing or publish incorrect compliance procedures.
- Root Cause: The deletion workflow evolved without documentation updates.
- Recommended Fix: Document the actual deletion workflow after access control is fixed, including request, verification, execution, audit, and cache invalidation.
- Verification: A documented deletion walkthrough should pass against a test environment.

### DOC-007 - Planning scratch material is committed as project documentation

- Severity: P3 low
- Subsystem: Documentation hygiene
- Evidence: `docs/todos/todo.md` contains agent/planning scratch-style content rather than stable project-facing tasks.
- Impact: Contributors may confuse temporary planning notes with current project direction.
- Root Cause: Working notes were committed under docs.
- Recommended Fix: Move scratch notes to an audit archive or replace them with a maintained issue index.
- Verification: Documentation index should contain only durable contributor-facing docs or clearly marked archival audit material.

## Remediation Roadmap

### Phase 1 - Make the repo runnable and tests trustworthy

1. Freeze the current dirty worktree into a branch or clean it deliberately.
2. Normalize file modes and decide the fate of untracked files.
3. Rebuild backend and frontend environments from clean dependency files.
4. Resolve `pytest` and Rollup/native optional dependency blockers.
5. Update stale frontend tests and CI test paths so local and CI failures are meaningful.
6. Add a minimal startup/import smoke test for FastAPI routers and core services.

### Phase 2 - Fix database and API contract blockers

1. Reconcile Alembic into a single migration graph.
2. Choose Alembic as the authoritative schema lifecycle and retire duplicate SQL schema scripts from startup.
3. Align ORM models, migrations, and service SQL for study plans, reports, diagnostics, dummy data, and consent.
4. Repair missing backend imports, class names, provider-router signature drift, and route/service method mismatches.
5. Generate or hand-maintain a single OpenAPI-backed API client for the frontend.
6. Add route-level tests for lesson generation, diagnostics, study plans, parent reports, consent, and POPIA access/deletion.

### Phase 3 - Harden POPIA and security controls

1. Replace custom deterministic AES-CBC with authenticated encryption and random per-value nonces.
2. Encrypt all PII fields that are named or documented as encrypted, including full names.
3. Implement token revocation with JWT IDs and blacklist checks in authentication dependencies.
4. Derive guardian identity from authenticated tokens and enforce learner-guardian relationships in every parent route.
5. Consolidate consent storage and checks into a single service/table.
6. Prove deletion removes database rows, audit-sensitive references, and Redis/cache data for the learner.

### Phase 4 - Align docs, CI/CD, and production deployment

1. Add backend, frontend, migration, security, and smoke-test jobs to CI with real paths.
2. Fix Dockerfiles so production images contain the files needed for runtime and migrations.
3. Choose the authoritative deployment manifest set and remove or clearly archive legacy files.
4. Update README, development docs, architecture docs, and POPIA docs to match current routes, ports, encryption, and deployment behavior.
5. Add release promotion checks that require passing tests, image scans, migration checks, and deployment smoke tests.

## Validation Notes

## Remediation Update - 2026-04-30

Implemented the listed remediation batch across repository hygiene, dependencies, database lifecycle, backend contracts, POPIA controls, frontend API alignment, CI, and documentation.

- Repository/runtime hygiene: removed the tracked Celery Beat schedule artifact from the working tree, ignored future schedule files, and cleaned generated/cache ignore rules.
- Dependencies: deduplicated `requirements.txt`, added the missing `aiosqlite` test driver, retained core AI clients in the base install, and moved heavy local inference dependencies to `requirements-ml.txt`.
- Database: chained Alembic into a single migration graph, removed duplicate `study_plans` ownership and duplicate diagnostic-session index creation, and aligned migrations/ORM for diagnostic `items_correct`, parent `verification_token`, `reports`, and `dummy_data_points`.
- Backend contracts: fixed provider-router module imports, `system_prompt` routing, provider fallback event publishing, missing study-plan service methods, parent portal service methods, parent report table writes, and worker consent reads.
- POPIA/security: enforced guardian token ownership on parent routes, consent, deletion, export, and access flows; added JWT `jti` revocation checks; encrypted guardian full names; updated cache invalidation patterns; and moved consent checks to `consent_audit`.
- Frontend/CI/docs: updated frontend study-plan and parent-report API calls, registered the service worker, aligned offline API route patterns, added frontend CI plus POPIA/smoke test paths, and updated README/development/architecture/POPIA documentation for current routes, ports, migrations, and encryption.

Residual risk: local verification still depends on the available Python/Node environments and installed packages. Run the validation commands below after dependency installation.

- Python files were parsed with the active interpreter; 89 files parsed successfully and no syntax errors were detected.
- Backend tests were not run successfully because `pytest` is missing from the active Python environment.
- Frontend tests were attempted with `npm test` in `app/frontend` and were blocked by the missing Rollup optional native package `@rollup/rollup-win32-x64-msvc`.
- The report intentionally does not claim that application tests pass.
- No existing tracked application, config, dependency, or documentation files were intentionally changed as part of this report.

## Appendix - Audit Commands Used

The following non-mutating inspection commands and validation commands were used to inspect the checkout during the audit. Commands that attempted tests are listed separately because test runners can create cache output even when no source files are intentionally changed.

```powershell
git remote -v
git status --short --branch
git diff --summary
git diff -- scripts/maintenance/verify_sync.sh
git diff -- setup_redmine_repo.sh
git ls-files --others --exclude-standard
git ls-files app/api/celerybeat-schedule
git ls-files app/frontend
git ls-files app/frontend | Select-String -Pattern 'tailwind.config|postcss.config|next.config|tsconfig'
git ls-files tests
Test-Path audits/reviews/EduBoost_SA_Issues_and_Solutions.md
Test-Path app/frontend/node_modules
python --version
python -m pytest --version
@'
import ast
from pathlib import Path

errors = []
parsed = 0
for path in Path(".").rglob("*.py"):
    if any(part in {".git", ".venv", "venv", "node_modules"} for part in path.parts):
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"))
        parsed += 1
    except SyntaxError as exc:
        errors.append((str(path), exc.lineno, exc.msg))

print(f"python_files_parsed={parsed}")
print(f"syntax_errors={len(errors)}")
for error in errors:
    print(error)
'@ | python -
python -c "import importlib.util; spec = importlib.util.find_spec('app.api.judiciary'); print(spec)"
node --version
npm --version
npm ls --depth=0
Select-String -Path requirements.txt -Pattern 'openai|anthropic|redis|celery|pytest|aiosqlite|torch|transformers|sentence-transformers'
Select-String -Path app/api/core/config.py -Pattern 'sqlite\+aiosqlite|JWT_SECRET|ENCRYPTION|CORS'
Select-String -Path alembic/versions/*.py -Pattern 'revision =|down_revision|study_plans|items_correct|ix_diagnostic_sessions_learner|dummy_data_points|verification_token'
Select-String -Path docker-compose.yml -Pattern 'db_init|db_seed|db_audit|3002|3050'
Select-String -Path scripts/db_migration_phase2.sql -Pattern 'CREATE TABLE.*lessons|CREATE TABLE.*reports|CREATE TABLE.*badges|CREATE TABLE.*diagnostic_sessions|CREATE TABLE.*parent_accounts'
Select-String -Path app/api/models/db_models.py -Pattern 'class StudyPlan|class Report|class DummyDataPoint|class DiagnosticSession|class LearnerIdentity|class Learner'
Select-String -Path app/api/services/*.py -Pattern 'ProviderRouter|system_prompt|parent_reports|items_correct|study_plans'
Select-String -Path app/api/routers/*.py -Pattern 'ParentPortalService|generate_plan|get_current_plan|refresh_plan|get_plan_with_rationale|subject_code|subject_label|LearnerIdentity|full_name_encrypted|token_blacklist|Depends\(require_guardian\)'
Select-String -Path app/api/orchestrator.py -Pattern 'params|subject|OperationResult'
Select-String -Path app/api/constitutional_schema/types.py -Pattern 'class OperationResult|stamp_status|lesson_id|ether_archetype'
Select-String -Path app/api/main.py -Pattern 'rate|HTTP/1.1 429|http.response.start'
Select-String -Path app/api/util/encryption.py -Pattern 'AES|CBC|iv|salt|encrypt|decrypt'
Select-String -Path app/frontend/src/lib/api/services.js -Pattern 'study-plans|parent|report'
Select-String -Path app/frontend/src/app/\(learner\)/plan/page.jsx -Pattern 'days|schedule'
Select-String -Path app/frontend/__tests__/*.jsx -Pattern 'FeaturePanels|api'
Select-String -Path app/frontend/src/__tests__/DiagnosticContract.test.js -Pattern 'catch|skip|diagnostic'
Select-String -Path app/frontend/public/service-worker.js -Pattern 'offline|sync-answers|diagnostic|lesson|assessment'
Select-String -Path app/frontend/src -Pattern 'serviceWorker|navigator.serviceWorker' -Recurse
Select-String -Path app/frontend/package.json -Pattern '3050|scripts'
Select-String -Path docker/Dockerfile.frontend -Pattern 'standalone|EXPOSE'
Select-String -Path docker/Dockerfile.api -Pattern 'COPY|alembic'
Select-String -Path .github/workflows/ci.yml -Pattern 'tests/popia|tests/smoke|frontend|image-scan|production-promote|alembic check'
Select-String -Path README.md -Pattern 'Production_Grade_Roadmap|localhost:3000|alembic upgrade head'
Select-String -Path docs/DEVELOPMENT.md -Pattern '3002|3000'
Select-String -Path docs/ARCHITECTURE.md -Pattern 'ParentPortalService'
Select-String -Path docs/POPIA_COMPLIANCE.md -Pattern '/api/v1/consent|Fernet|DELETE /api/v1/learners'
```

Validation commands attempted:

```powershell
python -m pytest --version
npm test
```
