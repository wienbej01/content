# Research Engine — Standard Operating Procedure

**Version:** 1.0
**Status:** Active
**Enforces:** Non-negotiable #1 (sourcing discipline)
**Reference:** BUSINESS_PLAN.md Ch.6

---

## Purpose

Every content unit produced by Leverage Mind must be built from original frameworks derived from primary sources. This SOP ensures legal compliance, differentiation, and defensibility.

---

## Hard Rules (non-negotiable)

1. **Minimum 3 independent primary sources** per content unit.
2. **TED talks / copyrighted content = trend discovery input ONLY.** Never reformulated, never structurally followed.
3. **Never paraphrase a single source's structure.** Always restructure into the brand's own framework.
4. **Quotations:** short, attributed, as commentary — never the substance.
5. **One original asset per unit** (your data, example, diagram, demo, or framework).
6. **Source log maintained per unit** for defensibility.

---

## Workflow

```
1. MINE → Scan sources for resonant themes
         Sources: TED (trend only), books, papers, Reddit, forums, newsletters, X
         Output: 3-5 candidate themes logged

2. VALIDATE → Check demand
         Tools: YouTube search volume, VidIQ/TubeBuddy, Google Trends, competitor views
         Gate: if low demand → back to step 1
         Output: 1-2 validated themes

3. PRIMARY SOURCES → Go deep on chosen theme
         Read ≥3 independent primary sources (papers, books, practitioner accounts)
         NOT secondary summaries or other YouTube videos
         Log each source in the source log

4. SYNTHESIZE → Build original framework
         Combine insights across sources into YOUR structure
         Add at least one original asset (your example, your data, your model)
         Name the framework something ownable

5. ORIGINALITY CHECK → Self-audit
         □ Does this track a single source's structure? → restructure
         □ Is the framework genuinely original? → not a rename of an existing model
         □ Could a viewer trace this back to one talk/article? → add more sources
         □ Is there at least one thing that only exists because James made it?

6. APPROVED BRIEF → Hand to scripting pipeline
         Output: content brief with topic, framework, sources, target audience
```

---

## Source Log Template

Use this for every content unit. Store in `research/source_logs/<project_id>.json`:

```json
{
  "project_id": "flagship_001_compound_clarity",
  "topic": "How compounding works for career capital",
  "pillar": "Career capital & wealth frameworks",
  "researched_at": "2026-06-10",
  "themes_scanned": [
    "TED: James Clear on habits (trend signal only — NOT a source)",
    "Reddit r/productivity: recurring question about career compounding"
  ],
  "primary_sources": [
    {
      "id": 1,
      "type": "book",
      "title": "The Compound Effect",
      "author": "Darren Hardy",
      "year": 2010,
      "how_used": "Concept of micro-consistency; NOT following his framework structure",
      "pages_chapters": "Ch. 2-3"
    },
    {
      "id": 2,
      "type": "paper",
      "title": "Deliberate Practice and Expert Performance",
      "author": "Ericsson et al.",
      "year": 1993,
      "how_used": "Evidence that quality repetition > quantity; supports principle 2"
    },
    {
      "id": 3,
      "type": "practitioner",
      "title": "Internal career-review framework (James's own experience)",
      "author": "Original",
      "year": null,
      "how_used": "The 4-quarter review cycle; entirely original asset"
    }
  ],
  "original_framework": {
    "name": "The Compound Clarity Model",
    "thesis": "Career capital compounds only when you have a system for directed repetition + periodic restructuring.",
    "principles": ["Directed Micro-Reps", "Quarterly Restructure", "Leverage Audit", "Compounding Signal"]
  },
  "originality_check": {
    "tracks_single_source": false,
    "framework_is_genuinely_new": true,
    "original_asset_present": true,
    "ted_used_only_as_trend": true
  },
  "approved": true,
  "approved_by": "founder",
  "notes": ""
}
```

---

## Forbidden

- Using TED talk structure as a content outline
- Reformulating a single book chapter into a video
- Citing fewer than 3 independent sources
- Publishing without a source log
- Claiming originality for a repackaged existing framework (Eisenhower Matrix, GTD, PARA, etc.)

---

## Directory Structure

```
research/
  source_logs/           # One JSON per content unit
  briefs/                # Approved content briefs (output of this SOP)
  themes/                # Raw theme scans (optional, for backlog)
```

---

## Integration with Pipeline

The source log is **created before scripting** and **referenced during QA**:

```
Research Engine → Source Log → Content Brief → Script (P4-02) → Storyboard → ...
                                                ↑
                                          QA checks source count ≥ 3
                                          QA checks originality_check fields
```

The LLM reviewer gates (P4-08, when built) will verify:
- `primary_sources` count ≥ 3
- `originality_check.tracks_single_source == false`
- `originality_check.original_asset_present == true`
