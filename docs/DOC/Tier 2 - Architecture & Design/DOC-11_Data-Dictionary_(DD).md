# Data Dictionary (DD)
**Document ID:** DBE-DD-011  
**Version:** 1.0.0  
**Date:** 2026-04-29

---

## 1. Canonical Data Entities

### 1.1 Document

| Field | Type | Nullable | Description | Example |
|-------|------|----------|-------------|---------|
| `id` | string | No | Globally unique document identifier | `"policy_001"` |
| `partitionKey` | string | No | Cosmos DB partition key, equals `category` | `"policy"` |
| `source` | string | No | Origin blob name or file path | `"policy_framework_2024.json"` |
| `title` | string | Yes | Human-readable document title | `"National Curriculum Framework"` |
| `category` | string | No | Document classification | `"policy"` / `"infrastructure"` |
| `content` | string | Yes | Full document body text | `"Guidelines for..."` |
| `created_at` | ISO 8601 | Yes | Ingestion timestamp | `"2026-04-29T12:00:00Z"` |
| `updated_at` | ISO 8601 | Yes | Last modification timestamp | `"2026-04-29T12:00:00Z"` |

**Allowed `category` values:** `policy`, `infrastructure`, `curriculum`, `governance`, `default`

---

### 1.2 QueryRequest

| Field | Type | Nullable | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `query` | string | No | Non-empty, max 2000 chars | Natural-language policy question |
| `user_id` | string | Yes | Default: `"anonymous"` | Caller identity for audit logging |

---

### 1.3 AgentResponse

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `response` | string | No | Synthesised policy recommendation |
| `sources` | string[] | No | List of knowledge sources used |
| `confidence` | float | No | Confidence score in range [0.0, 1.0] |

---

### 1.4 FeedbackPayload

| Field | Type | Nullable | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `query` | string | No | Non-empty | The original query submitted |
| `response` | string | No | Non-empty | The response that was rated |
| `rating` | integer | No | Range [1, 5] inclusive | User satisfaction rating |

---

### 1.5 Graph Vertex — ExpertSystem

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | Fixed value: `"dbe_root"` |
| `name` | string | `"DBE AI Expert System"` |
| `version` | string | Semantic version string |

### 1.6 Graph Vertex — Category

| Property | Type | Allowed Values |
|----------|------|----------------|
| `id` | string | `policy`, `infrastructure`, `curriculum`, `governance` |
| `name` | string | Human-readable label |
| `description` | string | Category purpose description |

### 1.7 Graph Vertex — Document

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | Matches Cosmos DB document `id` |
| `name` | string | Document title |
| `source` | string | Originating blob or file |
| `category` | string | Parent category id |

### 1.8 Graph Vertex — Agent

| Property | Type | Allowed Values |
|----------|------|----------------|
| `id` | string | Unique agent identifier |
| `name` | string | Human-readable name |
| `type` | string | `AzureML`, `Baseline`, `LLM` |

### 1.9 Graph Edge Properties (all edge types)

| Property | Type | Description |
|----------|------|-------------|
| `confidence` | float | Relationship confidence [0.0, 1.0] |
| `timestamp` | ISO 8601 | Edge creation time |
| `weight` | float | Traversal scoring weight |

---

## 2. Environment Variable Glossary

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `AZURE_ML_ENDPOINT` | URL | No | None | Azure ML Online Endpoint URL |
| `AZURE_ML_KEY` | string | No | None | Azure ML bearer token |
| `COSMOS_ENDPOINT` | URL | Prod | None | Cosmos DB SQL API endpoint |
| `COSMOS_KEY` | string | Prod | None | Cosmos DB primary key |
| `COSMOS_GREMLIN_ENDPOINT` | URL | Prod | None | Gremlin WSS endpoint |
| `COSMOS_GREMLIN_KEY` | string | Prod | None | Gremlin primary key |
| `COSMOS_DATABASE_NAME` | string | No | `KnowledgeDB` | Database name |
| `COSMOS_CONTAINER_NAME` | string | No | `IntelligenceStore` | Container name |
| `AZURE_STORAGE_CONNECTION_STRING` | string | Prod | None | Blob storage connection |
| `AZURE_STORAGE_CONTAINER_FEEDBACK` | string | No | `feedback` | Feedback blob container |
| `FEEDBACK_RETRAINING_THRESHOLD` | integer | No | `10` | Low-rating trigger count |
| `CACHE_TTL_SECONDS` | integer | No | `3600` | Redis cache TTL |
| `PORT` | integer | No | `8000` | FastAPI listen port |
| `ENVIRONMENT` | string | No | `development` | `development` / `staging` / `production` |
| `LOG_LEVEL` | string | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `JWT_SECRET_KEY` | string | Prod | None | JWT signing secret |
| `JWT_ALGORITHM` | string | No | `HS256` | JWT algorithm |
| `KEY_VAULT_NAME` | string | Prod | None | Azure Key Vault resource name |

---

*End of DD — DBE-DD-011 v1.0.0*
