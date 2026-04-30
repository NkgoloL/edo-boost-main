# Authority to Operate (ATO)
**Document ID:** DBE-ATO-034  
**Version:** 0.1.0 (DRAFT — Pending Completion)  
**Date:** 2026-04-29  
**Classification:** RESTRICTED — Executive

---

## 1. System Identification

| Field | Value |
|-------|-------|
| System Name | DBE AI Expert System |
| Document ID | DBE-ATO-034 |
| Owning Department | Department of Basic Education — IT Division |
| System Custodian | DBE IT Director |
| Environment | Production (`aks-dbe-expert-prod`) |
| Data Classification | Official (non-secret), POPIA-bearing |

---

## 2. ATO Preconditions Checklist

All items below must be resolved before this ATO may be signed. Current status reflects Phase 2 baseline.

### Security Preconditions

| # | Precondition | Evidence Required | Status |
|---|-------------|------------------|--------|
| SEC-01 | Gremlin injection vulnerability resolved | `docs/design/SecAD.md` §4.1; code review | ✅ |
| SEC-02 | FastAPI OAuth2 authentication middleware deployed | Code + integration test | ❌ |
| SEC-03 | `{{client-id}}` replaced with Key Vault Named Value in APIM | Terraform `azurerm_api_management_named_value` | ❌ |
| SEC-04 | PII scrubbing middleware deployed and verified via AC-013 | ATR sign-off | ❌ |
| SEC-05 | All secrets in Key Vault — no plaintext in code/images/values | Trufflehog scan report | ❌ |
| SEC-06 | Container image vulnerability scan — zero CRITICAL CVEs | Trivy scan report | ❌ |
| SEC-07 | Network policies restricting pod ingress/egress deployed | `kubectl get networkpolicies` | ❌ |
| SEC-08 | Penetration test completed — no unresolved critical findings | External pentest report | ❌ |
| SEC-09 | `localhost:3000` CORS origin removed from APIM policy | Code review | ❌ |
| SEC-10 | `purge_protection_enabled = true` on production Key Vault | Terraform plan + `az keyvault show` | ❌ |

### Compliance Preconditions

| # | Precondition | Evidence Required | Status |
|---|-------------|------------------|--------|
| COMP-01 | PIA signed by Information Officer | Signed `docs/security/PIA.md` | ❌ |
| COMP-02 | Privacy notice published to all users | URL | ❌ |
| COMP-03 | Information Officer appointed | DBE appointment letter | ❌ |
| COMP-04 | Data subject access/erasure mechanism | Endpoint or documented process | ❌ |
| COMP-05 | Azure ML endpoint confirmed in `southafricanorth` | Azure portal screenshot | ❌ |
| COMP-06 | Compliance scripts executed and findings resolved | `scripts/compliance_checks.ps1` output | ❌ |
| COMP-07 | Security audit scripts executed and findings resolved | `scripts/security_audit.ps1` output | ❌ |

### Operational Preconditions

| # | Precondition | Evidence Required | Status |
|---|-------------|------------------|--------|
| OPS-01 | Acceptance Test Procedure (ATP) fully passed | Signed `docs/verification/ATP.md` | ❌ |
| OPS-02 | SLA monitoring active (Azure Monitor alerts) | Alert rule screenshots | ❌ |
| OPS-03 | DRP tested — RTO validated | DRP test report | ❌ |
| OPS-04 | Deployment runbook reviewed by operations team | Signed `docs/operations/Deployment_Guide.md` | ❌ |
| OPS-05 | Cosmos DB second geo-location configured | Terraform output | ❌ |
| OPS-06 | APIM SKU upgraded to `Standard_1` | Terraform plan | ❌ |
| OPS-07 | CI/CD pipeline fully operational (build, test, deploy) | GitHub Actions green badge | ❌ |

---

## 3. Risk Acceptance Statement

By signing this ATO, the authorising officials acknowledge the following residual risks:

| Risk | Residual Level | Accepted By |
|------|---------------|-------------|
| Single Azure region deployment (DR-05) | Medium | *TBD* |
| In-memory keyword search for graph (Phase 4 replacement) | Low | *TBD* |
| 90-day feedback retention (may need extension) | Low | *TBD* |

---

## 4. ATO Decision

| Decision | ☐ AUTHORISED TO OPERATE |
|----------|------------------------|
| | ☐ INTERIM AUTHORISATION (conditions attached) |
| | ☐ DENIED — remediation required |

**Conditions (if Interim):**  
_[List any conditions under which interim operation is permitted]_

**Authorisation Period:** 12 months from signature date, with 6-month security review.

---

## 5. Signatures

| Role | Name | Signature | Date |
|------|------|-----------|------|
| DBE IT Director (System Owner) | | | |
| DBE Information Officer (POPIA) | | | |
| DBE IT Security Officer | | | |
| QA Lead (ATP witness) | | | |

---

**Current Status: ❌ NOT AUTHORISED — 24 of 24 preconditions outstanding.**  
**Target ATO Date:** Phase 5 completion (~Week 10 of roadmap)

---

*End of ATO — DBE-ATO-034 v0.1.0 (Draft)*
