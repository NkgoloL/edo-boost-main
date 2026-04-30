# Software Design Document (SDD)
**Document ID:** DBE-SDD-007  
**Version:** 1.0.0  
**Date:** 2026-04-29  
**Classification:** Internal — Controlled

---

## Document Control

| Field | Detail |
|-------|--------|
| Prepared By | DBE AI Expert System Team |
| Parent Documents | SRS (DBE-SRS-001), SSS (DBE-SSS-002) |
| Based On | MIL-STD-498 SDD DID |

---

## 1. Introduction

This Software Design Document specifies the detailed internal design of the DBE AI Expert System. It covers module decomposition, class responsibilities, method signatures, data flow, design patterns employed, and known design decisions with their rationale.

---

## 2. Design Overview

### 2.1 Architectural Style

The system follows a **layered microservice architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────┐
│            API Gateway (APIM)               │  ← Security boundary
├─────────────────────────────────────────────┤
│         Orchestration Layer (FastAPI)       │  ← Request coordination
├──────────────────┬──────────────────────────┤
│  Knowledge Graph │   Expert Model Suite     │  ← Domain intelligence
│  (Gremlin)       │   (Azure ML / Baseline)  │
├──────────────────┴──────────────────────────┤
│         Ingestion Pipeline                  │  ← Data acquisition
├─────────────────────────────────────────────┤
│    Azure Infrastructure (Cosmos, Blob, ML)  │  ← Platform services
└─────────────────────────────────────────────┘
```

### 2.2 Design Principles

- **Dependency Inversion:** `ExpertModel` ABC decouples orchestration from specific model implementations.
- **Single Responsibility:** Each class owns one concern (pipeline ingests, graph manages, orchestrator coordinates).
- **Fail-Safe Defaults:** Missing Azure credentials fall back to `BaselinePolicyModel`, never crash.
- **Parameterised Queries:** All Gremlin queries use binding dictionaries — no string interpolation.
- **Idempotency:** All write operations are safe to retry (upsert, coalesce graph patterns).
- **Externalized Configuration:** All environment-specific values injected via environment variables.

---

## 3. Module Design

### 3.1 `src/ingestion/pipeline.py` — `KnowledgeIngestionPipeline`

**Purpose:** Acquire and normalise documents from Blob Storage and Cosmos DB.

**Constructor:**
```python
def __init__(
    self,
    cosmos_endpoint: str,
    cosmos_key: str,
    database_name: str,
    container_name: str,
    blob_connection_string: Optional[str] = None
)
```

**Key Methods:**

| Method | Inputs | Outputs | Side Effects |
|--------|--------|---------|--------------|
| `ingest_from_blob(container, blob_name)` | container name, blob path | None | Upserts to Cosmos |
| `ingest_document(doc_path)` | local file path | None | Upserts to Cosmos |
| `upsert_to_cosmos(data, source)` | dict, source string | None | Cosmos upsert |

**Design Decision — Partition Key:**  
`partitionKey` is derived from `data.get('category', 'default')` to enable efficient category-scoped queries. This is not user-configurable at the method level to enforce schema consistency.

---

### 3.2 `src/ingestion/graph_manager.py` — `KnowledgeGraphManager`

**Purpose:** Schema-validated graph operations with lazy, fault-tolerant Gremlin client.

**Constructor:**
```python
def __init__(
    self,
    endpoint: str,
    key: str,
    database_name: str,
    graph_name: str,
    *,
    max_retries: int = 3,
    pool_size: int = 4
)
```

**Key Methods:**

| Method | Description | Pattern |
|--------|-------------|---------|
| `_get_client()` | Lazy Gremlin client factory | Lazy init |
| `_submit(query, bindings)` | Parameterised query execution | Retry + backoff |
| `initialize_graph()` | Idempotent graph bootstrap | `coalesce()` upsert |
| `add_document_node(doc_id, doc_name, category_id)` | Document vertex + edge creation | Pre-flight check |
| `get_documents_by_category(category_id)` | Category → documents traversal | 1-hop |
| `search_documents_by_keyword(keyword)` | Property scan + filter | Full scan |
| `get_related_categories(doc_id)` | Document → categories traversal | 1-hop reverse |
| `get_agent_triggers(query_type)` | Category → agent resolution | 1-hop |
| `validate_schema(element_type, label, properties)` | Schema enforcement | Config-driven |
| `health_check()` | Connectivity verification | Independent probe |
| `close()` | Pool graceful shutdown | Cleanup |

**Design Decision — Lazy Initialisation:**  
The Gremlin client is not instantiated in `__init__()`. This prevents pod startup failures when Cosmos DB is temporarily unreachable during rolling deployments. The `health_check()` method should be called by the readiness probe, not `__init__()`.

**Design Decision — Retry with Tenacity:**  
`@retry` from the `tenacity` library is applied to `_submit()` with exponential backoff targeting `GremlinServerError`, `ConnectionError`, and `TimeoutError`. This handles transient WebSocket disconnections without surfacing them to callers.

---

### 3.3 `src/models/expert_model.py` — Expert Model Suite

**Abstract Base:**
```python
class ExpertModel(ABC):
    @abstractmethod
    async def predict(self, query: str, context: str) -> str: ...
```

**Implementations:**

| Class | Activation Condition | Inference Target |
|-------|---------------------|-----------------|
| `AzureMLExpertModel` | `AZURE_ML_ENDPOINT` + `AZURE_ML_KEY` set | Azure ML Online Endpoint |
| `BaselinePolicyModel` | Fallback (credentials absent) | Heuristic keyword matching |

**Design Decision — Strategy Pattern:**  
The `ExpertModel` ABC implements the Strategy design pattern. `get_expert_model()` in `main.py` acts as the factory, selecting the concrete strategy at startup based on environment variables. Adding a new expert model requires only a new class implementing `predict()` — no orchestration code changes.

---

### 3.4 `src/orchestration/main.py` — FastAPI Application

**Application Startup:**
```python
settings = AppSettings()          # Pydantic-settings from env vars
expert_model = get_expert_model() # Strategy selection
app = FastAPI(...)
```

**Endpoint Designs:**

| Endpoint | Method | Auth | Handler Logic |
|----------|--------|------|---------------|
| `/health` | GET | None | Return static healthy status |
| `/version` | GET | None | Return git SHA + env |
| `/ask` | POST | JWT | retrieve_context() → expert_model.predict() → perform_reasoning() |
| `/feedback` | POST | JWT | FeedbackLoopManager.process_feedback() |

**`retrieve_context()` — Required Implementation (Phase 2/3):**
```python
async def retrieve_context(query: str) -> str:
    # Phase 3 target implementation:
    graph = KnowledgeGraphManager(...)  # injected dependency
    docs = graph.search_documents_by_keyword(query)
    return "\n".join(d.get("content", [""])[0] for d in docs)
```

**Design Decision — Dependency Injection (Phase 3):**  
`KnowledgeGraphManager` should be injected as a FastAPI dependency using `Depends()` rather than instantiated inside request handlers. This enables testability and connection lifecycle management.

---

### 3.5 `src/optimization/feedback_loop.py` — `FeedbackLoopManager`

**Key Design:**  
Blob upload uses `overwrite=True` with a UUID-named file to guarantee idempotency. The retraining trigger is fire-and-forget — pipeline failures do not fail the feedback endpoint.

---

## 4. Error Handling Strategy

| Layer | Strategy |
|-------|----------|
| FastAPI endpoints | `try/except` wrapping all handler logic; `HTTPException` with structured detail |
| Gremlin client | `tenacity` retry (3 attempts, exponential backoff) |
| Blob operations | Log error and continue — feedback loss is preferable to endpoint failure |
| Azure ML inference | Catch all exceptions; return structured error string; log via `logger.error` |

---

## 5. Performance Design

| Concern | Design Decision |
|---------|----------------|
| Gremlin connection pooling | `pool_size=4` (configurable) — reuses WebSocket connections |
| Async inference | `httpx.AsyncClient` for non-blocking Azure ML calls |
| Caching (Phase 4) | Redis cache keyed on query hash with TTL from `CACHE_TTL_SECONDS` |
| Bulk ingestion (Phase 4) | `execute_item_batch()` for Cosmos multi-document upserts |

---

## 6. Logging Design

All modules use `logging.getLogger(__name__)` with the `python-json-logger` formatter in production:

```python
{
  "timestamp": "2026-04-29T12:00:00Z",
  "level": "INFO",
  "logger": "src.ingestion.graph_manager",
  "message": "Document vertex added to graph",
  "document_id": "doc_001",
  "category_id": "policy",
  "duration_ms": 42
}
```

Log levels follow the principle:
- `DEBUG`: Gremlin query strings (development only)
- `INFO`: Successful operations with key identifiers
- `WARNING`: Recoverable anomalies (schema property warnings, fallback activations)
- `ERROR`: Failed operations with full exception context

---

## 7. Configuration Design

All configuration is managed via `pydantic-settings` `AppSettings` class reading from environment variables with `.env` file fallback for local development.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_ML_ENDPOINT` | No | None | Triggers Azure ML model |
| `COSMOS_ENDPOINT` | Yes (prod) | None | Cosmos DB SQL API |
| `COSMOS_GREMLIN_ENDPOINT` | Yes (prod) | None | Gremlin endpoint |
| `FEEDBACK_RETRAINING_THRESHOLD` | No | 10 | Low-rating trigger count |
| `CACHE_TTL_SECONDS` | No | 3600 | Redis cache TTL |
| `PORT` | No | 8000 | FastAPI listen port |

---

*End of SDD — DBE-SDD-007 v1.0.0*
