# Release Notes
**Document ID:** DBE-RN-028  
**Version History:** All releases

---

## Release 0.1.0 — Phase 2 Foundation
**Date:** 2026-04-29  
**Status:** Development  
**Branch:** `develop`

### Summary
Establishes the intelligence and data layer for the DBE AI Expert System. This release delivers a fully tested knowledge graph schema framework, an end-to-end ingestion flow orchestrator, and a corrected orchestration service.

### New Features

- **Knowledge Graph Manager** (`src/ingestion/graph_manager.py`)
  - Lazy, fault-tolerant Gremlin client with tenacity retry and exponential backoff.
  - Schema loaded from external `config/graph_schema.json` — no hardcoded definitions.
  - Idempotent graph initialisation via Gremlin `coalesce()` pattern.
  - Full traversal API: `get_documents_by_category()`, `search_documents_by_keyword()`, `get_related_categories()`, `get_agent_triggers()`.
  - `health_check()` method for independent connectivity verification.

- **Security Hardening**
  - All Gremlin queries converted to parameterised binding dictionaries — query injection vector eliminated.
  - `config/graph_schema.json` externalised for runtime schema management.

- **Documentation Suite** (39 documents)
  - Tiers 1–7 covering requirements, architecture, design, implementation, verification, operations, security, and project management.

### Bug Fixes

- **BUG-002** (Critical): Fixed `ImportError` on Pydantic v2 — migrated `BaseSettings` import to `pydantic_settings`.
- **BUG-006**: Fixed `asyncio.get_event_loop()` deprecation in `tests/test_models.py` — replaced with `pytest-asyncio`.
- **BUG-007**: Fixed `pyproject.toml` package discovery configuration (`package-dir` mapping).

### Dependency Changes

| Package | Change | Version |
|---------|--------|---------|
| `pydantic-settings` | Added | `≥2.0.0` |
| `pytest-asyncio` | Added | `≥0.21.0` |
| `pytest-cov` | Added | `≥4.1.0` |
| `pytest-httpx` | Added | `≥0.21.0` |
| `tenacity` | Added | latest |
| `python-json-logger` | Added | `≥2.0.7` |
| `opencensus-ext-azure` | Added | `≥1.1.13` |
| `redis` | Added | `≥4.6.0` |
| `ruff` | Added (dev) | `≥0.1.0` |
| `bandit` | Added (dev) | `≥1.7.5` |

### Known Issues

| ID | Severity | Description |
|----|----------|-------------|
| BUG-001 | Critical | `retrieve_context()` in `main.py` returns static string — not connected to graph. Targeted Phase 3. |
| BUG-003 | High | Performance test assertions only validate `> 0` threshold — no real Gremlin measurements yet. |
| BUG-004 | High | Gremlin injection regression test not yet implemented. |
| BUG-005 | High | `AzureMLExpertModel.predict()` has no test coverage. |

### Upgrade Instructions

```bash
git pull origin develop
pip install -e ".[dev]"     # picks up new pydantic-settings and test deps
pytest tests/ -v            # verify 25 tests pass
```

### Breaking Changes

None — this is an internal development release. No external API contracts changed.

---

## Release 0.0.1 — Phase 1 Foundation
**Date:** 2026-04-01  
**Status:** Superseded

### Summary
Initial repository setup. Terraform infrastructure definitions, Docker container, FastAPI skeleton, and knowledge ingestion pipeline MVP.

### Contents
- Azure infrastructure (Terraform): Resource Group, VNet, AKS, Cosmos DB, Azure ML, APIM, Key Vault.
- FastAPI orchestration service with `/health`, `/ask`, `/feedback` stubs.
- `KnowledgeIngestionPipeline` — Cosmos DB upsert via SQL API.
- `BaselinePolicyModel` — keyword heuristic fallback.
- CI/CD: GitHub Actions Terraform workflow.
- Helm chart: `dbe-agent-orchestrator`.

---

## Planned: Release 0.2.0 — Phase 3 Integration
**Target Date:** +3 weeks  
**Status:** Planned

### Planned Contents
- FastAPI OAuth2 JWT authentication middleware.
- `retrieve_context()` wired to `KnowledgeGraphManager.search_documents_by_keyword()`.
- Cosmos DB Gremlin + graph resources provisioned via Terraform.
- ACR provisioned and CI/CD image build/push pipeline active.
- Cosmos DB Emulator in GitHub Actions CI.
- Application Insights SDK integrated (structured JSON logs, distributed traces).
- Azure Monitor alert rules deployed via Terraform.
- HPA manifest (`hpa.yaml`) added to Helm chart.
- `SecretProviderClass` for Key Vault CSI driver.
- All Phase 2 TODO items from `docs/TODO.md` resolved.

---

*End of Release Notes — DBE-RN-028 v1.0.0*
