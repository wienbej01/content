# S07_T002 Audio Alignment Report

## Summary
Audio alignment analysis between source slice, provider diagnostic audio, and canary container audio.

## Duration and Silence

| Source | Duration | Lead Silence | Trail Silence |
|--------|----------|-------------|--------------|
| Source slice | 4.572s | 0.000s | 0.082s |
| Provider diagnostic | 5.062s | **0.240s** | 0.035s |
| Canary container | 5.062s | — | — |

The provider diagnostic audio has **240ms of leading silence** not present in the source slice.
The diagnostic audio is **490ms longer** than the source slice.

## Comparison Methods

| Method | Offset (ms) | Confidence | Note |
|--------|------------|------------|------|
| Raw xcorr (src vs diag) | -574.94 | 0.1736 | Large offset |
| Trimmed xcorr (src vs diag) | -334.56 | 0.1711 | Improved after silence removal |
| Envelope xcorr (src vs diag) | — | 0.0 | Failed — signals too different |
| Raw xcorr (canary vs diag) | **0.0** | **1.0000** | Perfect match |
| Trimmed xcorr (canary vs diag) | **0.0** | **1.0000** | Perfect match |

## Key Findings

1. **Canary container audio == Provider diagnostic audio** (0ms offset, confidence 1.0)
   - The audio extracted from the canary video AND the diagnostic audio are identical.
   - The diagnostic audio is a faithful extraction of the canary's audio track.

2. **Provider shifted the audio** relative to the source slice by ~335-575ms
   - 240ms is explained by leading silence prepended by the provider
   - The remaining offset (~95-335ms) is likely content padding or timing drift
   - The provider did NOT send back the exact same audio it received

3. **SyncNet confirms canary lip sync is acceptable** (-40ms offset, confidence 10.0)
   - The face/mouth in the canary video is synced to the canary's OWN audio track
   - Internal lip sync is fine — the video matches its own audio
   - The external audio alignment (source slice vs provider output) shows the shift

## Classification: **B_AUDIO_SLICE_SHIFTED_OR_PADDED**

The provider received the correct source slice but returned audio that is shifted/padded.
The canary's internal lip sync is acceptable per SyncNet.
The root cause is provider-side audio processing that alters timing.

## Recommended Action
- The provider's Seedance model returned audio with prepended silence and shifted timing
- This is a provider behavior issue, not a source slice issue
- If the assembly uses the correct audio window (not the shifted diagnostic), lip sync may be correct
- Verify assembly master window alignment independently (S02_T002)
