# S07_T003 Canary Visual Forensics

## Purpose
Extract frames/contact sheet from the fresh canary. Verify face is visible, mouth moves, no freeze, no non-speaking pose, no wrong crop.

## Required checks
- Still frame extraction
- Contact sheet
- Face detection (if OpenCV available)
- Frame-difference signal analysis
- Freeze/static frame detection

## Pass gate
Classify whether the visual is usable for lipsync evaluation.
