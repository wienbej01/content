# Current Repo Findings

Branch:

`forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z`

Relevant observed state from prior repo inspection:

## Assembly and lip-sync

- The repo has identified the key root cause: provider audio may be internally synced but shifted/padded relative to the source slice. If assembly strips provider audio and overlays the raw source/master audio, lip sync can break by hundreds of milliseconds.
- The repo has added audio-offset evaluation, SyncNet evaluation, compensated hero remux, and a SyncNet gate.
- The current manifest can carry `compensated_artifact_path` for hero segments.
- The current continuous voiceover path still mutes visual clips and overlays one global master narration track. This conflicts with hero lip-sync island requirements.

## Existing files to preserve/extend

Likely relevant:

- `scripts/assemble.py`
- `scripts/assemble_db.py`
- `scripts/evals/eval_audio_offset.py`
- `scripts/evals/eval_syncnet.py`
- `scripts/evals/remux_compensated_hero.py`
- `tests/test_compensated_hero_assembly.py`
- `tests/test_syncnet_gate.py`
- `tests/test_eval_audio_offset.py`
- `tests/test_eval_syncnet.py`
- `db/migrations/008_provider_audio_offset.sql`
- `db/migrations/009_compensated_hero_artifact.sql`

## Existing production sample

The inspected final sample had:

- S000 hero/lipsync
- S001 labelled generated_video/BROLL_FLEX
- S002 hero/lipsync
- S003 local_graphic/SILENT_GRAPHIC

Issues observed:

- Sync improved but still perceptibly slightly off.
- Existing threshold allowed S000 +80ms under a 160ms threshold; this is too loose for close corporate A-roll.
- B-roll label did not guarantee the viewer saw meaningful b-roll.
- Graphic was visually weak and topic-misaligned.
- Test-local resolution/output should not be called publish-grade.

## Planning implication

The system is viable, but it must become stricter and more semantically aware. It needs:

1. audio islands for hero
2. stricter per-segment SyncNet
3. shot-mix contract
4. semantic visual-role QA
5. deterministic professional graphics
6. candidate selection
7. publish vs test profiles
