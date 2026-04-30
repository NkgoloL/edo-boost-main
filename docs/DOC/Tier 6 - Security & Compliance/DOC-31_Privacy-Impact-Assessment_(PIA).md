# Privacy Impact Assessment (PIA)
**Document ID:** DBE-PIA-031  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** RESTRICTED — Compliance Sensitive  
**Regulatory Basis:** POPIA Act No. 4 of 2013 (South Africa)

---

## 1. Purpose and Scope

This PIA assesses the privacy risks associated with the DBE AI Expert System, identifies personal information processing activities, evaluates compliance with POPIA, and specifies required controls before the system may be deployed to production.

**Scope:** All data flows involving personal information within or passing through the DBE AI Expert System, including query inputs, feedback data, API logs, and telemetry.

---

## 2. Personal Information Inventory

| Data Category | Description | Collected? | Stored? | Shared? | POPIA Basis |
|---------------|-------------|-----------|---------|---------|-------------|
| User queries | Natural-language policy questions | Yes | No (transient) | No | Legitimate interest |
| `user_id` field | Analyst identifier in `/ask` payload | Yes | No (logged to AppInsights) | No | Legitimate interest |
| Feedback content | Query + response text | Yes | Yes (Blob 90 days) | No | Legitimate interest |
| Learner PII (incidental) | SA ID numbers, names in queries | Possible | Must NOT be | Never | N/A — must be scrubbed |
| API access logs | IP address, JWT claims (name/email) | Yes | Yes (APIM EventHub) | No | Legal obligation |
| Azure AD identity | Logged-in user identity | Yes | Yes (Azure AD) | No | Contract |

---

## 3. Privacy Risks

| Risk ID | Description | Likelihood | Impact | POPIA Section |
|---------|-------------|------------|--------|---------------|
| PR-01 | Learner SA ID number captured in query logs | Medium | Critical | S.19 (Security safeguards) |
| PR-02 | Feedback blobs containing PII retained beyond 90 days | Low | High | S.14 (Retention limitation) |
| PR-03 | API logs with `user_id` accessible to unauthorised Azure users | Low | High | S.19 |
| PR-04 | Query content routed to Azure ML (US East region) outside SA | Medium | High | S.72 (Transborder flows) |
| PR-05 | No data subject access/erasure mechanism | High | Medium | S.23–24 (Data subject rights) |
| PR-06 | No consent mechanism for query data use in ML retraining | High | High | S.11 (Consent) |

---

## 4. Compliance Controls

### POPIA Section Mapping

| POPIA Condition | Section | Control Required | Status |
|----------------|---------|-----------------|--------|
| Accountability | S.8 | Designated Information Officer | ⚠️ Appoint before launch |
| Processing limitation | S.9–10 | Query data used only for advisory; not sold | ✅ By design |
| Purpose specification | S.13 | Privacy notice to users | ⚠️ Required |
| Further processing limitation | S.15 | Feedback used only for model improvement | ✅ By design |
| Information quality | S.16 | Policy documents validated before ingestion | ✅ Pipeline validation |
| Openness | S.17–18 | Privacy Policy published | ⚠️ Required |
| Security safeguards | S.19 | Encryption, access control, PII scrubbing | ⚠️ Partial |
| Data subject participation | S.23–24 | Access/erasure endpoint | ⚠️ Not implemented |

---

## 5. PII Scrubbing Requirement

Before production launch, the following middleware must be implemented:

```python
import re

# Patterns for South African PII
SA_ID_PATTERN = re.compile(r'\b\d{13}\b')
SA_PHONE_PATTERN = re.compile(r'\b0[6-8]\d{8}\b')
SA_EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

def scrub_pii(text: str) -> str:
    """Remove South African PII patterns from log entries."""
    text = SA_ID_PATTERN.sub('[ID-REDACTED]', text)
    text = SA_PHONE_PATTERN.sub('[PHONE-REDACTED]', text)
    text = SA_EMAIL_PATTERN.sub('[EMAIL-REDACTED]', text)
    return text
```

This must be applied to:
- All Application Insights log entries containing user query content.
- Feedback blob content before storage (or at retrieval time).
- APIM EventHub log entries.

---

## 6. Transborder Data Flow Analysis

| Flow | Origin | Destination | Personal Data Involved | POPIA S.72 Risk |
|------|--------|-------------|----------------------|-----------------|
| Query → Azure ML | SA North | East US (if ML endpoint in US) | Query text (possible PII) | High |
| Feedback blobs | SA North | SA North only | Feedback text | None |
| API logs | SA North | SA North (EventHub) | IP + user_id | None |

**Required control for ML endpoint:** Either deploy Azure ML endpoint in `southafricanorth`, or obtain explicit consent for cross-border data transfer per POPIA S.72(1)(a).

---

## 7. Data Retention Policy

| Data | Retention Period | Deletion Mechanism |
|------|-----------------|-------------------|
| Query requests | Not stored (transient) | N/A |
| Feedback blobs | 90 days | Azure Blob lifecycle management rule |
| API logs (APIM EventHub) | 90 days | EventHub retention policy |
| Application Insights telemetry | 90 days | Workspace retention setting |
| Azure AD access logs | 30 days | Azure AD default |

---

## 8. PIA Sign-Off Gate

**This PIA must be reviewed and signed before production deployment.**

| Role | Name | Decision | Date |
|------|------|----------|------|
| Information Officer | *TBD — DBE Legal* | ☐ Approved ☐ Rejected | |
| DBE IT Security Officer | *TBD* | ☐ Approved ☐ Rejected | |
| Lead Engineer | *TBD* | ☐ Approved ☐ Rejected | |

**Open Items blocking sign-off:**
- [ ] PR-01: PII scrubbing middleware deployed and tested (AC-013 in ATP).
- [ ] PR-04: Azure ML endpoint region confirmed as `southafricanorth` or consent obtained.
- [ ] PR-05: Data subject access/erasure endpoint implemented or process documented.
- [ ] PR-06: Privacy notice published to all users.

---

*End of PIA — DBE-PIA-031 v1.0.0*
