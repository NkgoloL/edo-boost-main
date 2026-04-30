# Security Architecture Document (SecAD)
**Document ID:** DBE-SecAD-012  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** RESTRICTED — Security Sensitive

---

## 1. Security Architecture Overview

The DBE AI Expert System employs a **defence-in-depth** security model with five concentric security layers:

```
Layer 5 (Outermost): Network Perimeter (VNet, NSG, TLS)
Layer 4:             API Gateway (APIM JWT, Rate Limiting, CORS)
Layer 3:             Application (FastAPI Auth Middleware, Input Validation)
Layer 2:             Data (Gremlin Parameterisation, Cosmos Encryption, Key Vault)
Layer 1 (Innermost): Execution (Non-root containers, ReadOnlyRootFS, Pod Security)
```

---

## 2. Threat Model Summary

Full threat model in `docs/security/TMD.md`. Key identified threats:

| Threat | Category | STRIDE | Current Mitigation | Status |
|--------|----------|--------|--------------------|--------|
| Gremlin query injection | Tampering | T | Parameterised bindings (ADR-004) | ✅ Mitigated |
| Unauthenticated API access | Spoofing | S | APIM JWT + FastAPI middleware | ⚠️ Partial (FastAPI auth pending) |
| Credential leakage | Info Disclosure | I | Key Vault, gitignore | ✅ Mitigated |
| DoS via query flooding | Denial of Service | D | APIM rate limiting (1000/60s) | ✅ Mitigated |
| Privilege escalation in pod | Elevation | E | Non-root, readOnlyRootFS | ✅ Mitigated |
| Data exfiltration via logs | Info Disclosure | I | PII scrubbing in log pipeline | ⚠️ Pending |

---

## 3. Authentication & Authorisation Architecture

### 3.1 APIM Layer (External Boundary)

```xml
<validate-jwt header-name="Authorization" ...>
    <openid-config url="https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration" />
    <required-claims>
        <claim name="aud"><value>{{client-id}}</value></claim>
    </required-claims>
</validate-jwt>
```

- Token issuer: Azure Active Directory
- Required claim: `aud` must match the registered application client ID (stored in Key Vault Named Value)
- Invalid tokens: HTTP 401 returned before request reaches AKS

### 3.2 FastAPI Layer (Internal Defence)

**Required implementation (Phase 3):**
```python
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

@app.post("/ask", dependencies=[Depends(verify_token)])
async def ask_agent(request: QueryRequest): ...
```

---

## 4. Data Security

### 4.1 Gremlin Injection Prevention

**Vulnerable pattern (prohibited):**
```python
query = f"g.addV('Document').property('id', '{doc_id}')"  # INJECTION RISK
```

**Secure pattern (required):**
```python
query = "g.addV('Document').property('id', id_val)"
self._submit(query, {"id_val": doc_id})  # Binding — never interpolated
```

### 4.2 Secrets Management Architecture

```
┌────────────────────────────────────┐
│           Azure Key Vault          │
│  cosmos-endpoint   cosmos-key      │
│  azure-ml-endpoint azure-ml-key    │
│  storage-connection jwt-secret     │
└──────────────┬─────────────────────┘
               │ CSI Driver
               ▼
┌────────────────────────────────────┐
│    AKS Pod (SecretProviderClass)   │
│  Mounts secrets as env vars        │
│  No secrets in container image     │
│  No secrets in Helm values         │
└────────────────────────────────────┘
```

### 4.3 Encryption Standards

| Data State | Mechanism | Standard |
|------------|-----------|----------|
| At rest (Cosmos DB) | Azure-managed keys | AES-256 |
| At rest (Blob Storage) | Azure-managed keys | AES-256 |
| In transit (all) | TLS 1.2 minimum | TLS 1.2+ |
| In transit (internal AKS) | mTLS (future: Istio) | TLS 1.3 |

---

## 5. Network Security Architecture

```
Internet ──► APIM (public IP) ──► VNet Peering ──► AKS (private)
                                                     │
NSG Rules:                                           ▼
  Inbound 443: Allow from *                     Cosmos DB (private endpoint)
  Inbound 22:  DENY from *                      Blob Storage (private endpoint)
  Inbound 3389: DENY from *                     Key Vault (private endpoint)
```

**NetworkPolicy (Kubernetes):**
- Ingress: Only from APIM subnet CIDR
- Egress: Only to Cosmos DB, Blob Storage, Azure ML, Key Vault endpoints

---

## 6. Security Headers

Applied by APIM `policy.xml`:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `DENY` | Clickjacking prevention |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS filter |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | HSTS |
| `Content-Security-Policy` | `default-src 'self'` | CSP |
| `Cache-Control` | `no-cache, max-age=3600` | Cache control |

---

## 7. Container Security Baseline

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: [ALL]
```

Writable paths: `/tmp` only (tmpfs emptyDir volume mount).

---

## 8. Compliance Mapping (ISO 27001 Annex A)

| Control | Annex A Ref | Implementation |
|---------|------------|----------------|
| Access Control | A.9 | APIM JWT + AAD |
| Cryptography | A.10 | AES-256 at rest, TLS in transit |
| Physical Security | A.11 | Azure datacenter (out of scope) |
| Operations Security | A.12 | Azure Monitor + alert rules |
| Communications Security | A.13 | TLS, VNet, NSG, Private Endpoints |
| System Acquisition | A.14 | Parameterised queries, input validation |
| Supplier Relationships | A.15 | Microsoft Azure BAA |
| Incident Management | A.16 | IRP document |
| Audit Logging | A.12.4 | APIM EventHub, App Insights |

---

*End of SecAD — DBE-SecAD-012 v1.0.0*
