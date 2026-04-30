# Deployment Guide
**Document ID:** DBE-DEP-024  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** Internal — Controlled

---

## Prerequisites

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Azure CLI | 2.50+ | Azure resource management |
| Terraform | 1.5+ | Infrastructure provisioning |
| kubectl | 1.27+ | Kubernetes operations |
| Helm | 3.12+ | Application deployment |
| Docker | 24+ | Container build |
| Python | 3.10+ | Application runtime |
| git | 2.40+ | Source control |

**Required Azure permissions:** `Contributor` on the target resource group; `Key Vault Secrets Officer`; `AcrPush` on ACR.

---

## 1. First-Time Environment Bootstrap

### Step 1 — Authenticate Azure CLI
```bash
az login
az account set --subscription $AZURE_SUBSCRIPTION_ID
```

### Step 2 — Provision Infrastructure (Terraform)
```bash
cd infrastructure/

# Initialise remote state backend
terraform init \
  -backend-config="resource_group_name=rg-terraform-state" \
  -backend-config="storage_account_name=sttfstatedbeexpert" \
  -backend-config="container_name=tfstate" \
  -backend-config="key=terraform.tfstate"

# Plan — review before applying
terraform plan -var="environment=dev" -out=tfplan

# Apply
terraform apply tfplan
```

**Expected outputs after apply:**
- Cosmos DB endpoint and keys
- ACR login server
- AKS cluster name
- APIM gateway URL
- Key Vault URI

### Step 3 — Seed Key Vault Secrets
```bash
KV_NAME=$(terraform output -raw key_vault_name)

az keyvault secret set --vault-name $KV_NAME --name cosmos-endpoint     --value "<COSMOS_ENDPOINT>"
az keyvault secret set --vault-name $KV_NAME --name cosmos-key          --value "<COSMOS_KEY>"
az keyvault secret set --vault-name $KV_NAME --name azure-ml-endpoint   --value "<ML_ENDPOINT>"
az keyvault secret set --vault-name $KV_NAME --name azure-ml-key        --value "<ML_KEY>"
az keyvault secret set --vault-name $KV_NAME --name storage-connection-string --value "<CONN_STR>"
az keyvault secret set --vault-name $KV_NAME --name jwt-secret          --value "<JWT_SECRET>"
```

### Step 4 — Initialise Knowledge Graph
```bash
# Connect to Cosmos Gremlin and seed root vertices
COSMOS_GREMLIN_ENDPOINT=$(terraform output -raw cosmos_gremlin_endpoint)
COSMOS_GREMLIN_KEY=$(terraform output -raw cosmos_gremlin_key)

export COSMOS_GREMLIN_ENDPOINT COSMOS_GREMLIN_KEY
python src/ingestion/graph_manager.py
```

---

## 2. Container Build and Push

### Build Image
```bash
# Set environment variables
ACR_NAME=$(terraform output -raw acr_login_server)
GIT_SHA=$(git rev-parse --short HEAD)
IMAGE_TAG="${ACR_NAME}/agent-orchestrator:${GIT_SHA}"

# Build
docker build -t $IMAGE_TAG .

# Verify image starts
docker run --rm -e PORT=8000 $IMAGE_TAG python -c "from src.orchestration.main import app; print('OK')"
```

### Push to ACR
```bash
az acr login --name $ACR_NAME
docker push $IMAGE_TAG
docker tag $IMAGE_TAG ${ACR_NAME}/agent-orchestrator:latest
docker push ${ACR_NAME}/agent-orchestrator:latest
```

---

## 3. Kubernetes Deployment (Helm)

### Get AKS Credentials
```bash
AKS_NAME=$(terraform output -raw aks_cluster_name)
RESOURCE_GROUP="rg-dbe-ai-expert-system"

az aks get-credentials --resource-group $RESOURCE_GROUP --name $AKS_NAME
kubectl cluster-info
```

### Deploy with Helm
```bash
# First-time install
helm upgrade --install dbe-agent helm/dbe-agent-orchestrator/ \
  --namespace default \
  --set image.registry=$ACR_NAME \
  --set image.tag=$GIT_SHA \
  --set global.environment=staging \
  --wait --timeout 5m

# Verify rollout
kubectl rollout status deployment/dbe-agent-dbe-agent-orchestrator
kubectl get pods -l app.kubernetes.io/name=dbe-agent-orchestrator
```

### Post-Deploy Smoke Tests
```bash
GATEWAY_URL=$(kubectl get svc dbe-agent-dbe-agent-orchestrator -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Health check
curl -sf http://$GATEWAY_URL/health | grep '"status":"healthy"' && echo "HEALTH OK"

# Version check
curl -sf http://$GATEWAY_URL/version | python -m json.tool

# Baseline query (no auth — expected 401 from APIM, 200 from direct)
curl -sf -X POST http://$GATEWAY_URL/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "school infrastructure policy"}' \
  | python -m json.tool
```

---

## 4. Rollback Procedure

```bash
# List Helm release history
helm history dbe-agent --namespace default

# Rollback to previous revision
helm rollback dbe-agent 0 --namespace default --wait

# Verify rollback
kubectl rollout status deployment/dbe-agent-dbe-agent-orchestrator
curl -sf http://$GATEWAY_URL/health
```

---

## 5. Production Deployment Checklist

Before deploying to production, confirm:

- [ ] All tests pass on `develop` branch (CI green)
- [ ] Docker image scanned by Trivy — zero CRITICAL CVEs
- [ ] `helm upgrade --dry-run` executed without errors
- [ ] Cosmos DB Gremlin graph has been seeded and verified
- [ ] Key Vault secrets populated for production environment
- [ ] `localhost:3000` CORS origin removed from `apim/policy.xml`
- [ ] `{{client-id}}` replaced with Key Vault Named Value in APIM policy
- [ ] `PodDisruptionBudget` in place (`minAvailable: 1`)
- [ ] Azure Monitor alert rules active
- [ ] DRP reviewed and operations team briefed
- [ ] ATO signed (ref: `docs/security/ATO.md`)

---

## 6. Environment-Specific Configuration

| Parameter | Development | Staging | Production |
|-----------|-------------|---------|------------|
| `global.environment` | `development` | `staging` | `production` |
| `replicaCount` | 1 | 2 | 2 (HPA min) |
| `autoscaling.maxReplicas` | 2 | 5 | 10 |
| APIM SKU | `Developer_1` | `Developer_1` | `Standard_1` |
| Cosmos throughput | 400 RU/s | 400 RU/s | Autoscale |
| `purge_protection_enabled` | `false` | `false` | `true` |

---

*End of Deployment Guide — DBE-DEP-024 v1.0.0*
