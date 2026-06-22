## 17. Compact Ticket Index

### Sprint 0

- ENG-0001: Create reduced forensic regression fixtures
- AUD-0001: Audit forensic fixture completeness
- VAL-0001: Validate baseline regression fixtures

### Sprint 1

- ENG-0101: Add `scripts/media_contract.py`
- ENG-0102: Add provider prompt risk detector
- AUD-0101: Audit media contract correctness
- VAL-0101: Validate media contract against forensic fixture

### Sprint 2

- ENG-0201: Enforce provider eligibility before provider job creation
- ENG-0202: Add adapter-level second guard
- ENG-0203: Capability-gate `negative_prompt`
- AUD-0201: Audit provider boundary
- VAL-0201: Validate no forbidden provider jobs can exist

### Sprint 3

- ENG-0301: Add render metadata split
- ENG-0302: Implement prompt sanitizer for provider visuals
- ENG-0303: Route exact text into deterministic text specs
- AUD-0301: Audit prompt/text split
- VAL-0301: Validate compile output DB state

### Sprint 4

- ENG-0401: Add DB-native local graphic rendering function
- ENG-0402: Fix `graphics_compositing` stage
- AUD-0401: Audit local graphics rendering
- VAL-0401: Validate local graphic DB lifecycle

### Sprint 5

- ENG-0501: Add media QA contract router
- ENG-0502: Local graphic QA
- ENG-0503: Provider video text-policy QA
- ENG-0504: Status transitions on QA result
- **ENG-0505: Hero Lipsync Continuity & Sync QA**
- AUD-0501: Audit contract QA
- VAL-0501: Validate QA blocks known bad artifacts

### Sprint 6

- ENG-0601: Add validation failure classifier
- ENG-0602: Add repair action decision table
- ENG-0603: Implement DB repair lifecycle
- AUD-0601: Audit repair loop
- VAL-0601: Validate repair fixes failed local graphic

### Sprint 7

- ENG-0701: Add assembly input validator
- ENG-0702: Enforce preflight in `build_assembly_inputs`
- **ENG-0703: Assembly Timeline Heuristics (Repeated/Looping Assets)**
- AUD-0701: Audit assembly preflight
- VAL-0701: Validate assembly cannot consume bad forensic pattern

### Sprint 8

- ENG-0801: Extend final QA with DB-contract checks
- ENG-0802: Harden final review/publish gate
- AUD-0801: Audit final QA/gate hardening
- VAL-0801: Validate final gate blocks old failure

### Sprint 9

- ENG-0901: Add fake provider adapter for tests
- ENG-0902: End-to-end synthetic production test
- AUD-0901: Audit end-to-end dry run
- VAL-0901: Validate full no-paid pipeline

### Sprint 10

- ENG-1001: Add strict smoke config
- ENG-1002: Run compile-only smoke
- AUD-1001: Audit compile-only smoke state
- VAL-1001: Validate capped paid smoke
