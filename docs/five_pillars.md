# EduBoost SA — Five-Pillar Architecture

> Version: 1.0 | Status: Production-hardening | Last updated: 2026-04-29

---

## Overview

EduBoost SA uses a constitutional governance model inspired by the separation of powers. Every AI-generated action that touches learner data must flow through a defined pipeline before execution. No worker may call an LLM or write to the database without a verified **JudiciaryStamp**.

```
Legislature ──► Executive ──► Judiciary ──► Fourth Estate
(rules)         (actions)     (firewall)    (audit log)
                                │
                           Ether Layer
                         (psychographic)
```

---

## Pillar 1 — Legislature (Vector Knowledge Base)

**Purpose:** Maintain the authoritative set of `ConstitutionalRule` objects that all Judiciary decisions are grounded in.

**Key components:**
- `pillar_1_legislature/models.py` — `ConstitutionalRule` Pydantic model with SHA-256 `immutable_hash`
- `pillar_1_legislature/agent.py` — `LegislatureAgent` for document ingestion and versioned rule storage
- Postgres `constitutional_rules` table with UPDATE/DELETE triggers (append-only)

**Immutability guarantee:**
```
rule₁(effective_date=2024-01-01) → never modified
rule₁(effective_date=2025-03-01) → new row, new version
```
The Judiciary always retrieves the latest version per `rule_id` using `DISTINCT ON (rule_id) ORDER BY effective_date DESC`.

**Trigger event:** Document hash change detected, or admin `POST /admin/legislature/refresh`.

---

## Pillar 2 — Executive (WorkerAgent Framework)

**Purpose:** All services that touch learner data or call an LLM must extend `WorkerAgent`. Execution is impossible without a verified stamp.

**Key components:**
- `pillar_2_executive/base.py` — `WorkerAgent` ABC, `ExecutiveAction`, `JudiciaryStampRef`
- `pillar_2_executive/services.py` — `LessonService`, `StudyPlanService`, `ParentReportService`

**Execution contract:**
```python
# Worker cannot do this without a stamp:
await session.execute(...)  # → UnauthorizedExecutionError
await anthropic.messages.create(...)  # → UnauthorizedExecutionError

# Correct flow:
action = await self._build_action(**kwargs)
stamp = await self._stamp_gate(action)  # blocks until Judiciary responds
result = await self._execute(action, stamp, **kwargs)
```

**HMAC signing:** Every `ExecutiveAction` is signed with `ENCRYPTION_KEY` before being sent to Judiciary, preventing tampering in transit.

---

## Pillar 3 — Judiciary (Compliance Firewall)

**Purpose:** Review every `ExecutiveAction` and issue a `JudiciaryStamp` (APPROVED or REJECTED). Network-isolated as a separate microservice.

**Key components:**
- `pillar_3_judiciary/main.py` — FastAPI microservice (`judiciary-svc`)
- `pillar_3_judiciary/service.py` — Full review pipeline (fast-path + cache + LLM)
- `pillar_3_judiciary/client.py` — HTTP client used by workers

**Review pipeline:**
```
ExecutiveAction → Fast-path (PII regex, under-13 flag) → Cache lookup
    → LLM review (Claude, structured JSON output)
        → Persist stamp → Return JudiciaryStamp
```

**Network isolation:** Workers call `POST judiciary-svc/review`. A k8s `NetworkPolicy` ensures no worker can reach Groq/Anthropic APIs directly — all LLM calls originate from `judiciary-svc` after approval.

**Stamp caching:** Identical `(agent_id, intent, rules_hash)` tuples are cached for a configurable TTL to reduce LLM call volume.

---

## Pillar 4 — Fourth Estate (Audit Bus)

**Purpose:** Immutable, append-only audit trail of every action, stamp, and event in the system.

**Key components:**
- `pillar_4_fourth_estate/streams.py` — Redis Streams topology with consumer groups
- `pillar_4_fourth_estate/audit_agent.py` — Persistent consumer, orphan detection, lag monitoring

**Stream keys:**
| Stream | Event type |
|---|---|
| `audit:actions` | `ExecutiveAction` emitted |
| `audit:stamps` | `JudiciaryStamp` issued |
| `audit:violations` | Constitutional violation recorded |
| `audit:lessons` | Lesson completed |
| `audit:test_results` | Assessment result |
| `audit:consent` | Consent granted/revoked |
| `audit:dlq` | Dead-letter events |

**Reliability guarantees:**
- `XACK` only after successful Postgres write
- `XAUTOCLAIM` reclaims stale pending entries after configurable timeout
- Dead-letter stream for events that fail after 5 retries
- Autonomous orphan detection: flags actions with no stamp within the configured window

---

## Pillar 5 — Ether (Psychographic Profiler)

**Purpose:** Personalise lesson tone, pacing, and metaphor style to each learner's psychographic profile without blocking lesson delivery.

**Key components:**
- `pillar_5_ether/models.py` — `LearnerEtherProfile`, `EtherPromptModifier` (hot-path)
- `pillar_5_ether/profiler.py` — `EtherProfiler` (async Celery task, cold-path)

**Three-layer architecture:**
```
Hot path:  SELECT ether_profiles WHERE learner_pseudonym = $1  (sub-millisecond)
           └─ EtherPromptModifier.apply(prompt, profile)       (pure function)

Cold path: After session → Celery task → EtherProfiler.build_profile()
           └─ UPDATE ether_profiles                             (async, no latency impact)
```

**Sephira archetypes:** Ten archetypes (Keter–Malkuth) mapped to observable psychographic signals (response speed, reattempt rate, skip rate, etc.). See `docs/ether_archetype_map.md`.

**First session:** Grade-band default profile applied. No learner waits for profile computation.

---

## Cross-Cutting: POPIA Compliance

| Requirement | Implementation |
|---|---|
| Data minimisation | PII scrubber (`popia/compliance.py`) blocks any prompt containing SA ID, email, mobile |
| Parental consent gate | `ConsentGate.assert_active()` + Postgres RLS policy on `learner_sessions` |
| Right to erasure | `ErasureService.erase()` cascades across 7 tables + R2 asset deletion |
| Pseudonymisation | `learner_pseudonym` is the only identifier in all LLM-facing contexts |
| Audit trail | Append-only `audit_log` table with Postgres trigger blocking UPDATE/DELETE |
| Data retention | `data_retention_policy` table; Celery beat enforces auto-archival |

---

## Consent Enforcement — Defence in Depth

Three independent layers:

1. **Application layer** (`ConsentGate.assert_active()`) — checked in `WorkerAgent._build_action()`
2. **Judiciary layer** — Judiciary rejects any action with an inactive learner pseudonym
3. **Database layer** (Postgres RLS) — `consent_gate` policy on `learner_sessions` blocks queries at engine level

All three must be satisfied. A bypass at any single layer is caught by the other two.

---

## Orchestrator State Machine

```
IDLE
 ├─► DIAGNOSTIC_IN_PROGRESS ─► DIAGNOSTIC_COMPLETE
 │                                       │
 │   ┌───────────────────────────────────┘
 │   ▼
 ├─► LESSON_IN_PROGRESS ─► LESSON_COMPLETE
 │                                  │
 │                    ┌─────────────┘
 │                    ▼
 │           ASSESSMENT_IN_PROGRESS ─► ASSESSMENT_COMPLETE
 │                                              │
 │                         ┌────────────────────┘
 │                         ▼
 └──────────────── PLAN_GENERATION ─► PLAN_ACTIVE
                                           │
Any state ──────────────────────────► SUSPENDED ─► ARCHIVED
```

Every transition is persisted to Postgres and emits an event to `audit:actions`. A `WorkerAgent` that attempts an action invalid for the learner's current state is blocked by the orchestrator before the stamp gate is even reached.
