# Flagship 001 — Production Status

**Last updated:** 2026-06-10T05:43 SGT

## Current State: BLOCKED → RESOLVED (model switch needed)

### Problem
- `seedance_2_0` rejects ALL human face reference images due to ByteDance's upstream "Portrait Library" deepfake prevention filter (tightened after Feb 2026 Hollywood lawsuit)
- This is platform-wide and permanent for seedance_2_0 with real face references

### Tested Alternatives (all PASSED with face + audio + ref image):

| Model | Face | Audio (lipsync) | Ref Image | Status |
|-------|------|-----------------|-----------|--------|
| `cinematic_studio_3_0` | ✅ | ✅ | ✅ | **RECOMMENDED** |
| `wan2_7` | ✅ | ✅ | ✅ | Works |
| `kling3_0` | ✅ | ❌ no --audio | ✅ | No lipsync |
| `seedance_2_0` | ❌ nsfw | ✅ | ❌ blocked | Dead for humans |

### Next Action Required
1. Choose model: `cinematic_studio_3_0` (recommended) or `wan2_7`
2. Update `scripts/generate_media.py` line: `DEFAULT_LIPSYNC_MODEL = "cinematic_studio_3_0"`
3. Re-run: `python3.13 scripts/generate_media.py scripts/generated/flagship_001_learn_half_time.json --assemble`
4. Monitor: `tail -f /tmp/flagship_001_media_gen3.log`
5. After completion: send to Telegram for Gate B review

### Assets Ready
- ✅ 9 narration MP3s: `Videos/Projects/flagship_001_learn_half_time/narration/`
- ✅ Reference images: `assets/reference/studio_library/canonical/`
- ✅ Script JSON: `scripts/generated/flagship_001_learn_half_time.json`
- ✅ Manifest: `Videos/Projects/flagship_001_learn_half_time/manifest.json`
- ❌ Media (0/9): `assets/media/flagship_001/` — empty

### Higgsfield Account
- Email: jacobwienberg@gmail.com
- Plan: Plus
- Credits: 411.96
- Auth: Re-authenticated 2026-06-09 ~23:08 SGT

### Research Sources (Brave Search)
- ByteDance "Portrait Library" filter: reddit.com/r/generativeAI
- Face-in-image triggers rejection before prompt processing: morphic.com
- Hollywood lawsuit pressure (Feb 2026): vicsee.com/blog/seedance-content-filter
- Workarounds (Soul Cast, sketch, grid): reddit.com/r/HiggsfieldAI
- Lipsync Studio (web-only feature): higgsfield.ai/lipsync-studio
