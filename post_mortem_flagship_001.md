# Post-Mortem Analysis: Flagship_001

## 1. Critical Pipeline Failures (Visuals & Assembly)

### A. The "Blank Screen" Epidemic (`qa_media.py` Failure)
The video contains over 2.5 minutes of completely blank, off-white screens where B-roll should be. 
*   **Root Cause:** `generate_media.py` likely hit an API timeout, content filter, or failed generation from Kling 3.0, and returned empty or placeholder files. 
*   **System Failure:** `qa_media.py` (Gate 8) failed to detect this. It should have checked file size, frame variance, or color histograms and hard-failed the build rather than allowing `assemble.py` to compile.
*   **Actionable Fix:** Update `qa_media.py` to include a color variance/histogram check to catch solid color screens. Hard-fail Gate 8 if detected.

### B. Lipsync "Still-Stops" (Rule #4 Violation)
The rule *"Zero silent degradation — A hero_lipsync beat MUST produce a lipsync clip or hard-fail"* was violated repeatedly. The video freezes on static frames of the host while audio continues.
*   **Root Cause:** Seedance 2.0 failed to animate the provided image and audio, returning a static video. 
*   **System Failure:** `qa_media.py` failed to verify motion inside the video file.
*   **Actionable Fix:** Implement `ffmpeg` motion vector checks or structural similarity index (SSIM) between the first and last frames in `qa_media.py`. Reject clips with zero motion.

### C. The Audio Quality Shift
There is a jarring voice quality change between face-shots (A-roll) and B-roll. 
*   **Root Cause:** The pipeline preserves baked lipsync audio verbatim (`-map 0:a`). Seedance 2.0 re-encodes and compresses the audio stream during generation. Stitching compressed Seedance audio next to the raw ElevenLabs MP3 causes dramatic EQ/compression shifts.
*   **Actionable Fix:** Modify `assemble.py` and the assembly manifest. Mute all incoming video clips (`-an`). Lay down the single, continuous ElevenLabs master MP3 file, and snap the video clips to the audio timestamps defined in `media_plan.json`. Do not stitch segmented audio.

## 2. Script & Content Failures

### A. LLM Stuttering and Repetition (`review_script.py` Failure)
The script contains severe repetition loops (e.g., *"Read it. Sketch it. Explain it aloud... Read it. Sketch it. Explain it aloud."*).
*   **Root Cause:** The Sonnet model got caught in a generation loop.
*   **System Failure:** `review_script.py` (Gate 1) failed to catch obvious, machine-like stuttering.
*   **Actionable Fix:** Add a deterministic Python-based regex/N-gram check in `review_script.py` before sending the script to the LLM reviewer. If N-gram repetition exceeds a threshold, instantly fail the gate and trigger a re-roll.

### B. AI Gibberish & The Text Policy
The B-roll frequently shows close-ups of people writing alien scribbles or reading books with misspelled gibberish ("Reiding Nots").
*   **Root Cause:** Generative models cannot render coherent text without specific fine-tuning.
*   **Actionable Fix:** Update `constraints.json -> negative prompts` to strictly forbid "writing," "text," "words on page," "reading documents," or "drawing charts." Enforce that B-roll must be conceptual, observational, or metaphorical only.

## 3. Brand Continuity & Structural Deviations

### A. Wardrobe & Character Hallucinations (Rule #5 Violation)
The host's clothing changes between cuts (blue shirt to white shirt under sweater), and B-roll occasionally hallucinates entirely different host characters.
*   **Root Cause:** `media_plan.json` is not properly locking the `navy_sweater_library` reference frames, causing image prompts to drift.
*   **Actionable Fix:** Enforce strict reference rotation checking in `compile_media_prompts.py` and `qa_media.py` to ensure only the approved canonical frames are passed to Seedance.

### B. Missing MITmonk Formatting & Graphics
The video starts without a hook, contains 0% Graphics/UI (violating the ≥10% rule), and relies entirely on a monotonous A-roll/desk-B-roll pattern.
*   **Root Cause:** `storyboard.py` is failing to enforce the shot-mix bands and Act structure. The LLM is taking the lazy path.
*   **Actionable Fix:** Hardcode a structural failsafe in `storyboard.py`. If the parsed output lacks UI/Graphics or kinetic text, automatically insert placeholders or fail the parsing gate to force a re-generation of the storyboard.
