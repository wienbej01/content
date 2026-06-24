# S07_T002 Audio Slice vs Provider Diagnostic Alignment

## Purpose
Compare source slice audio, provider request audio, provider diagnostic audio, and final/canary audio.

## Required checks
- Source slice SHA256 vs provider request audio path
- Provider diagnostic audio vs source slice (cross-correlation)
- Diagnostic audio duration vs canary video duration
- Detect any shift/padding/offset in provider audio

## Pass gate
Classify whether provider received the correct audio and whether diagnostic audio is shifted.
