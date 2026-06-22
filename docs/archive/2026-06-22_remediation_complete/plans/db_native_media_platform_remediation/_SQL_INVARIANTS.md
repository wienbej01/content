## 14. Required SQL Invariant Checks

Use these after dry-run and smoke runs.

### 14.1 Forbidden provider jobs

```sql
SELECT pj.id, ru.id, ru.label, ru.ordinal, ru.asset_type, ru.model, pj.request_json
FROM provider_jobs pj
JOIN render_units ru ON ru.id = pj.render_unit_id
WHERE ru.asset_type IN (
  'local_graphic',
  'title_card',
  'lower_third',
  'source_card',
  'quote_card',
  'researcher_card',
  'framework_card',
  'chart',
  'diagram',
  'caption',
  'subtitle'
);
```

Expected: zero rows.

### 14.2 Risky provider prompts

```sql
SELECT pj.id, ru.label, ru.ordinal, ru.asset_type, pj.request_json
FROM provider_jobs pj
JOIN render_units ru ON ru.id = pj.render_unit_id
WHERE pj.request_json LIKE '%Title card:%'
   OR pj.request_json LIKE '%lower third%'
   OR pj.request_json LIKE '%Harvard Business Review%'
   OR pj.request_json LIKE '%McKinsey%'
   OR pj.request_json LIKE '%display text%'
   OR pj.request_json LIKE '%show text%'
   OR pj.request_json LIKE '%subtitle%'
   OR pj.request_json LIKE '%caption%';
```

Expected: zero rows for provider-generated video.

### 14.3 Local graphics provenance

```sql
SELECT ru.id, ru.label, ru.ordinal, ru.status, a.uri, a.metadata_json
FROM render_units ru
LEFT JOIN artifacts a ON a.id = ru.active_artifact_id
WHERE ru.asset_type = 'local_graphic'
ORDER BY ru.ordinal;
```

Expected:

- artifact exists;
- metadata contains local renderer provenance;
- text spec hash exists;
- latest validation passes.

### 14.4 Render units lacking passing validation

```sql
SELECT ru.id, ru.label, ru.ordinal, ru.asset_type, ru.status
FROM render_units ru
WHERE ru.production_id = '<prod_id>'
  AND ru.status NOT IN ('valid', 'stale')
ORDER BY ru.ordinal;
```

Expected before assembly: zero active non-valid rows.

### 14.5 Deliverable final QA evidence

```sql
SELECT d.id, d.variant, d.status, d.qa_validation_id, v.status, v.evidence_json
FROM deliverables d
LEFT JOIN validations v ON v.id = d.qa_validation_id
WHERE d.production_id = '<prod_id>';
```

Expected:

- final QA pass;
- evidence includes DB-contract checks, not only mechanical video checks.

---
