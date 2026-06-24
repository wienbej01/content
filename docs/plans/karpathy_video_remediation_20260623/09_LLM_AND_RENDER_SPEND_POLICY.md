# 09 LLM and Render Spend Policy

## Summary

LLM calls are allowed from the start. Actual video render calls are not.

## Allowed immediately

```text
- LLM analysis and planning
- LLM code generation through Kilo
- LLM review/audit prompts
- local deterministic graphics rendering
- ffmpeg/ffprobe analysis of existing files
- local tests and evals
- dry-run provider request construction
```

## Restricted

TTS/audio provider calls are not the same as video render, but they can still cost money and can disturb provenance. Use existing fixture audio unless a ticket explicitly allows TTS. If a ticket allows TTS, it must log cost and artifact hashes.

## Forbidden before Sprint 06

```text
- external video generation
- Higgsfield real generation
- bulk provider regeneration
- provider jobs submitted without explicit dry-run
```

## Unlock protocol for actual render

Actual video render is allowed only in Sprint 06 after all readiness gates pass and this file exists:

```text
ops/ACTUAL_RENDER_UNLOCK.json
```

Required content:

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

## Canary limit

The first actual render after unlock is one hero-lipsync canary render unit only. No full production rerender until the canary passes:

```text
- source slice hash verified
- provider request hash recorded
- provider diagnostic audio extracted
- audio-to-audio offset within threshold
- SyncNet/lipsync eval passes or returns calibrated inconclusive with human review
```
