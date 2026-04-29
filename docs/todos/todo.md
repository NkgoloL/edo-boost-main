The user wants code implementation of all 10 architectural recommendations. This is a substantial amount of code. Let me plan this out systematically:

Judiciary as network-isolated sidecar (separate FastAPI microservice)
DB driver consolidation (remove Supabase from backend, single asyncpg/psycopg2 strategy)
Ether as async enrichment pipeline (materialized profile + Celery task)
Legislature content-addressable immutability (SHA-256 hash, Postgres trigger, window function)
Redis Stream topology with consumer groups (XGROUP, XAUTOCLAIM, XACK, DLQ)
Consent as Postgres RLS policy
Multi-LLM circuit breaker (pybreaker-based ProviderRouter)
IRT drift monitoring and model versioning
Frontend offline resilience (Service Worker, IndexedDB queue)
Orchestrator as formal FSM

This is a LOT of code. Let me create multiple files organized by pillar/recommendation. I'll create a well-organized directory structure.
Let me think about the file structure:

eduboost_implementation/
├── pillar_1_legislature/
│   ├── models.py          - ConstitutionalRule Pydantic + SQLAlchemy models
│   ├── ingestion.py       - Document ingestion pipeline
│   ├── agent.py           - LegislatureAgent
│   └── migrations/        - Alembic migration for constitutional_rules
├── pillar_2_executive/
│   ├── base.py            - WorkerAgent ABC + ExecutiveAction + stamp gate
│   ├── lesson_service.py  - Refactored LessonService
│   └── study_plan.py      - Refactored StudyPlanService
├── pillar_3_judiciary/
│   ├── main.py            - Separate FastAPI microservice
│   ├── service.py         - JudiciaryService.review()
│   ├── models.py          - JudiciaryStamp, ConstitutionalViolation
│   └── fast_path.py       - Deterministic rule engine
├── pillar_4_fourth_estate/
│   ├── streams.py         - Redis Stream topology + consumer groups
│   └── audit_agent.py     - AuditAgent consumer
├── pillar_5_ether/
│   ├── models.py          - LearnerEtherProfile
