# Threat Model Document (TMD)
**Document ID:** DBE-TMD-030  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** RESTRICTED — Security Sensitive  
**Methodology:** STRIDE

---

## 1. System Assets Under Analysis

| Asset | Sensitivity | Impact if Compromised |
|-------|-------------|----------------------|
| DBE policy documents (Cosmos DB) | High | Unauthorised disclosure of unreleased policy |
| Knowledge graph structure | Medium | Manipulation of advisory outputs |
| User query logs | High | PII exposure (POPIA violation) |
| Azure ML model | Medium | Model poisoning via adversarial inputs |
| JWT signing secret | Critical | Full API impersonation |
| Cosmos DB / Storage keys | Critical | Full data exfiltration or destruction |
| Gremlin query execution | High | Graph data tampering via injection |

---

## 2. STRIDE Threat Analysis

### 2.1 Spoofing (Identity)

| Threat ID | Description | Entry Point | Likelihood | Impact | Mitigation |
|-----------|-------------|-------------|------------|--------|------------|
| S-01 | Attacker forges JWT to call `/ask` | APIM | Low | High | APIM validates against Azure AD OIDC; short token TTL (24h) |
| S-02 | Compromised service principal used for Azure resource access | Azure AD | Low | Critical | MFA on all human accounts; PIM for privileged roles |
| S-03 | Pod impersonation within AKS cluster | Internal VNet | Very Low | High | NetworkPolicy restricts pod-to-pod traffic; no service mesh bypass |

### 2.2 Tampering (Integrity)

| Threat ID | Description | Entry Point | Likelihood | Impact | Mitigation |
|-----------|-------------|-------------|------------|--------|------------|
| T-01 | **Gremlin injection** via malicious `query` parameter | `/ask` endpoint | Medium (before fix) | Critical | Parameterised bindings implemented (ADR-004); injection string never reaches Gremlin engine |
| T-02 | Unauthorised Cosmos DB document modification | Azure Portal / SDK | Low | High | RBAC role assignment restricts to authorised identities only |
| T-03 | Docker image tampering in ACR | ACR | Very Low | Critical | Image signing (Phase 5); Trivy scan in CI |
| T-04 | Terraform state tampering | Azure Storage (tfstate) | Low | High | Storage Account soft delete + access key rotation |

### 2.3 Repudiation (Non-repudiation)

| Threat ID | Description | Entry Point | Likelihood | Impact | Mitigation |
|-----------|-------------|-------------|------------|--------|------------|
| R-01 | User denies submitting low-rated feedback | `/feedback` | Low | Medium | APIM EventHub logs request + JWT identity; immutable blob storage |
| R-02 | Admin denies deploying a bad release | AKS | Low | High | Helm history + git commit SHA in `/version` endpoint |

### 2.4 Information Disclosure

| Threat ID | Description | Entry Point | Likelihood | Impact | Mitigation |
|-----------|-------------|-------------|------------|--------|------------|
| I-01 | PII in query logs (POPIA violation) | Application Insights | Medium | Critical | PII scrubbing middleware (Phase 3); POPIA-compliant data handling |
| I-02 | Cosmos DB key exposed via git commit | Source code | Low | Critical | `.gitignore` on `.env`; trufflehog pre-commit hook |
| I-03 | Stack traces in API error responses | `/ask` HTTP 500 | Medium | Low | `HTTPException` wraps internal errors; only `str(e)` surfaced |
| I-04 | Azure ML model weights accessible | Azure ML | Very Low | Medium | Azure ML endpoint key required; private deployment option |

### 2.5 Denial of Service

| Threat ID | Description | Entry Point | Likelihood | Impact | Mitigation |
|-----------|-------------|-------------|------------|--------|------------|
| D-01 | Query flooding exhausting Gremlin RU/s | `/ask` via APIM | Medium | High | APIM rate limiting 1000 req/60s; Cosmos autoscale |
| D-02 | Large query payload consuming memory | `/ask` | Low | Medium | Pydantic `max_length=2000` on `query` field |
| D-03 | Pod OOM kill loop | AKS | Low | High | Memory limit 512Mi; liveness probe restarts pod; HPA scales out |

### 2.6 Elevation of Privilege

| Threat ID | Description | Entry Point | Likelihood | Impact | Mitigation |
|-----------|-------------|-------------|------------|--------|------------|
| E-01 | Container escape to host | AKS node | Very Low | Critical | Non-root (UID 1000), `readOnlyRootFilesystem`, `drop: [ALL]` |
| E-02 | Unrestricted service account token access | AKS | Low | High | Workload Identity (AAD Pod Identity / OIDC) instead of node-level MSI |
| E-03 | Terraform state read grants full infra access | Storage Account | Low | Critical | Storage Account access key restricted to CI/CD service principal only |

---

## 3. Attack Surface Summary

```
Internet
   │
   ▼
[APIM] ── Attack surface: JWT bypass, rate limit bypass
   │
   ▼
[FastAPI] ── Attack surface: Pydantic bypass, missing auth middleware
   │
   ├──► [Gremlin] ── Attack surface: Injection (MITIGATED)
   │
   ├──► [Azure ML] ── Attack surface: Model poisoning
   │
   └──► [Blob Storage] ── Attack surface: Feedback blob exfiltration
```

---

## 4. Priority Remediation Order

| Priority | Threat ID | Action | Phase |
|----------|-----------|--------|-------|
| P0 | T-01 | Gremlin injection — parameterised bindings | ✅ Done |
| P1 | S-01 | FastAPI OAuth2 middleware | Phase 3 |
| P1 | I-01 | PII scrubbing middleware | Phase 3 |
| P1 | S-02 | Replace `{{client-id}}` in APIM policy | Phase 3 |
| P2 | I-02 | Trufflehog pre-commit hook | Phase 3 |
| P2 | T-03 | Trivy image scanning in CI | Phase 3 |
| P3 | E-01 | Validate pod security baseline in staging | Phase 5 |

---

*End of TMD — DBE-TMD-030 v1.0.0*
