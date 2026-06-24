# Loop Decision: S07_T001 SyncNet or Reliable Lipsync Metric

## Result: SYNCNET_AVAILABLE — LIP SYNC EVALUATED

SyncNet was installed and successfully evaluated both the bad fixture and the fresh canary.

## Critical finding
The canary S000 lip sync is **ACCEPTABLE** (SyncNet offset: -1 frame / -40ms, confidence: 10.000).
The original bad fixture has **MIXED** results:
- S000 segment: acceptable (+1 frame / +40ms)
- S002 segment: **BAD** (-15 frames / -600ms)

**Root cause narrowed:** The S002 hero lipsync segment (10.46-15.67s) has severe lip sync failure in the original fixture. The S000 segment was always acceptable.

## SyncNet installation status
- SyncNet: INSTALLED at `syncnet_python/`
- Dependencies: torch, opencv, scipy, python_speech_features
- Usage: `cd syncnet_python && python3 run_pipeline.py ... && python3 run_syncnet.py ...`

## Decision: PASS_TO_NEXT_TICKET
Proceed to **S07_T002** (Audio Slice vs Provider Diagnostic Alignment) to verify the audio alignment for both S000 and S002 segments.
