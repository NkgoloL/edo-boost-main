# Concept of Operations (ConOps)
**Document ID:** DBE-ConOps-003  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** Internal — Controlled

---

## 1. Background and Mission Context

The South African Department of Basic Education (DBE) manages policy for approximately **13 million learners** across **24,000 schools**. Policy analysts, district officials, and school administrators must navigate a complex and frequently updated corpus of educational legislation, curriculum frameworks, and infrastructure standards.

Currently, policy retrieval is manual — analysts search through static PDFs and email chains. The result is inconsistent advice, delayed decisions, and under-utilisation of institutional knowledge.

The **DBE AI Expert System** transforms this by providing an always-available, AI-driven advisory service that reasons over a live knowledge graph of DBE policy documents.

---

## 2. Operational Scenarios

### Scenario A — Policy Query (Primary Use Case)

1. A district official logs into the DBE portal.
2. They submit a natural-language query: *"What are the minimum connectivity requirements for a rural school applying for e-learning infrastructure funding?"*
3. The system retrieves relevant policy documents from the knowledge graph.
4. The expert model synthesises a response citing the applicable policy sections.
5. The official receives a structured recommendation with source citations within 2 seconds.
6. They rate the response (1–5 stars) to provide quality signal.

### Scenario B — Document Ingestion (Data Engineer)

1. A data engineer uploads a new policy circular to Azure Blob Storage.
2. The ingestion pipeline automatically processes the document and upserts it into Cosmos DB.
3. The graph manager links the document vertex to its corresponding category.
4. Within minutes, the document is queryable via the `/ask` endpoint.

### Scenario C — Automated Model Improvement

1. Over a two-week period, 15 policy queries receive ratings below 3.
2. The feedback threshold is exceeded.
3. The system automatically submits a retraining job to Azure ML.
4. The improved model is validated, registered, and promoted to production.
5. Subsequent queries benefit from improved accuracy without manual intervention.

### Scenario D — Incident Response

1. Azure Monitor detects a spike in HTTP 5xx responses from the orchestration service.
2. An alert fires to the DBE IT operations team.
3. The operations engineer consults the `OpsMan.md` runbook.
4. The issue is triaged, resolved, and post-incident documentation is updated.

---

## 3. Operational Environment

| Dimension | Description |
|-----------|-------------|
| Geography | South Africa (primary), Azure East US (DR) |
| Users | ~50 concurrent analysts at peak; ~500 daily active users |
| Access Method | REST API via APIM gateway; future: DBE web portal |
| Network | Public internet via HTTPS/TLS 1.2+; internal AKS VNet |
| Hours of Operation | 24/7; maintenance windows Sunday 00:00–02:00 SAST |

---

## 4. Roles and Responsibilities

| Role | Responsibilities |
|------|-----------------|
| Policy Analyst | Submit queries, rate responses, escalate inaccuracies |
| System Administrator | Monitor dashboards, respond to alerts, manage deployments |
| Data Engineer | Manage blob ingestion, maintain document quality |
| ML Engineer | Maintain expert models, review retraining results, manage lineage |
| Security Officer | Review audit logs, manage Key Vault, approve ATO |

---

## 5. Transition Concept

| Phase | State | Timeline |
|-------|-------|----------|
| Phase 1 | Foundation: Infrastructure provisioned, CI/CD operational | Complete |
| Phase 2 | Intelligence: Knowledge graph + expert models operational | In Progress |
| Phase 3 | Integration: APIM + AKS deployment pipeline live | Next sprint |
| Phase 4 | Optimisation: Feedback loop + LLM reasoning active | +6 weeks |
| Phase 5 | Production: Security-hardened, compliance-approved, ATO issued | +10 weeks |

---

*End of ConOps — DBE-ConOps-003 v1.0.0*
