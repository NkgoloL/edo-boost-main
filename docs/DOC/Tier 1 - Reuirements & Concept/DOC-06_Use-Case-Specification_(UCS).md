# Use Case Specification (UCS)
**Document ID:** DBE-UCS-006  
**Version:** 1.0.0  
**Date:** 2026-04-29

---

## 1. Use Case Diagram (Textual)

```
Actors: Policy Analyst, Data Engineer, System Administrator, Azure ML Pipeline

Policy Analyst     ──► UC-01: Submit Policy Query
Policy Analyst     ──► UC-02: Rate System Response
Policy Analyst     ──► UC-03: View Response with Citations
Data Engineer      ──► UC-04: Ingest Document from Blob Storage
Data Engineer      ──► UC-05: Seed Knowledge Graph
System Admin       ──► UC-06: Deploy New Application Version
System Admin       ──► UC-07: Monitor System Health
Azure ML Pipeline  ──► UC-08: Trigger Model Retraining
```

---

## 2. Use Case Descriptions

### UC-01: Submit Policy Query

| Field | Detail |
|-------|--------|
| **ID** | UC-01 |
| **Name** | Submit Policy Query |
| **Actor** | Policy Analyst |
| **Preconditions** | Actor is authenticated via APIM JWT. System is operational. |
| **Trigger** | Actor submits POST request to `/ask` with `{"query": "...", "user_id": "..."}` |
| **Main Flow** | 1. APIM validates JWT. 2. Request forwarded to FastAPI. 3. Orchestrator retrieves context from knowledge graph. 4. Expert model invoked. 5. Response synthesised. 6. `AgentResponse` returned with `response`, `sources`, `confidence`. |
| **Alternate Flow A** | If knowledge graph is empty, system falls back to `BaselinePolicyModel` context. |
| **Alternate Flow B** | If Azure ML endpoint is unreachable, system falls back to `BaselinePolicyModel`. |
| **Exception Flow** | If JWT is invalid → HTTP 401. If request body malformed → HTTP 422. If internal error → HTTP 500. |
| **Postconditions** | Response logged to Application Insights with request ID and latency. |
| **SRS Refs** | FR-030, FR-031, FR-032, FR-033, FR-034, NFR-001 |

---

### UC-02: Rate System Response

| Field | Detail |
|-------|--------|
| **ID** | UC-02 |
| **Name** | Rate System Response |
| **Actor** | Policy Analyst |
| **Preconditions** | Actor received a response from UC-01. |
| **Trigger** | Actor submits POST to `/feedback` with `{"query", "response", "rating": 1–5}` |
| **Main Flow** | 1. APIM validates JWT. 2. `FeedbackLoopManager.process_feedback()` called. 3. Feedback persisted as JSON blob. 4. If `rating < 3`, low-rating counter incremented. 5. If counter ≥ `FEEDBACK_RETRAINING_THRESHOLD`, retraining pipeline triggered. |
| **Exception Flow** | Rating outside 1–5 range → HTTP 422. Blob write failure → HTTP 500. |
| **Postconditions** | Feedback blob exists in `feedback` container. |
| **SRS Refs** | FR-040, FR-041, FR-042, FR-043 |

---

### UC-03: View Response with Citations

| Field | Detail |
|-------|--------|
| **ID** | UC-03 |
| **Name** | View Response with Source Citations |
| **Actor** | Policy Analyst |
| **Preconditions** | UC-01 completed successfully. |
| **Main Flow** | 1. Actor inspects `AgentResponse.sources` array. 2. Each source entry identifies the knowledge base or model used. 3. Actor can trace recommendation back to originating document. |
| **SRS Refs** | FR-032, SN-01-02 |

---

### UC-04: Ingest Document from Blob Storage

| Field | Detail |
|-------|--------|
| **ID** | UC-04 |
| **Name** | Ingest Document from Blob Storage |
| **Actor** | Data Engineer |
| **Preconditions** | Document uploaded to designated Blob container. Cosmos DB is operational. |
| **Trigger** | Data engineer calls `pipeline.ingest_from_blob(container, blob_name)` or automated trigger fires. |
| **Main Flow** | 1. Pipeline downloads blob. 2. JSON parsed. 3. `upsert_to_cosmos()` called with partition key derived from `category`. 4. Document available for graph linking. |
| **Exception Flow** | Blob not found → `BlobNotFoundError` logged, pipeline continues. JSON parse failure → logged and skipped. |
| **SRS Refs** | FR-001, FR-002, FR-003 |

---

### UC-05: Seed Knowledge Graph

| Field | Detail |
|-------|--------|
| **ID** | UC-05 |
| **Name** | Seed and Link Knowledge Graph |
| **Actor** | Data Engineer |
| **Preconditions** | Cosmos DB Gremlin endpoint is operational. Document exists in Cosmos DB. |
| **Main Flow** | 1. `graph_manager.initialize_graph()` bootstraps root vertex and categories. 2. `add_document_node()` called for each document. 3. `contains` edge created from category to document. |
| **Exception Flow** | Category vertex not found → `ValueError` raised, engineer notified. |
| **SRS Refs** | FR-010, FR-014, FR-017 |

---

### UC-06: Deploy New Application Version

| Field | Detail |
|-------|--------|
| **ID** | UC-06 |
| **Name** | Deploy New Application Version |
| **Actor** | System Administrator |
| **Preconditions** | CI/CD pipeline has passed all tests. Docker image pushed to ACR. |
| **Main Flow** | 1. CI/CD triggers `helm upgrade --install`. 2. AKS performs rolling update. 3. New pods start, pass readiness probe on `/health`. 4. Old pods terminate. 5. Smoke tests execute. |
| **Rollback Flow** | If smoke tests fail → `helm rollback` to previous revision. |
| **SRS Refs** | NFR-010, NFR-012, Deployment Guide |

---

### UC-07: Monitor System Health

| Field | Detail |
|-------|--------|
| **ID** | UC-07 |
| **Name** | Monitor System Health |
| **Actor** | System Administrator |
| **Main Flow** | 1. Admin opens Azure Monitor dashboard. 2. Reviews request volume, error rate, p95 latency. 3. Reviews Cosmos DB RU consumption. 4. If alert fires → consults OpsMan runbook. |
| **SRS Refs** | NFR-010, OpsMan |

---

### UC-08: Trigger Model Retraining

| Field | Detail |
|-------|--------|
| **ID** | UC-08 |
| **Name** | Automated Model Retraining |
| **Actor** | Azure ML Pipeline (automated) |
| **Preconditions** | Feedback threshold exceeded. Azure ML workspace is operational. |
| **Main Flow** | 1. `FeedbackLoopManager.trigger_retraining()` submits pipeline job. 2. Pipeline reads feedback blobs from storage. 3. New model version trained and evaluated. 4. If improved → registered and promoted. 5. Lineage tracker tags model with dataset ID. |
| **SRS Refs** | FR-042, FR-043 |

---

*End of UCS — DBE-UCS-006 v1.0.0*
