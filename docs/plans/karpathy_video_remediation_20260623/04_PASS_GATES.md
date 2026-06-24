# 04 Pass Gates

## Gate 0 — Render lock gate

Applies to every ticket until Sprint 06.

PASS requires:

```text
- YT_TEST_MODE=1 or equivalent test-mode protection is active
- HIGGSFIELD_DRY_RUN=1 for provider request tests
- no command submitted external video render
- no provider job row was created for a new paid render unless ticket explicitly allows dry-run row with no external job
- no actual render output was created by external provider
```

FAIL if:

```text
- command includes `higgsfield generate create` without dry-run protection
- provider adapter submits real external video job
- ticket report omits render-lock status
```

## Gate 1 — Forensic gate

PASS requires:

```text
- bad fixture path identified
- scene/timing context captured if video-related
- DB rows exported or missing DB evidence explicitly recorded
- failure class mapped to 02_FAILURE_TAXONOMY.md
- no engineering proposed before evidence
```

## Gate 2 — Eval-first gate

PASS requires:

```text
- deterministic eval command documented
- eval output JSON written
- eval fails on the known bad fixture OR explains that it is diagnostic-only
- expected thresholds are declared
- eval has clear subject_id / artifact path / production_id mapping
```

FAIL if:

```text
- eval is subjective prose only
- eval result is not machine-readable
- eval passes the bad fixture without explanation
- eval uses real provider render
```

## Gate 3 — Engineering gate

PASS requires:

```text
- changed files are within ticket scope
- implementation is minimal
- no platform rebuild
- no dummy fallback
- no broad exception swallowing
- tests added or updated
- all commands executed and logged
```

## Gate 4 — Audit gate

PASS requires:

```text
- audit report has no BLOCKER or MAJOR findings
- DB invariants preserved
- render lock preserved
- media contract preserved
- fake-green paths rejected
- edge cases listed
```

BLOCKER examples:

```text
- actual render possible before unlock
- DB source-of-truth bypassed
- validation can pass with missing artifacts
- migration missing or unsafe
- eval output ignored by QA
```

MAJOR examples:

```text
- evidence not linked to subject_id
- test does not exercise failure
- thresholds undocumented
- code works only for fixture filename
```

## Gate 5 — Black-box validation gate

PASS requires:

```text
- validator ran commands independently
- test/eval logs included
- required JSON evidence exists and is non-empty
- all expected failures/passes match ticket
- no hidden external render call occurred
```

## Gate 6 — Sprint exit gate

PASS requires:

```text
- all sprint tickets passed Gate 5
- sprint summary exists
- open defects are updated
- regression fixture updated if needed
- next sprint prerequisites are satisfied
```

## Gate 7 — Actual render readiness gate

Only Sprint 06 may pass this.

PASS requires all of the following:

```text
- Sprints 00-05 passed
- lipsync eval harness exists and runs on existing fixture
- audio provenance ledger exists for hero units
- provider diagnostic audio compare exists
- assembly transform ledger exists
- final QA consumes lipsync/timing/graphics evidence
- dry-run provider request payload was audited
- single canary render plan exists
- user-created unlock file exists at ops/ACTUAL_RENDER_UNLOCK.json
```

The unlock file must contain:

```json
{
  "allow_actual_video_render": true,
  "max_provider_jobs": 1,
  "production_id": "<production_id>",
  "approved_by": "human",
  "reason": "controlled canary after readiness gates",
  "created_at": "<ISO8601>"
}
```

If this file is absent, Sprint 06 must stop at dry-run.
