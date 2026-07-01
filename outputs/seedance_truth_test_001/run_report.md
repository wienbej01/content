# Seedance Truth Test 001 Run Report

verdict: RETRY

production_id: `prod_cbd3c35dfd08431b82b1b6ca9bc675d2`

topic: How to use AI to protect deep work time as a senior manager

format: `smoke`

final_mp4: MISSING

paid_renders_triggered: yes

estimated_video_cost_usd: 3.18

provider_jobs:

- `pjob_cb5166ba65e74cf593205faf4bab3738`: Seedance hero `S000`, completed, artifact `assets/media/prod_cbd3c35dfd08431b82b1b6ca9bc675d2/pjob_cb5166ba65e74cf593205faf4bab3738.mp4`
- `pjob_df8da2dff65c4f948a0f78530f53ab32`: Kling b-roll `S001`, completed, artifact `assets/media/prod_cbd3c35dfd08431b82b1b6ca9bc675d2/pjob_df8da2dff65c4f948a0f78530f53ab32.mp4`
- `pjob_dbac171ff851412dacf33ffbfd923211`: Seedance hero `S002`, completed, artifact `assets/media/prod_cbd3c35dfd08431b82b1b6ca9bc675d2/pjob_dbac171ff851412dacf33ffbfd923211.mp4`

blocking_result:

`qa_media` failed both Seedance hero units:

- `S000`: lipsync drift 609 ms; current policy failed it.
- `S002`: lipsync drift 158 ms; current policy failed it.

Existing repair path:

- `run_repair_lifecycle()` classifies these failures as `unknown_contract_failure`.
- Existing repair policy blocks them for manual review instead of automatic regeneration.
- No gate was weakened and no assembly bypass was attempted.

commands_run_after_spend_approval:

```bash
python3 scripts/produce_db.py approve prod_cbd3c35dfd08431b82b1b6ca9bc675d2 gate_a_spend --pass
python3 scripts/produce_db.py resume prod_cbd3c35dfd08431b82b1b6ca9bc675d2
python3 scripts/produce_db.py resume prod_cbd3c35dfd08431b82b1b6ca9bc675d2
python3 - <<'PY'
from media_service import run_repair_lifecycle
...
PY
ffmpeg ... sampled_frames/S000_hero_1s.jpg
ffmpeg ... sampled_frames/S001_broll_1s.jpg
ffmpeg ... sampled_frames/S002_hero_1s.jpg
```

artifacts_created_or_updated:

- `outputs/seedance_truth_test_001/render_plan.json`
- `outputs/seedance_truth_test_001/manifest.json`
- `outputs/seedance_truth_test_001/hero_sync_report.json`
- `outputs/seedance_truth_test_001/semantic_role_qa_report.json`
- `outputs/seedance_truth_test_001/graphic_qa_report.json`
- `outputs/seedance_truth_test_001/human_gate_b_review.md`
- `outputs/seedance_truth_test_001/run_report.md`
- `outputs/seedance_truth_test_001/sampled_frames/S000_hero_1s.jpg`
- `outputs/seedance_truth_test_001/sampled_frames/S001_broll_1s.jpg`
- `outputs/seedance_truth_test_001/sampled_frames/S002_hero_1s.jpg`

hero_lipsync_result: FAIL. Seedance produced real talking-head artifacts with provider audio, but current QA measured unacceptable lipsync drift.

broll_result: PARTIAL. Kling b-roll generated and passed media QA, but sampled visual evidence is abstract/generic and not strong corporate deep-work evidence.

graphics_result: NOT RUN. The local deterministic graphic was planned but `graphics_compositing` did not run because the pipeline stopped at failed hero QA.

assembly_result: NOT RUN.

qa_results:

- media QA: fail for both Seedance heroes; pass for b-roll.
- Sync/lipsync acceptance: fail by current media QA drift gate.
- semantic role QA: not run.
- graphic QA: not run.
- sampled-frame QA: partial manual evidence only; no final-frame QA.
- final QA: not run.
- Gate B: not run.

sampled_frames:

- `outputs/seedance_truth_test_001/sampled_frames/S000_hero_1s.jpg`
- `outputs/seedance_truth_test_001/sampled_frames/S001_broll_1s.jpg`
- `outputs/seedance_truth_test_001/sampled_frames/S002_hero_1s.jpg`

viability: NOT PROVEN. The current Seedance approach produced real hero clips, but did not pass the repo's lipsync QA and therefore cannot be called viable for final-video production yet.

recommendation: retry only via an explicit existing repair/regeneration path or a minimal patch that maps lipsync drift failures to the intended provider regeneration action. Do not continue to assembly with these hero units.

