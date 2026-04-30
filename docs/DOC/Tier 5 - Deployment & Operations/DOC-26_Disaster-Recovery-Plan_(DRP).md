# Disaster Recovery Plan (DRP)
**Document ID:** DBE-DRP-026  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** RESTRICTED — Operations Sensitive

---

## 1. Recovery Objectives

| Objective | Target | Measurement |
|-----------|--------|-------------|
| Recovery Time Objective (RTO) | 4 hours | Time from incident declaration to service restoration |
| Recovery Point Objective (RPO) | 1 hour | Maximum acceptable data loss |
| Maximum Tolerable Downtime (MTD) | 8 hours | Business tolerance limit |

---

## 2. Disaster Scenarios and Recovery Procedures

### Scenario DR-01 — Single AKS Node Failure

**Detection:** Azure Monitor node health alert; pod eviction events in `kubectl get events`.  
**Automatic Recovery:** AKS automatically reschedules pods on healthy nodes within 5 minutes (`PodDisruptionBudget` ensures 1 replica always available).  
**Manual Verification:**
```bash
kubectl get nodes
kubectl get pods -n default -o wide
curl -sf https://api.dbe-expert.gov.za/health
```
**RTO:** ~5 minutes (automatic). Manual steps only if automatic recovery fails.

---

### Scenario DR-02 — Full AKS Cluster Failure

**Detection:** All `/health` checks fail; no pods running.

**Recovery Steps:**
```bash
# Step 1: Determine failure cause
az aks show --name aks-dbe-expert-prod \
  --resource-group rg-dbe-ai-expert-system \
  --query "provisioningState"

# Step 2: If cluster is failed/deleting, re-provision via Terraform
cd infrastructure/
terraform apply -target=azurerm_kubernetes_cluster.main -auto-approve

# Step 3: Re-get credentials
az aks get-credentials --resource-group rg-dbe-ai-expert-system \
  --name aks-dbe-expert-prod

# Step 4: Re-deploy application
helm upgrade --install dbe-agent helm/dbe-agent-orchestrator/ \
  --set image.tag=$(git rev-parse --short HEAD) \
  --wait --timeout 10m

# Step 5: Validate
curl -sf https://api.dbe-expert.gov.za/health
```

**Estimated RTO:** 45–90 minutes.

---

### Scenario DR-03 — Cosmos DB Account Failure / Data Corruption

**Detection:** Gremlin health check fails; Cosmos DB portal shows degraded state.

**Recovery from Point-in-Time Backup:**
```bash
# Step 1: Identify corruption timestamp
# Check Application Insights for last known-good timestamp

# Step 2: Trigger PITR restore (7-day window)
az cosmosdb restore \
  --target-database-account-name cosmos-dbe-expert-prod-restored \
  --account-name cosmos-dbe-expert-prod \
  --restore-timestamp "2026-04-29T10:00:00Z" \
  --location "southafricanorth" \
  --resource-group rg-dbe-ai-expert-system

# Step 3: Update Key Vault secret with new endpoint
az keyvault secret set \
  --vault-name kv-dbe-prod \
  --name cosmos-endpoint \
  --value "<RESTORED_ENDPOINT>"

# Step 4: Rolling restart to pick up new secret
kubectl rollout restart deployment/dbe-agent-dbe-agent-orchestrator

# Step 5: Re-initialise graph if needed
export COSMOS_GREMLIN_ENDPOINT=<RESTORED_GREMLIN_ENDPOINT>
python src/ingestion/graph_manager.py
```

**Estimated RTO:** 2–4 hours (PITR restore time depends on data volume).  
**RPO:** Up to 1 hour (continuous backup).

---

### Scenario DR-04 — Azure Blob Storage Failure (Feedback Loss)

**Detection:** Feedback blob write errors in Application Insights.

**Impact Assessment:** Feedback data from the failure window may be unrecoverable. Existing blobs are safe (LRS/GRS redundancy).

**Recovery Steps:**
```bash
# Verify storage account status
az storage account show \
  --name stdbeexpertprod \
  --query "statusOfPrimary"

# If primary region unavailable, failover to secondary (GRS)
az storage account failover \
  --name stdbeexpertprod \
  --resource-group rg-dbe-ai-expert-system --yes

# Update connection string secret
NEW_CONN=$(az storage account show-connection-string \
  --name stdbeexpertprod \
  --resource-group rg-dbe-ai-expert-system \
  --query connectionString -o tsv)

az keyvault secret set \
  --vault-name kv-dbe-prod \
  --name storage-connection-string \
  --value "$NEW_CONN"

kubectl rollout restart deployment/dbe-agent-dbe-agent-orchestrator
```

---

### Scenario DR-05 — Azure Region Outage (South Africa North)

**Detection:** Azure Service Health alert; all endpoints unreachable.

**Failover to East US:**
```bash
# Step 1: Provision infrastructure in East US (pre-configured as Terraform workspace)
cd infrastructure/
terraform workspace select eastus
terraform apply -var="location=eastus" -var="environment=prod" -auto-approve

# Step 2: Update DNS (api.dbe-expert.gov.za) to point to East US APIM
# (Manual step via DNS provider)

# Step 3: Verify service in East US
curl -sf https://api-dr.dbe-expert.gov.za/health
```

**Estimated RTO:** 3–6 hours (DNS propagation included).  
**Note:** Cosmos DB second `geo_location` must be configured (TODO item in `docs/TODO.md`).

---

### Scenario DR-06 — Key Vault Secret Compromise

**Detection:** Security alert; suspected credential leak.

**Immediate Actions:**
```bash
# Step 1: Rotate ALL secrets immediately
for SECRET in cosmos-endpoint cosmos-key azure-ml-key jwt-secret storage-connection-string; do
  echo "Rotating $SECRET..."
  # Generate or retrieve new value, then:
  az keyvault secret set --vault-name kv-dbe-prod --name $SECRET --value "<NEW_VALUE>"
done

# Step 2: Rolling restart to invalidate old credentials in running pods
kubectl rollout restart deployment/dbe-agent-dbe-agent-orchestrator

# Step 3: Revoke old Cosmos DB keys via portal
# Step 4: Notify security officer and initiate IRP
```

---

## 3. DR Test Schedule

| Test | Frequency | Last Tested | Next Test |
|------|-----------|-------------|-----------|
| DR-01 (Node failure) | Quarterly | *Pending* | Phase 5 |
| DR-02 (Cluster failure) | Semi-annually | *Pending* | Phase 5 |
| DR-03 (Cosmos PITR) | Semi-annually | *Pending* | Phase 5 |
| DR-05 (Region failover) | Annually | *Pending* | Post-launch |

---

## 4. Recovery Team Contacts

| Role | Responsibility | Escalation Timeout |
|------|---------------|-------------------|
| On-Call Engineer | First responder; DR-01, DR-02 | Immediate |
| DevOps Lead | Infrastructure recovery; DR-02, DR-03 | 15 minutes |
| DBE IT Director | Business decision on MTD breach | 30 minutes |
| Microsoft Azure Support | DR-05 region-level incidents | Concurrent |

---

*End of DRP — DBE-DRP-026 v1.0.0*
