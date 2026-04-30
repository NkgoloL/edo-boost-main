# Security Plan (SecPlan)
**Document ID:** DBE-SecPlan-029  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** RESTRICTED — Security Sensitive

---

## Document Control

| Field | Detail |
|-------|--------|
| Prepared By | DBE AI Expert System Security Team |
| Authority | DBE IT Security Officer |
| Review Cycle | Annually or after any security incident |
| Based On | ISO/IEC 27001:2022, NIST CSF |

---

## 1. Security Objectives

1. Protect the confidentiality of DBE policy documents and user query data.
2. Ensure the integrity of the knowledge graph — no unauthorised modifications.
3. Maintain availability of the `/ask` endpoint to meet NFR-010 (99.9% uptime).
4. Achieve and maintain POPIA compliance.
5. Attain Authority to Operate (ATO) sign-off before production launch.

---

## 2. Security Controls by Domain

### 2.1 Identity and Access Management

| Control | Implementation | Status |
|---------|---------------|--------|
| External API authentication | APIM JWT validation (Azure AD) | ✅ Implemented |
| Internal API authentication | FastAPI OAuth2 middleware | ⚠️ Phase 3 pending |
| Service identity | AKS Managed Identity (SystemAssigned) | ✅ Implemented |
| Role-based access | RBAC on Cosmos DB, Storage, ML (via `azurerm_role_assignment`) | ⚠️ Phase 3 pending |
| Multi-factor authentication | Azure AD MFA for portal access | ✅ Azure AD default |
| Privileged access | Azure PIM for Contributor role | ⚠️ Recommended |

### 2.2 Data Protection

| Control | Implementation | Status |
|---------|---------------|--------|
| Encryption at rest | Azure-managed keys (AES-256) — Cosmos DB, Blob | ✅ Default |
| Encryption in transit | TLS 1.2+ on all connections | ✅ Enforced |
| Secret management | Azure Key Vault (all credentials) | ✅ Implemented |
| Gremlin injection prevention | Parameterised query bindings | ✅ Implemented |
| Input validation | Pydantic models on all endpoints | ✅ Implemented |
| PII scrubbing in logs | Structured logging with PII filter | ⚠️ Phase 3 pending |

### 2.3 Network Security

| Control | Implementation | Status |
|---------|---------------|--------|
| Network isolation | Azure VNet + private subnets | ✅ Implemented |
| NSG rules | Allow 443 inbound; deny 22/3389 | ✅ Implemented |
| Private endpoints | Cosmos DB, Storage, Key Vault | ⚠️ Phase 3 pending |
| Rate limiting | APIM: 1000 req/60s per IP | ✅ Implemented |
| DDoS protection | Azure DDoS Basic (Standard for prod) | ⚠️ Production gap |

### 2.4 Container and Workload Security

| Control | Implementation | Status |
|---------|---------------|--------|
| Non-root execution | `runAsUser: 1000` in pod spec | ✅ Implemented |
| Read-only root filesystem | `readOnlyRootFilesystem: true` | ✅ Implemented |
| Capability drop | `drop: [ALL]` | ✅ Implemented |
| Image vulnerability scan | Trivy in CI/CD (Phase 3) | ⚠️ Phase 3 pending |
| Network policies | Ingress/egress rules in Helm | ⚠️ Manifest missing |
| Image signing | Azure Container Registry content trust | ⚠️ Phase 5 |

### 2.5 Monitoring and Audit

| Control | Implementation | Status |
|---------|---------------|--------|
| API request logging | APIM EventHub logger | ✅ Implemented |
| Application telemetry | Application Insights | ⚠️ SDK integration Phase 3 |
| Alert rules | Azure Monitor metric alerts | ⚠️ Phase 3 pending |
| Security audit scripts | `scripts/security_audit.ps1` | ✅ Exists (not yet run) |
| Key Vault diagnostic settings | Audit log to Log Analytics | ⚠️ Phase 3 pending |
| Secrets scanning | Trufflehog / Gitleaks in CI | ⚠️ Phase 3 pending |

---

## 3. Security Testing Schedule

| Activity | When | Owner |
|----------|------|-------|
| SAST scan (`bandit`, `ruff`) | Every CI/CD run | DevOps |
| IaC scan (`checkov`) | Every infrastructure PR | DevOps |
| Dependency audit (`pip-audit`) | Weekly CI run | DevOps |
| Penetration test (external firm) | Phase 5 (before ATO) | Security Officer |
| Compliance script execution | Phase 5 | Security Officer |
| Annual security review | Annually post-launch | Security Officer |

---

## 4. Residual Risks

| Risk | Control Gap | Residual Level | Owner |
|------|-------------|----------------|-------|
| FastAPI endpoints accessible without APIM bypass | OAuth2 middleware pending | Medium | Lead Engineer |
| `{{client-id}}` placeholder in APIM policy | Named Value not yet wired | High | DevOps |
| No private endpoints on Cosmos DB / Storage | Network gap | Medium | DevOps |
| No image signing in ACR | Phase 5 item | Low | DevOps |

**Acceptance Criterion:** All High residual risks resolved before ATO sign-off.

---

*End of SecPlan — DBE-SecPlan-029 v1.0.0*
