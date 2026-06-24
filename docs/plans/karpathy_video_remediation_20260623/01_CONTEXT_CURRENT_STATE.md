# 01 Context: Current State

## Branch and fixture

```text
branch=forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z
production_id=prod_2f9bb58c0508465fb51ac6b4578bba92
fixture=prod_2f9bb58c0508465fb51ac6b4578bba92_16x9.mp4
```

## Observed bad final video

From manual/video forensic inspection of the uploaded MP4:

```text
Duration: about 22.9s
Resolution: 1920x1080
FPS: 24
Audio: AAC stereo
Scenes:
  0.00-4.58s   James hero talking head
  4.58-10.46s  phone b-roll
  10.46-15.67s James hero talking head with small caption
  15.67-22.90s static black graphic/title card
```

Observed failure classes:

```text
F-LIP-001: suspected severe mouth/audio lipsync offset
F-GFX-001: long static graphic hold
F-GFX-002: deterministic graphic exists but editorial content is weak/underdeveloped
F-TEXT-001: phone/screen text-risk surface
F-QA-001: QA likely passes without objective lipsync validation
F-PROV-001: insufficient proof that source audio slice == provider request audio == final master window
```

## Current architecture facts to verify in repo

Expected DB-native path:

```text
scripts/produce_db.py
scripts/production_db.py
scripts/production_repo.py
scripts/media_service.py
scripts/paid_adapters.py
scripts/render_graphics.py
scripts/assemble_db.py
scripts/assemble.py
scripts/stage_runner.py
scripts/media_contract.py
```

Expected canonical stages:

```text
research -> write_script -> review_script -> gate_a_content -> storyboard -> review_storyboard -> tts -> audio_timing -> reconcile_timing -> compile_media -> gate_a_spend -> generate_media -> qa_media -> repair -> graphics_compositing -> assemble -> qa_final -> gate_b_review -> publish -> analytics
```

Expected policy model:

```text
HERO_SYNC_LOCKED units must use master narration.
Provider audio is diagnostic only.
Final assembly may mute provider audio and overlay master narration only if exact audio-slice alignment is proven.
Local graphics must not go to providers.
```

## Current highest-risk design assumption

Continuous-voiceover assembly can be correct only if the system proves:

```text
source audio slice used for provider generation == exact master-audio window used in final assembly
```

If this proof is absent or wrong, the final video may have clean audio and plausible mouth motion but bad lipsync.

## Primary remediation thesis

Do not first regenerate videos. First prove the chain:

```text
script text -> master narration -> timing span -> source slice -> provider request -> provider output -> diagnostic provider audio -> final assembly window -> final MP4
```

The fix is not “try another prompt.” The fix is an evidence loop.
