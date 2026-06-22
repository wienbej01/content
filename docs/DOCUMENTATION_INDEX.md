# YTchannel Production System Documentation Index

## Enhanced Database-Driven System (Current)

### Core Architecture Documentation
| Document | Purpose | Status |
|----------|---------|--------|
| **[ENHANCED_DATABASE_SYSTEM_SUMMARY.md](ENHANCED_DATABASE_SYSTEM_SUMMARY.md)** | Executive summary of architectural transformation | ✅ Current |
| **[PRODUCTION_DATA_FLOW_MAP.md](PRODUCTION_DATA_FLOW_MAP.md)** | Enhanced database-driven flow with unified ledger | ✅ Updated |
| **[CLIP_DB_DESIGN.md](CLIP_DB_DESIGN.md)** | Clip authority database design (implemented) | ✅ Updated |
| **[HARMONIZED_CLIP_FINGERPRINTS.md](HARMONIZED_CLIP_FINGERPRINTS.md)** | Fingerprint drift elimination system | ✅ New |
| **[PIPELINE.md](PIPELINE.md)** | Database-integrated pipeline overview | ✅ Updated |

### Code Implementation
| Module | Purpose | Location |
|--------|---------|----------|
| `produce_db.py` | DB-native orchestrator (19 stages) | `scripts/produce_db.py` |
| `production_db.py` | Unified production ledger + migrations | `scripts/production_db.py` |
| `production_repo.py` | Artifact registry + render unit planning | `scripts/production_repo.py` |
| `media_contract.py` | Provider eligibility + text-risk guardrails | `scripts/media_contract.py` |
| `media_service.py` | Provider job state machine + contract QA + repair | `scripts/media_service.py` |
| `assemble_db.py` | DB-native assembly + deliverable registry + Gate B | `scripts/assemble_db.py` |
| `qa_final.py` | Final-cut QA + DB-contract evidence checks | `scripts/qa_final.py` |
| `render_graphics.py` | Deterministic local graphic compositing | `scripts/render_graphics.py` |
| `paid_adapters.py` | Higgsfield + ElevenLabs adapters (capability-gated) | `scripts/paid_adapters.py` |
| `smoke_config.py` | Strict smoke test configuration | `scripts/smoke_config.py` |
| `clip_db.py` | Clip authority database | `scripts/clip_db.py` |
| `content_db.py` | Content performance logging | `scripts/content_db.py` |

### Archive & Historical Context
| Document | Purpose | Status |
|----------|---------|--------|
| **[ARCHIVE_INDEX.md](ARCHIVE_INDEX.md)** | Outdated documentation sections archive | ✅ Current |
| `docs/archive/` | Historical documentation versions | Archived |

---

## Quick Start for New Contributors

### Understanding the Enhanced System

1. **Start with the summary**: Read `README.md` for pipeline overview; Read `ENHANCED_DATABASE_SYSTEM_SUMMARY.md` for architectural overview
2. **Study the flow**: Review `PRODUCTION_DATA_FLOW_MAP.md` for database-driven pipeline
3. **Understand fingerprints**: Read `HARMONIZED_CLIP_FINGERPRINTS.md` for drift elimination
4. **Review implementation**: Check `CLIP_DB_DESIGN.md` for database schema and API

### Key Concepts to Understand

1. **Unified Production Ledger**: Transactional system of record for all state
2. **Clip Authority Database**: Single source of truth for clip IDs and paths
3. **Harmonized Fingerprints**: Elimination of path drift and stale reuse
4. **Golden-Truth Invariant**: `assert_all_valid()` gates progression
5. **Interactive Change Requests**: Problem→resolution routing with owner assignment

### Working with the System

#### Adding a New Pipeline Step
1. Mirror state to ledger: `production_db.mirror_stage_state()`
2. Use clip authority: `clip_db.get_path()` for paths, `clip_db.can_reuse()` for validation
3. Record evidence: `production_db.mirror_validation()` for QA results
4. Gate with invariant: `clip_db.assert_all_valid()` before progression

#### Debugging Issues
1. Check production status: `python3 scripts/produce_db.py status <production_id>`
2. Run/resume production: `python3 scripts/produce_db.py run <production_id> [--from-stage STAGE]`
3. Review change requests: `python3 scripts/clip_db.py requests <project>`
4. Check golden-truth: `python3 scripts/clip_db.py assert-valid <project>`
5. Run validation tests: `python3 -m pytest tests/unit tests/integration tests/regression -v`

#### Extending the System
1. **New stage**: Add to `STAGE_REGISTRY` in `scripts/stage_runner.py` and invoker in `produce_db.STAGE_INVOKERS`
2. **New artifact type**: Register via `production_repo.register_artifact()`
3. **New validation**: Use `media_service.record_validation_evidence()` or `run_contract_media_qa()`
4. **New provider**: Implement `ProviderAdapter` subclass and register in `paid_adapters._register()`
5. **New guardrail**: Add to `media_contract.py` — pure Python, no DB imports, deterministic

---

## System Evolution Timeline

### Phase 1: File-Based Pipeline (Legacy)
- Independent path derivation by each step
- Recurring failure patterns: stale reuse, path mismatch, parent/child confusion
- Manual debugging and fix cycles

### Phase 2: Database-Driven Migration (Complete)
- ✅ Unified production ledger (`production_db.py`)
- ✅ DB-native orchestrator (`produce_db.py`) — 19 stages, gate approval workflow
- ✅ Provider boundary hardening (`media_contract.py`) — 3-layer guard: contract → service → adapter
- ✅ Contract-based QA (`media_service.py`, `qa_final.py`) — render-method dispatch, DB-contract evidence
- ✅ Local graphic compositing (`render_graphics.py`) — deterministic, no AI provider calls
- ✅ DB-native assembly (`assemble_db.py`) — preflight validation, timeline heuristics, deliverable registry
- ✅ Repair lifecycle (`media_service.py`) — failure classification, action routing, history preservation, idempotent
- ✅ Capability-gated adapters (`paid_adapters.py`) — negative prompt omission based on model capability
- ✅ Smoke config enforcement (`smoke_config.py`) — spend caps, provider job limits, strict mode
- ✅ 258 tests passing (unit + integration + regression + validation)
- ✅ Clip authority database (`clip_db.py`)
- ✅ Harmonized clip fingerprints
- ✅ Golden-truth invariant enforcement
- ✅ Interactive change request routing
- ✅ Legacy state mirroring

### Phase 3: Distributed Execution (Future)
- Multi-machine coordination via ledger
- Quality dashboards and analytics
- Automated optimization from ledger data
- Enhanced monitoring and alerting

---

## Testing & Verification

### Test Suite Status
- ✅ **588 tests green** across CDB-01 through CDB-06
- ✅ **Unit tests** for all database APIs
- ✅ **Integration tests** for pipeline stages
- ✅ **End-to-end tests** for complete workflow
- ✅ **Golden-truth tests** for invariant enforcement

### Verification Commands
```bash
# Verify ledger integrity
python3 scripts/production_db.py check

# List all productions
python3 scripts/production_db.py list

# Check project blockers
python3 scripts/production_db.py blockers <project_slug>

# Verify clip database
python3 scripts/clip_db.py init
python3 scripts/clip_db.py list <project_id>

# Run full test suite
python3 -m pytest tests/ -q
```

---

## Related Documentation

### Strategy & Planning
| Document | Location | Purpose |
|----------|----------|---------|
| Business Plan | `strategy/BUSINESS_PLAN.md` | Overall business strategy |
| Timeplan | `strategy/TIMEPLAN.yaml` | Execution roadmap |
| Plan Manager | `strategy/plan.py` | State management CLI |

### Channel Universe & Brand
| Document | Location | Purpose |
|----------|----------|---------|
| Universe Bible | `docs/channel_universe/` | Creative constraints |
| Technical Bible | `docs/channel_universe/` | Production standards |
| Brand Spec | `brand/BRAND_SPEC.md` | Visual identity |

### Implementation Details
| Document | Location | Purpose |
|----------|----------|---------|
| Research SOP | `docs/RESEARCH_SOP.md` | Sourcing discipline |
| Script Prompts | `docs/prompts/` | LLM prompt library |
| Reviewer Prompts | `docs/reviewer_prompts/` | Quality gate prompts |

---

## Maintenance & Updates

### Documentation Updates Required When:
1. **New database schema migration** - Update `CLIP_DB_DESIGN.md` schema section
2. **New pipeline stage added** - Update `PRODUCTION_DATA_FLOW_MAP.md` sequence
3. **New failure pattern identified** - Document in `HARMONIZED_CLIP_FINGERPRINTS.md`
4. **Architectural change** - Update `ENHANCED_DATABASE_SYSTEM_SUMMARY.md`

### Archive Management:
1. **Outdated sections**: Move to `ARCHIVE_INDEX.md` with superseding reference
2. **Historical versions**: Store in `docs/archive/` with date prefixes
3. **Stale content**: Mark as "Historical" in place if still useful for context

---

## Getting Help

### Common Issues & Solutions
| Issue | Solution | Documentation |
|-------|----------|--------------|
| Path mismatch error | Use `clip_db.get_path()` not manual path derivation | `HARMONIZED_CLIP_FINGERPRINTS.md` |
| Assembly blocked | Check `clip_db.assert-all-valid <project>` for blockers | Golden-Truth Invariant section |
| Change request stuck | Verify owning step is polling `open_change_requests()` | Interactive Change Requests section |
| Ledger inconsistency | Run `production_db.py check` for integrity verification | Testing & Verification section |

### Contact Points
- **System Design**: Review enhanced database system documentation
- **Code Issues**: Check test suite and implementation modules
- **Process Questions**: Refer to pipeline flow documentation
- **Architecture Decisions**: Study summary and design documents

---

**Last Updated**: 2026-06-16  
**System Version**: Database-Driven Edition v1.0  
**Status**: Fully operational with harmonized fingerprints and golden-truth invariant
