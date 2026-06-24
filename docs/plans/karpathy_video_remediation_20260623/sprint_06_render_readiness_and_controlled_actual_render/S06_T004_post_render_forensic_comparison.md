# S06_T004 Post-Render Forensic Comparison

## Purpose

Analyze the canary render output before any broader rerender.

## Required checks

```text
- provider output exists
- diagnostic audio extracted
- provider audio vs source slice comparison passes
- lipsync eval passes/warns with acceptable threshold
- artifact registered
- no additional provider jobs submitted
```

## Pass gates

PASS if canary proves the pipeline can generate one auditable hero-lipsync unit. Do not proceed to full production render in this sprint unless a new explicit human instruction is given.
