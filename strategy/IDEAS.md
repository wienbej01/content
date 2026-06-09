# IDEAS.md — Scratchpad

Running capture of ideas for the faceless AI-native education business.
Status legend: `raw` (just captured) · `shaping` (being scoped) · `planned` (added to TIMEPLAN.yaml) · `parked` (deferred) · `dropped`.

How this is used: ideas land here first. When one is ready to execute, the assistant turns it
into TIMEPLAN.yaml step(s) via plan.py and marks it `planned` here with the step id(s).

---

## IDEA-001 — Build a content buffer before launch
- **Status:** raw
- **Captured:** 2026-06-07
- **Idea:** Build a bulk repository of finished content before posting anything publicly.
  Maintain a target of ~10 ready-to-publish items in stock at any time (a rolling buffer).
- **Why it matters:** Consistency is the #1 driver on YouTube/algorithmic platforms. A buffer
  protects cadence against the part-time time-constraint, sick weeks, and the day job. It also
  lets you launch with momentum instead of a cold, sparse channel.
- **Open questions / to decide:**
  - Does "10 items" mean 10 flagships, or 10 publishable units (flagships + atomized sets)?
  - Buffer policy: build to 10 *before first publish*, then maintain >=10 via refill rule
    (publish 1 → produce 1, or batch-refill on weekends)?
  - Where is the buffer tracked — a "content pipeline" board (Notion/sheet) with states:
    idea → scripted → produced → QC-passed → scheduled → published?
- **Tradeoffs:** A 10-flagship pre-launch buffer is ~80 hrs of work before any public signal —
  that delays the first feedback/learning loop. Consider a hybrid: launch after ~4 flagships
  (existing P3 milestone) while continuing to build the buffer toward 10. Pure "build 10 before
  posting" maximizes consistency but slows validation; discuss before committing.
- **Maps to plan:** extends Phase 3 (P3-01/02) and Phase 4 cadence. Candidate new steps:
  a buffer-tracker setup + a buffer-refill SOP.

---

## IDEA-002 — Content performance DB + analysis tool ("the formula engine")
- **Status:** shaping (capture layer planned → TIMEPLAN P2-09; analysis layer deferred to P5/P6)
- **Captured:** 2026-06-07
- **Idea:** Build a tool that ingests performance data for every content unit (long-form,
  shorts, posts, newsletter, blog) across platforms, stores it in a growing database, and
  analyzes performance *against the content's own attributes* to surface trends and concrete
  recommendations for improving future content. The DB compounds over time and gradually
  refines the brand's repeatable "formula."
- **Why it matters:** This is a genuine moat (BUSINESS_PLAN Ch.15/16 — proprietary data). It
  turns gut-feel content decisions into a data-driven, compounding edge competitors can't copy.
  It also doubles as a strong dogfood candidate for the eventual micro-tool (Ch. P4-04/P6).
- **Design sketch (to refine):**
  - **Schema idea:** one row per content unit with (a) *attributes* — pillar, format archetype,
    hook type, length, topic, thumbnail style, publish time, CTA type, source-log refs; and
    (b) *metrics* — views, watch time / avg % viewed, CTR, retention curve, subs gained,
    clicks, conversions, revenue attributed.
  - **Ingestion:** start manual/CSV export → automate via YouTube Data API + platform exports
    through the n8n pipeline (P2-03).
  - **Analysis:** correlate attributes ↔ outcomes; flag patterns (e.g., "contrarian hooks +
    8-10 min + AI pillar → top quartile retention"); output a ranked list of recommendations
    that feed the idea engine (BUSINESS_PLAN Ch.5.2).
  - **Storage:** SQLite to start (simple, local, inspectable); grows over time. Could later
    expose insights inside the customer-facing micro-tool.
- **Open questions / to decide:**
  - Build incrementally (CSV + SQLite + a script) now, or wait until there's enough data
    (>= ~20-30 units) for analysis to be meaningful? Recommendation: stub the schema + manual
    logging early (cheap), defer the analysis/recommendation layer until data exists.
  - Is this an internal tool only, or the seed of the sellable micro-tool (P4-04/P6-01)?
- **Tradeoffs:** Analysis on tiny data is noise — premature optimization. The high-value, low-cost
  move now is to *capture* attributes+metrics from unit #1 so the DB is rich when it matters;
  build the analysis layer once data is sufficient.
- **Maps to plan:** strongly related to P2 (pipeline), the idea engine, and the micro-tool
  (P4-04 spec / P6-01 build). Candidate: a "content performance schema + logging" step in P2,
  and an "analysis/recommendation layer" step in P5/P6.

---

## Parking lot (unscoped, capture-only)
- (add quick ideas here; promote to a numbered IDEA when shaping)
