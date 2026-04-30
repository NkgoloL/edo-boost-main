# Project Management Plan (PMP)
**Document ID:** DBE-PMP-035  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** Internal — Controlled

---

## 1. Project Overview

| Field | Value |
|-------|-------|
| Project Name | DBE AI Expert System |
| Sponsor | DBE IT Director |
| Project Manager | TBD |
| Start Date | 2026-03-01 |
| Target Completion | 2026-06-30 (10 weeks remaining) |
| Budget | Within existing Azure Enterprise Agreement |

---

## 2. Scope Statement

**In scope:**
- All 83 TODO items documented in `docs/TODO.md`.
- Five delivery phases (Phase 1 complete; Phases 2–5 in progress).
- All 39 documentation artefacts in this document suite.
- POPIA compliance certification and ATO sign-off.
- Production deployment to `southafricanorth` Azure region.

**Out of scope:**
- Web UI / portal for end users (separate project).
- Intranet identity provider integration.
- Mobile application.
- Content management of policy documents.

---

## 3. Delivery Schedule

| Phase | Focus | Weeks | Status |
|-------|-------|-------|--------|
| Phase 1 | Foundation & Infrastructure | 1–2 | ✅ Complete |
| Phase 2 | Intelligence & Data | 3–4 | 🔄 ~50% |
| Phase 3 | Integration & CI/CD | 5–7 | ⬜ Not started |
| Phase 4 | Optimisation & LLM | 7–9 | ⬜ Not started |
| Phase 5 | Production & Governance | 9–10 | ⬜ Not started |

### Detailed Milestone Schedule

| Milestone | Target Date | Deliverable |
|-----------|-------------|-------------|
| M1 | Week 4 | Phase 2 complete — 80% test coverage, Gremlin traversal wired |
| M2 | Week 5 | CI/CD pipeline green — build, test, Trivy, deploy to staging |
| M3 | Week 6 | APIM JWT, FastAPI auth, PII scrubbing deployed to staging |
| M4 | Week 7 | AKS fully managed — HPA, SecretProviderClass, NetworkPolicy |
| M5 | Week 8 | Azure Monitor alerts, structured logging, Application Insights live |
| M6 | Week 9 | Performance benchmarks completed (PBR populated) |
| M7 | Week 9 | Penetration test completed |
| M8 | Week 10 | ATP executed and signed |
| M9 | Week 10 | PIA signed; ATO issued; production deployment |

---

## 4. Resource Plan

| Role | Allocation | Responsibilities |
|------|-----------|-----------------|
| Lead Engineer | 100% | Architecture, code review, Phase 3–4 implementation |
| Backend Engineer | 100% | Python services, Gremlin, FastAPI |
| DevOps Engineer | 80% | Terraform, Helm, CI/CD, AKS, monitoring |
| ML Engineer | 50% | Azure ML endpoints, retraining pipeline |
| Security Engineer | 30% | Threat model, pen test coordination, compliance scripts |
| QA Engineer | 50% | Test plan, ATP execution, coverage reporting |
| DBE Legal | 20% | PIA review, Information Officer appointment, privacy notice |

---

## 5. Communication Plan

| Communication | Frequency | Format | Audience |
|---------------|-----------|--------|---------|
| Sprint standup | Daily | 15-min call | Engineering team |
| Sprint review | Bi-weekly | Demo + retro | All stakeholders |
| Phase completion report | Per phase | Written report | DBE management |
| Security status | Weekly | Email | Security Officer |
| Incident notification | Ad hoc | Email + call | IT Director |
| DOC_MASTER_TRACKER | Continuous | Git commit | All |

---

## 6. Budget Management

| Category | Allocated | Estimated Monthly | Notes |
|----------|-----------|-------------------|-------|
| AKS (2 nodes D2s_v2) | R8,000/month | R8,000 | Scale up in Phase 4 |
| Cosmos DB (Gremlin) | R3,500/month | R3,500 | 400 RU/s base |
| Azure ML Workspace | R2,000/month | R2,000 | Endpoint hosting |
| APIM Standard_1 | R4,000/month | R4,000 | Production only |
| Storage + Key Vault | R500/month | R500 | |
| **Total** | **~R18,000/month** | | Within EA budget |

---

## 7. Acceptance Criteria

The project is considered complete when:
1. All 24 ATO preconditions in `docs/security/ATO.md` are resolved.
2. ATO signed by all required authorising officials.
3. System live in production (`api.dbe-expert.gov.za`) with 99.9% uptime SLA.
4. First 100 queries processed with average rating ≥ 3.5.
5. All 83 TODO items in `docs/TODO.md` resolved or formally deferred.

---

*End of PMP — DBE-PMP-035 v1.0.0*
