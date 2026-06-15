# Command Log

Audit root: `/home/jacobw/YTchannel`  
Target: `Videos/Projects/using_ai_to_help_memory_retention_short`  
Started: `2026-06-14T10:26:22+0800`

No paid API, ElevenLabs, Higgsfield, Seedance, or Kling generation command was executed.

## Discovery and Inventory

```bash
find Videos -maxdepth 4 -type d -iname '*memory*' -o -type f -iname '*memory*'
find Videos/Projects/using_ai_to_help_memory_retention_short -maxdepth 6 -printf ...
rg --files docs scripts tests
rg -n 'duration|freeze|lipsync|music|overlay|QA|manifest|state|resume' video_forensic_audit_report.md
find assets/media -maxdepth 4 -printf ...
rg -l 'assets/media/001_hook/B001.mp4|assets/media/001_hook/B002.mp4' Videos scripts/generated
```

Key result: B001 and B002 media files predate project creation and are referenced by several other projects. B001-B003 have no current generation-log record.

## Documentation and Code Inspection

```bash
sed -n '1,320p' docs/PIPELINE.md
sed -n '1,260p' video_forensic_audit_report.md
cat docs/plans/AUDIO_SYSTEM_APPROVED.md
cat docs/plans/LIPSYNC_TICKETS.md
cat docs/plans/audits/VISUAL_PIPELINE_AUDIT.md
cat docs/archive/2026-06-13_doc_overhaul/PIPELINE_GAPS_AND_PENDING_STEPS.md
rg -n ... docs/plans/PRODUCTION_V2_BLUEPRINT.md docs/archive/.../REVIEW_AND_QUALITY_SYSTEM.md docs/archive/.../RUNBOOK_PRODUCTION_V2.md
nl -ba scripts/produce.py | sed -n ...
nl -ba scripts/audio_timing.py | sed -n ...
nl -ba scripts/slice_continuous_lipsync.py | sed -n ...
nl -ba scripts/qa_media.py | sed -n ...
nl -ba scripts/generate_media.py | sed -n ...
nl -ba scripts/compile_media_prompts.py | sed -n ...
nl -ba scripts/assemble.py | sed -n ...
nl -ba scripts/tts.py | sed -n ...
nl -ba scripts/qa_final.py | sed -n ...
rg -n 'qa_final|render_graphics|composite_overlays' scripts tests docs/PIPELINE.md README.md
```

Key results: QA status casing mismatch, non-fatal compile errors, stale existing-file reuse, 10s lipsync clamp, one-second `tpad`, continuous-mode baked-audio discard, no overlay wiring, no music block, no final-QA orchestration, and unsafe resume semantics.

## Final MP4 Forensics

```bash
ffprobe -hide_banner -v error -show_format -show_streams -of json \
  Videos/Projects/using_ai_to_help_memory_retention_short/using_ai_to_help_memory_retention_short_16x9.mp4 \
  > reports/forensics/video_pipeline_audit_20260614_102622/ffprobe_final.json

ffmpeg -hide_banner -nostdin -i FINAL.mp4 \
  -map 0:v:0 -vf 'freezedetect=n=-50dB:d=0.5' -an -f null - \
  2> reports/forensics/video_pipeline_audit_20260614_102622/freezedetect_final.log

ffmpeg -hide_banner -nostdin -i FINAL.mp4 \
  -map 0:a:0 -af 'silencedetect=n=-45dB:d=0.5,volumedetect' -vn -f null - \
  2> reports/forensics/video_pipeline_audit_20260614_102622/audio_silence_vol_final.log
```

Result: container 146.600000s; video 83.333333s/2,000 frames; audio 146.600000s; mismatch 63.266667s.

## Existing Final QA Reproduction

```bash
python3 scripts/qa_final.py \
  Videos/Projects/using_ai_to_help_memory_retention_short/using_ai_to_help_memory_retention_short_16x9.mp4 \
  --output reports/forensics/video_pipeline_audit_20260614_102622/qa_final_existing_code.json
```

Observed output: `final cut PASS ... audio==video (146.6s)`. This is a false pass caused by using format duration as video duration.

## Beat and Media Probes

```bash
ffprobe -v error -show_entries format=duration \
  -show_entries stream=index,codec_type,duration,nb_frames,width,height \
  -of compact=p=0:nk=0 assets/media/.../Bxxx.mp4

ffmpeg -hide_banner -nostdin -i assets/media/.../Bxxx.mp4 \
  -vf 'freezedetect=n=-50dB:d=0.5' -an -f null -
```

Results: source media sum 75.731656s; normalized `cont_seg_*` sum 83.333336s. No source clip triggered freeze detection; final freezes align with one-second assembly padding.

## Visual Evidence Frames

```bash
ffmpeg -hide_banner -loglevel error -ss 15 -i FINAL.mp4 -frames:v 1 frame_B003_laptop.png -y
ffmpeg -hide_banner -loglevel error -ss 28 -i FINAL.mp4 -frames:v 1 frame_B005_notebook.png -y
ffmpeg -hide_banner -loglevel error -ss 46 -i FINAL.mp4 -frames:v 1 frame_B007_notebook.png -y
```

The extracted frames confirm pseudo-UI and pseudo-handwriting. Files are retained in this report directory.

## Tests

```bash
python3 -m pytest -q \
  tests/test_qa_media.py \
  tests/test_continuous_voiceover.py \
  tests/test_assemble.py \
  tests/test_generate_media.py \
  tests/test_audio_timing.py
```

Result: `61 passed in 34.74s`. This confirms a production-case coverage gap; it does not validate the artifact.

## Report Generation

Local Python inspection commands joined JSON artifacts and ffprobe output to write:

- `artifact_inventory.csv`: 73 rows, including expected-missing and stale/unprovenanced classification.
- `duration_reconciliation.csv`: 10 beat rows; 146.599s expected vs 83.333336s actual visual coverage.

Two initial CSV-generation attempts failed locally due to defensive-script errors (`None` audio slice handling and a dead comparison). They wrote no final output and were corrected; the delivered CSVs were regenerated successfully.
