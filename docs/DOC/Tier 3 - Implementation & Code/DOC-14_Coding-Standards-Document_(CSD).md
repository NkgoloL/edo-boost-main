# Coding Standards Document (CSD)
**Document ID:** DBE-CSD-014  
**Version:** 1.0.0  
**Date:** 2026-04-29

---

## 1. Language and Runtime

| Item | Standard |
|------|----------|
| Language | Python 3.10+ |
| Type Hints | Mandatory on all public function signatures |
| Async | `async/await` for all I/O-bound operations |
| String Formatting | f-strings for display; **binding dicts for all query construction** |

---

## 2. Docstring Standard — Google Style

All public classes, methods, and module-level functions must have Google-style docstrings conforming to PEP 257.

**Class docstring:**
```python
class KnowledgeGraphManager:
    """Schema-validated Gremlin graph client with lazy initialisation.

    Provides parameterised query execution, retry logic, and full
    schema validation loaded from config/graph_schema.json at runtime.

    Attributes:
        _schema: Loaded schema definition dictionary.
        _client: Lazily-initialised Gremlin client instance.
    """
```

**Method docstring:**
```python
def validate_schema(
    self,
    element_type: str,
    label: str,
    properties: Optional[List[str]] = None,
) -> bool:
    """Validate a graph element against the runtime schema definition.

    Args:
        element_type: Graph element class — must be 'vertex' or 'edge'.
        label: The element label to validate against the schema registry.
        properties: Optional list of property names to validate for label.
            Unknown properties emit a WARNING but do not fail validation.

    Returns:
        True if the label is registered in the schema, False otherwise.

    Raises:
        TypeError: If element_type is neither 'vertex' nor 'edge'.

    Example:
        >>> manager = KnowledgeGraphManager(endpoint, key, "db", "graph")
        >>> manager.validate_schema("vertex", "Document")
        True
        >>> manager.validate_schema("vertex", "InvalidType")
        False
    """
```

---

## 3. Naming Conventions

| Construct | Convention | Example |
|-----------|-----------|---------|
| Module | `snake_case` | `graph_manager.py` |
| Class | `PascalCase` | `KnowledgeGraphManager` |
| Method / Function | `snake_case` | `get_documents_by_category` |
| Private method | `_snake_case` | `_submit`, `_get_client` |
| Constant | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |
| Variable | `snake_case` | `category_id` |
| Type alias | `PascalCase` | `DocumentMap = Dict[str, Any]` |

---

## 4. Logging Standards

```python
# ✅ Correct — lazy % formatting
logger.info("Document '%s' ingested to category '%s'.", doc_id, category_id)
logger.error("Gremlin query failed: %s", exc)

# ❌ Wrong — eager f-string evaluation regardless of log level
logger.info(f"Document {doc_id} ingested")  # PROHIBITED
```

| Level | Usage |
|-------|-------|
| `DEBUG` | Gremlin query strings, raw payloads (dev only) |
| `INFO` | Successful operations with key identifiers |
| `WARNING` | Recoverable anomalies, fallback activations, schema property mismatches |
| `ERROR` | Failed operations with full exception context |
| `CRITICAL` | System cannot continue — must page on-call |

**Production log format (JSON):**
```json
{
  "timestamp": "2026-04-29T12:00:00Z",
  "level": "INFO",
  "logger": "src.ingestion.graph_manager",
  "message": "Document vertex added",
  "document_id": "doc_001",
  "duration_ms": 42
}
```

---

## 5. Security Coding Rules

| Rule | Enforcement |
|------|-------------|
| **No f-string in Gremlin queries** | Ruff rule + Bandit S608 |
| **No hardcoded credentials** | Bandit B105, B106 + trufflehog in CI |
| **No `eval()` or `exec()`** | Bandit B307 |
| **All external inputs validated by Pydantic** | Code review gate |
| **Exception messages must not expose internal paths or stack traces to API callers** | Code review gate |

---

## 6. Testing Standards

```python
# ✅ Correct async test pattern (pytest-asyncio)
@pytest.mark.asyncio
async def test_expert_model_inference():
    model = BaselinePolicyModel()
    result = await model.predict("infrastructure query", "context")
    assert "Infrastructure Recommendation" in result

# ❌ Deprecated pattern (Python 3.10+)
loop = asyncio.get_event_loop()
result = loop.run_until_complete(model.predict(...))  # PROHIBITED
```

- Every new public method requires a unit test.
- Every new endpoint requires an integration test.
- Coverage floor: 80% (enforced by `--cov-fail-under=80` in CI).
- No mocking at the service layer — use MSW or `pytest-httpx` to mock at the network layer.

---

## 7. Import Organisation

```python
# Standard library
import json
import logging
from typing import Any, Dict, List, Optional

# Third-party
import httpx
from tenacity import retry, stop_after_attempt

# Internal
from src.ingestion.graph_manager import KnowledgeGraphManager
from src.models.expert_model import ExpertModel
```

Order enforced by `ruff` isort rules.

---

## 8. Code Review Checklist

Before any PR is merged:
- [ ] All public methods have Google-style docstrings
- [ ] Type hints present on all function signatures
- [ ] No f-strings in Gremlin query construction
- [ ] No hardcoded credentials or secrets
- [ ] Logging uses `%s` format, not f-strings
- [ ] New functionality has corresponding tests
- [ ] `ruff` passes with zero errors
- [ ] `bandit` passes with zero HIGH findings
- [ ] Coverage does not fall below 80%

---

*End of CSD — DBE-CSD-014 v1.0.0*
