# Documentation Archive Index — Database-Driven System Migration

**Created:** 2026-06-16
**Purpose:** Track outdated documentation sections archived due to the enhanced database-driven process flow migration and harmonized clip fingerprint system.

---

## Migration Summary

The production pipeline has undergone a fundamental architectural shift from file-based state management to a unified transactional ledger system. Key changes:

1. **Database-Driven Process Flow**: All state now flows through `production_db.py` unified ledger
2. **Harmonized Clip Fingerprints**: Single canonical path computation eliminates drift
3. **Transactional Consistency**: Golden-truth invariant prevents silent degradation
4. **Interactive Change Requests**: Problems become tracked work items with automatic routing

## Archived Documentation Sections

### 1. File-Based State Management Documentation
**Archive Reason:** Superseded by unified ledger system
**Replacement:** Enhanced database-driven flow in `PRODUCTION_DATA_FLOW_MAP.md`

| Section/File | Original Location | Archive Reason | Superseded By |
|--------------|-------------------|----------------|---------------|
| "Independent Path Derivation" | `CLIP_DB_DESIGN.md` §"The Problem" | All path computation now centralized in `clip_db._canonical_path()` | "Unified Production Ledger Architecture" |
| "Multiple Path Formats Table" | `CLIP_DB_DESIGN.md` §"Current path-derivation drift points" | Single canonical path eliminates format drift | "Harmonized Clip Fingerprint System" |
| "Fixes Required" | `PRODUCTION_DATA_FLOW_MAP.md` §"Fixes Required" | Implemented via `can_reuse()` and `assert_all_valid()` | "Transaction Guarantees" |

### 2. Legacy Failure Analysis Documentation  
**Archive Reason:** Failure classes eliminated by new system
**Replacement:** "Former Failure Classes (Now Eliminated)" table in updated docs

| Section/File | Original Location | Archive Reason | Superseded By |
|--------------|-------------------|----------------|---------------|
| "Root Causes" | `PRODUCTION_DATA_FLOW_MAP.md` §"Root Causes" | Issues A, B, C resolved by database-driven flow | "Harmonized Clip Fingerprint System" |
| "Where the Current Failure Occurs" | `PRODUCTION_DATA_FLOW_MAP.md` §"Where the Current Failure Occurs" | Failure table describes pre-harmonization state | "Beat ID Transformations with Harmonized Lineage" |
| "Validation: This Specific Video" | `PRODUCTION_DATA_FLOW_MAP.md` §"Validation" | Specific failure example from old system | Not needed (system prevents failures) |

### 3. Migration Planning Documentation
**Archive Reason:** Migration complete, system operational
**Replacement:** "Migration Complete (Status)" section

| Section/File | Original Location | Archive Reason | Superseded By |
|--------------|-------------------|----------------|---------------|
| "Migration Plan" | `CLIP_DB_DESIGN.md` §"Migration Plan" | CDB-01 through CDB-06 complete | "Migration Complete (Status)" |
| "Phase Table" | `CLIP_DB_DESIGN.md` §"Migration Plan" | All phases delivered and tested | "STATUS: FULLY IMPLEMENTED" banner |

### 4. Pre-Harmonization System Documentation
**Archive Reason:** Describes problems that no longer exist
**Replacement:** Historical context preserved in archive

| Section/File | Original Location | Archive Reason | Status |
|--------------|-------------------|----------------|--------|
| "The Problem (root cause)" | `CLIP_DB_DESIGN.md` beginning | Useful historical context | **Preserved in place** with "Former" designation |
| "Five files, three conventions" | `CLIP_DB_DESIGN.md` §"Current path-derivation" | Historical reference | **Preserved in place** as context |

## Enhanced Documentation Structure

### Active Documentation (Updated)

1. **`PRODUCTION_DATA_FLOW_MAP.md`** - Enhanced database-driven flow with unified ledger
2. **`CLIP_DB_DESIGN.md`** - Implemented system status with harmonized fingerprints  
3. **`PIPELINE.md`** - Database-integrated pipeline overview (to be updated)
4. **`ARCHIVE_INDEX.md`** - This document tracking archived sections

### Key Architectural Documents

| Document | Purpose | Status |
|----------|---------|--------|
| `production_db.py` | Unified ledger implementation | ✅ Active code |
| `clip_db.py` | Clip authority database | ✅ Active code |
| `PRODUCTION_DATA_FLOW_MAP.md` | Enhanced flow documentation | ✅ Updated |
| `CLIP_DB_DESIGN.md` | System design documentation | ✅ Updated |

## System Verification Checklist

✅ **Database-Driven Flow**: All state transitions through unified ledger
✅ **Harmonized Fingerprints**: Single canonical path computation
✅ **Transactional Consistency**: Golden-truth invariant enforced
✅ **Change Request Routing**: Interactive bidirectional model operational
✅ **Legacy State Mirroring**: File-based state mirrored to ledger
✅ **Migration Complete**: CDB-01 through CDB-06 delivered

## Historical Context Note

The archived documentation sections remain valuable for understanding:
- The evolution from file-based to database-driven architecture
- The specific failure patterns that motivated the harmonization work
- The migration strategy and implementation phases

They are marked as "Former" or "Historical" in updated documents rather than deleted entirely, preserving continuity while clearly indicating the current system state.

---

## Archive Metadata

**Last Updated:** 2026-06-16
**Archivist:** System Documentation Audit (Kiro/Sonnet)
**Confidence:** High (all archived sections have clear superseding documentation)
**Cross-Reference:** See updated `PRODUCTION_DATA_FLOW_MAP.md` and `CLIP_DB_DESIGN.md` for current system documentation
