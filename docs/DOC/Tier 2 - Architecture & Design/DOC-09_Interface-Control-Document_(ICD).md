# Interface Control Document (ICD)
**Document ID:** DBE-ICD-009  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** Internal — Controlled

---

## 1. Introduction

This ICD defines all interfaces between subsystems and between the DBE AI Expert System and external services. Each interface is assigned an ID, protocol, data format, authentication mechanism, and error contract.

---

## 2. Internal Interfaces

### IF-01: Blob Storage → Ingestion Pipeline

| Field | Detail |
|-------|--------|
| **Interface ID** | IF-01 |
| **Provider** | Azure Blob Storage |
| **Consumer** | `KnowledgeIngestionPipeline` |
| **Protocol** | HTTPS (Azure SDK) |
| **Auth** | Connection string / Managed Identity |
| **Data Format** | JSON blobs |
| **Schema** | `{ "id"?: string, "title": string, "category": string, "content"?: string }` |
| **Error Handling** | `BlobNotFoundError` → log and skip; `Exception` → log and raise |

---

### IF-02: Ingestion Pipeline → Cosmos DB (SQL API)

| Field | Detail |
|-------|--------|
| **Interface ID** | IF-02 |
| **Protocol** | HTTPS (Azure Cosmos SDK) |
| **Auth** | Primary key |
| **Operation** | `container.upsert_item(data)` |
| **Partition Key** | `/partitionKey` (set to `data["category"]`) |
| **Throughput** | 400 RU/s (configurable via `COSMOS_THROUGHPUT`) |
| **Error Handling** | Raise; caller handles retry |

---

### IF-03: Knowledge Graph ↔ Orchestration Layer

| Field | Detail |
|-------|--------|
| **Interface ID** | IF-03 |
| **Protocol** | In-process Python method calls |
| **Invocations** | `search_documents_by_keyword(keyword)` → `List[Dict]` |
| | `get_documents_by_category(category_id)` → `List[Dict]` |
| | `add_document_node(doc_id, doc_name, category_id)` → None |
| **Error Contract** | `ValueError` for schema/validation failures; `GremlinServerError` propagated |

---

### IF-04: Orchestration → Expert Model

| Field | Detail |
|-------|--------|
| **Interface ID** | IF-04 |
| **Protocol** | In-process async Python call |
| **Method** | `await expert_model.predict(query: str, context: str) -> str` |
| **Timeout** | 15 seconds (`httpx.AsyncClient(timeout=15.0)`) |
| **Error Contract** | Exception caught; error string returned to caller |

---

### IF-05: Expert Model → Azure ML Endpoint (External)

| Field | Detail |
|-------|--------|
| **Interface ID** | IF-05 |
| **Protocol** | HTTPS POST |
| **URL** | `AZURE_ML_ENDPOINT` (env var) |
| **Auth** | `Authorization: Bearer {AZURE_ML_KEY}` |
| **Request Body** | `{ "input_data": { "columns": ["query", "context"], "data": [[query, context]] } }` |
| **Response** | `{ "result": string }` or `[string]` |
| **Error Handling** | HTTP errors → log + return error string |

---

### IF-06: Orchestration → Feedback Manager

| Field | Detail |
|-------|--------|
| **Interface ID** | IF-06 |
| **Protocol** | In-process Python call |
| **Method** | `manager.process_feedback(query, response, rating)` |
| **Guarantee** | Fire-and-forget — feedback errors do not fail `/feedback` HTTP response |

---

### IF-07: Feedback Manager → Azure Blob Storage

| Field | Detail |
|-------|--------|
| **Interface ID** | IF-07 |
| **Protocol** | HTTPS (Azure SDK) |
| **Container** | `AZURE_STORAGE_CONTAINER_FEEDBACK` (default: `feedback`) |
| **Blob Name** | `{uuid4()}.json` |
| **Content** | `{ "query": string, "response": string, "rating": int }` |
| **Overwrite** | `True` — safe for retry |

---

### IF-08: Feedback Manager → Azure ML Pipeline

| Field | Detail |
|-------|--------|
| **Interface ID** | IF-08 |
| **Protocol** | Azure ML SDK (`MLClient.jobs.create_or_update`) |
| **Trigger Condition** | Feedback count with `rating < 3 >= FEEDBACK_RETRAINING_THRESHOLD` |
| **Error Handling** | Pipeline submission failure logged; does not fail feedback path |

---

## 3. External API Interfaces

### IF-10: External Client → APIM → `/ask`

**Endpoint:** `POST https://api.dbe-expert.gov.za/api/v1/ask`

**Request:**
```json
{
  "query": "What are the connectivity requirements for rural schools?",
  "user_id": "analyst_007"
}
```

**Response (HTTP 200):**
```json
{
  "response": "Based on DBE Infrastructure Circular 12/2024, rural schools...",
  "sources": ["Internal Knowledge Base", "Azure ML Endpoint"],
  "confidence": 0.98
}
```

**Error Responses:**

| HTTP Code | Condition | Body |
|-----------|-----------|------|
| 401 | Missing or invalid JWT | `{"detail": "Unauthorized"}` |
| 422 | Malformed request body | `{"detail": [{"loc": [...], "msg": "..."}]}` |
| 429 | Rate limit exceeded (1000 req/60s) | `{"detail": "Rate limit exceeded"}` |
| 500 | Internal server error | `{"detail": "Internal error description"}` |

---

### IF-11: External Client → APIM → `/feedback`

**Endpoint:** `POST https://api.dbe-expert.gov.za/api/v1/feedback`

**Request:**
```json
{
  "query": "What are the connectivity requirements?",
  "response": "Rural schools require minimum 10Mbps...",
  "rating": 4
}
```

**Response (HTTP 200):**
```json
{ "status": "feedback received" }
```

**Validation Rules:**
- `rating` must be integer in range [1, 5] inclusive.
- `query` and `response` must be non-empty strings.

---

### IF-12: External Client → `/health`

**Endpoint:** `GET /health`  
**Auth:** None  
**Response:** `{ "status": "healthy" }` (HTTP 200)

---

### IF-13: External Client → `/version`

**Endpoint:** `GET /version`  
**Auth:** None  
**Response:** `{ "version": "0.1.0", "git_sha": "abc123", "environment": "production", "build_timestamp": "2026-04-29T12:00:00Z" }`

---

## 4. Interface Change Control

Any modification to an interface listed in this document requires:
1. An approved Change Request (ref: `docs/management/CMP.md`).
2. Version bump to this ICD.
3. Update to affected consumer tests.
4. Notification to all downstream teams minimum 5 business days before deployment.

---

*End of ICD — DBE-ICD-009 v1.0.0*
