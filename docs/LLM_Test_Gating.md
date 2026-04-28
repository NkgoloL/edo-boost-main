LLM Test Gating

Purpose
- Prevent costly or rate-limited LLM API calls from running in CI by marking tests that make real LLM calls with the `llm` pytest marker.

Usage
- Local development:
  - Run all tests including LLM tests: `pytest -m llm`
  - Run non-LLM tests (fast): `pytest -m "not llm"`

- CI configuration:
  - The GitHub Actions `backend-test` job runs `pytest -m "not llm"` to skip live LLM calls.

Best practices
- Prefer mocking LLM client responses in unit/integration tests.
- For end-to-end LLM tests, run them locally or in a controlled environment with appropriate API keys and usage monitoring.
- Use feature flags to gate experimental LLM-dependent features.
