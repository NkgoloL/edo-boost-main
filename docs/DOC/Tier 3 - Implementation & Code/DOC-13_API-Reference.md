# API Reference
**Document ID:** DBE-API-013  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Base URL:** `https://api.dbe-expert.gov.za/api/v1`

---

## Authentication

All endpoints except `/health` and `/version` require a JWT Bearer token issued by Azure Active Directory.

```http
Authorization: Bearer <JWT_TOKEN>
```

Tokens are validated by APIM against Azure AD OpenID configuration. Invalid tokens receive `HTTP 401`.

---

## Rate Limiting

1000 requests per 60 seconds per IP address. Exceeded requests receive `HTTP 429`.

---

## Endpoints

### GET /health

Health check. No authentication required.

**Response 200:**
```json
{ "status": "healthy" }
```

---

### GET /version

Returns application version metadata.

**Response 200:**
```json
{
  "version": "0.1.0",
  "git_sha": "abc1234",
  "environment": "production",
  "build_timestamp": "2026-04-29T12:00:00Z"
}
```

---

### POST /ask

Submit a policy query to the expert system.

**Request Body:**
```json
{
  "query": "string (required, non-empty, max 2000 chars)",
  "user_id": "string (optional, default: 'anonymous')"
}
```

**Response 200 — `AgentResponse`:**
```json
{
  "response": "Based on DBE Infrastructure Circular 12/2024, rural schools require a minimum of 10Mbps...",
  "sources": [
    "Internal Knowledge Base",
    "Azure ML Endpoint"
  ],
  "confidence": 0.98
}
```

**Error Responses:**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid JWT |
| 422 | Request body validation failure |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

**Example cURL:**
```bash
curl -X POST https://api.dbe-expert.gov.za/api/v1/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are school infrastructure funding criteria?", "user_id": "analyst_007"}'
```

---

### POST /feedback

Submit a satisfaction rating for a previous response.

**Request Body:**
```json
{
  "query": "string (required)",
  "response": "string (required)",
  "rating": "integer (required, 1–5 inclusive)"
}
```

**Response 200:**
```json
{ "status": "feedback received" }
```

**Error Responses:**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid JWT |
| 422 | Rating out of range [1–5] or missing fields |
| 500 | Blob storage write failure |

**Example cURL:**
```bash
curl -X POST https://api.dbe-expert.gov.za/api/v1/feedback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Infrastructure criteria?", "response": "Schools require...", "rating": 4}'
```

---

## Data Models

### QueryRequest
```
query    : string  — The policy question (required)
user_id  : string  — Caller identity (optional, default: "anonymous")
```

### AgentResponse
```
response   : string  — Synthesised policy recommendation
sources    : string[] — Knowledge sources used in the response
confidence : float   — Confidence score [0.0, 1.0]
```

### FeedbackPayload
```
query    : string  — Original query
response : string  — Response that was rated
rating   : integer — Satisfaction rating [1, 5]
```

---

## Internal Python API

### `KnowledgeGraphManager`

```python
manager = KnowledgeGraphManager(endpoint, key, database_name, graph_name)

# Write
manager.initialize_graph()
manager.add_document_node(doc_id, doc_name, category_id)

# Read
docs = manager.get_documents_by_category(category_id)    # List[Dict]
docs = manager.search_documents_by_keyword(keyword)       # List[Dict]
cats = manager.get_related_categories(doc_id)             # List[Dict]
agents = manager.get_agent_triggers(query_type)           # List[Dict]

# Validation
is_valid = manager.validate_schema("vertex", "Document")  # bool
schema   = manager.get_schema_definition()                 # Dict
reachable = manager.health_check()                        # bool

# Lifecycle
manager.close()
```

### `KnowledgeIngestionPipeline`

```python
pipeline = KnowledgeIngestionPipeline(
    cosmos_endpoint, cosmos_key, database_name, container_name,
    blob_connection_string=None
)

pipeline.ingest_from_blob(container_name, blob_name)
pipeline.ingest_document(doc_path)
pipeline.upsert_to_cosmos(data_dict, source="filename.json")
```

### `ExpertModel` (Strategy Interface)

```python
# Async predict — implemented by AzureMLExpertModel and BaselinePolicyModel
result: str = await model.predict(query="...", context="...")
```

---

## OpenAPI Specification

The live OpenAPI (Swagger) UI is available at:
- Development: `http://localhost:8000/docs`
- Staging: (disabled for security)
- Production: (disabled for security)

OpenAPI JSON export: `http://localhost:8000/openapi.json`

---

*End of API Reference — DBE-API-013 v1.0.0*
