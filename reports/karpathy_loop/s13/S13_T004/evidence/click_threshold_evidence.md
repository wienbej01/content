# Click-Detection Threshold Evidence (S13_T004_FIX001)

Measured via /tmp/click_diag*.py — AAC 128k encode/decode round-trip (matches
real assembly codec path), 16kHz mono PCM decode.

## Metric
At each **known seam** (from segment timeline metadata), search ±15 ms for the
peak sample; reference = RMS of the 30 ms window immediately preceding the
search region. Click if `20*log10(peak/refRMS) > threshold`.

## Why seam-based (not whole-waveform)
RMS-adjacent-window detection (the prior implementation) sees at most **15.7 dB**
for a full-scale 30 ms noise burst — short transients are averaged away by 50 ms
windows, so the prior 20 dB threshold was **structurally unreachable**. Clicks are
transients at joins; they must be measured at the join against local context.

## Measured separation (continuous bandpass-noise speech, seam at 2.0 s)
| case | ratio dB | peak | refRMS |
|------|---------:|-----:|-------:|
| clean seam (no impulse) | 5.7 | 246 | 127 |
| full-scale impulse at seam | 45.3 | 31851 | 172 |

**Threshold 20 dB** sits between 5.7 dB (clean) and 45.3 dB (defect) with a wide
margin on both sides.

## Guard
Skip a seam if refRMS < 50 (int16) — a silence reference makes the ratio
unreliable; report as ambiguous rather than false-positive.

## Faded-seam corroboration (diag5)
faded clean seam = 3.4 dB, impulse = 57.4 dB — same ordering, same threshold.
