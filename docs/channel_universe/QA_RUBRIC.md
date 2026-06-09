# QA Rubric

**Version:** 1.0
**Status:** Active
**See also:** `TECHNICAL_BIBLE.md` §15 (automatic fail conditions), `UNIVERSE_BIBLE.md` §10, `FORBIDDEN_PATTERNS.md`

---

## 1. Purpose

This rubric defines scoring and pass/fail criteria at every QA gate in the production pipeline. It is used by:
- Human reviewers at approval gates
- `scripts/qa_media.py` (technical checks)
- Future LLM reviewer gates (`scripts/review_*.py`) called via Kiro-CLI

The rubric has five scoring levels. Dimensions are scored individually. Overall pass requires all blocking conditions absent and no dimension below 3 on a critical dimension.

### Scoring scale
| Score | Meaning |
|---|---|
| 5 | Excellent; strongly on-brand; no issues |
| 4 | Good; on-brand; minor notes only |
| 3 | Acceptable but weak; one or more improvements needed |
| 2 | Poor; major repair needed; likely blocks if critical dimension |
| 1 | Unusable; automatic fail |

---

## 2. Pre-Generation QA (Process Gate)

**Runs before any Higgsfield credits are spent.**
**Required by:** project lead / reviewer. Enforced by process; not yet automated.

| Check | Pass condition |
|---|---|
| Storyboard review passed | `may_proceed: true` from storyboard reviewer |
| Prompt plan review passed | `may_proceed: true` from prompt plan reviewer |
| All required reference assets exist | Check `REFERENCE_ASSET_MANIFEST.md` status column |
| Final narration exists (for lipsync) | The ElevenLabs mp3 file is present and confirmed |
| No `reference_missing: true` entries in prompt plan | All A-roll/studio prompts have references |

**Fail = credits must not be spent.**

---

## 3. Storyboard QA

**Run by:** `sonnet_creative` LLM reviewer (`scripts/review_storyboard.py`) + human gate

| Dimension | What to score |
|---|---|
| Narrative continuity | Does the sequence of beats tell a coherent story? Does each beat follow logically? |
| A-roll/B-roll ratio | Is James present enough for the episode type? (See Technical Bible §7 guardrails) |
| James presence | Is James represented as the intellectual anchor, or is he absent/marginal? |
| Scene evolution | Does the visual sequence progress meaningfully? Same angle throughout = low score. |
| Audience relevance | Would the target audience (30–50, analytical professional) engage with this? |
| Hook strength | Does the opening beat create a reason to keep watching? Is there a clear promise? |
| Visual feasibility | Are the requested scenes physically generatable with current tools and references? |
| Universe compliance | No forbidden environments, motifs, or character behavior |
| Technical compliance | No forbidden camera language, audio mode errors, or text policy violations in beat plan |

**Blocking conditions (score 1, `may_proceed: false`):**
- James-presence % = 0% in a host-led episode (measured by beat count of non-transition/title beats; see `TECHNICAL_BIBLE.md` §7)
- James-presence % below the minimum guardrail for the episode type **and** the reviewer judges the gap non-recoverable without restructuring
- No hook beat

**Warning conditions (score 2, `may_proceed: true` but fix recommended):**
- James-presence ratio below the lower guardrail for the episode type
- No scene evolution (all beats use the same angle)
- Hook is weak but present

---

## 4. Prompt Plan QA

**Run by:** `sonnet_creative` LLM reviewer + optionally `auto_utility` for field completeness pre-screen

| Dimension | What to score |
|---|---|
| Required fields complete | All fields from PROMPT_RULES §3 present in every entry |
| Reference assets specified | A-roll/studio prompts have reference asset IDs |
| Universe compliance | No forbidden environment, motif, or character in prompt text |
| Technical compliance | Camera, lighting, and palette are from the allowed lists |
| Negative constraints included | Default negative block present and unmodified |
| Text policy clear | `text_policy` specified; no prompt requests in-scene readable text |
| Audio policy clear | `audio_policy` matches `audio_mode` for the segment |
| Crop safety clear | `crop_safety` specified for every A-roll entry |
| Generation cost justified | Model assigned is appropriate; expensive models only where needed |

**Blocking conditions:**
- Any A-roll prompt missing reference assets
- Any prompt requesting in-scene text generation
- Any A-roll lipsync prompt without final narration confirmation
- `reference_missing: true` on any required entry

---

## 5. Media Technical QA

**Run by:** `scripts/qa_media.py` (automated, no API cost)

| Check | Pass condition | Fail |
|---|---|---|
| File exists | File present at expected path | Fail |
| ffprobe readable | ffprobe returns valid metadata | Fail |
| Video stream exists | `codec_type: video` present | Fail |
| Duration | Within ±1s of `duration_target_sec` from prompt plan | Warn if >2s off |
| Resolution | 1280×720 minimum; 1920×1080 preferred | Warn if below 720p |
| Audio stream (`generated_tts`) | NO audio stream — must be stripped | **Auto-fail if audio present** |
| Audio stream (`baked_in`) | Audio stream MUST be present | Auto-fail if missing |
| Codec | h264 video; aac audio if present | Warn on unusual codec |
| Crop safety metadata | If crop safety annotation available, confirm James in center zone | Warn |

---

## 6. Media Creative QA

**Run by:** `sonnet_creative` LLM reviewer (on text-based description) + human review for final approval

*Note: automated creative QA via vision models is deferred; human review remains the primary creative gate until a vision pipeline is built.*

| Dimension | Scoring |
|---|---|
| James consistency | Face, build, wardrobe match established reference |
| Studio consistency | Same layout, furniture, light as established reference |
| Cat consistency | If present: same breed/color/size/behavior |
| Lighting compliance | Warm, directional, motivated source; no glow-without-source |
| Color compliance | Warm neutral palette; no neon or incompatible colors |
| Camera compliance | Movement type from allowed list; no forbidden movements |
| Realism | Physically plausible; no AI-over-smooth surfaces |
| Text contamination | No garbled or semi-readable generated text in focus |
| Audio contamination | No baked-in Higgsfield ambient mistaken for narration |
| No logos | No brand logos visible |
| No random characters | No unplanned people in A-roll positions |

**Scoring: score each dimension 1–5. Any dimension scoring 1 is an automatic fail regardless of overall average.**

---

## 7. Audio QA

**Run by:** `scripts/audio_timing.py` (technical) + `sonnet_creative` LLM review for pacing

| Check | Pass condition | Note |
|---|---|---|
| Narration mode | `continuous_voiceover` for final publish | `segment_tts` only in tests |
| WPS | 2.2–3.0 for standard; 2.0–3.2 with explicit approval | Flag outside range |
| Audible breaks | No silence >0.8s between sentences in continuous narration | Flag gaps >1s |
| Long pauses | Deliberate pauses (0.5–1.5s) before key ideas are acceptable | Flag >3s pauses |
| Voice consistency | ElevenLabs James Harrington, locked settings | See BRAND_SPEC §2 |
| B-roll contamination | No b-roll ambient audio in assembled output | Automatic fail if present |
| Music ducking | Music below -26dB under narration | Warn if above -22dB |

---

## 8. Final Assembly QA

**Run by:** Human gate; `scripts/qa_media.py` for technical checks on assembled output

| Check | Pass condition |
|---|---|
| 16:9 output exists | File present, playable, expected duration |
| 9:16 output exists | File present, playable, same duration |
| Narrative coherence | Story makes sense; narration and visuals are aligned |
| Audio continuity | No audible breaks in narration; no sudden transitions |
| A-roll/B-roll balance | Visually varied; not all-b-roll |
| Visual evolution | Different angles/environments across the episode |
| No off-brand frames | Screen review; no forbidden patterns visible |
| 9:16 crop quality | James's face and key moments visible in center crop |
| Volume levels | Mean volume in broadcast range (-22 to -12 dB) |
| No abrupt audio transitions | Gaps between segments ≤0.4s (the standard `gap_seconds` value) |

---

## 9. Automatic Fail Conditions (Canonical)

Any of the following is an automatic fail at any gate. `score: 1`, `may_proceed: false`, regeneration required.

| Condition | Gate |
|---|---|
| `generated_tts` b-roll audio present in assembled output | Media Technical, Audio, Final Assembly |
| James absent from host-led episode | Storyboard, Media Creative |
| All-b-roll host-led video | Storyboard |
| Prominent garbled/AI-generated text in focus | Media Creative, Final Assembly |
| Cyberpunk / futuristic hologram visuals | Media Creative, Final Assembly |
| Wrong James appearance (wardrobe, face, age) | Media Creative |
| Wrong studio/library layout | Media Creative |
| Cat looks different from established reference | Media Creative |
| Visible logo or copyrighted text | Media Creative, Final Assembly |
| Major 9:16 crop failure (James face cropped) | Final Assembly |
| Audible break between narration segments in final | Audio, Final Assembly |
| Scene content contradicts narration | Storyboard, Final Assembly |
| Random substitute presenter in A-roll | Media Creative |
| Neon / electric-glow lighting | Media Creative |
| Credits spent before storyboard/prompt plan approved | Pre-Generation |
| Media prompt compiled from raw `visual_brief` (after M5/M8) | Prompt Plan |

---

## 10. Approval Rules

| Gate | Who approves | Required for |
|---|---|---|
| Storyboard | Sonnet reviewer `may_proceed: true` + human confirm | Before prompt compilation |
| Prompt plan | Sonnet reviewer `may_proceed: true` | Before generation credits spent |
| Media technical | `qa_media.py` pass | Before assembly |
| Media creative | Human review (until vision pipeline) | Before assembly |
| Audio | `audio_timing.py` pass + human ear check | Before final assembly |
| Final assembly | Human gate | Before any publish step |

**`auto_utility` (auto model) must never be the sole approver for any creative gate.** It may pre-screen, but a Sonnet-class approval is required for storyboard review, prompt plan review, and final assembly sign-off.

---

## 11. Human Review Points

Even after LLM reviewer gates are implemented, human review remains required at:

1. **Storyboard final approval** — a human reads the full storyboard before generation
2. **Post-media creative review** — a human watches or screens generated clips before assembly
3. **Final video approval (Gate B)** — a human watches both 16:9 and 9:16 before any publish step

These are not optional. They are the "sourcing discipline + craft bar" non-negotiables from `strategy/BUSINESS_PLAN.md`.
