# Incident Response Plan (IRP)
**Document ID:** DBE-IRP-033  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** RESTRICTED — Operations Sensitive

---

## 1. Incident Severity Classification

| Severity | Criteria | Response SLA | Examples |
|----------|----------|-------------|---------|
| **P1 — Critical** | Production down; data breach; POPIA violation | 15 min acknowledgement; 4 hr resolution | All endpoints returning 5xx; Cosmos key leaked; PII in logs |
| **P2 — High** | Degraded performance; partial outage; security anomaly | 1 hr acknowledgement; 8 hr resolution | p95 > 5s; HPA not scaling; failed login spike |
| **P3 — Medium** | Non-critical functional issue; compliance gap | 4 hr acknowledgement; next sprint | Feedback blob write failing; missing audit log |
| **P4 — Low** | Minor issue; documentation gap | 24 hr acknowledgement; backlog | Wrong version in `/version` endpoint |

---

## 2. Incident Response Phases

### Phase 1 — Detection & Triage (0–15 min)

```
Azure Monitor alert fires
       │
       ▼
On-call engineer acknowledges in PagerDuty
       │
       ├── Classify severity (P1/P2/P3/P4)
       │
       ├── P1: Immediately page DBE IT Director + Security Officer
       │
       └── Open incident ticket in tracking system
```

**Initial triage checklist:**
```bash
# Is the API responding?
curl -sf https://api.dbe-expert.gov.za/health || echo "API DOWN"

# Are pods running?
kubectl get pods -n default

# Any recent deployments?
helm history dbe-agent --namespace default | tail -5

# Any Azure service disruptions?
az resource list --resource-type Microsoft.ContainerService/managedClusters \
  --query "[].provisioningState"
```

---

### Phase 2 — Containment (15 min – 2 hr)

**For data breach / credential leak:**
```bash
# Immediately rotate all affected secrets
az keyvault secret set --vault-name kv-dbe-prod \
  --name cosmos-key --value "<NEW_KEY>"

# Force pod restart to invalidate cached secrets
kubectl rollout restart deployment/dbe-agent-dbe-agent-orchestrator

# Revoke compromised Azure credentials
az ad sp credential reset --id <SERVICE_PRINCIPAL_ID>
```

**For production instability:**
```bash
# Rollback to last known-good release
helm rollback dbe-agent 0 --namespace default --wait

# Verify health
curl -sf https://api.dbe-expert.gov.za/health
```

**For POPIA breach (PII in logs):**
1. Immediately notify DBE Information Officer.
2. Identify scope — run Application Insights query to determine time range and data volume:
   ```kusto
   traces
   | where message matches regex @'\b\d{13}\b'
   | summarize count() by bin(timestamp, 1h)
   ```
3. Purge affected log entries via Azure Monitor data purge API.
4. Begin 72-hour POPIA notification clock (S.22 — must notify IRSA if high risk).

---

### Phase 3 — Eradication & Recovery (2 hr – RTO)

1. Identify and eliminate root cause (patch code, update config, rotate credentials).
2. Re-run CI/CD pipeline to deploy fixed version.
3. Re-run ATP smoke tests (ref: `docs/verification/ATP.md` AC-001, AC-002, AC-003).
4. Confirm from Application Insights that error rate returns to < 1%.

---

### Phase 4 — Post-Incident Review (within 5 business days)

**Post-Incident Report template:**

```markdown
## Post-Incident Report

**Incident ID:** INC-YYYY-NNN
**Date/Time:** YYYY-MM-DD HH:MM SAST
**Duration:** X hours Y minutes
**Severity:** P1 / P2 / P3
**Systems Affected:** [list]

### Timeline
| Time | Event |
|------|-------|
| HH:MM | Alert fired |
| HH:MM | On-call acknowledged |
| HH:MM | Root cause identified |
| HH:MM | Fix deployed |
| HH:MM | Service restored |

### Root Cause
[Concise technical description]

### Impact
[Users affected, data impacted, SLA breach?]

### Immediate Corrective Actions
[What was done to restore service]

### Long-term Preventive Actions
[TODO items to prevent recurrence — add to docs/TODO.md]

### Lessons Learned
[What would we do differently?]
```

---

## 3. Escalation Matrix

| Time Since P1 Alert | Action | Contact |
|--------------------|--------|---------|
| 0 min | On-call engineer responds | PagerDuty primary |
| 15 min (no ack) | Escalate to backup on-call | PagerDuty secondary |
| 30 min (unresolved) | Notify DBE IT Director | Direct call |
| 60 min (unresolved) | Notify DBE CIO | Email + call |
| 4 hr (unresolved) | Invoke DRP | DRP lead |
| 72 hr (data breach) | Notify IRSA (POPIA S.22) | DBE Information Officer → IRSA |

---

## 4. Incident Log

| Incident ID | Date | Severity | Description | Resolution | PIR Complete |
|-------------|------|----------|-------------|------------|--------------|
| *(No incidents recorded)* | | | | | |

---

*End of IRP — DBE-IRP-033 v1.0.0*
