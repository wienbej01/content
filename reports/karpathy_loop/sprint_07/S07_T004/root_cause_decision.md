# S07_T004 Root Cause Decision

## Classification: **E_ASSEMBLY_MASTER_WINDOW_FAILURE** caused by **B_AUDIO_SLICE_SHIFTED_OR_PADDED**

---

## 1. Evidence Table

| Source | Test | Result | Verdict |
|--------|------|--------|---------|
| **S07_T001** | SyncNet on canary (provider audio) | **-40ms offset, confidence 10.0** | **PASS — provider sync is good** |
| **S07_T001** | SyncNet on baseline S002 track | -600ms offset, confidence 0.791 | FAIL — original fixture S002 is bad |
| **S07_T002** | Audio raw xcorr (source vs diagnostic) | -575ms | Provider audio shifted |
| **S07_T002** | Audio trimmed xcorr (source vs diagnostic) | -335ms | More reliable estimate |
| **S07_T002** | Audio canary container vs diagnostic | 0ms, confidence 1.0 | Diagnostic = canary audio (faithful extraction) |
| **S07_T002** | Diagnostic leading silence | 240ms | Provider prepended silence |
| **S07_T003** | Visual quality: face detected | 100% frames | Canary is visually usable |
| **S07_T003** | Remux A: control (provider audio) | **-40ms PASS** | **Provider internal sync is correct** |
| **S07_T003** | Remux B: raw source overlay (no offset) | **+400ms FAIL** | **Uncompensated source overlay breaks sync** |
| **S07_T003** | Remux C1: source + 335ms delay | **+80ms PASS** | **Compensation restores sync** |
| **S07_T003** | Remux C2: source + 575ms delay | -160ms FAIL | Overcorrection |
| **S07_T003** | Remux C3: source + 240ms delay | +160ms FAIL | Undercorrection |

---

## 2. Failed Hypotheses Rejected

### ❌ Provider is incapable of good lip sync
- **Rejected because:** The canary with provider audio scores **-40ms, confidence 10.0 on SyncNet**. The provider CAN generate good lip sync. The original S002 segment failure may be a different issue (wrong timing parameters, different source slice), but the canary S000 proves provider capability.

### ❌ Bad visual / reference image
- **Rejected because:** Face detected in **100% of frames**. Mouth motion detected (mean frame diff 2.1, non-zero). Reference image is the canonical James medium shot.

### ❌ Missing diagnostic audio
- **Rejected because:** Diagnostic audio extracted and verified: `canary_pjob_...diagnostic_audio.wav` (486KB), 5.062s. Matches canary container audio perfectly (0ms offset, confidence 1.0).

### ❌ Insufficient render freshness
- **Rejected because:** Freshness gate passed 10/10. New provider_job row (`pjob_fe40c769...`), new artifact (`art_e5f7eeb9...`), submitted_at and completed_at both after unlock timestamp.

### ❌ Full-production issue
- **Rejected because:** The canary was a single S000 segment, not a full assembly. The issue is reproducible with a single hero unit and does not require full production context.

---

## 3. Raw Source/Master Overlay is Unsafe

The remux experiment proves definitively:

```
A_control (provider audio)  →  SyncNet: -40ms  ✔ PASS  ← provider's audio is in-sync
B_raw_source (no offset)    →  SyncNet: +400ms ✗ FAIL  ← raw source overlay is broken
C1_335ms (corrected)        →  SyncNet: +80ms  ✔ PASS  ← 335ms delay restores acceptable sync
```

**Raw source/master audio overlay on HERO_SYNC_LOCKED video is unsafe unless the provider's audio shift is measured and compensated.**

The provider pads/processes the audio before embedding it in the generated video. If assembly strips this audio and overlays the original source slice without compensation, the visual-audio offset increases by approximately **335ms**, pushing the result from **PASS (-40ms)** to **FAIL (+400ms)**.

---

## 4. Required Assembly Invariant

For every HERO_SYNC_LOCKED render unit where provider diagnostic audio offset exceeds threshold (≥160ms):

> **Assembly must either:**
> 
> **A.** Apply measured audio/video offset compensation before overlaying master audio, OR
> **B.** Preserve provider audio for the hero unit (use as-is), OR
> **C.** Block assembly and request re-slice/re-render.

### Implementation sketch (not implemented)

```python
# In assembly preflight or assembly segment processing:
def _check_provider_audio_offset(render_unit_id, diagnostic_audio_path, source_slice_path) -> dict:
    \"\"\"Measure provider audio offset before deciding audio overlay strategy.\"\"\"
    offset = compute_audio_offset(source_slice_path, diagnostic_audio_path)
    if abs(offset) < 160:  # threshold
        return {"action": "use_master_audio", "compensation_ms": 0}
    elif abs(offset) < 600:
        return {"action": "use_master_audio_with_compensation", "compensation_ms": offset}
    else:
        return {"action": "block_assembly", "reason": f"Provider audio offset {offset}ms exceeds salvage threshold"}
```

---

## 5. Decision

| Field | Value |
|-------|-------|
| Classification | `E_ASSEMBLY_MASTER_WINDOW_FAILURE` |
| Caused by | `B_AUDIO_SLICE_SHIFTED_OR_PADDED` |
| Confidence | High — SyncNet + audio xcorr + remux experiment all agree |
| Evidence count | 12 checks across 3 tickets |
| Root cause | Assembly strips provider audio (which is in-sync) and overlays unadjusted source slice |
| Effect | ~335ms uncompensated shift → SyncNet offset goes from -40ms (PASS) to +400ms (FAIL) |
| Compensation needed | ~335ms delay applied to source audio before overlay restores PASS |

## Output
Proceed to **S07_T005** (Next Render Strategy) to design the fix.
