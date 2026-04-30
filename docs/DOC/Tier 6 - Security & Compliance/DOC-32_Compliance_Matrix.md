# Compliance Matrix
**Document ID:** DBE-CM-032  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** Internal — Controlled

---

## Instructions

This matrix maps each compliance requirement to its implementing control, the responsible owner, the evidence artefact, and current verification status.

Status codes: ✅ Compliant | ⚠️ Partial | ❌ Non-compliant | ⬜ Not yet assessed

---

## 1. POPIA Act No. 4 of 2013

| POPIA Condition | Section | Control | Owner | Evidence | Status |
|----------------|---------|---------|-------|----------|--------|
| Accountability | S.8 | Information Officer appointed | DBE Legal | Appointment letter | ⬜ |
| Lawful processing | S.9 | Queries used only for advisory | Lead Eng | Design docs, PIA | ✅ |
| Minimality | S.10 | Only `query` and `user_id` collected | Lead Eng | ICD §3, DD §1 | ✅ |
| Purpose specification | S.13 | Privacy notice to users | DBE Legal | Published notice | ⬜ |
| Further processing | S.15 | Feedback only for model improvement | Lead Eng | `feedback_loop.py` | ✅ |
| Information quality | S.16 | Document validation on ingestion | Lead Eng | `pipeline.py` | ✅ |
| Openness | S.17 | Privacy policy published | DBE Legal | URL | ⬜ |
| Security safeguards | S.19 | Encryption, PII scrubbing, RBAC | Security | SecAD, PIA §5 | ⚠️ |
| Data subject access | S.23 | Access/erasure mechanism | Lead Eng | Endpoint / process | ❌ |
| Transborder flows | S.72 | ML endpoint in SA or consent | Lead Eng | PIA §6 | ⚠️ |

---

## 2. ISO/IEC 27001:2022 Annex A

| Control Domain | Control | Annex A Ref | Implementation | Status |
|----------------|---------|------------|----------------|--------|
| Information security policies | Policy document | A.5.1 | SecPlan, CSD | ✅ |
| Access control | AAD RBAC | A.5.15 | APIM JWT, RBAC | ⚠️ |
| User authentication | JWT Bearer | A.5.17 | APIM policy | ✅ |
| Cryptography | AES-256 at rest, TLS in transit | A.8.24 | SecAD §4.3 | ✅ |
| Physical security | Azure datacentre | A.7.1 | Azure SLA | ✅ |
| Operations security | Monitoring, patch mgmt | A.8.8 | OpsMan, CI/CD | ⚠️ |
| Network security | VNet, NSG, TLS | A.8.20 | infrastructure/main.tf | ✅ |
| Secure development | SAST, code review | A.8.28 | CSD, CI/CD | ⚠️ |
| Vulnerability mgmt | Trivy, pip-audit, bandit | A.8.8 | CI/CD (Phase 3) | ⚠️ |
| Incident management | IRP document | A.5.26 | IRP.md | ✅ |
| Business continuity | DRP | A.5.29 | DRP.md | ✅ |
| Compliance | Legal obligations tracking | A.5.36 | This matrix | ⚠️ |
| Audit logging | APIM EventHub + AppInsights | A.8.15 | policy.xml | ⚠️ |
| Supplier relationships | Microsoft Azure BAA | A.5.19 | Azure portal | ✅ |

---

## 3. Azure Government / South African Sovereignty

| Requirement | Control | Status |
|-------------|---------|--------|
| Data residency in SA | Primary region: `southafricanorth` | ✅ |
| Disaster recovery region | `eastus` (required consent for SA data) | ⚠️ |
| Azure Government SLA | Standard_1 APIM in production | ⚠️ (Phase 5) |
| Compliance certification | Azure compliance portal evidence | ⬜ |

---

## 4. Summary Dashboard

| Framework | Total Controls | Compliant | Partial | Non-compliant | Not Assessed |
|-----------|---------------|-----------|---------|---------------|--------------|
| POPIA | 10 | 4 | 3 | 1 | 2 |
| ISO 27001 Annex A | 14 | 6 | 6 | 0 | 2 |
| Azure Sovereignty | 4 | 2 | 1 | 0 | 1 |
| **TOTAL** | **28** | **12** | **10** | **1** | **5** |

**Overall compliance readiness: 43% fully compliant — ATO not yet achievable.**  
Target: 100% Compliant or Partial with accepted residual risk before ATO.

---

## 5. Compliance Remediation Roadmap

| Priority | Item | Owner | Target |
|----------|------|-------|--------|
| P0 | Appoint Information Officer (POPIA S.8) | DBE Legal | Phase 5 |
| P0 | Fix POPIA S.23 data subject access | Lead Eng | Phase 5 |
| P1 | PII scrubbing middleware (POPIA S.19) | Lead Eng | Phase 3 |
| P1 | FastAPI RBAC / OAuth2 middleware | Lead Eng | Phase 3 |
| P1 | SAST + image scanning in CI/CD | DevOps | Phase 3 |
| P2 | Publish privacy notice (POPIA S.17) | DBE Legal | Phase 5 |
| P2 | ML endpoint region confirmation | Lead Eng | Phase 3 |
| P3 | Azure compliance evidence collection | DevOps | Phase 5 |

---

*End of Compliance Matrix — DBE-CM-032 v1.0.0*
