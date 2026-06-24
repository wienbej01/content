# Video Forensic Report: S00_T002

## Subject
fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4
SHA256: 35b972d44c3c4e20090a568aa915aa947e8c46865408344a7d4c31df6bca0386

## Media Properties
- Duration: 22.9s (video 22.833s, audio 22.900s)
- Resolution: 1920x1080
- FPS: 24 (548 frames)
- Video: H.264 High, yuv420p
- Audio: AAC LC, stereo, 96kHz
- Bitrate: 3.6 Mbps total
- Encoder: Lavf61.7.100 / Lavc61.19.101 libx264
- Mean volume: -19.5 dB, Max: -2.9 dB
- No silence gaps detected (continuous audio)

## Scene Timeline (ffmpeg scene detection, threshold=0.1)
| Scene | Start | End | Duration | Type |
|-------|-------|-----|----------|------|
| 1 | 0.000s | 4.583s | 4.583s | Hero talking head (S000) |
| 2 | 4.583s | 10.458s | 5.875s | Phone b-roll |
| 3 | 10.458s | 15.667s | 5.209s | Hero talking head (S002) |
| 4 | 15.667s | 22.833s | 7.166s | Static black graphic |

## Static Hold Analysis (ffmpeg blackdetect)
- Black detected: 15.667s – 22.792s
- Duration: 7.125 seconds (31.1% of total runtime)
- Frames at 17s, 19s, 21s are identical (40264 bytes each) — confirmed static
- Classification: F-GFX-001 (Static graphic hold excessive)

## Hero Talking Head Analysis
### Scene 1 (0.000-4.583s)
- DB label: S000, HERO_SYNC_LOCKED
- Render units: slot-based splits (0-11638ms, 11638-23276ms in original timing)
- Audio policy: HERO_SYNC_LOCKED
- Text policy: NO_VISIBLE_TEXT
- Narrative claim: "Your phone interrupts you constantly..."
- Active artifact: art_591c2070 (generated_media) from last generation round

### Scene 3 (10.458-15.667s)
- DB label: S002, HERO_SYNC_LOCKED
- Audio policy: HERO_SYNC_LOCKED
- Text policy: NO_VISIBLE_TEXT
- Narrative claim: "Rootly silences up to ninety percent of incident..."
- Active artifact: art_419c9df3 (generated_media) from last generation round

## Lipsync Assessment (PROVISIONAL)
No SyncNet/Wav2Lip eval has been run on this fixture.
The following observations are provisional:
1. Audio is continuous with no silence gaps (volume detected throughout)
2. Audio duration (22.900s) slightly exceeds video duration (22.833s) by 67ms
3. The 67ms audio-video duration gap exceeds typical AV sync tolerance (<1 frame = 41.7ms at 24fps)
4. QA final report has no lipsync/audio-timing gate — F-QA-001
5. No provider diagnostic audio is present in the final MP4 — the audio is continuous

Assessment: The audio-video duration mismatch (67ms) means the final frame(s) of video display
while audio continues, or vice versa. At 24fps, 67ms ≈ 1.6 frames. This alone is not proof
of lipsync error but is consistent with the suspected offset.

## Text-Risk Assessment
- Scene 2 (phone b-roll, 4.583-10.458s) contains phone screen content
- NO_VISIBLE_TEXT policy is applied to hero lipsync units
- B-roll scenes may have text visible on phone screens
- F-TEXT-001: potential text-risk surface

## Commands executed
```bash
# Scene detection (4 thresholds: 0.4, 0.2, 0.15, 0.1 — all same result)
ffmpeg -i final_16x9.mp4 -vf "select='gte(scene,0.1)',showinfo" -vsync vfr -f null -

# Black hold detection
ffmpeg -i final_16x9.mp4 -vf blackdetect=d=0.5:pic_th=0.98 -f null -

# Contact sheet
ffmpeg -i final_16x9.mp4 -vf "fps=1/2,scale=320:-1,tile=4x3" -frames:v 1 -update 1 contact_sheet.jpg

# Key frames
for ts in 0 2.0 4.5 6.0 8.0 10.0 11.0 13.0 15.5 17.0 19.0 21.0; do
  ffmpeg -ss "$ts" -i final_16x9.mp4 -frames:v 1 -q:v 2 frame_${ts}s.jpg
done

# Audio analysis
ffmpeg -i final_16x9.mp4 -af "volumedetect" -f null -
ffmpeg -i final_16x9.mp4 -af "silencedetect=n=-50dB:d=0.5" -f null -
```

## Deliverables
- `fixtures/bad_runs/*/contact_sheet.jpg` — Contact sheet (tiled frames)
- `fixtures/bad_runs/*/scene_timeline.csv` — Scene timeline
- `fixtures/bad_runs/*/forensic_summary.json` — Machine-readable summary
- `reports/karpathy_loop/sprint_00/S00_T002/frame_*.jpg` — Representative frames

Gate status:
- Gate 0 Render lock: PASS
- Gate 1 Forensic: PASS
- Gate 2 Eval-first: PENDING
Decision: (pending eval)
