# Stakeholder Requirements Definition (StRS)
**Document ID:** DBE-StRS-004  
**Version:** 1.0.0  
**Date:** 2026-04-29

---

## 1. Stakeholder Register

| ID | Stakeholder | Role | Interest Level | Influence |
|----|------------|------|---------------|-----------|
| SH-01 | DBE Policy Division | Primary user | High | High |
| SH-02 | DBE IT Operations | System owner | High | High |
| SH-03 | District Officials | End users | High | Medium |
| SH-04 | School Principals | End users | Medium | Low |
| SH-05 | DBE Data Engineering | Technical | High | Medium |
| SH-06 | DBE ML Engineering | Technical | High | Medium |
| SH-07 | DBE Legal & Compliance | Governance | Medium | High |
| SH-08 | SITA (State IT Agency) | Infrastructure | Low | Medium |
| SH-09 | DBE Auditors | Oversight | Low | High |

---

## 2. Stakeholder Needs

### SH-01 — Policy Division

| Need ID | Description | Priority |
|---------|-------------|----------|
| SN-01-01 | Query the system in plain language without technical training | Must |
| SN-01-02 | Receive responses with source document citations | Must |
| SN-01-03 | Trust that responses are based on current, approved documents | Must |
| SN-01-04 | Flag incorrect or outdated responses for review | Should |

### SH-02 — IT Operations

| Need ID | Description | Priority |
|---------|-------------|----------|
| SN-02-01 | Deploy, update, and roll back the system without downtime | Must |
| SN-02-02 | Monitor system health via a single dashboard | Must |
| SN-02-03 | Receive alerts when error rates or latency exceed thresholds | Must |
| SN-02-04 | All secrets managed in Azure Key Vault — no manual credential handling | Must |

### SH-07 — Legal & Compliance

| Need ID | Description | Priority |
|---------|-------------|----------|
| SN-07-01 | All personal data processing compliant with POPIA | Must |
| SN-07-02 | Complete audit trail of all system actions | Must |
| SN-07-03 | No learner PII stored in query logs | Must |
| SN-07-04 | Data residency within South African Azure regions | Must |

### SH-09 — Auditors

| Need ID | Description | Priority |
|---------|-------------|----------|
| SN-09-01 | Access to immutable audit logs for any date range | Must |
| SN-09-02 | Evidence of security controls implementation | Must |
| SN-09-03 | Signed Authority to Operate (ATO) before production | Must |

---

## 3. Needs-to-Requirements Mapping

| Stakeholder Need | Derived SRS Requirement |
|-----------------|------------------------|
| SN-01-01 | FR-030, FR-032 |
| SN-01-02 | FR-032 (sources field), FR-031 |
| SN-01-03 | FR-001, FR-010, FR-014 |
| SN-02-01 | NFR-010, NFR-012, Deployment Guide |
| SN-02-02 | NFR monitoring requirements, OpsMan |
| SN-02-03 | Azure Monitor alert rules (Phase 3) |
| SN-07-01 | CR-001, CR-002, PIA |
| SN-07-03 | CR-001, SR-007 |
| SN-09-01 | APIM EventHub logging, SR-007 |
| SN-09-03 | ATO document |

---

*End of StRS — DBE-StRS-004 v1.0.0*
