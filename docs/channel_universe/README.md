# Channel Universe — Creative Control Layer

This folder is the creative control layer for the Leverage Mind channel. Every AI-driven step in the production pipeline — storyboard generation, media-prompt compilation, media QA, and reviewer gates — must consult these documents before generating or evaluating anything.

## What this folder contains

| File | Purpose |
|---|---|
| `UNIVERSE_BIBLE.md` | What exists in the James channel world |
| `JAMES_CHARACTER_BIBLE.md` | James Harrington in production detail |
| `JAMES_RECORDING_STUDIO_LIBRARY.md` | The fixed recurring set + approved camera angles |
| `BACKGROUND_CAT_BIBLE.md` | The occasional recurring cat |
| `PEOPLE_AND_EXTRAS_BIBLE.md` | Other people and how they may appear |
| `FORBIDDEN_PATTERNS.md` | Explicit universe failures with detection and replacement guidance |
| `REFERENCE_ASSET_MANIFEST.md` | The ID'd reference image library |
| `TECHNICAL_BIBLE.md` | Production grammar: color, lighting, camera, framing, audio, editing, model constraints |
| `PROMPT_RULES.md` | How compiled media prompts must be structured; source hierarchy; examples |
| `QA_RUBRIC.md` | Scoring rubric for storyboard, prompt plan, media, audio, and final assembly QA |
| `constraints.json` | Machine-readable subset of key constraints for storyboard validator, prompt compiler, and QA scripts |

## What this folder is NOT

These documents define two complementary layers:

- **Universe Bible** (UNIVERSE_BIBLE.md and its companions): **what exists** in the James world — who James is, where he records, what the cat looks like, what environments are allowed, what is forbidden.
- **Technical Bible** (TECHNICAL_BIBLE.md): **how the universe is produced** — color, lighting, camera grammar, framing, audio rules, editing rules, model constraints.

`constraints.json` is the machine-readable subset of both layers, designed for use by Python scripts, storyboard validators, prompt compilers, and QA tools without needing to parse the full markdown bibles.

## Why it exists

Without a shared creative universe, every AI-generated scene invents its own world. Eight prompts produce eight unrelated micro-films. These documents prevent that by defining what belongs in the James world, who James is, where he records, and what must never appear — so later storyboard and media-generation steps can create freely *within* the universe instead of independently.

## How to use it

1. **Storyboard generator** (`scripts/storyboard.py`): reads universe bibles to validate that beats use allowed locations, respect James presence rules, and avoid forbidden patterns.
2. **Media-prompt compiler** (`scripts/compile_media_prompts.py`): reads these bibles and `constraints.json` to inject universe constraints into every generated video prompt.
3. **Media QA** (`scripts/qa_media.py`): reads `QA_RUBRIC.md` and `FORBIDDEN_PATTERNS.md` to score clips for universe compliance.
4. **Reviewer gates** (`scripts/review_*.py`): reads these bibles as context when evaluating whether a script or storyboard may proceed to generation.

## Relationship to `brand/BRAND_SPEC.md`

`brand/BRAND_SPEC.md` is the single source of truth for brand identity: name, tagline, persona summary, color palette, typography, and voice settings. These documents **extend** BRAND_SPEC with production-grade creative specificity. Where BRAND_SPEC states a rule, these bibles cite it and add actionable detail for AI generation.

## Bounded universe, not a rigid formula

These documents define a bounded creative world, not a scene-by-scene template. The AI model and the storyboard author may create freely inside the universe. The bibles prevent the universe from being abandoned; they do not prevent creative variation within it.
