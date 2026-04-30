# System/Subsystem Specification (SSS)
**Document ID:** DBE-SSS-002  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** Internal — Controlled  
**Status:** Baseline Draft

---

## Document Control

| Field | Detail |
|-------|--------|
| Prepared By | DBE AI Expert System Team |
| Parent Document | `docs/requirements/SRS.md` (DBE-SRS-001) |
| Based On | MIL-STD-498 SSS DID, ISO/IEC 12207 |

---

## 1. Introduction

This document decomposes the DBE AI Expert System into its constituent subsystems, defines subsystem boundaries, and specifies the responsibilities and interface obligations of each subsystem. It serves as the authoritative decomposition bridge between the system-level SRS and the component-level SDD.

---

## 2. System Overview

The DBE AI Expert System comprises **six subsystems** operating as a directed pipeline:

```
[SS-01] Knowledge Ingestion
        ↓
[SS-02] Knowledge Graph
        ↓
[SS-03] Expert Model Suite
        ↓
[SS-04] Agentic Orchestration
        ↓
[SS-05] API Gateway
        ↓
[SS-06] Feedback & Optimisation
        ↑_________________________|
```

---

## 3. Subsystem Specifications

### SS-01: Knowledge Ingestion Subsystem

**Responsibility:** Acquire, validate, normalise, and persist raw documents from external sources into the Cosmos DB document store.

**Components:**
- `KnowledgeIngestionPipeline` (`src/ingestion/pipeline.py`)
- Azure Blob Storage client
- Azure Cosmos DB SQL API client

**Inputs:**
- JSON documents from Azure Blob Storage containers
- Local file system documents (development/testing)

**Outputs:**
- Upserted documents in Cosmos DB (`IntelligenceStore` container)
- Ingestion audit log entries

**Key Constraints:**
- All documents must have or receive a unique `id` field.
- Partition key must derive from `category` field.
- Blob connection string must be externally configured.

**Interfaces:**
- `ICD §2.1`: Blob Storage → Ingestion Pipeline
- `ICD §2.2`: Ingestion Pipeline → Cosmos DB

---

### SS-02: Knowledge Graph Subsystem

**Responsibility:** Maintain a schema-validated property graph of educational knowledge entities and their relationships. Expose traversal and search operations to the orchestration layer.

**Components:**
- `KnowledgeGraphManager` (`src/ingestion/graph_manager.py`)
- Graph schema registry (`config/graph_schema.json`)
- Azure Cosmos DB Gremlin API client

**Inputs:**
- Document vertices from SS-01 (via direct method calls)
- Graph traversal queries from SS-04

**Outputs:**
- Graph traversal results (document sets, categories, agent triggers)
- Schema validation responses

**Key Constraints:**
- All Gremlin queries must use parameterised bindings.
- Schema changes must update `config/graph_schema.json` — no hardcoded schema.
- Graph initialisation must be idempotent.

**Interfaces:**
- `ICD §2.3`: Knowledge Graph ↔ Orchestration Layer

---

### SS-03: Expert Model Suite Subsystem

**Responsibility:** Abstract the inference layer, routing prediction requests to either an Azure ML Online Endpoint or the built-in baseline heuristic model.

**Components:**
- `AzureMLExpertModel` (`src/models/expert_model.py`)
- `BaselinePolicyModel` (`src/models/expert_model.py`)
- `ExpertModel` ABC

**Inputs:**
- `query` string from SS-04
- `context` string from SS-02

**Outputs:**
- Inference result string (policy recommendation or advisory text)

**Key Constraints:**
- Fallback to `BaselinePolicyModel` must be automatic and transparent.
- Inference timeout: 15 seconds maximum.
- Model selection is determined at application startup from environment variables.

**Interfaces:**
- `ICD §2.4`: Orchestration → Expert Model
- `ICD §2.5`: Expert Model → Azure ML Endpoint (external)

---

### SS-04: Agentic Orchestration Subsystem

**Responsibility:** Serve as the cognitive core — receive user queries, coordinate context retrieval from SS-02, dispatch to SS-03, synthesise responses, and expose the public REST API.

**Components:**
- FastAPI application (`src/orchestration/main.py`)
- Prompt templates (`src/orchestration/prompts/`)
- `perform_reasoning()` function
- LLM integration (Phase 4)

**Inputs:**
- HTTP requests from SS-05 (`/ask`, `/feedback`, `/health`, `/version`)
- Graph traversal results from SS-02
- Inference results from SS-03

**Outputs:**
- `AgentResponse` JSON payloads
- Feedback forwarded to SS-06
- Structured error responses

**Key Constraints:**
- Context retrieval must query SS-02 — static string stubs are not acceptable for production.
- All endpoints require JWT authentication middleware (Phase 3).

**Interfaces:**
- `ICD §3.1`: APIM → Orchestration (`/ask`)
- `ICD §3.2`: APIM → Orchestration (`/feedback`)
- `ICD §2.3`: Orchestration → Knowledge Graph

---

### SS-05: API Gateway Subsystem

**Responsibility:** Provide secure, rate-limited, authenticated external ingress. Enforce JWT validation, CORS, security headers, and request logging before traffic reaches SS-04.

**Components:**
- Azure API Management (`apim-dbe-expert-{env}`)
- APIM Policy (`infrastructure/apim/policy.xml`)
- Route definitions (`infrastructure/apim/routes.json`)
- APIM Named Values (Key Vault references)

**Inputs:**
- External HTTP/HTTPS requests from consumer applications

**Outputs:**
- Proxied requests to SS-04 (AKS internal DNS)
- Rejected requests (HTTP 401, 429, 403) with structured error bodies

**Key Constraints:**
- `{{client-id}}` placeholder must be replaced with a Key Vault Named Value before deployment.
- `localhost:3000` CORS origin must be removed for production deployments.
- APIM must be `Standard_1` SKU in production for SLA compliance.

**Interfaces:**
- `ICD §3.1`: External Client → APIM → Orchestration

---

### SS-06: Feedback & Optimisation Subsystem

**Responsibility:** Collect, store, and act on user feedback signals to drive continuous model improvement.

**Components:**
- `FeedbackLoopManager` (`src/optimization/feedback_loop.py`)
- `LineageTracker` (`src/optimization/lineage_tracker.py`)
- Azure Blob Storage (feedback container)
- Azure ML Client (retraining trigger)

**Inputs:**
- Feedback payloads from SS-04
- Low-rating threshold events

**Outputs:**
- JSON feedback blobs in Azure Blob Storage
- Azure ML retraining pipeline job submissions
- Model lineage tags in Azure ML model registry

**Key Constraints:**
- Feedback must be persisted atomically — no data loss after HTTP 200 response.
- Retraining trigger must be threshold-gated (not per-feedback).
- `LineageTracker.log_inference_event()` must push to Azure Monitor in production.

**Interfaces:**
- `ICD §2.6`: Orchestration → Feedback Manager
- `ICD §2.7`: Feedback Manager → Azure Blob Storage
- `ICD §2.8`: Feedback Manager → Azure ML Pipeline

---

## 4. Subsystem Dependency Matrix

| Subsystem | Depends On | Depended On By |
|-----------|-----------|----------------|
| SS-01 Ingestion | Azure Blob, Cosmos DB | SS-02 Graph |
| SS-02 Graph | Cosmos DB Gremlin | SS-04 Orchestration |
| SS-03 Expert Models | Azure ML | SS-04 Orchestration |
| SS-04 Orchestration | SS-02, SS-03, SS-06 | SS-05 Gateway |
| SS-05 API Gateway | SS-04 | External Clients |
| SS-06 Feedback | Azure Blob, Azure ML | SS-04 Orchestration |

---

## 5. Allocated Requirements

| SRS Requirement | Allocated Subsystem |
|----------------|---------------------|
| FR-001 to FR-006 | SS-01 |
| FR-010 to FR-017 | SS-02 |
| FR-020 to FR-023 | SS-03 |
| FR-030 to FR-035 | SS-04 |
| FR-040 to FR-043 | SS-06 |
| FR-050 to FR-052 | SS-04 |
| NFR-001 to NFR-005 | SS-04, SS-02, SS-03 |
| NFR-010 to NFR-012 | SS-04, SS-05 |
| SR-001 to SR-002 | SS-05, SS-04 |
| SR-003 | SS-02 |

---

*End of SSS — DBE-SSS-002 v1.0.0*
