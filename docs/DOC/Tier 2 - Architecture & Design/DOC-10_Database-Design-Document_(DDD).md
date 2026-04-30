# Database Design Document (DDD)
**Document ID:** DBE-DDD-010  
**Version:** 1.0.0  
**Date:** 2026-04-29

---

## 1. Data Store Overview

The system uses two distinct Azure Cosmos DB APIs on the same account:

| Store | API | Container | Purpose |
|-------|-----|-----------|---------|
| Document Store | SQL (Core) | `IntelligenceStore` | Flat document storage, keyword search |
| Knowledge Graph | Gremlin | `ExpertGraph` | Relationship traversal and reasoning |
| Feedback Store | Azure Blob | `feedback/` | Unstructured feedback JSON blobs |

---

## 2. Cosmos DB SQL — Document Store

### 2.1 Account Configuration

| Parameter | Value |
|-----------|-------|
| Account Name | `cosmos-dbe-expert-{env}` |
| API | Core (SQL) |
| Consistency | Session |
| Throughput | 400 RU/s (autoscale in production) |
| Backup | Continuous (7-day PITR) |
| Encryption | Azure-managed keys (AES-256) |

### 2.2 Container: `IntelligenceStore`

| Parameter | Value |
|-----------|-------|
| Partition Key | `/partitionKey` |
| Indexing Policy | All paths indexed (default — optimise in Phase 4) |
| TTL | Not set (documents retained indefinitely) |

### 2.3 Document Schema

```json
{
  "id":           "string (required, unique)",
  "partitionKey": "string (required, = category value)",
  "source":       "string (blob name or file path)",
  "title":        "string",
  "category":     "string (policy | infrastructure | curriculum | ...)",
  "content":      "string (document body text)",
  "created_at":   "ISO 8601 timestamp",
  "updated_at":   "ISO 8601 timestamp",
  "_ts":          "integer (Cosmos system timestamp)",
  "_etag":        "string (Cosmos optimistic concurrency)"
}
```

### 2.4 Query Patterns

| Pattern | Query | Index Required |
|---------|-------|---------------|
| Get by ID | `SELECT * FROM c WHERE c.id = @id` | Default |
| Get by category | `SELECT * FROM c WHERE c.partitionKey = @cat` | Partition key |
| Full-text keyword | `SELECT * FROM c WHERE CONTAINS(c.content, @kw)` | Custom composite (Phase 4) |

---

## 3. Cosmos DB Gremlin — Knowledge Graph

### 3.1 Graph Configuration

| Parameter | Value |
|-----------|-------|
| Database | `KnowledgeDB` |
| Graph Container | `ExpertGraph` |
| Partition Key | `/category` |
| Throughput | 400 RU/s |

### 3.2 Vertex Schema

All vertices are defined in `config/graph_schema.json`.

#### ExpertSystem Vertex
```
Properties: id (PK), name, version
Example:    id="dbe_root", name="DBE AI Expert System", version="1.0"
```

#### Category Vertex
```
Properties: id (PK), name, description
Examples:   id="policy", id="infrastructure", id="curriculum"
```

#### Document Vertex
```
Properties: id (PK), name, source, category, content
```

#### Agent Vertex
```
Properties: id (PK), name, type
Example:    id="policy_agent", name="Policy Expert", type="AzureML"
```

### 3.3 Edge Schema

| Edge | From | To | Properties |
|------|------|-----|------------|
| `manages` | ExpertSystem | Category | confidence, timestamp, weight |
| `contains` | Category | Document | confidence, timestamp, weight |
| `references` | Document | Document | confidence, timestamp, weight |
| `triggers` | Category | Agent | confidence, timestamp, weight |

### 3.4 Graph Initialisation State

```
(ExpertSystem: dbe_root)
    ──[manages]──► (Category: policy)
    ──[manages]──► (Category: infrastructure)

After document ingestion:
(Category: policy) ──[contains]──► (Document: policy_001)
(Category: policy) ──[contains]──► (Document: policy_002)
```

### 3.5 Key Gremlin Traversals

```groovy
// Retrieve all documents in a category
g.V().has('id', 'policy').out('contains').hasLabel('Document').valueMap(true)

// Two-hop: get all categories a document belongs to
g.V().has('id', 'doc_001').in('contains').hasLabel('Category').valueMap(true)

// Get agents triggered by a category
g.V().has('Category', 'id', 'policy').out('triggers').hasLabel('Agent').valueMap(true)
```

---

## 4. Azure Blob Storage — Feedback Store

| Parameter | Value |
|-----------|-------|
| Account | `stdbeexpert{env}` |
| Container | `feedback` |
| Access | Private (no public blob access) |
| Redundancy | LRS (dev) / GRS (prod) |
| Retention | 90 days (lifecycle management policy) |

### 4.1 Blob Schema

**Filename:** `{uuid4()}.json`  
**Content:**
```json
{
  "query": "string",
  "response": "string",
  "rating": "integer (1–5)"
}
```

---

## 5. Data Migration & Seeding

Initial graph seeding is performed by `KnowledgeGraphManager.initialize_graph()` which is safe to re-run due to the `coalesce()` idempotency pattern. Document seeding is performed by the ingestion pipeline processing blobs in the `documents` container.

---

*End of DDD — DBE-DDD-010 v1.0.0*
