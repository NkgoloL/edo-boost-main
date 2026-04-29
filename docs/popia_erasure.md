# Runbook: POPIA Right-to-Erasure Request

> Severity: P0 (compliance) | Owner: Information Officer | Last reviewed: 2026-04-29

## Legal basis
POPIA Section 24: A data subject may request erasure of personal information.
For learners under 18, the request must be made by the registered guardian.

---

## Step 1 — Verify the request

1. Confirm the requestor's identity (guardian verification).
2. Retrieve the learner's `learner_pseudonym` from the guardian's verified account.
3. Log the request receipt in `popia_erasure_requests` table (manual entry).

---

## Step 2 — Execute erasure via API

```bash
# Authenticated as an operator with erasure scope:
curl -X DELETE \
  "https://api.eduboost.co.za/learner/{pseudonym}" \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json"
```

The `ErasureService.erase()` will cascade across:
- `learner_profiles`
- `irt_responses`
- `study_plans`
- `lesson_results`
- `ether_profiles`
- `session_states`
- `consent_log`
- R2/S3 assets under `learners/{pseudonym}/`

---

## Step 3 — Verify erasure

```sql
-- Confirm no rows remain for the pseudonym
SELECT 'learner_profiles' as t, COUNT(*) FROM learner_profiles WHERE learner_pseudonym = '<pseudonym>'
UNION ALL
SELECT 'irt_responses', COUNT(*) FROM irt_responses WHERE learner_pseudonym = '<pseudonym>'
UNION ALL
SELECT 'lesson_results', COUNT(*) FROM lesson_results WHERE learner_pseudonym = '<pseudonym>'
UNION ALL
SELECT 'ether_profiles', COUNT(*) FROM ether_profiles WHERE learner_pseudonym = '<pseudonym>';
```

All counts must be 0.

---

## Step 4 — Audit trail

The deletion event is appended to `audit_log` by `ErasureService`. Verify:

```sql
SELECT * FROM audit_log
WHERE event_type = 'popia_erasure'
  AND event_data->>'learner_pseudonym' = '<pseudonym>'
ORDER BY created_at DESC LIMIT 1;
```

The `audit_log` row itself is NOT deleted (deletion of audit records is not permitted under POPIA record-keeping obligations).

---

## Step 5 — Notify the guardian

Send a written confirmation within 72 hours. Include:
- Date of erasure
- Data categories erased
- Reference to the `audit_log.event_id` for the erasure event

---

## Escalation

If erasure fails for any reason:
1. Immediately notify the Information Officer.
2. Do not attempt partial erasure and leave the system in an inconsistent state.
3. Open a P0 incident in the incident tracker.
