# Operations Manual (OpsMan)
**Document ID:** DBE-OpsMan-025  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** Internal — Controlled

---

## 1. System Overview

| Component | URL / Resource | Health Indicator |
|-----------|---------------|-----------------|
| API (via APIM) | `https://api.dbe-expert.gov.za` | `GET /health → 200` |
| AKS Cluster | `aks-dbe-expert-{env}` | Pod status `Running` |
| Cosmos DB | `cosmos-dbe-expert-{env}` | Azure portal metrics |
| Azure ML | `mlw-dbe-{env}` | Endpoint status `Healthy` |
| Application Insights | `appi-dbe-{env}` | Live Metrics stream |

**Operations Dashboard:** `https://portal.azure.com/#dashboard/dbe-expert-{env}`

---

## 2. Daily Health Checks

Run each morning before business hours (08:00 SAST):

```bash
# 1. API health
curl -sf https://api.dbe-expert.gov.za/health | grep healthy && echo "API OK"

# 2. Pod status
kubectl get pods -n default -l app.kubernetes.io/name=dbe-agent-orchestrator

# 3. Check recent error rate in Application Insights (last 1 hour)
az monitor app-insights query \
  --app appi-dbe-prod \
  --analytics-query "requests | where timestamp > ago(1h) | summarize errorRate = countif(resultCode >= 500) * 100.0 / count()"

# 4. Check Cosmos DB throttling (429s)
az cosmosdb show --name cosmos-dbe-expert-prod \
  --resource-group rg-dbe-ai-expert-system \
  --query "documentEndpoint"
```

---

## 3. Alert Triage Runbook

### ALERT: High 5xx Error Rate

**Trigger:** HTTP 5xx rate > 1% over 5-minute window.  
**Severity:** P1 — page on-call immediately.

```bash
# Step 1: Check pod health
kubectl get pods -n default
kubectl describe pod <pod-name>

# Step 2: Inspect recent logs (last 50 lines per pod)
kubectl logs -n default -l app.kubernetes.io/name=dbe-agent-orchestrator \
  --tail=50 --all-containers=true

# Step 3: Check Gremlin connectivity
kubectl exec -it <pod-name> -- python -c "
from src.ingestion.graph_manager import KnowledgeGraphManager
import os
m = KnowledgeGraphManager(
  os.environ['COSMOS_GREMLIN_ENDPOINT'],
  os.environ['COSMOS_KEY'],
  'KnowledgeDB', 'ExpertGraph'
)
print('Gremlin OK' if m.health_check() else 'Gremlin FAILED')
"

# Step 4: If Gremlin unreachable — check Cosmos DB service health
az cosmosdb check-name-exists --name cosmos-dbe-expert-prod

# Step 5: If pod crashlooping — rollback
helm rollback dbe-agent 0 --namespace default --wait
```

---

### ALERT: High p95 Latency

**Trigger:** `/ask` p95 > 3 000 ms sustained for 10 minutes.  
**Severity:** P2.

```bash
# Step 1: Check pod CPU/memory
kubectl top pods -n default

# Step 2: Check HPA status
kubectl get hpa -n default
kubectl describe hpa dbe-agent-dbe-agent-orchestrator

# Step 3: Force manual scale if HPA is slow
kubectl scale deployment dbe-agent-dbe-agent-orchestrator \
  --replicas=5 -n default

# Step 4: Check Cosmos DB RU consumption
# (View in Azure Portal → Cosmos DB → Metrics → Total Request Units)

# Step 5: Flush Redis cache if applicable (Phase 4)
# redis-cli FLUSHDB
```

---

### ALERT: Feedback Blob Write Failures

**Trigger:** Any `BlobServiceError` in Application Insights.  
**Severity:** P2.

```bash
# Check storage account status
az storage account show \
  --name stdbeexpertprod \
  --resource-group rg-dbe-ai-expert-system \
  --query "statusOfPrimary"

# Verify connection string secret in Key Vault
az keyvault secret show \
  --vault-name kv-dbe-prod \
  --name storage-connection-string \
  --query "value" -o tsv | grep -c "AccountKey"
```

---

### ALERT: Low Feedback Rating Average

**Trigger:** Average `rating` < 3.0 over rolling 24 hours (Application Insights custom metric).  
**Severity:** P3 — notify ML Engineer.

**Action:** Review feedback blobs in storage container, identify query patterns, escalate to ML team for model inspection.

---

## 4. Log Query Reference

**Application Insights — Kusto queries:**

```kusto
// Recent errors with stack traces
exceptions
| where timestamp > ago(1h)
| order by timestamp desc
| project timestamp, type, outerMessage, details

// Request latency distribution
requests
| where timestamp > ago(1h)
| summarize
    p50 = percentile(duration, 50),
    p95 = percentile(duration, 95),
    p99 = percentile(duration, 99)
  by name

// Failed feedback writes
traces
| where message contains "Failed to save feedback blob"
| project timestamp, message, severityLevel

// Gremlin retry events
traces
| where message contains "Gremlin" and severityLevel >= 2
| order by timestamp desc
```

---

## 5. Routine Maintenance Tasks

| Task | Frequency | Procedure |
|------|-----------|-----------|
| Rotate Cosmos DB keys | Quarterly | Update Key Vault secret; restart pods via rolling update |
| Update base Docker image | Monthly | Rebuild on latest `python:3.10-slim`; push to ACR; deploy |
| Review feedback blobs | Weekly | Spot-check 10 blobs for anomalies |
| Review Azure Monitor alerts | Monthly | Tune thresholds based on observed baselines |
| Cosmos DB index review | Quarterly | Run `az cosmosdb sql container show` and compare against DDD |
| AKS node pool update | Per Azure advisory | `az aks nodepool upgrade` during maintenance window |

---

## 6. Capacity Planning Indicators

Scale up Cosmos DB throughput (increase RU/s) when:
- Cosmos DB metric `NormalizedRUConsumption` consistently > 70%.
- Gremlin p95 latency rising above 300 ms.

Scale up AKS node pool when:
- `kubectl top nodes` shows CPU > 80% on majority of nodes for > 30 minutes.
- HPA is at `maxReplicas` and latency is degrading.

---

*End of OpsMan — DBE-OpsMan-025 v1.0.0*
