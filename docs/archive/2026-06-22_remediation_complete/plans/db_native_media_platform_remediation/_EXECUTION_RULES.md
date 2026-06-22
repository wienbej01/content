# DB-Native Media Platform Remediation: Ticketed Sprint Plan

## Purpose

This document converts the remedial architecture into executable tickets for three agent roles:

- **Engineer**: implements code, tests, migrations, and local fixes.
- **Auditor**: reviews code, tests, DB invariants, and failure-mode coverage.
- **Validator**: runs black-box and DB-state validation after Engineer and Auditor issues are resolved.

The plan is designed for the existing `wienbej01/content` infrastructure. It does **not** prescribe a rebuild, new workflow engine, new orchestration layer, or second source of truth. The production database remains the authoritative control plane.

The known failures this plan must permanently prevent:

1. `local_graphic` render units were sent to a paid video provider.
2. Exact text such as title cards, names, HBR/McKinsey references, and study labels entered provider prompts.
3. Provider-generated text became garbled.
4. Hero lipsync suffered audio/video drift and internal cuts.
5. Assembly allowed extreme timeline errors (e.g., 48s of repeated/looping graphics).
6. Media QA passed because files existed and had acceptable dimensions/duration/SHA.
7. Final QA passed because it checked mechanical video properties rather than render-unit contracts.
8. Assembly consumed bad but mechanically valid artifacts.

The platform must become structurally incapable of repeating those failures.

---

## 0. Execution Rules

### 0.1 Branch

Use one implementation branch unless the repository already has an active remediation branch.

```bash
git switch main
git pull
git switch -c fix/db-native-media-contract-remediation
```

Do **not** merge the forensic evidence branch into `main`.

### 0.2 Minimal-change policy

Prefer:

- pure Python contract helpers;
- existing DB tables;
- existing JSON metadata fields;
- existing `render_units`, `provider_jobs`, `artifacts`, `validations`, `deliverables`;
- existing stage sequence;
- existing `render_graphics.py`;
- existing `assemble_db.py` / `assemble.py`.

Avoid unless absolutely required:

- schema changes;
- new services;
- new queues;
- new workflow engine;
- Remotion/Manim integration;
- broad refactors;
- manual QA as the primary pass gate;
- another JSON manifest as source of truth.

### 0.3 Database authority rule

Files are evidence, not state. A media artifact is production-usable only if the DB says:

- render unit exists;
- artifact exists;
- artifact is active;
- artifact SHA is recorded;
- latest applicable validation passed;
- artifact provenance matches render method;
- assembly selected it through DB state.

### 0.4 Agent feedback loop

Each sprint follows this sequence:

```text
Engineer implements ticket group
  -> Engineer runs local tests
  -> Auditor reviews code + tests + DB invariants
  -> Engineer fixes all Auditor BLOCKER/MAJOR issues
  -> Auditor confirms closure
  -> Validator runs black-box / integration / DB validation
  -> Engineer fixes all Validator BLOCKER/MAJOR issues
  -> Validator reruns failed checks
  -> Auditor signs off sprint
  -> proceed to next sprint
```

No sprint may proceed if there is an unresolved BLOCKER.

### 0.5 Defect severity

#### BLOCKER

The system can still:

- send `local_graphic` or exact text to a provider;
- pass bad media as valid;
- assemble unvalidated artifacts;
- publish without final DB-contract evidence;
- spend money despite illegal render plan;
- silently bypass DB state.

#### MAJOR

The core invariant holds, but:

- evidence is incomplete;
- tests miss a known failure mode;
- implementation is not idempotent;
- repair creates duplicate active artifacts;
- error messages are unclear;
- stage status can be misleading.

#### MINOR

Cosmetic, naming, minor test cleanup, docs.

### 0.6 Engineer response to audit/validation issues

For each Auditor or Validator issue, Engineer must respond in this format:

```text
Issue ID:
Severity:
Root cause:
Files changed:
Fix summary:
Tests added/updated:
Retest command:
Result:
```

### 0.7 Required command discipline

No ticket may invoke real paid provider calls unless explicitly marked as production smoke.

Tests must use:

- fake provider;
- dry-run provider;
- small synthetic files;
- DB fixture data;
- forensic JSON fixture excerpts.

---
