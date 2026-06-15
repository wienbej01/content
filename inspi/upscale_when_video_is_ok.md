Based on a visual analysis of the provided hero shots (e.g., at 00:00, 00:07, 01:15, 01:43), your assessment is entirely correct: **the quality is unacceptably soft for a "premium" educational channel.** It lacks high-frequency detail in the skin texture, hair, and clothing, giving it a distinct, slightly blurred "AI-generated" look. 

Here is a technical breakdown of the hero shot quality, why it looks this way, and exactly how to fix it in your pipeline.

### 1. The Resolution and Seedance 2.0 Capabilities
*   **Current State:** The hero shot appears to be rendering at a native resolution of **720p (1280x720) or lower** (some models default to 512x896 or similar non-standard resolutions and stretch them). It is definitely not native, crisp 1080p or 4K.
*   **Is this the best Seedance 2.0 can produce?** Natively, **yes**. AI lipsync models (like Seedance, Wav2Lip, or Sync1.6) dedicate massive compute to mapping audio phonemes to facial landmarks. To do this quickly and efficiently, they compress the overall image texture and output at a lower resolution. They are not designed to be final-render engines; they are animation engines. 
*   **The Artifacts:** If you look closely at James's face around the mouth and eyes, the pixels are slightly "swimming" or smoothing over frame-by-frame. This is standard degradation for raw lipsync outputs.

### 2. The Solution: You Must Upscale
To hit the "MITmonk" standard and compete in the mid-career professional niche, your videos must be pristine 1080p or 4K. **You cannot use raw Seedance 2.0 outputs in the final assembly.**

You need to inject an **AI Video Upscaling step** into your pipeline. 

### 3. How to Fix This in Your Architecture

To fix this without breaking your automated, JSON-driven architecture, you need to add a step between `generate_media.py` and `qa_media.py`.

**Step 1: Check the Reference Images (`assets/brand/`)**
Before doing anything, check your `navy_sweater_library` reference images. AI video cannot invent detail that wasn't there. Your base reference images must be generated at ultra-high resolution (e.g., Midjourney v6 upscaled). If the input image is 1080p, the lipsync model will downgrade it to 720p. If the input image is 4K, the downgrade will be less severe, and it will be much easier to upscale later.

**Step 2: Add `upscale_media.py` to the Pipeline**
Update your pipeline workflow to look like this:

```text
[6. Generation] → [6.5 Upscaling] → [7. QA] → [8. Assembly]
       ↓                 ↓              ↓             ↓
 generate_media   upscale_media.py   qa_media.py   assemble.py
```

**Step 3: Choose an Upscaling Engine**
You need a CLI-compatible, headless upscaler.
*   **Option A (Open Source / Free):** `Real-ESRGAN` or `Topaz Video AI` (via CLI). You can run a pass that upscales the 720p Seedance output to 1080p/4K while specifically enhancing facial details.
*   **Option B (Higgsfield API):** Check the Higgsfield/Seedance API documentation. Do they offer a native `--upscale true` or `--enhance` parameter? If so, this is the easiest fix. Add it to `compile_media_prompts.py`.
*   **Option C (Cloud API):** Use an API like Replicate to pass the Seedance video through a video enhancer (like `tencent/real-esrgan-video`) before saving it to the `assets/media/` folder.

### Addendum for your Claude Opus Prompt:

*I highly recommend adding this section to the markdown document you are feeding to Claude Opus.*

```markdown
### 4. Hero Shot Visual Quality & Resolution
The talking head shots ("James") are unacceptably soft and blurry. They lack high-frequency detail and appear to be raw 720p (or lower) outputs.
*   **Root Cause:** Seedance 2.0 natively outputs at lower resolutions, sacrificing texture detail to calculate lipsync animations.
*   **Actionable Fix:** 
    1. Ensure `navy_sweater_library` input frames are pristine 4K.
    2. Check if Higgsfield API supports an upscale/enhance flag and implement it in `compile_media_prompts.py`.
    3. If no native API upscaling exists, introduce a new script (`scripts/upscale_media.py`) that runs all Seedance `.mp4` outputs through a CLI-based AI video upscaler (e.g., Real-ESRGAN or similar headless tool) before they reach `qa_media.py`.
```
