## What the Repo Audit Found

The infrastructure scaffolding is genuinely solid — Docker Compose, Prometheus/Grafana, Celery, Alembic, pre-commit, structlog, Sentry, rate limiting, R2 storage, and three LLM providers are all wired in. The skeleton of all five pillars exists as file names. The gap is that the five-pillar architecture is mostly **nominal** right now — the files exist (`judiciary.py`, `fourth_estate.py`, `profiler.py`, `orchestrator.py`) but the critical contracts between them (signed `ExecutiveAction`, `JudiciaryStamp` gate, append-only audit stream with consumer groups, `LearnerEtherProfile` as a real model) are not yet implemented as enforced invariants.

The most serious outstanding gaps are all `[P0]` POPIA-class issues: the Judiciary is not yet a hard blocking gate before LLM calls; the Right-to-Erasure workflow is unverified end-to-end; parental consent is not enforced at the DB layer; and the audit stream consumer group design is unresolved, which means missed events are possible.

---

## The 10 Architectural Modifications I'd Make

The document covers all ten in detail, but the four highest-leverage ones are:

**1. Judiciary as a network-isolated sidecar.** An in-process firewall can be bypassed by exceptions and misconfigurations. LLM provider calls should originate from the Judiciary service *after* approval, not from the worker. This is the only design where the POPIA firewall is structurally genuine.

**2. Consent as a Postgres RLS policy, not application logic.** Application checks can be missed by any new code path. A database-level row security policy is enforced regardless of which service issues the query — it's the only consent enforcement that holds under adversarial conditions.

**3. Ether as a materialized profile + async enrichment pipeline.** Profile computation in the hot path will destroy p99 latency. The right design is a Celery-updated materialized row that the hot path reads in a single key-value lookup.

**4. The Orchestrator as a formal finite state machine.** Without state machine semantics, you'll get race conditions — lessons generated for learners mid-diagnostic, assessments triggered while a plan is being generated. The state machine also gives you a clean transition event stream for the Fourth Estate to consume.