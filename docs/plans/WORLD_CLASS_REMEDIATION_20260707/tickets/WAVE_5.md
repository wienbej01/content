## Wave 5 — Audio Design & Music Scoring Rules

### TKT-501 — Act-specific music scoring rules

| Field | Value |
|-------|-------|
| Ticket | TKT-501 |
| Title | Act-specific music scoring rules in configs/audio_scoring.yaml |
| Requirement IDs | R-AUD-1, MITmonk §5 |
| Class | ROUTINE |
| Wave | 5 |
| Deps | W0 |

**Observable outcome:** `configs/audio_scoring.yaml` defines per-act: tempo_bpm, instrumentation, energy_level, reference_style. Assembler selects matching stem. Test mode uses TKT-004 fixtures.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| load yaml | valid, acts 1-6 | `pytest tests/test_audio_scoring.py::test_load -q` |
| act 3 settings | correct | `pytest tests/test_audio_scoring.py::test_act3 -q` |

**Acceptance gates:** G1 file loads; G2 each act distinct; G3 full suite.

---

### TKT-502 — Paradigm-shift music silence rule

| Field | Value |
|-------|-------|
| Ticket | TKT-502 |
| Title | Paradigm-shift music silence rule |
| Requirement IDs | R-AUD-2, F4 |
| Class | COMPLEX |
| Wave | 5 |
| Deps | W0 |

**Observable outcome:** Beats whose `narrative_function` in `SILENCE_FUNCTIONS` (default: `myth_bust_reveal`, `paradigm_shift`, `philosophical_close`) have music volume `-∞` for beat duration + 1s ramp-in. Configurable in `configs/audio_scoring.yaml`.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| paradigm_shift beat | music -∞ | `pytest tests/test_silence_rule.py::test_silence -q` |
| factual_data beat | music unchanged | `pytest tests/test_silence_rule.py::test_nosilence -q` |

**Acceptance gates:** G1 silence for paradigm_shift; G2 non-silence unchanged; G3 full suite.

---

### TKT-503 — Chapter marker audio cue library + manifest schema

| Field | Value |
|-------|-------|
| Ticket | TKT-503 |
| Title | Chapter marker audio cue library |
| Requirement IDs | R-AUD-3 |
| Class | COMPLEX |
| Wave | 5 |
| Deps | W0 |

**Observable outcome:** `assets/audio/cues/` with 3-5 CC0 WAVs. `configs/audio_cues.yaml` maps names. Assembler inserts at act boundary. Behind `CHAPTER_MARKERS_MODE = off|on`.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| act boundary | cue inserted | `pytest tests/test_chapter_markers.py::test_insert -q` |

**Acceptance gates:** G1 cue at boundary; G2 full suite.

---

### TKT-504 — Frequency-selective dynamic ducking

| Field | Value |
|-------|-------|
| Ticket | TKT-504 |
| Title | Frequency-selective dynamic ducking |
| Requirement IDs | R-AUD-4 |
| Class | COMPLEX |
| Wave | 5 |
| Deps | W0 |

**Observable outcome:** Replace loudnorm with ffmpeg sidechain compress keyed on narration. `MUSIC_DUCK_DB` configurable. Behind `DUCKING_MODE = simple|selective`. Default `simple`.

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| narration 1-4kHz high | music 1-4kHz reduced | `pytest tests/test_ducking.py::test_selective -q` |

**Acceptance gates:** G1 selective reduces; G2 simple unchanged.

---

### TKT-505 — Animated element for emotional beats

| Field | Value |
|-------|-------|
| Ticket | TKT-505 |
| Title | Animated element for emotional beats |
| Requirement IDs | MITmonk §5 |
| Class | ROUTINE |
| Wave | 5 |
| Deps | W0 |

**Observable outcome:** Graphics >2s whose `narrative_function` in config set get alpha animation (fade, scale, reveal).

**Test matrix:**

| Scenario | Expected | Command |
|----------|----------|---------|
| emotional graphic >2s | animation metadata | `pytest tests/test_graphics.py -k animation -q` |

**Acceptance gates:** G1 animation applied; G2 full suite.

---

## Wave 5 gate

- W5-G1: TKT-501..TKT-505 accepted.
- W5-G2: Act-scored, silence operational, chapter markers optional, ducking selective.
- W5-G3: Full suite passes.
