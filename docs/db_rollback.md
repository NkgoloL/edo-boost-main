# Runbook: Database Rollback

> Severity: P0 | Owner: Platform Engineering | Last reviewed: 2026-04-29

## Prerequisites
- `alembic` CLI available
- Access to `DATABASE_URL` for the target environment
- At minimum one prior Alembic migration revision exists

---

## Step 1 — Identify the target revision

```bash
# List current revision
alembic current

# List all revisions
alembic history --verbose

# Show the previous revision
alembic heads
```

Note the revision hash you are rolling back FROM and the revision you are rolling back TO.

---

## Step 2 — Take a database backup (MANDATORY)

```bash
pg_dump "$DATABASE_URL" \
  --format=custom \
  --file="backup_$(date +%Y%m%d_%H%M%S).dump"
```

Do NOT proceed without a verified backup.

---

## Step 3 — Execute the rollback

```bash
# Roll back one migration
alembic downgrade -1

# Roll back to a specific revision
alembic downgrade <revision_hash>

# Roll back all (DANGEROUS — development only)
alembic downgrade base
```

---

## Step 4 — Verify

```bash
alembic current
alembic check
psql "$DATABASE_URL" -c "\dt"
```

---

## Step 5 — Notify

1. Post in `#platform-incidents` with: revision rolled back, reason, and timestamp.
2. If `constitutional_rules` or `audit_log` tables were affected, notify the Information Officer.
3. Update `CHANGELOG.md`.

---

## Constraints

- `constitutional_rules` and `audit_log` have DELETE-blocking triggers.
  Rolling back migrations that drop these tables will fail unless the triggers are dropped first.
  **Only do this with Information Officer approval.**

```sql
-- To temporarily allow (requires superuser):
DROP TRIGGER trg_constitutional_rules_no_delete ON constitutional_rules;
DROP TRIGGER trg_audit_log_no_delete ON audit_log;
-- After rollback, re-apply migration to restore triggers.
```
