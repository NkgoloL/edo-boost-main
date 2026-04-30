# Installation & Configuration Guide (ICG)
**Document ID:** DBE-ICG-027  
**Version:** 1.0.0  
**Date:** 2026-04-29

---

## 1. Local Development Setup

### 1.1 Clone and Install

```bash
git clone https://github.com/NkgoloL/dbe-ai-expert-system.git
cd dbe-ai-expert-system

# Create and activate virtual environment
python3.10 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .\.venv\Scripts\Activate.ps1     # Windows PowerShell

# Install package with dev extras
pip install -e ".[dev]"
```

### 1.2 Environment Configuration

```bash
cp .env.example .env
# Edit .env with your values — see Section 2 for each variable
```

**Minimum required for local development (no Azure):**
```bash
# .env
ENVIRONMENT=development
PORT=8000
LOG_LEVEL=DEBUG
# Leave Azure variables blank — system will use BaselinePolicyModel fallback
```

### 1.3 Run the Application Locally

```bash
python src/orchestration/main.py
# Server starts at http://localhost:8000
# Swagger UI: http://localhost:8000/docs
```

### 1.4 Run the Test Suite

```bash
# All tests (unit + integration, mocked)
pytest tests/ -v

# With coverage report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# Specific module
pytest tests/test_graph_integration.py -v

# Fail fast on first failure
pytest tests/ -x
```

---

## 2. Environment Variable Reference

Copy from `.env.example` and populate each section:

### Azure Credentials
```bash
AZURE_SUBSCRIPTION_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=your-client-secret
```
> Obtain from: Azure Portal → Azure Active Directory → App Registrations

### Cosmos DB (SQL API)
```bash
COSMOS_ENDPOINT=https://cosmos-dbe-expert-dev.documents.azure.com:443/
COSMOS_KEY=<primary-key>
COSMOS_DATABASE_NAME=KnowledgeDB
COSMOS_CONTAINER_NAME=IntelligenceStore
```
> Obtain from: Azure Portal → Cosmos DB account → Keys

### Cosmos DB (Gremlin API)
```bash
COSMOS_GREMLIN_ENDPOINT=https://cosmos-dbe-expert-dev.gremlin.cosmos.azure.com:443/
COSMOS_GREMLIN_KEY=<same-primary-key>
```

### Azure Blob Storage
```bash
AZURE_STORAGE_ACCOUNT_NAME=stdbeexpertdev
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER_FEEDBACK=feedback
AZURE_STORAGE_CONTAINER_DOCUMENTS=documents
```
> Obtain from: Storage Account → Access keys → Connection string

### Azure Machine Learning
```bash
AZURE_ML_ENDPOINT=https://your-endpoint.eastus.inference.ml.azure.com/score
AZURE_ML_KEY=<endpoint-key>
AZURE_ML_WORKSPACE=mlw-dbe-dev
AZURE_RESOURCE_GROUP=rg-dbe-ai-expert-system
```
> If unset, system uses `BaselinePolicyModel` automatically.

### Application Settings
```bash
PORT=8000
ENVIRONMENT=development           # development | staging | production
LOG_LEVEL=INFO                    # DEBUG | INFO | WARNING | ERROR
FEEDBACK_RETRAINING_THRESHOLD=10  # Number of low ratings before retraining trigger
CACHE_TTL_SECONDS=3600            # Redis cache TTL (Phase 4)
```

### Security
```bash
KEY_VAULT_NAME=kv-dbe-dev
JWT_SECRET_KEY=<strong-random-secret-min-32-chars>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

---

## 3. Cosmos DB Emulator (CI / Offline Testing)

For integration tests without a live Azure account:

```bash
# Pull and run the emulator
docker run -d \
  --name cosmosdb-emulator \
  -p 8081:8081 -p 10251:10251 -p 10252:10252 -p 10253:10253 -p 10254:10254 \
  mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator

# Export emulator endpoint
export COSMOS_ENDPOINT=https://localhost:8081/
export COSMOS_KEY=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw==

# Run integration tests against emulator
USE_REAL_COSMOS=true pytest tests/test_graph_integration.py -v
```

---

## 4. Docker Build (Local)

```bash
# Build
docker build -t dbe-agent-orchestrator:local .

# Run with .env file
docker run --rm \
  --env-file .env \
  -p 8000:8000 \
  dbe-agent-orchestrator:local

# Verify
curl http://localhost:8000/health
```

---

## 5. Code Quality Checks

```bash
# Linting (ruff)
ruff check src/ tests/

# Formatting check
black --check src/ tests/

# Security scan (bandit)
bandit -r src/ -ll

# Dependency vulnerability scan
pip-audit

# Pre-commit hooks (install once)
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ImportError: cannot import name 'BaseSettings' from 'pydantic'` | Pydantic v2 breaking change | `pip install pydantic-settings` |
| `GremlinServerError: WebSocket handshake failed` | Wrong endpoint format | Ensure endpoint uses `wss://` and ends with port `443/` |
| `CosmosHttpResponseError: 401` | Wrong key | Re-copy primary key from Azure Portal |
| `AttributeError: 'NoneType' object has no attribute 'submit'` | Gremlin client not initialised | Ensure `COSMOS_GREMLIN_ENDPOINT` is set |
| Tests fail with `DeprecationWarning: There is no current event loop` | Deprecated `get_event_loop()` | Use `pytest-asyncio` and `@pytest.mark.asyncio` |
| `bandit: No issues identified` but test fails | Coverage below 80% | Add tests for uncovered paths (check `htmlcov/`) |

---

*End of ICG — DBE-ICG-027 v1.0.0*
