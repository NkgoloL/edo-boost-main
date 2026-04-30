# System Requirements Specification (SRS)
**Document ID:** DBE-SRS-001  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** Internal — Controlled  
**Status:** Baseline Draft

---

## Document Control

| Field | Detail |
|-------|--------|
| Prepared By | DBE AI Expert System Team |
| Reviewed By | *Pending* |
| Approved By | *Pending* |
| Based On | ISO/IEC 29148:2018, MIL-STD-498 SRS DID |

### Revision History

| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 0.1 | 2026-04-28 | System Agent | Initial draft from architecture review |
| 1.0 | 2026-04-29 | System Agent | Baseline release |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Overall Description](#2-overall-description)
3. [Functional Requirements](#3-functional-requirements)
4. [Non-Functional Requirements](#4-non-functional-requirements)
5. [Interface Requirements](#5-interface-requirements)
6. [Data Requirements](#6-data-requirements)
7. [Security Requirements](#7-security-requirements)
8. [Compliance Requirements](#8-compliance-requirements)
9. [Constraints](#9-constraints)
10. [Requirements Traceability Matrix](#10-requirements-traceability-matrix)

---

## 1. Introduction

### 1.1 Purpose

This System Requirements Specification (SRS) defines all functional, non-functional, interface, and constraint requirements for the **DBE AI Expert System** — an agentic AI platform designed to support the South African Department of Basic Education (DBE) in automated knowledge ingestion, expert policy reasoning, and orchestrated advisory services.

### 1.2 Scope

The DBE AI Expert System shall:
- Ingest, classify, and store educational policy documents from multiple source formats.
- Represent ingested knowledge as a queryable knowledge graph.
- Invoke specialised AI expert models to generate policy recommendations.
- Expose an authenticated REST API for downstream consumer applications.
- Collect user feedback and trigger automated model retraining pipelines.
- Operate within the Azure Government Cloud tenancy of the DBE.

### 1.3 Definitions and Acronyms

| Term | Definition |
|------|-----------|
| AKS | Azure Kubernetes Service |
| APIM | Azure API Management |
| ConOps | Concept of Operations |
| Cosmos DB | Azure Cosmos DB (Gremlin and SQL APIs) |
| DBE | Department of Basic Education (South Africa) |
| Gremlin | Apache TinkerPop graph traversal language |
| ICD | Interface Control Document |
| LLM | Large Language Model |
| ML | Machine Learning |
| POPIA | Protection of Personal Information Act (South Africa) |
| RTO | Recovery Time Objective |
| RPO | Recovery Point Objective |
| SLA | Service Level Agreement |
| VNet | Azure Virtual Network |

### 1.4 References

| ID | Document |
|----|---------|
| REF-01 | `docs/design/SAD.md` — Software Architecture Document |
| REF-02 | `docs/design/ICD.md` — Interface Control Document |
| REF-03 | `docs/requirements/ConOps.md` — Concept of Operations |
| REF-04 | `infrastructure/main.tf` — Azure Infrastructure Definition |
| REF-05 | ISO/IEC 25010:2011 — Systems and Software Quality Models |
| REF-06 | POPIA Act No. 4 of 2013 |

---

## 2. Overall Description

### 2.1 Product Perspective

The DBE AI Expert System is a cloud-native, microservice-based AI advisory platform. It is not a standalone product — it integrates with:
- Azure Blob Storage (document landing zone)
- Azure Cosmos DB (knowledge graph and document store)
- Azure ML Workspace (expert model hosting)
- Azure API Management (external API gateway)
- Azure Kubernetes Service (containerised workload execution)
- Azure Monitor / Application Insights (observability)

### 2.2 Product Functions (Summary)

1. **Document Ingestion** — Automated extraction and normalisation of documents from Azure Blob Storage.
2. **Knowledge Graph Management** — Schema-validated graph construction and traversal using Gremlin API.
3. **Expert Model Inference** — Asynchronous invocation of specialised Azure ML endpoints for domain-specific recommendations.
4. **Query Orchestration** — Context retrieval, expert model dispatch, and response synthesis via the `/ask` endpoint.
5. **Feedback Collection** — User rating capture via `/feedback` endpoint with blob persistence.
6. **Automated Retraining** — Feedback-triggered Azure ML retraining pipeline invocation.

### 2.3 User Classes

| Class | Description | Interaction Mode |
|-------|-------------|-----------------|
| Policy Analyst | DBE staff querying educational policies | REST API / Web UI |
| System Administrator | Deploys, monitors, and maintains the platform | AKS / Azure Portal |
| Data Engineer | Manages document ingestion and graph seeding | CLI / Pipeline |
| ML Engineer | Maintains expert models and retraining pipelines | Azure ML Studio |
| Auditor | Reviews compliance and access logs | Azure Monitor |

### 2.4 Operating Environment

- **Cloud:** Microsoft Azure (South Africa North preferred; East US failover)
- **Runtime:** Python 3.10+, FastAPI, Kubernetes 1.27+
- **Availability Target:** 99.9% monthly uptime for the `/ask` and `/feedback` endpoints
- **Data Residency:** All PII-bearing data must remain within South African Azure regions

---

## 3. Functional Requirements

Requirements are identified as `FR-XXX`. Priority: **M** = Must, **S** = Should, **C** = Could.

### 3.1 Document Ingestion

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-001 | M | The system shall ingest JSON-formatted documents from Azure Blob Storage containers. |
| FR-002 | M | The system shall upsert ingested documents into Cosmos DB with a partition key derived from the `category` field. |
| FR-003 | M | The system shall assign a unique `id` to each ingested document if none is present. |
| FR-004 | S | The system shall support bulk ingestion of multiple documents in a single pipeline invocation. |
| FR-005 | S | The system shall log ingestion success and failure events with document identifiers. |
| FR-006 | C | The system should support PDF and plain-text document ingestion with automatic format detection. |

### 3.2 Knowledge Graph

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-010 | M | The system shall maintain a schema-validated knowledge graph with vertex types: ExpertSystem, Category, Document, Agent. |
| FR-011 | M | The system shall maintain edge types: manages, contains, references, triggers. |
| FR-012 | M | The system shall reject vertex and edge creation requests that violate the schema definition. |
| FR-013 | M | The system shall use parameterised Gremlin queries exclusively — f-string interpolation is prohibited. |
| FR-014 | M | The system shall initialise the graph idempotently — repeated initialisation calls must not create duplicate vertices. |
| FR-015 | S | The system shall support keyword-based document search across `name` and `content` vertex properties. |
| FR-016 | S | The system shall support two-hop traversal to retrieve related categories for a given document. |
| FR-017 | S | The system shall validate that a target Category vertex exists before creating a `contains` edge. |

### 3.3 Expert Model Inference

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-020 | M | The system shall invoke the Azure ML Online Endpoint asynchronously when `AZURE_ML_ENDPOINT` and `AZURE_ML_KEY` are configured. |
| FR-021 | M | The system shall fall back to the `BaselinePolicyModel` when Azure ML credentials are absent. |
| FR-022 | M | The system shall return expert inference results within 15 seconds or surface a structured error response. |
| FR-023 | S | The system shall log all expert model invocations with query hash, model version, and latency. |

### 3.4 Query Orchestration (`/ask`)

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-030 | M | The system shall expose a `POST /ask` endpoint accepting `{"query": string, "user_id": string}`. |
| FR-031 | M | The system shall retrieve relevant context from the knowledge graph before invoking the expert model. |
| FR-032 | M | The system shall return a response conforming to `AgentResponse` schema: `{response, sources, confidence}`. |
| FR-033 | M | The system shall return HTTP 422 for malformed request bodies. |
| FR-034 | M | The system shall return HTTP 500 with a structured error body on internal failures. |
| FR-035 | S | The system shall include a reasoning trace in the response when `debug=true` query parameter is supplied. |

### 3.5 Feedback Collection

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-040 | M | The system shall expose a `POST /feedback` endpoint accepting `{"query", "response", "rating": 1–5}`. |
| FR-041 | M | The system shall persist feedback as a JSON blob in Azure Blob Storage. |
| FR-042 | M | The system shall trigger retraining consideration when `rating < 3`. |
| FR-043 | S | The system shall trigger an Azure ML retraining pipeline after accumulating N low-rated feedbacks (configurable via `FEEDBACK_RETRAINING_THRESHOLD`). |

### 3.6 System Health

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-050 | M | The system shall expose a `GET /health` endpoint returning `{"status": "healthy"}` with HTTP 200. |
| FR-051 | M | The system shall expose a `GET /version` endpoint returning git SHA, build timestamp, and environment. |
| FR-052 | S | The health endpoint shall include Gremlin and Cosmos connectivity status when `detailed=true` is supplied. |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement |
|----|-------------|
| NFR-001 | The `/ask` endpoint shall respond within **2 seconds** at the 95th percentile under nominal load (≤ 50 concurrent users). |
| NFR-002 | The `/feedback` endpoint shall respond within **500ms** at the 95th percentile. |
| NFR-003 | Single Gremlin vertex retrieval shall complete within **100ms**. |
| NFR-004 | Two-hop graph traversal shall complete within **500ms**. |
| NFR-005 | Document ingestion throughput shall support a minimum of **100 documents per minute**. |

### 4.2 Availability

| ID | Requirement |
|----|-------------|
| NFR-010 | The system shall achieve **99.9% monthly uptime** for production API endpoints. |
| NFR-011 | Planned maintenance windows shall not exceed **2 hours per month**. |
| NFR-012 | The system shall recover from a single AKS node failure within **5 minutes** without operator intervention. |

### 4.3 Scalability

| ID | Requirement |
|----|-------------|
| NFR-020 | The system shall scale horizontally from 2 to 10 pod replicas via the Horizontal Pod Autoscaler at 70% CPU utilisation. |
| NFR-021 | The knowledge graph shall support a minimum of **100,000 document vertices** without performance degradation beyond NFR-003/004. |

### 4.4 Reliability

| ID | Requirement |
|----|-------------|
| NFR-030 | All Gremlin queries shall implement retry logic with exponential backoff (max 3 attempts). |
| NFR-031 | The system shall not lose feedback data once HTTP 200 has been returned to the caller. |
| NFR-032 | The Gremlin client shall reconnect automatically following a network interruption. |

### 4.5 Maintainability

| ID | Requirement |
|----|-------------|
| NFR-040 | All public Python methods shall have Google-style docstrings. |
| NFR-041 | Code coverage shall not fall below **80%** as measured by `pytest-cov`. |
| NFR-042 | All linting checks (`ruff`, `bandit`) shall pass with zero errors in CI/CD. |

### 4.6 Portability

| ID | Requirement |
|----|-------------|
| NFR-050 | The application shall be containerised via Docker and deployable to any OCI-compliant Kubernetes cluster. |
| NFR-051 | Environment configuration shall be entirely externalised via environment variables — no hardcoded credentials. |

---

## 5. Interface Requirements

### 5.1 External API Interfaces

Refer to `docs/design/ICD.md` for complete contract definitions.

| Interface | Protocol | Format | Auth |
|-----------|----------|--------|------|
| `/ask` (inbound) | HTTPS/REST | JSON | JWT Bearer via APIM |
| `/feedback` (inbound) | HTTPS/REST | JSON | JWT Bearer via APIM |
| `/health` (inbound) | HTTPS/REST | JSON | None |
| Azure ML Endpoint (outbound) | HTTPS/REST | JSON | Bearer token |
| Cosmos DB Gremlin (outbound) | WSS/WebSocket | GraphSON v2 | Primary key |
| Azure Blob Storage (outbound) | HTTPS | Binary / JSON | Connection string |

### 5.2 User Interfaces

The system does not provide a direct user interface. Consumer applications integrate via the APIM gateway.

### 5.3 Hardware Interfaces

The system operates exclusively on cloud virtualised infrastructure. No physical hardware interfaces are defined.

---

## 6. Data Requirements

| ID | Requirement |
|----|-------------|
| DR-001 | All document data shall be stored in Azure Cosmos DB with partition key `/category`. |
| DR-002 | Feedback data shall be persisted as JSON blobs with UUID-named files in the `feedback` container. |
| DR-003 | The knowledge graph shall enforce the schema defined in `config/graph_schema.json`. |
| DR-004 | All stored data shall be encrypted at rest using Azure-managed keys (AES-256). |
| DR-005 | Feedback data shall be retained for a minimum of **90 days** as configured by `FEEDBACK_STORAGE_RETENTION_DAYS`. |

---

## 7. Security Requirements

| ID | Requirement |
|----|-------------|
| SR-001 | All inbound API calls shall be authenticated via JWT Bearer tokens validated by APIM. |
| SR-002 | The FastAPI application shall implement OAuth2 Bearer authentication middleware as a secondary defence layer. |
| SR-003 | All Gremlin queries shall use parameterised bindings — no string interpolation of user-supplied data. |
| SR-004 | All credentials shall be stored in Azure Key Vault — never in code, environment files, or container images. |
| SR-005 | TLS 1.2 minimum shall be enforced on all inbound and outbound connections. |
| SR-006 | The AKS pod security context shall run as non-root (UID 1000) with `readOnlyRootFilesystem: true`. |
| SR-007 | Security headers (X-Content-Type-Options, X-Frame-Options, HSTS, CSP) shall be injected by APIM. |

---

## 8. Compliance Requirements

| ID | Regulation | Requirement |
|----|-----------|-------------|
| CR-001 | POPIA Act No. 4 of 2013 | Personal information of learners and staff must not be logged, stored, or transmitted without explicit consent. |
| CR-002 | POPIA | A Privacy Impact Assessment (PIA) shall be completed before production launch. |
| CR-003 | NDP (National Development Plan) | The system shall support DBE strategic objectives for digital education transformation. |
| CR-004 | ISO/IEC 27001 | The security controls shall align with ISO 27001 Annex A control categories. |
| CR-005 | Azure Government SLA | The system shall operate exclusively within Azure regions compliant with South African data sovereignty requirements. |

---

## 9. Constraints

| ID | Constraint |
|----|-----------|
| CON-001 | The system must be implemented in Python 3.10+ and deployed on Azure. |
| CON-002 | The knowledge graph must use Azure Cosmos DB Gremlin API — no alternative graph database is permitted. |
| CON-003 | The APIM SKU must be `Developer_1` for development and `Standard_1` for production. |
| CON-004 | The system must operate within the `rg-dbe-ai-expert-system` resource group naming convention. |
| CON-005 | All infrastructure must be defined as code (Terraform) — manual portal provisioning is not permitted for production resources. |

---

## 10. Requirements Traceability Matrix

| Req ID | Description (summary) | Design Ref | Test Ref |
|--------|----------------------|------------|----------|
| FR-001 | Blob document ingestion | SDD §3.1, ICD §2.1 | STP TC-001 |
| FR-010 | Schema-validated graph | SDD §3.2, DDD §2 | STP TC-010 |
| FR-013 | Parameterised Gremlin | SecAD §4.1 | STP TC-013 |
| FR-030 | `/ask` endpoint | ICD §3.1, SDD §3.4 | STP TC-030 |
| FR-040 | `/feedback` endpoint | ICD §3.2, SDD §3.5 | STP TC-040 |
| NFR-001 | 2s p95 latency | SDD §5, PBR | STP TC-100 |
| NFR-010 | 99.9% availability | SAD §4, DRP | ATP AC-010 |
| SR-003 | Parameterised queries | SecAD §4.1, TMD | STP TC-013 |
| CR-001 | POPIA compliance | PIA, SecPlan | ATP AC-050 |

---

*End of SRS — DBE-SRS-001 v1.0.0*
