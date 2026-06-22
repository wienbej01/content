# DB-Native Media Platform Remediation: Ticketed Sprint Plan

## Purpose

This document converts the remedial architecture into executable tickets for three agent roles:

- **Engineer**: implements code, tests, migrations, and local fixes.
- **Auditor**: reviews code, tests, DB invariants, and failure-mode coverage.
- **Validator**: runs black-box and DB-state validation after Engineer and Auditor issues are resolved.

The plan is designed for the existing `wienbej01/content` infrastructure. It does **not** prescribe a rebuild, new workflow engine, new orchestration layer, or second source of truth. The production database remains the authoritative control plane.

The known failure this plan must permanently prevent:

1. `local_graphic` render units were sent to a paid video provider.
2. Exact text such as title cards, names, HBR/McKinsey references, and study labels entered provider prompts.
3. Provider-generated text became garbled.
4. Media QA passed because files existed and had acceptable dimensions/duration/SHA.
5. Final QA passed because it checked mechanical video properties rather than render-unit contracts.
6. Assembly consumed bad but mechanically valid artifacts.

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

## 1. Sprint Overview

| Sprint | Goal | Main outcome |
|---|---|---|
| Sprint 0 | Baseline and fixtures | Known failure captured as regression fixture |
| Sprint 1 | Media contract module | Provider eligibility and text-risk rules exist |
| Sprint 2 | Provider boundary hardening | Forbidden render units cannot create provider jobs |
| Sprint 3 | Prompt/text split | Provider prompts become text-free; exact text becomes deterministic spec |
| Sprint 4 | DB-native local graphics | Local graphics render locally and register DB artifacts |
| Sprint 5 | Contract media QA | `valid` means contract-valid, not only file-valid |
| Sprint 6 | Repair loop | Repair acts on validation failures and preserves audit history |
| Sprint 7 | Assembly preflight | Assembly consumes only validated active DB artifacts |
| Sprint 8 | Final QA and gates | Final deliverable requires DB-contract evidence |
| Sprint 9 | End-to-end dry run | Full synthetic pipeline works without paid calls |
| Sprint 10 | Capped production smoke | Minimal real run proves system is production-safe |

---

## 2. Sprint 0 — Baseline, Fixtures, and Non-Regression Harness

### Objective

Create small fixtures from the failed production so the failure becomes a permanent test case. Do not use large MP4s. Use reduced JSON rows extracted from the forensic bundle.

### ENG-0001 — Create reduced forensic regression fixtures

**Owner:** Engineer  
**Dependencies:** None

**Create:**

```text
tests/fixtures/failed_provider_jobs_min.json
tests/fixtures/failed_render_units_min.json
tests/fixtures/failed_validations_min.json
tests/fixtures/failed_deliverable_validation_min.json
tests/regression/test_failed_production_fixture_loads.py
```

**Implementation steps:**

1. Extract only the minimal rows needed to prove:
   - `local_graphic` was sent to provider;
   - provider prompt contained `Title card:`;
   - provider prompt contained `Harvard Business Review`;
   - media QA passed using mechanical checks;
   - final QA passed using mechanical checks only.
2. Keep fixture files small and human-readable.
3. Include at least these cases:
   - one `lipsync_video` provider job with `negative_prompt`;
   - one `generated_video` provider job with `Harvard Business Review`;
   - one `local_graphic` provider job with `Title card: I'M JAMES HARRINGTON. MCKINSEY'S`;
   - one `qa_media` pass evidence with only file/duration/dimensions/SHA checks;
   - one `qa_final` pass evidence with no freeze/black/duration issues but no contract checks.
4. Do not include full media files.

**Required tests:**

- all fixture files load as JSON;
- fixtures contain the five known failure signals;
- no fixture file exceeds 100 KB.

**Commands:**

```bash
pytest tests/regression/test_failed_production_fixture_loads.py -q
```

**Engineer pass criteria:**

- fixtures load;
- tests pass;
- no large binary file added.

### AUD-0001 — Audit forensic fixture completeness

**Owner:** Auditor

**Review checklist:**

1. Fixtures contain enough information to test the old failure.
2. No large media files were added.
3. Fixture content is not so broad that it becomes hard to maintain.
4. Fixture includes both provider misuse and QA false-pass evidence.
5. Fixture names are clear.

**Auditor output:**

```text
AUD-0001 RESULT: PASS
```

or:

```text
AUD-0001 RESULT: FAIL
Issues:
- [BLOCKER] ...
- [MAJOR] ...
```

### VAL-0001 — Validate baseline regression fixtures

**Owner:** Validator

**Validation steps:**

```bash
pytest tests/regression/test_failed_production_fixture_loads.py -q
git status --short
find tests/fixtures -type f -maxdepth 1 -printf '%s %p\n' | sort -n
```

**Pass criteria:**

- fixture tests pass;
- no large fixture;
- working tree only contains expected files.

---

## 3. Sprint 1 — Media Contract Module

### Objective

Add pure contract logic that defines provider eligibility, deterministic graphics requirements, prompt text-risk detection, and render-method classification.

This sprint should not change generation behavior yet.

### ENG-0101 — Add `scripts/media_contract.py`

**Owner:** Engineer

**Create:**

```text
scripts/media_contract.py
tests/unit/test_media_contract.py
```

**Implementation steps:**

1. Add constants:

```python
PROVIDER_ELIGIBLE_ASSET_TYPES = {
    "lipsync_video",
    "generated_video",
    "broll_video",
    "atmospheric_video",
}

PROVIDER_FORBIDDEN_ASSET_TYPES = {
    "local_graphic",
    "title_card",
    "lower_third",
    "source_card",
    "quote_card",
    "researcher_card",
    "framework_card",
    "chart",
    "diagram",
    "caption",
    "subtitle",
}
```

2. Add functions:

```python
def normalize_asset_type(asset_type: str | None) -> str: ...
def is_provider_eligible_asset_type(asset_type: str | None) -> bool: ...
def is_provider_forbidden_asset_type(asset_type: str | None) -> bool: ...
def requires_local_renderer(asset_type: str | None, text_policy: str | None = None) -> bool: ...
def classify_render_method(asset_type: str, audio_policy: str | None, text_policy: str | None) -> str: ...
```

3. Add exception class:

```python
class MediaContractError(RuntimeError):
    pass
```

4. Add guard:

```python
def assert_provider_eligible(render_unit_or_payload: Mapping[str, Any]) -> None:
    ...
```

5. The guard must produce clear messages:

```text
BLOCKED: render unit is not provider eligible: asset_type=local_graphic
```

6. Keep the module pure. Do not import DB code.

**Required tests:**

1. `local_graphic` is provider-forbidden.
2. `title_card` is provider-forbidden.
3. `lower_third` is provider-forbidden.
4. `lipsync_video` is provider-eligible.
5. `generated_video` is provider-eligible.
6. `local_graphic` requires local renderer.
7. Unknown asset type fails closed.
8. Error message contains `BLOCKED`.

**Command:**

```bash
pytest tests/unit/test_media_contract.py -q
```

### ENG-0102 — Add provider prompt risk detector

**Owner:** Engineer

**Modify:**

```text
scripts/media_contract.py
tests/unit/test_media_contract.py
```

**Implementation steps:**

1. Add function:

```python
def detect_provider_prompt_text_risks(prompt: str | None) -> list[str]:
    ...
```

2. Start with deterministic keyword checks. Include at minimum:

```text
title card
lower third
source card
quote card
caption
subtitle
show text
display text
text overlay
Harvard Business Review
McKinsey
Stanford
MIT
researcher
study title
chart label
```

3. Add guard:

```python
def assert_provider_prompt_text_free(prompt: str | None) -> None:
    ...
```

4. Fail closed when prompt is missing or non-string only if caller requires prompt.

**Required tests:**

1. `Title card: I'M JAMES HARRINGTON` fails.
2. `As Harvard Business Review put it in 2026` fails.
3. `McKinsey's latest research` fails.
4. `Text-free cinematic office metaphor` passes.
5. Risk detector returns useful reason strings.
6. Guard error contains `provider prompt contains exact-text risk`.

**Command:**

```bash
pytest tests/unit/test_media_contract.py -q
```

### AUD-0101 — Audit media contract correctness

**Owner:** Auditor

**Review checklist:**

1. Contract module is pure and DB-free.
2. Unknown asset types fail closed.
3. Provider-forbidden list includes `local_graphic`.
4. Prompt-risk detector catches the forensic examples.
5. Tests include both positive and negative cases.
6. Errors are explicit enough for repair/triage.
7. No broad refactor introduced.

**Commands:**

```bash
pytest tests/unit/test_media_contract.py -q
python -m compileall scripts/media_contract.py
```

### VAL-0101 — Validate media contract against forensic fixture

**Owner:** Validator

**Validation steps:**

1. Load `tests/fixtures/failed_provider_jobs_min.json`.
2. Assert the contract rejects:
   - `local_graphic` provider job;
   - `Title card:` prompt;
   - `Harvard Business Review` prompt.
3. Add or run regression test:

```text
tests/regression/test_failed_production_contract_rejection.py
```

**Commands:**

```bash
pytest tests/unit/test_media_contract.py -q
pytest tests/regression/test_failed_production_contract_rejection.py -q
```

---

## 4. Sprint 2 — Provider Boundary Hardening

### Objective

Make it impossible for forbidden render units or exact-text prompts to create provider jobs. Also stop unguarded `negative_prompt` forwarding.

### ENG-0201 — Enforce provider eligibility before provider job creation

**Owner:** Engineer

**Files to inspect/modify:**

```text
scripts/media_service.py
scripts/produce_db.py
scripts/production_repo.py
tests/unit/test_provider_boundary.py
tests/integration/test_provider_job_db_boundary.py
```

**Implementation steps:**

1. Locate the DB provider job creation path.
2. Before inserting a `provider_jobs` row, call:

```python
assert_provider_eligible(render_unit)
```

3. Before submission, call:

```python
assert_provider_prompt_text_free(provider_visual_prompt or prompt)
```

4. Failure behavior:
   - do not insert provider job;
   - record or raise explicit `BLOCKED` error;
   - do not mark render unit `generating`;
   - leave render unit in a recoverable state, preferably `blocked` or `needs_repair`.
5. Do not add a new DB table unless strictly necessary.

**Required tests:**

1. `local_graphic` render unit cannot create provider job.
2. `local_graphic` failure leaves zero provider job rows.
3. `generated_video` with safe prompt can create provider job in dry-run/fake mode.
4. `generated_video` with `Harvard Business Review` prompt fails.
5. `lipsync_video` with audio path passes provider eligibility.
6. Error message includes render unit ID and asset type.

**Commands:**

```bash
pytest tests/unit/test_provider_boundary.py -q
pytest tests/integration/test_provider_job_db_boundary.py -q
```

### ENG-0202 — Add adapter-level second guard

**Owner:** Engineer

**Files:**

```text
scripts/paid_adapters.py
tests/unit/test_paid_adapters_contract.py
```

**Implementation steps:**

1. In provider adapter submit/build-args path, validate payload:
   - asset type provider-eligible;
   - prompt text-free if prompt is present;
   - no deterministic text spec included.
2. This guard must exist even if `media_service.py` already guards the call.
3. Raise:

```text
BLOCKED: provider adapter received forbidden asset_type=local_graphic
```

**Required tests:**

1. Direct adapter call with `asset_type=local_graphic` fails.
2. Direct adapter call with `prompt=Title card: ...` fails.
3. Direct adapter call with safe `generated_video` payload passes in dry-run mode.
4. Direct adapter call with `lipsync_video` and audio path passes in dry-run mode.
5. Adapter error does not create/modify files.

**Command:**

```bash
pytest tests/unit/test_paid_adapters_contract.py -q
```

### ENG-0203 — Capability-gate `negative_prompt`

**Owner:** Engineer

**Files:**

```text
scripts/paid_adapters.py
tests/unit/test_paid_adapters_contract.py
```

**Implementation steps:**

1. Add provider capability mapping:

```python
PROVIDER_CAPABILITIES = {
    "seedance_2_0": {
        "supports_negative_prompt": False,
        "supports_audio_path": True,
    },
    "kling3_0": {
        "supports_negative_prompt": False,
        "supports_audio_path": False,
    },
}
```

2. Replace unconditional `--negative_prompt` append with capability check.
3. If unsupported:
   - omit from CLI args;
   - record in dry-run return metadata if possible:

```json
{
  "negative_prompt_omitted": true,
  "omitted_reason": "provider_capability"
}
```

4. Do not break existing dry-run behavior.

**Required tests:**

1. Seedance dry-run with `negative_prompt` does not include `--negative_prompt`.
2. Kling dry-run with `negative_prompt` does not include `--negative_prompt`.
3. If a future provider is configured with `supports_negative_prompt=True`, arg is included.
4. Dry-run metadata records omission.

**Command:**

```bash
pytest tests/unit/test_paid_adapters_contract.py -q
```

### AUD-0201 — Audit provider boundary

**Owner:** Auditor

**Review checklist:**

1. Provider job cannot be inserted for `local_graphic`.
2. Adapter direct call cannot bypass service guard.
3. Prompt-risk guard runs before paid submission.
4. `negative_prompt` is not appended unconditionally.
5. Tests use fake/dry-run only.
6. Failure messages are actionable.
7. No unrelated broad refactor.

**Commands:**

```bash
pytest tests/unit/test_media_contract.py -q
pytest tests/unit/test_provider_boundary.py -q
pytest tests/unit/test_paid_adapters_contract.py -q
pytest tests/integration/test_provider_job_db_boundary.py -q
```

### VAL-0201 — Validate no forbidden provider jobs can exist

**Owner:** Validator

**Validation steps:**

1. Create a temporary test production DB.
2. Insert/plan:
   - one `local_graphic`;
   - one `generated_video` with HBR prompt;
   - one safe `generated_video`.
3. Run provider submission in dry-run/fake mode.
4. Query DB:

```sql
SELECT pj.id, ru.asset_type, pj.request_json
FROM provider_jobs pj
JOIN render_units ru ON ru.id = pj.render_unit_id
WHERE ru.asset_type IN ('local_graphic', 'title_card', 'lower_third', 'source_card', 'quote_card', 'chart', 'diagram');
```

Expected: zero rows.

5. Query risky provider prompts:

```sql
SELECT pj.id, pj.request_json
FROM provider_jobs pj
WHERE pj.request_json LIKE '%Title card:%'
   OR pj.request_json LIKE '%Harvard Business Review%'
   OR pj.request_json LIKE '%McKinsey%';
```

Expected: zero rows.

**Command:**

```bash
pytest tests/integration/test_provider_job_db_boundary.py -q
```

---

## 5. Sprint 3 — Prompt/Text Split in Compile Media

### Objective

Separate provider-safe visual prompts from deterministic text specs. Exact display text must never enter provider prompts.

### ENG-0301 — Add render metadata split

**Owner:** Engineer

**Files:**

```text
scripts/produce_db.py
scripts/production_repo.py
tests/unit/test_compile_media_prompt_split.py
```

**Implementation steps:**

1. Modify render-unit metadata to support:

```json
{
  "provider_visual_prompt": "...",
  "deterministic_text_spec": null,
  "prompt_revision_id": null
}
```

or:

```json
{
  "provider_visual_prompt": null,
  "deterministic_text_spec": {
    "type": "source_card",
    "headline": "...",
    "source": "...",
    "year": "..."
  },
  "prompt_revision_id": null
}
```

2. Preserve backward compatibility:
   - existing `prompt` may remain temporarily;
   - new code should prefer `provider_visual_prompt`.
3. Add helper:

```python
def get_provider_visual_prompt(metadata: dict) -> str | None: ...
def get_deterministic_text_spec(metadata: dict) -> dict | None: ...
```

4. Do not require schema change unless unavoidable.

**Required tests:**

1. Metadata can store provider prompt and deterministic spec.
2. Existing metadata with `prompt` still works.
3. New provider payload uses `provider_visual_prompt`.
4. `deterministic_text_spec` is not included in provider payload.

### ENG-0302 — Implement prompt sanitizer for provider visuals

**Owner:** Engineer

**Files:**

```text
scripts/produce_db.py
scripts/media_contract.py
tests/unit/test_compile_media_prompt_split.py
```

**Implementation steps:**

1. Add function:

```python
def sanitize_provider_visual_prompt(raw_text: str, *, text_policy: str = "NO_VISIBLE_TEXT") -> str:
    ...
```

2. The sanitizer should:
   - remove exact study/source names from visual prompt;
   - remove title-card/lower-third instructions;
   - add text-free constraints;
   - preserve visual intent.
3. Minimum examples:
   - `As Harvard Business Review put it in 2026...` becomes `Text-free cinematic office/library metaphor for work intensification. No screens, documents, visible writing, labels, captions, charts, or readable text.`
   - `Title card: I'M JAMES HARRINGTON. MCKINSEY'S` must not become provider prompt at all; it should route to deterministic text spec.
4. Run `assert_provider_prompt_text_free` after sanitizer.

**Required tests:**

1. HBR narration does not appear in provider prompt.
2. McKinsey does not appear in provider prompt.
3. `Title card:` does not appear in provider prompt.
4. Sanitized prompt includes `text-free` or equivalent.
5. Sanitized prompt passes prompt-risk guard.

### ENG-0303 — Route exact text into deterministic text specs

**Owner:** Engineer

**Files:**

```text
scripts/produce_db.py
scripts/authoring_service.py
scripts/production_repo.py
tests/unit/test_compile_media_prompt_split.py
```

**Implementation steps:**

1. For graphic/text shot types, produce `asset_type=local_graphic`.
2. Store exact display text in `deterministic_text_spec`.
3. Supported minimal spec types:
   - `title_card`;
   - `lower_third`;
   - `source_card`;
   - `quote_card`;
   - `framework_card`.
4. For James intro:
   - produce a `lower_third` or `title_card` spec.
5. For study/source names:
   - produce `source_card`.
6. For researcher names:
   - produce `researcher_card` only if already verified in source metadata; otherwise avoid exact person card.

**Required tests:**

1. James name becomes local deterministic spec.
2. HBR source reference becomes source-card spec.
3. McKinsey reference becomes source-card spec or safe text spec, not provider prompt.
4. Exact text appears only in `deterministic_text_spec`.
5. Provider render units have no exact display text.

### AUD-0301 — Audit prompt/text split

**Owner:** Auditor

**Review checklist:**

1. Provider payload builder uses `provider_visual_prompt`.
2. Exact text is not present in provider payload.
3. Local graphics are planned as `local_graphic`.
4. Backward compatibility does not bypass safety checks.
5. Tests cover forensic examples.
6. No dependence on LLM judgment at provider boundary.

**Commands:**

```bash
pytest tests/unit/test_compile_media_prompt_split.py -q
pytest tests/unit/test_provider_boundary.py -q
pytest tests/unit/test_media_contract.py -q
```

### VAL-0301 — Validate compile output DB state

**Owner:** Validator

**Validation steps:**

1. Run compile stage on a tiny synthetic script/storyboard containing:
   - James intro;
   - HBR source reference;
   - McKinsey source reference;
   - one safe b-roll.
2. Query render units and metadata.
3. Confirm:
   - exact text appears only in deterministic specs;
   - provider prompts are text-free;
   - local graphics are not provider-eligible.

**SQL checks:**

```sql
SELECT id, label, ordinal, asset_type, audio_policy, text_policy, metadata_json
FROM render_units
WHERE production_id = '<prod_id>'
ORDER BY ordinal;
```

Risk query must return zero:

```sql
SELECT id, metadata_json
FROM render_units
WHERE metadata_json LIKE '%provider_visual_prompt%'
  AND (
       metadata_json LIKE '%Title card:%'
    OR metadata_json LIKE '%Harvard Business Review%'
    OR metadata_json LIKE '%McKinsey%'
  );
```

---

## 6. Sprint 4 — DB-Native Local Graphics Rendering

### Objective

Make local graphics render locally, register artifacts in DB, and never create provider jobs.

### ENG-0401 — Add DB-native local graphic rendering function

**Owner:** Engineer

**Files:**

```text
scripts/render_graphics.py
scripts/produce_db.py
scripts/production_repo.py
tests/unit/test_local_graphics_db.py
```

**Implementation steps:**

1. Add a function:

```python
def render_local_graphic_render_unit(db, production_id: str, render_unit_id: str) -> str:
    ...
```

2. Function must:
   - load render unit from DB;
   - assert `asset_type == "local_graphic"`;
   - read `deterministic_text_spec`;
   - render via existing `render_graphics.py` logic;
   - write output to project/media path;
   - compute SHA;
   - register artifact;
   - link artifact to render unit;
   - set render unit status to generated/pending QA.
3. Output format:
   - minimum acceptable: MP4 clip with deterministic text;
   - alternative acceptable: PNG plus assembly overlay support, only if already supported cleanly.
4. Artifact metadata must include:

```json
{
  "render_method": "local_graphic",
  "renderer": "render_graphics.py",
  "text_spec_sha256": "...",
  "expected_text": ["..."],
  "source_render_unit_id": "..."
}
```

**Required tests:**

1. Local graphic render unit renders a file.
2. Missing deterministic text spec fails.
3. Non-local graphic render unit fails.
4. Artifact is registered in DB.
5. Artifact metadata includes renderer provenance.
6. Active artifact is linked to render unit.

### ENG-0402 — Fix `graphics_compositing` stage

**Owner:** Engineer

**Files:**

```text
scripts/produce_db.py
scripts/render_graphics.py
tests/integration/test_graphics_compositing_db.py
```

**Implementation steps:**

1. Update `invoke_graphics_compositing` to query active `local_graphic` render units.
2. It must not query only `still_kenburns`.
3. For each pending local graphic:
   - render locally;
   - register artifact;
   - leave ready for media QA.
4. It must not call provider submission.
5. It must be idempotent:
   - rerun should not create duplicate active artifacts unless repair explicitly requests a new artifact.

**Required tests:**

1. `graphics_compositing` renders all pending `local_graphic` units.
2. It creates zero provider jobs.
3. Rerun is idempotent.
4. Old provider-generated local graphic can be invalidated and replaced locally.
5. Local graphic artifact is usable by assembly input builder.

### AUD-0401 — Audit local graphics rendering

**Owner:** Auditor

**Review checklist:**

1. `graphics_compositing` queries `local_graphic`.
2. Local rendering records DB artifact.
3. Artifact has provenance metadata.
4. No provider job path exists for local graphics.
5. Idempotency is tested.
6. Missing text spec fails loudly.
7. Existing renderer is reused rather than replaced wholesale.

**Commands:**

```bash
pytest tests/unit/test_local_graphics_db.py -q
pytest tests/integration/test_graphics_compositing_db.py -q
```

### VAL-0401 — Validate local graphic DB lifecycle

**Owner:** Validator

**Validation steps:**

1. Create synthetic production with:
   - one title card;
   - one lower-third;
   - one source card.
2. Run graphics compositing.
3. Query DB:

```sql
SELECT ru.id, ru.asset_type, ru.status, ru.active_artifact_id, a.uri, a.metadata_json
FROM render_units ru
LEFT JOIN artifacts a ON a.id = ru.active_artifact_id
WHERE ru.production_id = '<prod_id>'
ORDER BY ru.ordinal;
```

4. Query forbidden provider jobs:

```sql
SELECT pj.id
FROM provider_jobs pj
JOIN render_units ru ON ru.id = pj.render_unit_id
WHERE ru.production_id = '<prod_id>'
  AND ru.asset_type = 'local_graphic';
```

Expected: zero rows.

**Pass criteria:**

- all local graphics have artifacts;
- artifacts have local renderer provenance;
- no provider jobs exist for them.

---

## 7. Sprint 5 — Contract Media QA

### Objective

Make `qa_media` validate artifacts according to render method.

### ENG-0501 — Add media QA contract router

**Owner:** Engineer

**Files:**

```text
scripts/media_service.py
scripts/produce_db.py
scripts/production_repo.py
tests/unit/test_media_qa_contract.py
```

**Implementation steps:**

1. Add:

```python
def run_contract_media_qa(db, production_id: str, render_unit_id: str) -> dict:
    ...
```

2. Dispatch by render method/asset type:
   - provider video;
   - hero lipsync;
   - local graphic;
   - still/asset reuse.
3. Existing mechanical checks remain but are not sufficient.
4. Validation evidence must include:

```json
{
  "render_method": "...",
  "contract_version": "...",
  "file_exists": true,
  "sha_match": true,
  "dimensions_ok": true,
  "duration_ok": true,
  "provenance_ok": true,
  "text_policy_ok": true
}
```

### ENG-0502 — Local graphic QA

**Owner:** Engineer

**Implementation steps:**

For `local_graphic`, QA must check:

1. artifact exists;
2. active artifact is linked;
3. artifact provenance says local renderer;
4. no provider job exists for render unit;
5. deterministic text spec exists;
6. artifact metadata text-spec hash matches current text spec;
7. if OCR/text extraction is available, expected text approximately matches observed text.

Minimum acceptable first version:

- local provenance;
- no provider job;
- text spec hash match;
- file exists;
- dimensions/duration if MP4.

If OCR is unavailable, record it explicitly.

**Required tests:**

1. Provider-generated local graphic fails.
2. Local-rendered graphic passes.
3. Local graphic with wrong text hash fails.
4. Missing text spec fails.
5. Missing artifact fails.
6. No provider job exists check is enforced.

### ENG-0503 — Provider video text-policy QA

**Owner:** Engineer

**Implementation steps:**

For `text_policy=NO_VISIBLE_TEXT`:

1. sample frames;
2. run OCR if dependency available;
3. fail on visible readable text above threshold;
4. if OCR unavailable in strict mode, fail with explicit evidence.

Do not silently pass text policy if OCR is unavailable.

**Required tests:**

1. OCR unavailable + strict mode fails.
2. OCR unavailable + non-strict mode records warning but does not silently claim enforcement.
3. Synthetic frame with visible text fails if OCR/test detector is available or mocked.
4. Text-free synthetic frame passes.

### ENG-0504 — Status transitions on QA result

**Owner:** Engineer

**Implementation steps:**

On pass:

```text
validation.status = pass
render_unit.status = valid
```

On fail:

```text
validation.status = fail
render_unit.status = needs_repair
```

Do not leave failed render units marked valid.

**Required tests:**

1. Fail updates status to `needs_repair`.
2. Pass updates status to `valid`.
3. Latest validation result is used by downstream checks.
4. Historical failed validations remain in DB.

### AUD-0501 — Audit contract QA

**Owner:** Auditor

**Review checklist:**

1. QA dispatches by render method.
2. Local graphics cannot pass with provider provenance.
3. Text policy cannot be silently unenforced.
4. Evidence JSON is complete enough for repair.
5. Failures update DB state.
6. Mechanical checks still run.
7. Tests include forensic false-pass pattern.

**Commands:**

```bash
pytest tests/unit/test_media_qa_contract.py -q
pytest tests/integration/test_qa_media_db_contract.py -q
```

### VAL-0501 — Validate QA blocks known bad artifacts

**Owner:** Validator

**Validation steps:**

1. Use failed fixture:
   - local graphic provider row;
   - mechanical QA pass evidence.
2. Run new QA interpretation/regression test.
3. Confirm old evidence is insufficient.

**Required regression test:**

```text
tests/regression/test_failed_production_qa_rejected.py
```

Test:

- old `qa_media` evidence does not satisfy new contract;
- provider-generated local graphic fails;
- old final QA evidence does not imply media contract success.

**Commands:**

```bash
pytest tests/regression/test_failed_production_qa_rejected.py -q
pytest tests/unit/test_media_qa_contract.py -q
```

---

## 8. Sprint 6 — DB-Driven Repair Loop

### Objective

Repair should consume failed validations, classify them, choose repair actions, preserve history, and activate only passing artifacts.

### ENG-0601 — Add validation failure classifier

**Owner:** Engineer

**Files:**

```text
scripts/media_service.py
scripts/produce_db.py
tests/unit/test_repair_classifier.py
```

**Implementation steps:**

Add:

```python
def classify_validation_failure(validation_evidence: dict) -> str:
    ...
```

Classifications:

```text
missing_artifact
sha_mismatch
duration_shortfall
provider_forbidden_asset
unexpected_visible_text
local_graphic_not_local
local_graphic_text_mismatch
ocr_unavailable
hero_lipsync_unverified
unknown_contract_failure
```

**Required tests:**

Each classification above has at least one test.

### ENG-0602 — Add repair action decision table

**Owner:** Engineer

**Implementation steps:**

Add:

```python
def choose_repair_action(render_unit: dict, failure_class: str) -> str:
    ...
```

Actions:

```text
render_local_graphic
regenerate_provider_video
recover_artifact
rerun_qa
block_for_manual_review
```

Rules:

| Failure | Action |
|---|---|
| `local_graphic_not_local` | `render_local_graphic` |
| `local_graphic_text_mismatch` | `render_local_graphic` |
| `provider_forbidden_asset` | `render_local_graphic` if local graphic, else block |
| `unexpected_visible_text` | `regenerate_provider_video` |
| `missing_artifact` | `recover_artifact` |
| `sha_mismatch` | `block_for_manual_review` unless explicit recompute path |
| `ocr_unavailable` | block in strict mode |

**Required tests:**

Decision table test for each failure class.

### ENG-0603 — Implement DB repair lifecycle

**Owner:** Engineer

**Files:**

```text
scripts/produce_db.py
scripts/media_service.py
scripts/production_repo.py
tests/integration/test_repair_loop_db.py
```

**Implementation steps:**

Repair loop:

1. Query latest failed validations.
2. Load render unit.
3. Classify failure.
4. Choose action.
5. Mark old artifact inactive/stale where appropriate.
6. Create replacement artifact or new attempt.
7. Run QA again.
8. Activate replacement only on QA pass.
9. Preserve old artifacts and validations.

**Required tests:**

1. Provider-generated local graphic is repaired by local renderer.
2. Old provider artifact remains in DB but is inactive.
3. New local artifact becomes active only after QA pass.
4. Repair is idempotent.
5. Repair does not create duplicate active artifacts.
6. Repair does not assemble prematurely.

### AUD-0601 — Audit repair loop

**Owner:** Auditor

**Review checklist:**

1. Repair reads validation failures, not ad hoc filesystem state.
2. Failure classifier covers known failure modes.
3. Old artifacts are preserved but not active.
4. Replacement activation requires QA pass.
5. Idempotency is tested.
6. Strict mode blocks unresolved OCR/text uncertainty.
7. No hidden manual workaround.

**Commands:**

```bash
pytest tests/unit/test_repair_classifier.py -q
pytest tests/integration/test_repair_loop_db.py -q
```

### VAL-0601 — Validate repair fixes failed local graphic

**Owner:** Validator

**Validation steps:**

1. Seed DB with a failed provider-generated local graphic.
2. Run repair.
3. Query:

```sql
SELECT ru.id, ru.status, ru.active_artifact_id, a.metadata_json
FROM render_units ru
JOIN artifacts a ON a.id = ru.active_artifact_id
WHERE ru.id = '<render_unit_id>';
```

4. Query old artifacts for same render unit and confirm they are not active.
5. Rerun repair and confirm no duplicate active artifacts.

**Pass criteria:**

- repair replaces provider artifact with local artifact;
- history preserved;
- QA pass required;
- idempotent.

---

## 9. Sprint 7 — Assembly Preflight

### Objective

Assembly must consume only active, validated DB artifacts.

### ENG-0701 — Add assembly input validator

**Owner:** Engineer

**Files:**

```text
scripts/assemble_db.py
scripts/production_repo.py
tests/unit/test_assembly_preflight.py
```

**Implementation steps:**

Add:

```python
def validate_assembly_inputs(db, production_id: str, variant: str = "16x9") -> dict:
    ...
```

Checks:

1. active timeline spans exist;
2. no gaps/overlaps beyond tolerance;
3. each span maps to exactly one active render unit;
4. each selected render unit has active artifact;
5. each selected render unit has latest passing contract QA;
6. no stale render units selected;
7. no provider-generated local graphic selected;
8. files exist;
9. artifact set hash can be computed.

**Required tests:**

1. Missing render unit fails.
2. Missing artifact fails.
3. Failed QA fails.
4. Provider-generated local graphic fails.
5. Duplicate active artifact fails.
6. Valid minimal production passes.
7. Error messages identify failing span/render unit.

### ENG-0702 — Enforce preflight in `build_assembly_inputs`

**Owner:** Engineer

**Files:**

```text
scripts/assemble_db.py
tests/integration/test_assemble_db_valid_artifacts.py
```

**Implementation steps:**

1. Call `validate_assembly_inputs` before returning assembly inputs.
2. If failed:
   - raise `BLOCKED`;
   - do not write final MP4.
3. Store or return preflight evidence for final QA.

**Required tests:**

1. Assembly blocked on invalid artifact.
2. Assembly blocked on missing local graphic.
3. Assembly passes after repair and QA.
4. Assembly does not silently substitute files from disk.
5. Assembly evidence includes render unit IDs and artifact IDs.

### AUD-0701 — Audit assembly preflight

**Owner:** Auditor

**Review checklist:**

1. Assembly is not a QA bypass.
2. It refuses unvalidated artifacts.
3. It refuses provider-generated local graphics.
4. It uses DB state, not filesystem discovery.
5. Preflight evidence is usable by final QA.
6. Tests cover invalid and valid cases.

**Commands:**

```bash
pytest tests/unit/test_assembly_preflight.py -q
pytest tests/integration/test_assemble_db_valid_artifacts.py -q
```

### VAL-0701 — Validate assembly cannot consume bad forensic pattern

**Owner:** Validator

**Validation steps:**

1. Use fixture or synthetic DB with provider-generated local graphic.
2. Try assembly.
3. Expected:

```text
BLOCKED: assembly input validation failed
```

4. Repair it.
5. Rerun assembly.
6. Expected pass.

**Pass criteria:**

- bad media cannot assemble;
- repaired DB-valid media can assemble.

---

## 10. Sprint 8 — Final QA and Gates

### Objective

Final QA and review/publish gate must require DB-contract evidence, not only mechanical video checks.

### ENG-0801 — Extend final QA with DB-contract checks

**Owner:** Engineer

**Files:**

```text
scripts/qa_final.py
scripts/produce_db.py
scripts/production_repo.py
tests/unit/test_final_qa_contract.py
```

**Implementation steps:**

Keep existing mechanical checks:

- duration;
- frame count;
- black spans;
- freeze spans;
- audio/video mismatch.

Add DB-contract checks:

1. all selected render units have latest media QA pass;
2. all local graphics have local provenance;
3. no provider-generated local graphics;
4. all expected local graphics represented in assembly;
5. final deliverable artifact exists and SHA is recorded;
6. assembly preflight evidence exists;
7. no failed validation newer than last pass for selected render units.

**Required tests:**

1. Mechanical pass but missing DB contract fails.
2. Provider-generated local graphic fails.
3. Missing assembly preflight evidence fails.
4. Valid synthetic final passes.
5. Final QA evidence includes contract checks.

### ENG-0802 — Harden final review/publish gate

**Owner:** Engineer

**Files:**

```text
scripts/produce_db.py
scripts/stage_runner.py
tests/integration/test_gate_b_review_contract.py
```

**Implementation steps:**

Before final approval/publish:

1. require latest `qa_final` pass;
2. require final QA evidence includes DB-contract fields;
3. require no unresolved failed validations for selected render units;
4. require deliverable status is not `published` until gate passes.

**Required tests:**

1. Gate B blocks mechanical-only final QA.
2. Gate B blocks failed render-unit QA.
3. Gate B blocks missing local graphic provenance.
4. Gate B passes valid synthetic production.
5. Publish status not set before gate pass.

### AUD-0801 — Audit final QA/gate hardening

**Owner:** Auditor

**Review checklist:**

1. Final QA does not replace media QA; it checks DB evidence.
2. Mechanical-only final QA cannot pass gate.
3. Final deliverable is linked to artifact and validation.
4. Gate cannot publish with unresolved failed validations.
5. Tests include the known false-pass pattern.

**Commands:**

```bash
pytest tests/unit/test_final_qa_contract.py -q
pytest tests/integration/test_gate_b_review_contract.py -q
```

### VAL-0801 — Validate final gate blocks old failure

**Owner:** Validator

**Validation steps:**

1. Use failed final QA fixture.
2. Run new final QA/gate check.
3. Expected fail.
4. Run valid synthetic production.
5. Expected pass.

**Pass criteria:**

- old final QA evidence is insufficient;
- valid DB-contract evidence passes.

---

## 11. Sprint 9 — End-to-End No-Paid-Provider Dry Run

### Objective

Prove the full DB-native state machine works without paid generation.

### ENG-0901 — Add fake provider adapter for tests

**Owner:** Engineer

**Files:**

```text
tests/helpers/fake_provider.py
tests/integration/test_e2e_db_native_no_paid_provider.py
```

**Implementation steps:**

1. Fake provider must create tiny synthetic videos.
2. It must support:
   - generated video;
   - lipsync placeholder;
   - duration control;
   - dimensions control;
   - optional visible-text failure mode.
3. It must never call external APIs.

**Required tests:**

1. Fake provider creates expected file.
2. Fake provider can simulate visible-text failure.
3. Fake provider records deterministic SHA.

### ENG-0902 — End-to-end synthetic production test

**Owner:** Engineer

**Files:**

```text
tests/integration/test_e2e_db_native_no_paid_provider.py
```

**Implementation steps:**

Create synthetic production with:

1. one hero/lipsync render unit;
2. one safe text-free b-roll;
3. one local title card/lower-third;
4. one source card;
5. master narration placeholder;
6. final assembly.

Run stages or equivalent service calls:

```text
compile_media
gate_a_spend dry validation
generate_media fake provider
graphics_compositing
qa_media
repair if needed
assemble
qa_final
gate_b_review
```

**Required assertions:**

1. No provider job for local graphics.
2. Provider prompts contain no exact display text.
3. Local graphics render locally.
4. All artifacts registered in DB.
5. All render units have passing QA.
6. Assembly consumes only valid active artifacts.
7. Final QA passes.
8. Deliverable registered.
9. Rerun is idempotent or safely blocked.

### AUD-0901 — Audit end-to-end dry run

**Owner:** Auditor

**Review checklist:**

1. No external APIs.
2. DB state is checked at every stage.
3. Test includes provider video and local graphics.
4. Test includes final assembly and final QA.
5. Test checks negative cases or uses separate negative tests.
6. Test is not brittle on timestamps/paths.

**Command:**

```bash
pytest tests/integration/test_e2e_db_native_no_paid_provider.py -q
```

### VAL-0901 — Validate full no-paid pipeline

**Owner:** Validator

**Validation steps:**

Run:

```bash
pytest tests/unit -q
pytest tests/integration/test_e2e_db_native_no_paid_provider.py -q
pytest tests/regression -q
```

**Pass criteria:**

- full no-paid dry run passes;
- regression tests pass;
- no forbidden provider jobs created;
- no assembly of invalid artifacts.

---

## 12. Sprint 10 — Capped Production Smoke

### Objective

Run a controlled real smoke test with spend protection.

This sprint is the only sprint allowed to touch paid generation.

### ENG-1001 — Add strict smoke config

**Owner:** Engineer

**Implementation steps:**

Add or document config:

```yaml
strict_media_contract: true
strict_provider_prompt_text_free: true
strict_local_graphics: true
strict_final_qa_contract: true
allow_ocr_unavailable: false
max_paid_provider_jobs: 2
max_total_usd: 0.25
```

**Required checks:**

1. Spend gate reads cap.
2. Spend gate blocks if provider jobs exceed cap.
3. Spend gate blocks if forbidden provider job planned.
4. Spend gate blocks if provider prompt text-risk exists.

### ENG-1002 — Run compile-only smoke

**Owner:** Engineer

**Steps:**

1. Create a short production seed.
2. Run through compile/media plan only.
3. Do not call providers yet.
4. Dump DB state:

```sql
SELECT id, label, ordinal, asset_type, model, audio_policy, text_policy, status, metadata_json
FROM render_units
WHERE production_id = '<prod_id>'
ORDER BY ordinal;
```

5. Run forbidden provider plan query:

```sql
SELECT id, asset_type, metadata_json
FROM render_units
WHERE production_id = '<prod_id>'
  AND asset_type IN ('local_graphic', 'title_card', 'lower_third', 'source_card', 'quote_card', 'chart', 'diagram')
  AND metadata_json LIKE '%provider_visual_prompt%';
```

Expected: zero illegal provider-bound text specs.

### AUD-1001 — Audit compile-only smoke state

**Owner:** Auditor

**Review checklist:**

1. No local graphic planned for provider.
2. Exact text is in deterministic specs.
3. Provider prompts are text-free.
4. Spend estimate is capped.
5. DB state is coherent.

Auditor must approve before paid generation.

### VAL-1001 — Validate capped paid smoke

**Owner:** Validator

**Steps:**

1. Run only the approved capped provider jobs.
2. Render local graphics.
3. Run QA.
4. Run assembly.
5. Run final QA.
6. Query:

```sql
SELECT pj.id, ru.asset_type, pj.request_json
FROM provider_jobs pj
JOIN render_units ru ON ru.id = pj.render_unit_id
WHERE ru.production_id = '<prod_id>';
```

7. Confirm:
   - no local graphics provider job;
   - provider prompts text-free;
   - no illegal `negative_prompt`;
   - local graphics have local renderer provenance;
   - final QA includes contract evidence.

**Pass criteria:**

- final short smoke video passes;
- no garbled text;
- no provider-generated exact text;
- DB evidence proves correctness.

---

## 13. Global Regression Suite

After each sprint from Sprint 5 onward, run:

```bash
pytest tests/unit/test_media_contract.py -q
pytest tests/unit/test_provider_boundary.py -q
pytest tests/unit/test_paid_adapters_contract.py -q
pytest tests/unit/test_compile_media_prompt_split.py -q
pytest tests/unit/test_local_graphics_db.py -q
pytest tests/unit/test_media_qa_contract.py -q
pytest tests/unit/test_repair_classifier.py -q
pytest tests/unit/test_assembly_preflight.py -q
pytest tests/unit/test_final_qa_contract.py -q
pytest tests/regression -q
```

Before merge, run:

```bash
pytest tests/unit tests/integration tests/regression -q
```

If the full suite is too slow, Auditor must approve a documented subset, but the regression tests for the failed production are mandatory.

---

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

## 15. Merge Criteria

Do not merge until all are true:

1. Forensic regression fixtures exist.
2. Old failed production pattern is rejected by regression tests.
3. `local_graphic` cannot create provider jobs.
4. Provider prompts are text-free.
5. Exact display text is stored in deterministic specs.
6. Local graphics render locally and register DB artifacts.
7. Media QA validates render-method contracts.
8. Repair acts on validation failures and preserves history.
9. Assembly consumes only active validated DB artifacts.
10. Final QA requires DB-contract evidence.
11. End-to-end no-paid-provider test passes.
12. Capped smoke run passes or is explicitly deferred with Auditor sign-off.
13. No large forensic media files are added to `main`.
14. No paid provider call can occur before spend gate confirms legal render plan.

---

## 16. Final Handoff Prompt for Implementation Agents

Use this prompt for the implementation run:

```text
You are implementing the DB-native media platform remediation in repo wienbej01/content.

Do not rebuild the platform. Preserve the production database as the single source of truth. Make minimal changes to existing infrastructure.

Implement the ticketed sprint plan in docs/db_native_media_platform_remediation_tickets.md.

Critical invariants:
- local_graphic and all exact-text assets must never be sent to paid video providers.
- Provider prompts must be text-free and must not contain title cards, lower-thirds, source names, study names, researcher names, quotes, chart labels, captions, or subtitles.
- Exact text must be stored in deterministic_text_spec and rendered locally.
- Media QA must validate render-method contracts, not just file existence/duration/dimensions/SHA.
- Repair must operate from DB validation failures and preserve old artifacts as inactive/stale.
- Assembly must consume only active validated DB artifacts.
- Final QA and final gate must require DB-contract evidence.

Work ticket by ticket. For each Engineer ticket:
1. implement the minimal code change;
2. add required tests;
3. run the specified commands;
4. report files changed, tests run, and results.

For each Auditor ticket:
1. review code and tests;
2. check invariants;
3. list BLOCKER/MAJOR/MINOR issues;
4. do not allow progression with unresolved BLOCKER or MAJOR.

For each Validator ticket:
1. run black-box/integration/DB checks;
2. verify SQL invariants;
3. report any failure with reproduction commands.

If blocked, fail loudly with:
BLOCKED: <specific reason>

Do not make paid provider calls except in Sprint 10 capped smoke.
```

---

## 17. Compact Ticket Index

### Sprint 0

- ENG-0001: Create reduced forensic regression fixtures
- AUD-0001: Audit forensic fixture completeness
- VAL-0001: Validate baseline regression fixtures

### Sprint 1

- ENG-0101: Add `scripts/media_contract.py`
- ENG-0102: Add provider prompt risk detector
- AUD-0101: Audit media contract correctness
- VAL-0101: Validate media contract against forensic fixture

### Sprint 2

- ENG-0201: Enforce provider eligibility before provider job creation
- ENG-0202: Add adapter-level second guard
- ENG-0203: Capability-gate `negative_prompt`
- AUD-0201: Audit provider boundary
- VAL-0201: Validate no forbidden provider jobs can exist

### Sprint 3

- ENG-0301: Add render metadata split
- ENG-0302: Implement prompt sanitizer for provider visuals
- ENG-0303: Route exact text into deterministic text specs
- AUD-0301: Audit prompt/text split
- VAL-0301: Validate compile output DB state

### Sprint 4

- ENG-0401: Add DB-native local graphic rendering function
- ENG-0402: Fix `graphics_compositing` stage
- AUD-0401: Audit local graphics rendering
- VAL-0401: Validate local graphic DB lifecycle

### Sprint 5

- ENG-0501: Add media QA contract router
- ENG-0502: Local graphic QA
- ENG-0503: Provider video text-policy QA
- ENG-0504: Status transitions on QA result
- AUD-0501: Audit contract QA
- VAL-0501: Validate QA blocks known bad artifacts

### Sprint 6

- ENG-0601: Add validation failure classifier
- ENG-0602: Add repair action decision table
- ENG-0603: Implement DB repair lifecycle
- AUD-0601: Audit repair loop
- VAL-0601: Validate repair fixes failed local graphic

### Sprint 7

- ENG-0701: Add assembly input validator
- ENG-0702: Enforce preflight in `build_assembly_inputs`
- AUD-0701: Audit assembly preflight
- VAL-0701: Validate assembly cannot consume bad forensic pattern

### Sprint 8

- ENG-0801: Extend final QA with DB-contract checks
- ENG-0802: Harden final review/publish gate
- AUD-0801: Audit final QA/gate hardening
- VAL-0801: Validate final gate blocks old failure

### Sprint 9

- ENG-0901: Add fake provider adapter for tests
- ENG-0902: End-to-end synthetic production test
- AUD-0901: Audit end-to-end dry run
- VAL-0901: Validate full no-paid pipeline

### Sprint 10

- ENG-1001: Add strict smoke config
- ENG-1002: Run compile-only smoke
- AUD-1001: Audit compile-only smoke state
- VAL-1001: Validate capped paid smoke
