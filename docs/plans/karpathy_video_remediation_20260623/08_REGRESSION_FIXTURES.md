# 08 Regression Fixtures

## Required bad fixture: prod_2f9bb58c0508465fb51ac6b4578bba92

Expected location:

```text
fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4
```

If the MP4 is too large to commit, store a README with local path instructions and commit all lightweight derived artifacts:

```text
contact_sheet.jpg
scene_timeline.csv
forensic_summary.json
failure_ledger.json
```

## Required fixture metadata

```json
{
  "production_id": "prod_2f9bb58c0508465fb51ac6b4578bba92",
  "expected_failures": [
    "F-LIP-001",
    "F-GFX-001",
    "F-GFX-002",
    "F-TEXT-001",
    "F-QA-001",
    "F-PROV-001"
  ],
  "actual_render_required": false
}
```

## Fixture rules

1. Never delete a bad fixture after fixing the bug.
2. Add a new expected-good fixture only after the relevant eval passes.
3. A fixture can be marked superseded, but must remain available for regression.
4. Fixture evals must not call paid video providers.
5. Fixture reports must be stable across reruns.
