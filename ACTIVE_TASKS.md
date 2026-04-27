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

