# S00_T003 DB Provenance Export

## Purpose

Export DB evidence for the bad production so later tickets can prove or disprove source-audio and assembly lineage.

## Failure classes addressed

```text
F-PROV-001
F-PROV-002
F-QA-001
```

## Allowed files

```text
reports/karpathy_loop/sprint_00/S00_T003/**
```

## Forbidden files

```text
scripts/**
db/migrations/**
```

## Required tables

```text
productions
stage_runs
timeline_spans
creative_beats
render_units
provider_jobs
artifacts
validations
deliverables
change_requests
production_events
```

## Required command

Use the DB export command in `05_COMMANDS_AND_FIXTURE_PROTOCOL.md` with production id:

```text
prod_2f9bb58c0508465fb51ac6b4578bba92
```

## Pass gates

PASS if:

```text
- JSONL export exists for each available table
- missing tables are recorded as explicit issues
- suspicious provenance fields are listed
- no DB writes were made
```
