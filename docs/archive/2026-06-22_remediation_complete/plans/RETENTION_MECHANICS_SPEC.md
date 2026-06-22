# Retention Mechanics — Reviewer Judgments vs. Enforced Rules

**Date:** 2026-06-13
**Source:** YTextract.md (watch/save/share) + the 10 algorithm tips + the pattern-interrupt code spec.
**Principle (owner-directed):** LLM makes the creative calls; Python rules enforce compliance.
Each retention mechanic below is classified as an **LLM-judgment** (taste/prediction) or an
**enforced rule** (countable, deterministic gate or assembly injection).

## North-star metrics (what every mechanic serves)
- **Watch-time / AVD** — hold attention all the way through
- **Saves** — useful/valuable enough to refer back to
- **Shares** — made the viewer FEEL something (inspired/shocked/entertained)
- The 3 publish questions: *Will they watch it through? Save it? Send it to someone?*

## A. LLM AUDIENCE-REVIEWER judgments (predict viewer behavior; can't be measured)
| Mechanic | What the reviewer predicts | Stage |
|----------|----------------------------|-------|
| Hook = real 3s open loop that delivers the title promise (#1,#4) | Would a skeptical viewer stay past 3s? | script + storyboard |
| Reason-to-stay every ~20-30s | Are there continuous open loops / payoffs? | script + storyboard |
| Save-worthy | Is it useful enough to bookmark? | script |
| Share-worthy | Does it evoke a feeling worth sending? | script |
| Curiosity/emotional title (#7) | Browse-feature pull | packaging |
| Specific binary engagement question (#8) | Will it drive comments? | script (CTA) |
| Verbal end-screen → relevant next video (#6) | Subscriber/binge pull, no "in conclusion" | script (CTA) |
| Payoff lands (hero + integrated graphic) | Does the takeaway hit? | storyboard |

## B. ENFORCED RULES (deterministic — storyboard validator or assembly injection)
| Rule | Enforcement point | Spec |
|------|-------------------|------|
| **Visual change ≤ every 4-6s** (#3) | storyboard validator | No beat's on-screen visual may hold >5s without a cut / new shot / zoom punch / graphic / text change. Long narration → multi-shot. |
| **No static/slow intro** (#1, intro code) | storyboard validator | First beat (0-3s) must be MOTION (hero in-motion or dynamic b-roll), never a static card or slow fade-in. |
| **Pattern-interrupt zoom punches** (#9, 5s-rule code) | assembly injection | On alternating sustained beats, apply a 10-15% scale/crop punch to reset attention (the moviepy `resize(1.15)` idea, done in ffmpeg). |
| **SFX on overlay/text appearance** (#3) | assembly injection | Subtle whoosh/pop when a graphic/lower-third/key-line appears. (needs a small SFX asset pack) |
| **Music duck −15 to −20dB under VO** (#3) | assembly (exists, tune to −18dB) | Already implemented; confirm level. |
| **End-screen window 5-20s, high pace, no slow fade** (#5,#6) | assembly append | Branded end-card with VO running over it pointing to next video; no audio fade-out. |
| **B-roll ≤6s, multi-shot coverage** | storyboard validator (built) | Already in direct_storyboard validators. |
| **Motion in every clip (no freeze)** | qa_final (built) | Already enforced + graphic-card ken-burns. |

## C. Implications for the reviewer cast
The audience reviewer's rubric is rewritten around **watch / save / share + the 3 questions + hook/open-loop/reason-to-stay**. It is the highest-weighted reviewer at BOTH script and storyboard stages. The deterministic mechanics in (B) are NOT reviewer opinions — they become a `retention_rules` validator on the storyboard + injection steps in assembly, so the LLM is freed to judge taste while Python guarantees the mechanical retention scaffold.

## D. New build items this introduces (beyond the reviewer cast)
1. `retention_rules` storyboard validator: ≤5s visual-hold, motion-intro, multi-shot.
2. Assembly: zoom-punch pattern interrupts, SFX-on-overlay, end-screen window, confirm music duck −18dB.
3. (asset) a small royalty-free SFX pack (whoosh/pop) — flag: needs sourcing.
