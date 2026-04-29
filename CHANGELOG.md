# Changelog

## [2.0.0] — 2026-04-29

### Summary
Full five-pillar architectural implementation. This release represents a major
production-hardening effort covering all ten architectural recommendations from the
repo audit. Every outstanding P0 and P1 task across all six domains has been
addressed in code, infrastructure, tests, and documentation.

---

### PILLAR 1 — Legislature (Vector Knowledge Base)

#### Added
- `pillar_1_legislature/models.py` — `ConstitutionalRule` Pydantic model (frozen/immutable)
  with SHA-256 `immutable_hash` auto-computed from canonical fields on construction.
  Hash is verified on load via `verify_integrity()`. The `model_config = {"frozen": True}`
  setting ensures no mutation is possible at the Python layer after construction.
- `ConstitutionalRuleORM` SQLAlchemy model with `before_update` and `before_delete` event
  listeners that raise `RuntimeError` at the Python layer — defence in depth alongside the
  Postgres trigger.
- `RuleSetSignatureORM` — operator-keypair signed rule-set bundle for startup verification.
- `pillar_1_legislature/agent.py` — `LegislatureAgent` implementing:
  - File-hash change detection (SHA-256 per source document) — skips ingestion if unchanged
  - Text chunking pipeline (512-word chunks with 64-word overlap)
  - Vector upsert stub wired for OpenAI `text-embedding-3-small` or `sentence-transformers`
  - LLM rule extraction stub with structured `ConstitutionalRule` output
  - Versioned rule persistence: new policy version → new row with new `effective_date`, never
    mutates existing rows
  - `get_active_rules()` using `DISTINCT ON (rule_id) ORDER BY effective_date DESC` window
    function to retrieve the latest version of each rule
- `migrations/0001_five_pillar_schema.py` — Alembic migration adding Postgres trigger
  `trg_constitutional_rules_no_update` and `trg_constitutional_rules_no_delete`, enforcing
  immutability at the database engine level independent of application code.

---

### PILLAR 2 — Executive (WorkerAgent Refactor)

#### Added
- `pillar_2_executive/base.py` — `WorkerAgent` abstract base class implementing:
  - `ExecutiveAction` Pydantic model with HMAC-SHA256 signing via `sign()` and
    `verify_signature()` using `ENCRYPTION_KEY`
  - `JudiciaryStampRef` lightweight reference model
  - `_stamp_gate()` method — submits `ExecutiveAction` to `JudiciaryClient`, blocks until
    stamp returned, raises `UnauthorizedExecutionError` on REJECTED verdict
  - `_assert_consent()` — verifies `consent_status = ACTIVE` in `consent_log` before building
    the action; raises `ConsentViolationError` if absent
  - `_assert_stamped()` guard — must be called at the top of every `_execute()` method before
    any DB write or LLM call; raises `UnauthorizedExecutionError` if called without a prior stamp
  - `run()` entry point enforces: build → sign → stamp → execute contract; subclasses cannot
    override `run()`, only `_build_action()` and `_execute()`
- `pillar_2_executive/services.py` — Three `WorkerAgent` subclasses refactored:
  - `LessonService` — generates CAPS-aligned lessons via `ProviderRouter`; applies
    `EtherPromptModifier` after stamp approval (pure function, no latency impact); persists
    result to `lesson_results` table only after `_assert_stamped()` passes
  - `StudyPlanService` — generates 4-week CAPS study plans; same stamp-gate contract
  - `ParentReportService` — reads from append-only `audit_log` only (read path); still
    requires a stamp because it accesses learner-linked data

---

### PILLAR 3 — Judiciary (Compliance Firewall)

#### Added
- `pillar_3_judiciary/main.py` — Standalone FastAPI microservice (`judiciary-svc`):
  - Deployed as a separate container/pod with its own isolated DB connection
  - `POST /review` — accepts `ExecutiveActionIn`, returns `JudiciaryStamp`
  - `GET /stamps/{action_id}` — stamp retrieval for audit verification
  - `GET /health` — liveness probe
  - `GET /metrics` — Prometheus counters and histograms
  - `X-Judiciary-API-Key` header authentication — key unknown to worker services
  - CORS restricted to empty origins (worker-to-worker only, no browser access)
- `pillar_3_judiciary/models.py` — `JudiciaryStamp`, `ConstitutionalViolationORM`,
  `ExecutiveActionIn`, `StampVerdict` enum
- `pillar_3_judiciary/service.py` — `JudiciaryService` four-stage review pipeline:
  1. **Fast-path** deterministic checks (SA ID regex, email regex, SA mobile regex, under-13
     flag) — short-circuits LLM call for obvious violations
  2. **Cache lookup** — `(agent_id, intent, rules_hash)` cache with configurable TTL; reduces
     LLM call volume for repeated identical actions
  3. **LLM review** — structured Claude prompt with `APPROVED`/`REJECTED` JSON output; fails
     closed on LLM error (returns REJECTED)
  4. **Persistence** — stamps persisted to `judiciary_stamps`; violations to
     `constitutional_violations`
- `pillar_3_judiciary/client.py` — `JudiciaryClient` HTTP client used by `WorkerAgent._stamp_gate()`
- Prometheus metrics: `judiciary_reviews_total{verdict}` counter,
  `judiciary_review_latency_seconds` histogram

---

### PILLAR 4 — Fourth Estate (Audit Bus)

#### Added
- `pillar_4_fourth_estate/streams.py` — Redis Streams topology:
  - Seven stream keys: `audit:actions`, `audit:stamps`, `audit:violations`, `audit:lessons`,
    `audit:test_results`, `audit:consent`, `audit:dlq`
  - `initialise_streams()` — `XGROUP CREATE` with `$` start ID and `MKSTREAM`, idempotent on
    `BUSYGROUP` error; sets `MAXLEN` retention cap on all streams
  - `publish_*` helpers for each stream with JSON serialisation and timestamp injection
  - `read_pending()` — `XREADGROUP` with blocking read
  - `claim_stale()` — `XAUTOCLAIM` for entries idle beyond `PENDING_CLAIM_TIMEOUT_MS`
  - `ack_message()` — `XACK` (called only after confirmed Postgres write)
  - `get_consumer_lag()` — reads pending count from `XINFO GROUPS`
- `pillar_4_fourth_estate/audit_agent.py` — `AuditAgent` persistent consumer:
  - Independent DB connection with write access only to `audit_log` and `constitutional_violations`
  - Four concurrent async loops: consume, reclaim stale, orphan detection, lag metrics
  - `XACK` issued only after successful `INSERT INTO audit_log` — guarantees at-least-once delivery
  - **Orphan detection** — autonomously flags `ExecutiveAction` entries that have no corresponding
    `judiciary_stamp` within `AUDIT_ORPHAN_WINDOW_SECONDS`; inserts `ConstitutionalViolation`
  - Dead-letter queue (`audit:dlq`) for events failing after 5 retries
  - Prometheus `audit_events_written_total` counter and `audit_stream_consumer_lag` gauge
- `migrations/0001_five_pillar_schema.py` — `audit_log` table with:
  - Postgres trigger `trg_audit_log_no_update` / `trg_audit_log_no_delete` (append-only enforcement)
  - Composite index on `(learner_pseudonym, event_type, created_at)` for portal queries
  - Partial descending index on `created_at DESC`

---

### PILLAR 5 — Ether (Psychographic Profiler)

#### Added
- `pillar_5_ether/models.py` — Full `LearnerEtherProfile` model:
  - `Sephira` enum (10 archetypes: Keter through Malkuth)
  - `MetaphorStyle` enum (narrative/analytical/visual/kinesthetic)
  - `NarrativeFrame` enum (hero/explorer/builder/healer)
  - `LearnerEtherProfile` Pydantic model with `default_for_grade()` factory — Grade R-3, 4-7,
    and 8-12 default profiles applied on first session so lesson delivery is never blocked
  - `EtherPromptModifier` — hot-path prompt injection:
    - Single `SELECT` from `ether_profiles` (sub-millisecond)
    - Pure function `_inject()` appends pedagogy guidance block to base prompt
    - Gracefully falls back to unmodified prompt on DB error
  - `update_ether_profile()` — async Celery task called after session completion (not in hot path)
- `pillar_5_ether/profiler.py` — `EtherProfiler`:
  - `build_profile()` — derives `LearnerEtherProfile` from 19 session signals
  - `SEPHIRA_MAP` — authoritative signal-to-archetype classification table (documented in
    `docs/ether_archetype_map.md`)
  - `apply_decay()` — decays profile toward neutral `Tiferet` prior; configurable `decay_rate`
    per grade band; called by Celery beat task for inactive learners

---

### Infrastructure

#### Added
- `infrastructure/provider_router.py` — `ProviderRouter` with circuit-breaker pattern:
  - `pybreaker` circuit breakers for Groq (primary), Anthropic (secondary), local
    HuggingFace (last resort — critical for ZA network resilience)
  - Per-provider `fail_max` and `reset_timeout` configurable via environment variables
  - `PROVIDER_FALLBACK` audit event emitted to `audit:violations` stream on every provider switch
  - `ProviderHealth` dict exposing circuit state per provider
  - Local HuggingFace pipeline loaded at startup and kept warm
  - Prometheus `llm_circuit_breaker_state` gauge and `llm_provider_fallbacks_total` counter
- `infrastructure/service-worker.js` — Offline resilience for ZA 2G/3G learners:
  - Cache-first strategy for static assets and lesson content
  - Network-first with cache fallback for general navigation
  - **Offline answer queue** — buffers POST requests (diagnostic responses, lesson answers,
    assessment submissions) in IndexedDB when offline
  - Background Sync API (`sync-answers` tag) replays queue on reconnection
  - Queue drain on service worker activation as fallback for browsers without Background Sync
  - Queued responses return HTTP 202 with user-friendly offline message
- `infrastructure/alerts.yml` — Prometheus alerting rules:
  - Judiciary rejection rate > 5% over 15 minutes (`JudiciaryHighRejectionRate`)
  - Judiciary p99 latency > 500ms (`JudiciaryHighLatency`)
  - Judiciary service absent (`JudiciaryServiceDown`) — critical
  - Audit stream lag > 1000 / > 10000 events (`AuditStreamHighLag` / `AuditStreamCriticalLag`)
  - Audit DLQ non-empty (`AuditDLQNonEmpty`) — critical
  - Primary LLM circuit open (`LLMPrimaryProviderCircuitOpen`)
  - All LLM providers down (`LLMAllProvidersDown`) — critical
  - IRT theta drift > 0.5 std (`IRTThetaDrift`)
  - PII scrubber anomaly spike (`PIIScrubberBypass`) — critical

---

### IRT Engine

#### Added
- `irt/engine.py` — `IRTEngine` with:
  - 3-Parameter Logistic (3PL) model implementation
  - EAP (Expected A Posteriori) theta update via gradient step
  - **Versioned item parameters** — `update_item_params()` always inserts a new row
    (increments `version`), never mutates existing parameter rows
  - `score_response()` — scores a learner response, updates `irt_learner_estimates`,
    persists to `irt_responses`
- `IRTDriftMonitor` Celery beat task:
  - Nightly theta distribution analysis (mean, std) published to Prometheus
  - Item parameter drift detection: flags items with `STDDEV(b) > 1.0` over 30 days
  - `joblib` model snapshot serialised to R2 with content-hash filename for reproducibility

---

### Orchestrator

#### Added
- `orchestrator/state_machine.py` — `SessionOrchestrator` formal FSM:
  - 10 states: IDLE, DIAGNOSTIC_IN_PROGRESS, DIAGNOSTIC_COMPLETE, LESSON_IN_PROGRESS,
    LESSON_COMPLETE, ASSESSMENT_IN_PROGRESS, ASSESSMENT_COMPLETE, PLAN_GENERATION,
    PLAN_ACTIVE, SUSPENDED, ARCHIVED
  - `VALID_TRANSITIONS` table — every invalid transition raises `InvalidTransitionError`
  - SUSPENDED state automatically appended as a valid target from any state
  - `ConsentSuspendedError` raised on any non-archival action against a SUSPENDED learner
  - Redis fast state cache (1-hour TTL) + durable Postgres `session_states` table
  - Every transition emits an event to `audit:actions` stream
  - `assert_state_allows()` — called by workers before building an `ExecutiveAction` to
    prevent race conditions across concurrent requests

---

### POPIA Compliance

#### Added
- `popia/compliance.py` — Three compliance modules:
  - **`PIIScrubber`** — five regex patterns: SA ID number (13-digit), email, SA mobile
    (0[6-8]xxxxxxxx), bank account (9–12 digits), full name with prefix. `assert_pii_clean()`
    raises `ValueError` with violation list — call before any LLM request.
  - **`ConsentGate`** — application-layer enforcement (backs up Postgres RLS):
    - `assert_active()` queries `consent_log` for most recent non-revoked record
    - `grant()` inserts consent record and emits to `audit:consent` stream
    - `revoke()` sets `revoked_at` and emits revocation event
  - **`ErasureService`** — POPIA Section 24 right-to-erasure cascade:
    - Deletes from 7 tables: `learner_profiles`, `irt_responses`, `study_plans`,
      `lesson_results`, `ether_profiles`, `session_states`, `consent_log`
    - Deletes R2/S3 assets under `learners/{pseudonym}/` prefix via boto3 paginator
    - Emits `popia_erasure` event to audit stream as the final operation
    - Audit log record for the erasure event itself is never deleted (POPIA record-keeping)
- **Postgres RLS consent gate** (in migration) — `consent_gate` policy on `learner_sessions`
  enforces `consent_status = ACTIVE` at the DB engine level, independent of application code

---

### Database & Migrations

#### Added
- `migrations/0001_five_pillar_schema.py` — Single Alembic migration creating all 18 tables:
  - `constitutional_rules` with immutability triggers
  - `rule_set_signatures`, `legislature_source_hashes`
  - `lesson_results`, `study_plans`
  - `judiciary_stamps`, `judiciary_stamp_cache`, `constitutional_violations`
  - `audit_log` with append-only triggers and composite/partial indexes
  - `consent_log` with RLS policy on `learner_sessions`
  - `ether_profiles`
  - `irt_item_parameters` (versioned), `irt_responses`, `irt_learner_estimates`
  - `session_states`
  - `data_retention_policy`

#### Changed
- Database bootstrapping is now exclusively Alembic-driven (`alembic upgrade head`)
- `alembic check` added as a required CI gate before merge to `main`

---

### Testing

#### Added
- `tests/test_five_pillars.py` — 30+ `pytest` / `pytest-asyncio` tests:
  - `TestConstitutionalRuleImmutability` — 7 tests: hash computation, determinism,
    `verify_integrity()`, frozen model mutation prevention, tamper detection, ORM event listeners
  - `TestPIIScrubber` — 7 tests: clean text pass, SA ID detection, email detection, mobile
    detection, `assert_pii_clean()` raise, clean text pass-through, multi-pattern detection
  - `TestWorkerAgentStampGate` — 5 tests: approved stamp unblocks execution, rejected stamp
    raises `UnauthorizedExecutionError`, `_assert_stamped()` without prior stamp, HMAC signing,
    tampered signature fails verification
  - `TestJudiciaryFastPath` — 3 tests: SA ID triggers rejection, email triggers rejection,
    clean action passes
  - `TestConsentGate` — 3 tests: active consent passes, no consent raises, revoked raises
  - `TestSessionOrchestrator` — 3 tests: valid transition, invalid transition, SUSPENDED learner
  - `TestIRTEngine` — 4 tests: parameter versioning, 3PL probability bounds, EAP update
    direction correct on right/wrong answers
  - `TestEtherProfiler` — 3 tests: profile build, decay toward neutral, zero-day no-change

---

### CI/CD

#### Added
- `.github/workflows/ci.yml` — Full CI/CD pipeline:
  - **lint** — `ruff` and `mypy` on every push and PR
  - **unit-tests** — pytest with `--cov-fail-under=80` coverage gate
  - **integration-tests** — with Postgres 15 and Redis 7 service containers; runs
    `alembic upgrade head` before tests
  - **schema-drift** — `alembic check` must pass as a required gate before merge to `main`
  - **popia-tests** — dedicated POPIA compliance test run
  - **image-scan** — Trivy vulnerability scan on `CRITICAL,HIGH`; uploads SARIF to GitHub
    Advanced Security; fails CI on CRITICAL findings
  - **production-promote** — tag-triggered; runs smoke tests against staging before deploying;
    uses `kubectl set image` + `kubectl rollout status --timeout=5m`

---

### Documentation

#### Added
- `docs/architecture/five_pillars.md` — Authoritative technical spec for the five-pillar
  model as implemented: pillar summaries, immutability guarantees, network isolation
  diagram, consent defence-in-depth table, orchestrator FSM ASCII diagram
- `docs/ether_archetype_map.md` — Full Sephira → psychographic signal mapping table for
  all 10 archetypes; includes signal definitions, Guardian Report language translations,
  profile decay schedule per grade band, and A/B shadow mode description
- `docs/runbooks/db_rollback.md` — Step-by-step DB rollback procedure including mandatory
  backup step, constraint notes for append-only tables, and notification checklist
- `docs/runbooks/popia_erasure.md` — POPIA Section 24 erasure workflow: guardian
  verification, API call, SQL verification queries, audit trail confirmation, guardian
  notification template, and escalation procedure
- `CONTRIBUTING.md` — Branch naming conventions, PR checklist, per-path reviewer
  requirements table, test requirements, commit message convention, and a "Do Not" list
- `CODEOWNERS` — GitHub CODEOWNERS file assigning mandatory reviewers for judiciary,
  constitutional schema, audit infrastructure, POPIA paths, and Alembic migrations

---

## Unreleased

- Normalize `knowledge_gaps` input handling in `StudyPlanService` so remediation and scheduling accept either strings (concept names) or dicts with metadata.
- Add backward-compatible `report` object in `ParentPortalService.generate_parent_report` to satisfy integrations/tests expecting `report`.
- Pin CI and repository Python target to 3.11 via `.python-version` and GitHub Actions update.
- Add `scripts/check_env.sh` to verify local Python runtime is 3.11.

These changes fix multiple failing tests related to study plan generation and parent report structure, and standardise local/CI Python versions.

---
