# EduBoost SA — Security Penetration Test Runbook & Checklist
Version: 1.0 (Phase 2 Baseline)

This document outlines the security controls and the penetration testing procedures required before full production deployment of EduBoost SA.

## 1. Governance & Compliance
- [ ] **POPIA Compliance**: Verify that no plaintext PII (Name, Email, ID Number) is stored in the database. Use `consent_service` for all data handling.
- [ ] **Data Retention**: Verify that `DeletionRequest` flow correctly wipes learner data after the 30-day grace period.
- [ ] **Consent Gate**: Confirm that all API routes under `/api/v1/learner` return `403 Forbidden` if active parental consent is missing.

## 2. API Security (OWASP Top 10)
- [ ] **Authentication (Broken Access Control)**:
    - [ ] Verify JWT token expiration (short-lived) and refresh flow.
    - [ ] Test cross-tenant access: Can Guardian A view data for Learner B? (Use `has_active_consent` and ownership checks).
- [ ] **Injection**:
    - [ ] Verify all SQLAlchemy queries use parameterized inputs (AsyncPG/psycopg2).
    - [ ] Test for prompt injection in `lesson_service.py`. Try to bypass the Judiciary gate.
- [ ] **Rate Limiting**:
    - [ ] Verify `slowapi` decorators are active on all public endpoints.
    - [ ] Test for brute-force attacks on `/api/v1/auth/login`.

## 3. AI Safety & Governance (Pillar 3 & 5)
- [ ] **Judiciary Gate**:
    - [ ] Force the LLM to generate harmful content. Verify that the `JudiciaryAgent` rejects the response with `verdict="REJECTED"`.
    - [ ] Verify that `PROMETHEUS` alert `JudiciaryHighRejectionRate` triggers.
- [ ] **PII Scrubber**:
    - [ ] Input a prompt containing a South African ID number or phone number. Verify that `inference_gateway.py` scrubs it before sending to the provider.
- [ ] **Ether Profiling**:
    - [ ] Verify that sensitive cultural context (Pillar 5) is handled with dignity and does not reinforce stereotypes.

## 4. Infrastructure Security
- [ ] **Container Isolation**:
    - [ ] Verify that the `inference` microservice is only reachable internally via `eduboost-net`.
    - [ ] Ensure all containers run as non-root users (`appuser`).
- [ ] **Secrets Management**:
    - [ ] Verify that `.env` is NOT committed to git.
    - [ ] Confirm `AZURE_KEYVAULT_URL` integration works for retrieving production DB credentials.
- [ ] **Network**:
    - [ ] Check `docker-compose.yml` for exposed ports. Only `8000` (API), `3000` (Frontend), and `9090/3000` (Obs) should be external.

## 5. Persistence & Recovery
- [ ] **Backups**: Test a full database restore from an Alembic snapshot.
- [ ] **Audit Trail**: Confirm every `consent.grant` and `erasure.request` event is recorded in the `audit_events` table with an IP hash.

---
*Date of last audit: 2026-05-01*
*Auditor: Antigravity AI*
