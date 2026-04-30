# Change Management Plan (CMP)
**Document ID:** DBE-CMP-037  
**Version:** 1.0.0  
**Date:** 2026-04-29

---

## 1. Purpose

This document defines the process for managing changes to the DBE AI Expert System — including changes to source code, infrastructure, interfaces, documentation, and security controls — to ensure all changes are assessed, approved, and traceable.

---

## 2. Change Categories

| Category | Definition | Approval Required | Lead Time |
|----------|-----------|-------------------|-----------|
| **Standard** | Pre-approved, low-risk, routine (e.g., dependency patch, log level change) | Tech Lead | Same sprint |
| **Normal** | Planned change requiring assessment (e.g., new endpoint, schema change) | Tech Lead + PM | 1 sprint |
| **Emergency** | Critical security fix or P1 incident resolution | Tech Lead (post-hoc PM notification) | Immediate |
| **Major** | Breaking interface change, architecture revision, data migration | Tech Lead + PM + DBE IT Director | 2 sprints |

---

## 3. Change Request Process

```
Engineer identifies change need
        │
        ▼
   Create Change Request (CR)
   in issue tracker with:
   - CR-ID
   - Category
   - Description
   - Affected components
   - Impact assessment
   - Rollback plan
        │
        ▼
   Tech Lead reviews
        │
   ┌────┴────┐
Standard/   Normal/
Emergency   Major
   │           │
   ▼           ▼
Approve     PM + Director
immediately    review
   │           │
   └─────┬─────┘
         │
         ▼
   Implement on feature branch
   Run CI/CD pipeline
   Peer code review
         │
         ▼
   Merge to develop
   Staging deployment
   Smoke tests
         │
         ▼
   Merge to main (production)
   Update CHANGELOG / Release Notes
```

---

## 4. Interface Change Control

Any change to interfaces defined in `docs/design/ICD.md` is automatically classified as **Normal** or **Major** and requires:

1. ICD version increment.
2. Consumer team notification ≥ 5 business days before deployment.
3. Updated consumer integration tests.
4. Backwards compatibility maintained for at least one sprint, or explicit breaking change notice.

---

## 5. Infrastructure Change Control

All infrastructure changes must be:
- Implemented in Terraform (`infrastructure/` directory).
- Reviewed via `terraform plan` output in PR.
- Applied only via CI/CD pipeline — no manual `az` commands in production.
- Documented with a comment block in the relevant `.tf` file.

---

## 6. Emergency Change Procedure

For P1 security incidents or outages:

1. Engineer implements fix on `hotfix/<incident-id>` branch.
2. Tech Lead approves via PR review (minimum 1 reviewer).
3. CI/CD pipeline runs (tests must pass — no bypassing).
4. Deploy to production.
5. Retrospective within 5 business days; lessons learned added to `docs/management/RR.md`.
6. Full CR documentation completed within 24 hours post-deployment.

---

## 7. Change Log

| CR-ID | Date | Category | Description | Approved By | Status |
|-------|------|----------|-------------|-------------|--------|
| CR-001 | 2026-04-29 | Normal | Migrate BaseSettings to pydantic-settings | Tech Lead | ✅ Merged |
| CR-002 | 2026-04-29 | Normal | Parameterise all Gremlin queries (security fix) | Tech Lead | ✅ Merged |
| CR-003 | 2026-04-29 | Normal | Externalise graph schema to config/graph_schema.json | Tech Lead | ✅ Merged |
| CR-004 | 2026-04-29 | Normal | Add tenacity retry to Gremlin client | Tech Lead | ✅ Merged |

---

*End of CMP — DBE-CMP-037 v1.0.0*
