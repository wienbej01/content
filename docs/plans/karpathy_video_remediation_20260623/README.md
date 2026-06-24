# Karpathy Video Remediation Pack — 2026-06-23

This directory is a repo-ready operating plan for running an eval-first remediation loop in Kilo Code.

Target branch:

```text
forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z
```

Current forensic fixture:

```text
prod_2f9bb58c0508465fb51ac6b4578bba92_16x9.mp4
production_id=prod_2f9bb58c0508465fb51ac6b4578bba92
```

The loop is designed for DeepSeek v4 Flash High or equivalent mid-cost coding models. It deliberately separates investigation, eval construction, engineering, audit, and black-box validation so the model does not prematurely code broad fixes.

## Critical policy

Actual video render/provider generation is locked until the render-readiness gates pass. LLM calls for analysis, planning, and code assistance may be made from the start. Video render calls, Higgsfield calls, or any provider generation call are forbidden until the controlled render sprint and explicit unlock file are present.

Start with:

```text
docs/plans/karpathy_video_remediation_20260623/10_KILO_START_PROMPT.md
```
