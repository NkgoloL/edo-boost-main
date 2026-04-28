# EduBoost SA: Implementation Roadmap & Epics

This document outlines the strategic Epics required to address the recommendations in `System_Review.md`. These Epics focus on bridging the gap between the architectural vision and the current prototype implementation.

---

## Epic 1: Constitutional Integrity & Pillar Completion
**Goal**: Complete the "Five Pillars" implementation to ensure the pedagogical and regulatory layers are fully functional as designed.

- [x] **Ether Integration**: Pass `LearnerEtherProfile.to_prompt_modifier()` into the system prompt construction in `lesson_service.py`.
- [ ] **Judiciary LLM Path**: Implement a fast Claude-backed evaluation path for critical constitutional rules in `judiciary.py`.
- [ ] **Legislature Knowledge Base**: Transition from hardcoded stubs to a vector knowledge base of real CAPS curriculum documents.
- [x] **Judiciary LLM Caching & Test Gating**: Add a short-lived cache for rapid Claude responses and gate LLM-based tests with the `llm` pytest marker so CI doesn't call paid APIs by default.
- [x] **Ether Prompt Modifier Wiring**: Ensure `LearnerEtherProfile.to_prompt_modifier()` is accepted by `build_lesson_prompts()` and is plumbed through the lesson generation path.
- [ ] **Constitutional Alignment**: Ensure all `ExecutiveAction` reviews actually honor the `use_llm_review` flag.

## Epic 2: Data Privacy, Security & Compliance
**Goal**: Ensure the system meets POPIA requirements and maintains rigorous PII protection.

- [ ] **AES-256 Email Encryption**: Replace SHA-256 email hashing with decryptable AES-256 encryption in the `LearnerIdentity` model.
	- [ ] **Migration Plan**: Add an Alembic migration to decrypt/hash-migrate existing email values into the new encrypted column while keeping a rollback path.
- [x] **Audit Service Reconciliation**: Fix field name mismatches in `audit_query_service.py` to match SQLAlchemy models.
- [ ] **PII Scrubber Refinement**: Update the SA ID regex pattern with context anchors or Luhn validation to reduce false positives.
- [ ] **Production Gating**: Implement environment-based gating for developer login bypasses.
- [ ] **Right-to-Access Endpoint**: Fix `Learner` field references in `system.py` to ensure data subject reports can be generated.

## Epic 3: Core Diagnostic & Educational Engine Hardening
**Goal**: Resolve structural bugs in the IRT logic, database schema, and automated testing.

- [ ] **Diagnostic Session Model**: Add `items_correct` column to `DiagnosticSession` (including migration) or refactor accuracy calculations.
	- [ ] **Benchmark Backwards-compatibility**: When adding `items_correct`, add a data-migration script that backfills values from existing diagnostic response tables.
- [ ] **Alembic Fixes**: Correct the `parent_learnner_links` typo in migration `0002` downgrade function.
- [ ] **Authorization Logic Validation**: Refactor `_verify_guardian_access` in `parent_portal_service.py` to ensure tests exercise the real DB-backed authorization path.
	- [ ] **Test Coverage**: Add integration tests that exercise the real `AsyncSession` path against an ephemeral Postgres service in CI to avoid false positives from mocked sessions.
- [ ] **IRT Precision**: Review MLE theta estimation edge cases for perfect/zero scores.

## Epic 4: Frontend/Backend Alignment & UX Polish
**Goal**: Resolve integration issues and "broken links" that impact user experience.

- [ ] **Gamification URL Fix**: Resolve the 404 mismatch for the gamification profile endpoint in `services.js`.
	- [ ] **API Contract Tests**: Add a small suite that loads OpenAPI (or a hand-written contract) and verifies frontend calls match backend routes.
- [ ] **API Contract Audit**: Synchronize frontend service calls with backend router definitions across all pillars.
- [ ] **Dashboard State Persistence**: Ensure XP, levels, and badges reflect real-time backend state accurately.

---

## Priority & Sequencing

### Phase 1: Critical Fixes (Immediate)
1. Fix Gamification URL mismatch.
2. Wire Ether `to_prompt_modifier()`.
3. Fix `AuditEvent` field mismatches.

### Phase 1.5: Fast wins and safety
1. Add lightweight LLM-review cache and gate LLM tests in CI under a separate job.
2. Add `scripts/check_env.sh` to validate local Python is 3.11 for reproducibility.

### Phase 2: Compliance & Hardening
1. Implement AES-256 Email Encryption.
2. Fix `DiagnosticSession` schema.
3. Refine PII Scrubber regex.

### Phase 3: Architectural Completion
1. Implement Judiciary LLM path.
2. Build Legislature Vector Store.
