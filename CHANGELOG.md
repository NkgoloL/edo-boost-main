# Changelog

## Unreleased

- Normalize `knowledge_gaps` input handling in `StudyPlanService` so remediation and scheduling accept either strings (concept names) or dicts with metadata.
- Add backward-compatible `report` object in `ParentPortalService.generate_parent_report` to satisfy integrations/tests expecting `report`.
- Pin CI and repository Python target to 3.11 via `.python-version` and GitHub Actions update.
- Add `scripts/check_env.sh` to verify local Python runtime is 3.11.

These changes fix multiple failing tests related to study plan generation and parent report structure, and standardise local/CI Python versions.
