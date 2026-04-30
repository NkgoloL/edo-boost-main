# Risk Register (RR)
**Document ID:** DBE-RR-036  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** Internal — Controlled

---

## Risk Rating Matrix

| Probability \ Impact | Low (1) | Medium (2) | High (3) | Critical (4) |
|---------------------|---------|-----------|---------|-------------|
| High (3) | 3 — Medium | 6 — High | 9 — Critical | 12 — Critical |
| Medium (2) | 2 — Low | 4 — Medium | 6 — High | 8 — Critical |
| Low (1) | 1 — Low | 2 — Low | 3 — Medium | 4 — Medium |

---

## Active Risks

### Technical Risks

| ID | Risk | Probability | Impact | Rating | Mitigation | Owner | Status |
|----|------|------------|--------|--------|------------|-------|--------|
| TR-01 | Cosmos DB Gremlin quota exhaustion during load tests | Medium | High | **6 — High** | Use emulator in CI; reserve quota for staging | DevOps | Open |
| TR-02 | `pydantic-settings` breaking change in future minor version | Low | Medium | **2 — Low** | Pin version in `requirements.txt`; dependabot alerts | Lead Eng | Open |
| TR-03 | Azure ML cold-start latency exceeds `/ask` 2s SRS target | Medium | High | **6 — High** | Warm-up probe; Redis cache for repeat queries (Phase 4) | ML Eng | Open |
| TR-04 | Gremlin keyword scan too slow at 100k+ documents | Medium | High | **6 — High** | Azure Cognitive Search integration planned Phase 4 | Lead Eng | Open |
| TR-05 | AKS node pool version falls behind Kubernetes supported window | Low | Medium | **2 — Low** | Azure Monitor advisory alerts; quarterly node pool upgrade | DevOps | Open |
| TR-06 | Azure ML model regression after automated retraining | Medium | High | **6 — High** | Model evaluation gate before promotion; lineage tracker | ML Eng | Open |
| TR-07 | WebSocket Gremlin connection drops under sustained load | Medium | High | **6 — High** | Tenacity retry (3 attempts); connection pool_size=4 | Lead Eng | Mitigated |

### Security Risks

| ID | Risk | Probability | Impact | Rating | Mitigation | Owner | Status |
|----|------|------------|--------|--------|------------|-------|--------|
| SR-01 | FastAPI endpoints bypassed (no auth middleware yet) | Medium | Critical | **8 — Critical** | OAuth2 middleware — Phase 3 priority | Lead Eng | Open |
| SR-02 | Accidental secret commit to git | Low | Critical | **4 — Medium** | `.gitignore`, trufflehog pre-commit; Key Vault only | DevOps | Open |
| SR-03 | APIM `{{client-id}}` placeholder shipped to production | Medium | High | **6 — High** | Terraform Named Value; pre-deploy checklist | DevOps | Open |
| SR-04 | PII in Application Insights logs (POPIA S.19) | Medium | Critical | **8 — Critical** | PII scrubbing middleware — Phase 3 priority | Lead Eng | Open |

### Compliance Risks

| ID | Risk | Probability | Impact | Rating | Mitigation | Owner | Status |
|----|------|------------|--------|--------|------------|-------|--------|
| CR-01 | POPIA Information Officer not appointed before launch | High | High | **9 — Critical** | Engage DBE Legal immediately; ATO gate | DBE Legal | Open |
| CR-02 | Azure ML data routed to East US (transborder flow) | Medium | High | **6 — High** | Deploy ML endpoint in `southafricanorth` | ML Eng | Open |
| CR-03 | Privacy notice not published before go-live | High | Medium | **6 — High** | Block production deploy without notice URL | DBE Legal | Open |

### Project / Schedule Risks

| ID | Risk | Probability | Impact | Rating | Mitigation | Owner | Status |
|----|------|------------|--------|--------|------------|-------|--------|
| PR-01 | Azure subscription quota insufficient for staging | Medium | High | **6 — High** | Request quota increases 2 weeks ahead of Phase 3 | DevOps | Open |
| PR-02 | Penetration test vendor unavailable for Phase 5 slot | Medium | High | **6 — High** | Engage vendor at Phase 3 start (6-week lead time) | Security | Open |
| PR-03 | 80% coverage target unachievable without real Cosmos DB | Medium | Medium | **4 — Medium** | Cosmos DB emulator in CI (Phase 3) | DevOps | Open |
| PR-04 | Key developer unavailable during critical Phase 3 sprint | Low | High | **3 — Medium** | Knowledge transfer sessions; bus factor documentation | PM | Open |

---

## Closed Risks

| ID | Risk | Closure Reason | Date Closed |
|----|------|---------------|-------------|
| TR-08 | Gremlin injection vector in `add_document_node()` | Fixed — parameterised bindings implemented | 2026-04-29 |
| TR-09 | `BaseSettings` import failure on Pydantic v2 | Fixed — `pydantic-settings` added | 2026-04-29 |

---

## Risk Review Schedule

| Review | Frequency | Attendees |
|--------|-----------|---------|
| Risk register update | Per sprint | PM + Lead Eng |
| Critical risk escalation | Immediately | PM + IT Director |
| Full risk review | Per phase | All team leads |

---

*End of RR — DBE-RR-036 v1.0.0*
