#!/usr/bin/env python3
"""Verify enhanced database-driven documentation consistency."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS_DIR = ROOT / "docs"

# Key documentation files that should exist
REQUIRED_DOCS = [
    "ENHANCED_DATABASE_SYSTEM_SUMMARY.md",
    "PRODUCTION_DATA_FLOW_MAP.md", 
    "CLIP_DB_DESIGN.md",
    "HARMONIZED_CLIP_FINGERPRINTS.md",
    "PIPELINE.md",
    "ARCHIVE_INDEX.md",
    "DOCUMENTATION_INDEX.md",
]

# Key terms that should appear in enhanced system docs
ENHANCED_TERMS = [
    "database-driven",
    "unified ledger",
    "clip_db",
    "production_db",
    "harmonized",
    "fingerprint",
    "canonical path",
    "golden-truth",
    "assert_all_valid",
    "can_reuse",
    "change request",
    "transactional",
]

# Legacy terms that should be marked as historical
LEGACY_TERMS = [
    "path mismatch",
    "stale reuse", 
    "parent/child confusion",
    "fingerprint drift",
    "independent derivation",
]

def check_file_exists(path):
    """Check if a documentation file exists."""
    return path.exists()

def check_enhanced_terms(content):
    """Check if enhanced system terms appear in documentation."""
    content_lower = content.lower()
    found = []
    missing = []
    
    for term in ENHANCED_TERMS:
        if term.lower() in content_lower:
            found.append(term)
        else:
            missing.append(term)
    
    return found, missing

def check_legacy_context(content):
    """Check if legacy terms are properly contextualized as historical."""
    lines = content.split('\n')
    legacy_lines = []
    
    for i, line in enumerate(lines):
        for term in LEGACY_TERMS:
            if term.lower() in line.lower():
                # Check if line contains historical context markers
                if not any(marker in line.lower() for marker in ["historical", "former", "legacy", "resolved", "eliminated"]):
                    legacy_lines.append((i+1, line.strip()))
    
    return legacy_lines

def verify_documentation():
    """Main verification function."""
    print("🔍 Verifying enhanced database-driven documentation...")
    print("-" * 60)
    
    results = {
        "files_exist": {},
        "enhanced_terms": {},
        "legacy_context": {},
        "overall_status": "PASS"
    }
    
    # Check required files
    print("\n📁 Required Documentation Files:")
    for doc in REQUIRED_DOCS:
        path = DOCS_DIR / doc
        exists = check_file_exists(path)
        results["files_exist"][doc] = exists
        
        status = "✅" if exists else "❌"
        print(f"  {status} {doc}")
        
        if not exists:
            results["overall_status"] = "FAIL"
    
    # Check enhanced terms in key docs
    print("\n🔑 Enhanced System Terminology:")
    key_docs = ["ENHANCED_DATABASE_SYSTEM_SUMMARY.md", "PRODUCTION_DATA_FLOW_MAP.md"]
    
    for doc in key_docs:
        path = DOCS_DIR / doc
        if path.exists():
            content = path.read_text()
            found, missing = check_enhanced_terms(content)
            
            results["enhanced_terms"][doc] = {
                "found": found,
                "missing": missing,
                "coverage": len(found) / len(ENHANCED_TERMS)
            }
            
            print(f"\n  📄 {doc}:")
            print(f"    Found: {len(found)}/{len(ENHANCED_TERMS)} terms")
            if missing:
                print(f"    Missing: {', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}")
    
    # Check legacy term context
    print("\n🏛️ Legacy Term Contextualization:")
    for doc in REQUIRED_DOCS:
        path = DOCS_DIR / doc
        if path.exists() and doc != "ARCHIVE_INDEX.md":  # Archive doc handles legacy differently
            content = path.read_text()
            legacy_lines = check_legacy_context(content)
            
            results["legacy_context"][doc] = {
                "lines": legacy_lines,
                "count": len(legacy_lines)
            }
            
            if legacy_lines:
                print(f"\n  ⚠️ {doc}: {len(legacy_lines)} legacy term(s) without historical context")
                for line_num, line in legacy_lines[:2]:  # Show first 2 examples
                    print(f"    Line {line_num}: {line[:80]}...")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Verification Summary:")
    
    missing_files = [doc for doc, exists in results["files_exist"].items() if not exists]
    if missing_files:
        print(f"❌ Missing files: {', '.join(missing_files)}")
    else:
        print("✅ All required documentation files present")
    
    total_coverage = 0
    coverage_count = 0
    for doc, data in results["enhanced_terms"].items():
        total_coverage += data["coverage"]
        coverage_count += 1
    
    if coverage_count > 0:
        avg_coverage = total_coverage / coverage_count
        print(f"📈 Enhanced term coverage: {avg_coverage:.1%}")
    
    total_legacy_issues = sum(data["count"] for data in results["legacy_context"].values())
    if total_legacy_issues > 0:
        print(f"⚠️  Legacy context issues: {total_legacy_issues}")
    else:
        print("✅ Legacy terms properly contextualized")
    
    print(f"\n🎯 Overall Status: {results['overall_status']}")
    
    # Save results
    results_path = DOCS_DIR / "verification_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {results_path}")
    return results["overall_status"] == "PASS"

if __name__ == "__main__":
    success = verify_documentation()
    exit(0 if success else 1)
