# 02 Failure Taxonomy

This file defines canonical failure classes. Agents must use these labels in reports and JSON ledgers. Add new labels only if no existing label fits.

## Lipsync and audio provenance

### F-LIP-001: Mouth/audio offset

The speaker's mouth motion does not align with the audible phonemes in final output.

Required evidence:

```text
- SyncNet/Wav2Lip/equivalent score, OR
- clear frame/audio forensic evidence marked as provisional
```

Repair candidates:

```text
- verify source audio slice
- verify final master window
- re-render affected hero unit with correct slice
- avoid final audio overlay if not provably aligned
```

### F-LIP-002: No face track found

A hero-lipsync unit cannot be evaluated because the face detector cannot track the speaker.

Repair candidates:

```text
- regenerate with clearer close-up face
- add reference-image/prompt constraints
- mark eval inconclusive and require human review
```

### F-LIP-003: Provider output audio mismatch

The audio embedded in provider output does not match the source slice sent in the provider request.

Repair candidates:

```text
- inspect provider request payload
- re-submit with correct audio_path
- reject provider output if provider altered timing materially
```

### F-LIP-004: Final master window mismatch

The final master narration window under a hero visual does not match the source slice used to generate that visual.

Repair candidates:

```text
- fix timeline span boundaries
- fix assembly timing map
- preserve provider audio for that segment only if policy allows
```

## Assembly/timing

### F-ASM-001: Hero temporal edit

A HERO_SYNC_LOCKED visual was speed-changed, looped, frozen, reversed, interpolated, or trimmed through speech.

Repair candidates:

```text
- fail assembly
- regenerate exact-duration hero unit
- change timeline split, not video speed
```

### F-ASM-002: Visual bed duration mismatch

The concatenated visual bed does not match master narration duration within tolerance.

Repair candidates:

```text
- regenerate short clips
- split long spans
- fix timeline contract
```

### F-ASM-003: Static hold excessive

A static image/graphic/card persists longer than allowed without explicit hold policy.

Repair candidates:

```text
- split graphic into progressive beats
- add animation/motion treatment
- shorten graphic span
```

## Graphics/text

### F-GFX-001: Static graphic hold excessive

A deterministic graphic is held too long.

### F-GFX-002: Graphic editorial value weak

The graphic is readable but does not complete the idea, has weak hierarchy, or looks like an unfinished title.

### F-GFX-003: Missing deterministic text spec

A local graphic lacks its deterministic text specification or hash.

### F-TEXT-001: Provider text-risk surface

Provider-generated clip contains or likely contains screens/documents/labels/readable text when policy says no visible text.

## QA/evidence

### F-QA-001: Fake-green QA

A validation passes without checking the failure it claims to cover.

### F-QA-002: Missing eval artifact

A required eval output is absent, empty, malformed, or not linked to the relevant subject.

### F-PROV-001: Broken or incomplete provenance

DB/artifact records cannot prove lineage across source input, provider request, provider output, and final assembly.

### F-PROV-002: Wrong hash target

A provenance field stores the hash of a generated video/artifact where it should store the source audio slice hash, source prompt hash, or deterministic text spec hash.

## Provider/spend

### F-SPEND-001: Render lock violation

A video render/provider job was submitted before readiness unlock.

### F-SPEND-002: Non-idempotent provider request

Provider request can be repeated without a stable idempotency key.
