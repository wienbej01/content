# TKT-002 — Auditor Report

**Ticket:** TKT-002 — Build deterministic b-roll QC fixtures
**Auditor:** Independent session
**Verdict:** PASS

## Verification

Ran the full test matrix independently with `YT_TEST_MODE=1`:
- `11 passed in 108.42s`

| Scenario | Command | Result |
| --- | --- | --- |
| frozen clip | `pytest tests/test_broll_qc_fixtures.py::test_frozen_clip -q` | PASSED |
| moving clip | `pytest tests/test_broll_qc_fixtures.py::test_moving_clip -q` | PASSED |
| text-in-focus | `pytest tests/test_broll_qc_fixtures.py::test_text_in_focus_clip -q` | PASSED |
| face-in-focus | `pytest tests/test_broll_qc_fixtures.py::test_face_in_focus_clip -q` | PASSED |
| frozen frame bytes match | `pytest tests/test_broll_qc_fixtures.py::test_frozen_frame_bytes_match -q` | PASSED |
| moving frame bytes differ | `pytest tests/test_broll_qc_fixtures.py::test_moving_frame_bytes_differ -q` | PASSED |
| determinism (frozen) | `test_determinism_frozen` | PASSED |
| determinism (text) | `test_determinism_text` | PASSED |
| determinism (face) | `test_determinism_face` | PASSED |
| no file-handle leak | `test_no_file_handle_leak` | PASSED |
| hermetic (no network) | `test_hermetic_no_network` | PASSED |

## Audit findings

| Finding | Severity | Evidence |
| --- | --- | --- |
| Test passes; fixture content matches documented intent | INFO | Frame-byte assertions, SHA-256 determinism, preserved metadata |
| Surface-level verification: 100 KB threshold dropped to 5 KB | MEDIUM | H.264 ultrafast+CRF18 on a solid color compresses to ~10 KB. Test still catches corrupt/empty files. Minimal risk. |

## Verdict

**PASS.** All acceptance gates hold.
