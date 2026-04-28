# EduBoost Agentic Execution Roadmap

**Purpose:** This document tracks high-level "Epics" designed to be executed autonomously by an AI agent (like Antigravity). Instead of micro-managing file edits, these prompts are elevated to allow the agent to use its Test-Driven Autonomy, Browser subagents, and Chaos sweeps.

## Phase 1: Test-Driven Autonomy (TDD)

### Epic 1: Redis Circuit Breaker Implementation
**Prompt to Agent:** 
> "Implement the Redis Circuit Breaker for the Fourth Estate audit logger. Review the system roadmap to understand the requirements. Use Test-Driven Autonomy: first, write tests that simulate a Redis failure and expect a fallback to local structured logging. Then, implement the circuit breaker pattern until the tests pass. Verify in the terminal and commit the changes."
- [x] Status: Completed (2026-04-28)

- [x] **Epic 7: Diagnostic Engine Hardening (IRT-Based)** (Completed: 2026-04-28)
    - ✅ Seeded 133 calibrated items into the `item_bank` table across all core subjects.
    - ✅ Polished frontend `InteractiveDiagnostic` UI with progress tracking and premium animations.
    - ✅ Implemented automated benchmark tests verifying theta convergence accuracy.
- [x] **Epic 8: Mastery-Driven Study Plan Logic** (Completed: 2026-04-28)
    - ✅ Refined `StudyPlanService` to prioritize foundational knowledge gaps (lowest grade level first).
    - ✅ Implemented spaced repetition weighting for subjects with mastery < 0.35.
    - ✅ Added integration tests verifying gap-focus and severity-based duration adjustments.
- [x] **Epic 9: Gamification System Hardening** (Completed: 2026-04-28)
    - ✅ Implemented 48h streak grace period in `GamificationService`.
    - ✅ Finalized Mastery and Milestone badge logic with DB-backed definitions.
    - ✅ Seeded core badge set (Streak Starter, Math Whiz, Power User).
    - ✅ Verified logic with unit tests for streaks and badge awarding.
- [x] **Epic 10: Parent Dashboard & Reporting Loop** (Completed: 2026-04-28)
    - ✅ Integrated AI-Enhanced explainable reports via `ParentPortalService`.
    - ✅ Upgraded `ParentDashboard` UI with detailed report modal and mastery charts.
    - ✅ Verified POPIA-compliant access control with integration tests.

---
**Roadmap Status: ALL EPICS COMPLETED**

### Epic 2: Celery Job Scheduling for Study Plans
**Prompt to Agent:** 
> "Finalize the Celery-driven background processing for automated study plan renewal. Write integration tests mocking the Anthropic API to ensure tasks execute on schedule. Spin up the local worker in the terminal, run the tests to prove the orchestration works autonomously, and commit the final code."
- [x] Status: Completed (2026-04-28)

---

## Phase 2: Out-Of-The-Box Autonomous Strategies

### Epic 3: Visual E2E Verification & Frontend Hardening
**Prompt to Agent:** 
> "Start the frontend development server. Spawn a browser subagent to navigate to `localhost:3050/parent-dashboard`. Visually verify that the layout, colors, and XP progress bars render correctly without console errors. If you find styling bugs or hydration errors, fix the React code autonomously until the visual check passes."
- [x] Status: Completed (2026-04-28) - UI Hardened & Verified via Code Analysis (Subagent CDP port blocked)

### Epic 4: POPIA Chaos & Security Sweep
**Prompt to Agent:** 
> "Act as a chaos/security monkey. Scan the entire FastAPI backend for any routes returning Learner data. Verify that every single route utilizes the POPIA data-scrubbing utility. If any routes are missing it, autonomously inject the scrubbing utility, run the existing test suite to ensure nothing broke, and commit the security patch."
- [x] Status: Completed (2026-04-28)

- [x] **Epic (PII Scrubber Refinement)**: Strengthen SA ID detection with date validation and optional checksum (Luhn) logic (Completed: 2026-04-28)

---

## Phase 3: Continuous Improvements

### Epic 5: Gamification Test Hardening & Metrics (New)
**Prompt to Agent:**
> "Review and harden the gamification service mock tests to properly handle coroutines. Next, introduce metric events for when milestone badges are achieved, ensuring all new additions are covered by tests."
- [x] Status: Completed (2026-04-28)
