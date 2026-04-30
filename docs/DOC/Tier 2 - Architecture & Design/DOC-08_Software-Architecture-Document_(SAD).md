# Software Architecture Document (SAD)
**Document ID:** DBE-SAD-008  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** Internal — Controlled

---

## 1. Architectural Views (C4 Model)

### 1.1 Context View (C4 Level 1)

```
                    ┌──────────────────────────────────────────────┐
                    │              Azure Cloud Boundary            │
                    │                                              │
[Policy Analyst] ──►│  [APIM Gateway] ──► [DBE AI Expert System] │
                    │                                              │
                    │  [Azure Blob]    [Cosmos DB]   [Azure ML]   │
                    └──────────────────────────────────────────────┘
```

**External actors:**
- Policy Analysts / District Officials (REST API consumers)
- Data Engineers (direct pipeline operators)
- Azure ML Pipeline (automated retraining agent)

### 1.2 Container View (C4 Level 2)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Azure Environment                            │
│                                                                     │
│  ┌────────────┐    ┌────────────────────────────────────────────┐  │
│  │    APIM    │───►│              AKS Cluster                   │  │
│  │  Gateway   │    │  ┌──────────────────────────────────────┐  │  │
│  └────────────┘    │  │    agent-orchestrator (FastAPI)      │  │  │
│                    │  │    Replicas: 2–10 (HPA)              │  │  │
│  ┌────────────┐    │  └──────────────┬───────────────────────┘  │  │
│  │ Azure Blob │◄───┼─────────────────┤                          │  │
│  │  Storage   │    │                 │                          │  │
│  └────────────┘    │  ┌──────────────▼───────────────────────┐  │  │
│                    │  │      Cosmos DB (Gremlin + SQL)        │  │  │
│  ┌────────────┐    │  └──────────────────────────────────────┘  │  │
│  │  Azure ML  │◄───┤                                            │  │
│  │ Workspace  │    │  ┌──────────────────────────────────────┐  │  │
│  └────────────┘    │  │     Azure Key Vault (Secrets)        │  │  │
│                    │  └──────────────────────────────────────┘  │  │
│  ┌────────────┐    │                                            │  │
│  │  Azure     │    │  ┌──────────────────────────────────────┐  │  │
│  │  Monitor   │◄───┤  │   Application Insights (Telemetry)  │  │  │
│  └────────────┘    │  └──────────────────────────────────────┘  │  │
│                    └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Component View (C4 Level 3)

```
agent-orchestrator container:
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │  /ask       │    │ KnowledgeGraph  │    │  ExpertModel    │  │
│  │  /feedback  │───►│    Manager      │    │  (Strategy)     │  │
│  │  /health    │    │                 │    │                 │  │
│  │  /version   │    │  - Traversal    │    │  AzureML /      │  │
│  └─────────────┘    │  - Validation   │    │  Baseline       │  │
│         │           └────────┬────────┘    └────────┬────────┘  │
│         │                    │                      │           │
│         ▼                    ▼                      ▼           │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │  Feedback   │    │   Cosmos DB     │    │   Azure ML      │  │
│  │  Loop Mgr   │    │  Gremlin API    │    │   Endpoint      │  │
│  └─────────────┘    └─────────────────┘    └─────────────────┘  │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────┐    ┌─────────────────┐                         │
│  │  Blob Store │    │ Lineage Tracker │                         │
│  │  (feedback) │    │  (Azure ML)     │                         │
│  └─────────────┘    └─────────────────┘                         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Deployment View

```
┌─────────────────────────────────────────────────────────────────┐
│  Azure AKS — aks-dbe-expert-{env}                               │
│                                                                  │
│  Namespace: default                                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Deployment: agent-orchestrator                         │   │
│  │  Replicas: 2 (min) → 10 (max, HPA)                     │   │
│  │  Image: <acr>.azurecr.io/agent-orchestrator:<sha>       │   │
│  │  Resources: 250m CPU / 256Mi RAM (request)              │   │
│  │             1000m CPU / 512Mi RAM (limit)               │   │
│  │  SecurityContext: non-root, readOnlyRootFS              │   │
│  │  Probes: /health (liveness + readiness)                 │   │
│  │  Secrets: CSI driver → Key Vault                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Services: LoadBalancer (port 80 → 8000)                        │
│  Ingress: Azure Application Gateway → api.dbe-expert.gov.za     │
│  NetworkPolicy: Ingress from APIM subnet only                    │
│  PodDisruptionBudget: minAvailable: 1                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Infrastructure View (Terraform-Managed Resources)

| Resource | Name Pattern | Region | Purpose |
|----------|-------------|--------|---------|
| Resource Group | `rg-dbe-ai-expert-system` | SA North | Logical container |
| VNet | `vnet-dbe-expert` | SA North | Network isolation |
| AKS Cluster | `aks-dbe-expert-{env}` | SA North | Compute |
| Cosmos DB | `cosmos-dbe-expert-{env}` | SA North | Graph + Documents |
| Azure ML | `mlw-dbe-{env}` | SA North | Expert model hosting |
| ACR | `acrdbeexpert{env}` | SA North | Container registry |
| APIM | `apim-dbe-expert-{env}` | SA North | API gateway |
| Key Vault | `kv-dbe-{env}` | SA North | Secrets management |
| Storage | `stdbeexpert{env}` | SA North | Feedback + Documents |
| App Insights | `appi-dbe-{env}` | SA North | Observability |

---

## 4. Quality Attribute Scenarios

### 4.1 Availability
- **Scenario:** AKS node failure during business hours.
- **Response:** HPA maintains minimum 2 replicas; `PodDisruptionBudget` prevents both pods being evicted simultaneously. Recovery < 5 minutes.

### 4.2 Security
- **Scenario:** Malicious Gremlin injection attempt via `/ask` query parameter.
- **Response:** APIM JWT validation rejects unauthenticated requests. FastAPI input validation enforces schema. All Gremlin queries use binding dictionaries — injection strings are never interpolated.

### 4.3 Performance
- **Scenario:** 50 concurrent `/ask` requests.
- **Response:** HPA scales pods; Gremlin pool_size=4 per pod; Redis cache (Phase 4) absorbs repeat queries. p95 latency target: 2 seconds.

### 4.4 Modifiability
- **Scenario:** New expert model added for curriculum queries.
- **Response:** Implement `ExpertModel` ABC subclass. Update `get_expert_model()` factory. Zero orchestration code changes.

---

## 5. Architecture Decision Records (ADRs)

### ADR-001: Gremlin over Cypher
**Decision:** Use Azure Cosmos DB Gremlin API rather than a Neo4j-compatible graph.  
**Rationale:** Azure Cosmos DB is already provisioned for SQL API; enabling Gremlin on the same account incurs minimal cost. Neo4j would require a separate managed service.  
**Consequences:** Limited to Gremlin traversal language; cannot use Cypher's richer pattern matching.

### ADR-002: Strategy Pattern for Expert Models
**Decision:** `ExpertModel` ABC with runtime strategy selection.  
**Rationale:** Enables zero-downtime model swaps and local development without Azure credentials.  
**Consequences:** All expert models must be stateless and implement the same async `predict()` interface.

### ADR-003: pydantic-settings for Configuration
**Decision:** Migrate from `pydantic.BaseSettings` to `pydantic_settings.BaseSettings`.  
**Rationale:** Pydantic v2.3.0 removed `BaseSettings` from the core package. `pydantic-settings` is the official migration path.  
**Consequences:** `pydantic-settings` must be added as an explicit dependency.

### ADR-004: Tenacity for Gremlin Retry
**Decision:** Use `tenacity` library rather than manual retry loops for Gremlin query execution.  
**Rationale:** Tenacity provides declarative retry configuration, jitter, and detailed logging hooks that would require significant boilerplate to replicate manually.  
**Consequences:** `tenacity` added to `requirements.txt`.

---

*End of SAD — DBE-SAD-008 v1.0.0*
