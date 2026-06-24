# S00_T001 Fixture Capture and Artifact Ledger

## Purpose

Capture the current bad final video as a permanent regression fixture and create a ledger of lightweight derived evidence. No code changes are required unless a helper script is missing and the Eval Engineer explicitly proposes one.

## Failure classes addressed

```text
F-QA-002
F-PROV-001
```

## Allowed files

```text
fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/**
reports/karpathy_loop/sprint_00/S00_T001/**
```

## Forbidden files

```text
scripts/**
db/migrations/**
```

## Required forensic work

1. Locate/copy/reference `prod_2f9bb58c0508465fb51ac6b4578bba92_16x9.mp4`.
2. Create fixture README.
3. Create artifact ledger JSON with file paths, SHA256 if available, and whether file is committed or external.

## Required eval work

Create a diagnostic fixture integrity eval.

## Required commands

```bash
mkdir -p fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92
sha256sum fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4 || true
ffprobe -v error -show_format -show_streams -of json fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4 > reports/karpathy_loop/sprint_00/S00_T001/video_probe.json || true
```

## Pass gates

PASS if:

```text
- fixture exists or external-reference README exists
- artifact_ledger.json exists
- render lock verified
- no code modified
- no provider render call
```
