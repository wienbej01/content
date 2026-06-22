# TKT-10 Audit Report

**Ticket:** Music mandatory for short/explainer formats  
**Auditor:** Kiro subagent (read-only)  
**Date:** 2026-06-14  
**Verdict:** PASS

---

## Requirement

Assembly must hard-fail when:
1. Music is disabled (`enabled: false`) for a format listed in `constraints.json → music.required_for_formats`.
2. Music is enabled but the path is missing or unresolvable.

## Code Inspection (`scripts/assemble.py`)

### Format-gated enforcement (lines 928–946)

```python
required_formats = constraints.get("music", {}).get("required_for_formats", [])
...
elif video_format in required_formats:
    raise RuntimeError(
        f"Music is required for format '{video_format}' but music.enabled=false. "
        f"Enable music in the manifest or change the format.")
```

- Reads `required_for_formats` from `docs/channel_universe/constraints.json`.
- If `music.enabled` is falsy and the manifest format is in the list → `RuntimeError`.

### Missing/invalid path enforcement (lines 936–941, 652–660)

```python
if music_cfg.get("enabled"):
    rel = music_cfg.get("path") or music_cfg.get("file")
    if rel:
        music_file = resolve(base, rel)
        if not music_file.exists():
            raise RuntimeError(f"Music enabled but file not found: {music_file}")
```

Additionally at line 654:
```python
raise ValueError("music.enabled=true but no music.path specified")
```

- Enabled + missing key → `ValueError`.
- Enabled + nonexistent file → `RuntimeError`.

### Constraints configuration

```json
"music": {
  "required_for_formats": ["short", "explainer"],
  "default_path": "brand/music/night_snow.mp3",
  ...
}
```

Both `short` and `explainer` are listed — matching the ticket requirement.

## Assessment

| Check | Status |
|-------|--------|
| Disabled music + required format raises | ✅ |
| Enabled music + missing file raises | ✅ |
| Error messages are actionable | ✅ |
| No `--force-unsafe` bypass in production path | ✅ |
| constraints.json is authoritative source | ✅ |

No issues found. Implementation is correct and minimal.
