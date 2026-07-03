# Claim Inventory Contract

**Version:** 1.0
**Status:** Active
**Applies to:** `storyboard_generation` via Sonnet 5 through Kilo
**See also:** `schemas/claim_inventory.schema.json`, `schemas/storyboard_v2.schema.json`

---

## 1. Purpose

The claim inventory is the authoritative list of every factual assertion that the video makes. It exists between the approved script and the storyboard so that:

- Every **statistic, study, person claim, date, fact, reference, source quote** has an identified source.
- Every **opinion or original argument** is explicitly labelled so viewers and reviewers know the source is the author's reasoning, not external evidence.
- Storyboard **shots** and **overlays** link back to specific claims so that B-roll, graphics, and on-screen text never invent unsupported evidence.

The claim inventory is **not** a research log. It is a **production contract**: it tells Sonnet 5 which claims must be visually reinforced and how.

---

## 2. Claim Properties

| Field | Required | Description |
|---|---|---|
| `claim_id` | yes | Stable identifier (e.g. `C001`, `C-climate-3`). Must be unique within the inventory. |
| `source_id` | if source-backed | Reference into the source research log or citation database. |
| `claim_text` | yes | Exact or paraphrased claim text from the approved script. |
| `claim_type` | yes | One of: `fact`, `reference`, `source_quote`, `statistic`, `narrative_premise`, `definition`, `comparison`, `analogy`, `conclusion`, `opinion`, `original_argument`, `study`, `person`, `date`. |
| `citation_status` | recommended | `source_backed`, `unsupported_opinion`, or `unverified`. |
| `requires_visual_reinforcement` | recommended | `true` if the storyboard must include a shot or overlay that reinforces this claim. |
| `allowed_visual_treatment` | recommended | `literal_evidence`, `metaphorical`, `stat_display`, `diagram`, `source_label`, `quote_card`, `comparison`, `emotional_reset`, or `no_visual_needed`. |
| `script_segment_refs` | recommended | Array of script segment IDs where this claim appears. |
| `storyboard_entity_refs` | recommended | Array of storyboard shot/overlay IDs that visually represent this claim (populated after storyboard generation). |

---

## 3. Source-Backed vs Opinion Rules

### Source-backed claims

`claim_type` = `fact`, `reference`, `source_quote`, `statistic`, `study`, `person`, `date`, `narrative_premise`, `definition`, `comparison`, `analogy`, or `conclusion`

- **Must** have a `source_id` referencing the research log or citation database.
- **Must** have `citation_status` = `source_backed`.
- The storyboard **should** include a visual that reinforces the claim (exact treatment per `allowed_visual_treatment`).

### Unsupported / Opinion claims

`claim_type` = `opinion` or `original_argument`

- **May** omit `source_id`.
- `citation_status` should be `unsupported_opinion`.
- The storyboard **may** still use visuals, but they must not imply external evidence that does not exist.

---

## 4. How Sonnet 5 Must Link Claims to Visuals

When Sonnet 5 generates the storyboard, it must:

1. **Extract every claim** from the approved script into `claim_inventory[]`.
2. **Classify each claim** by type and source status.
3. **Assign `allowed_visual_treatment`** per claim — choosing the most appropriate visual strategy for the claim's type and narrative importance.
4. **Add `claim_refs`** to each shot or overlay that visually reinforces a claim. For example, a shot showing a neural network must reference the `claim_id` about AI scaling.
5. **Add `source_ref`** to overlays that display a statistic or quote, linking back to the claim's `source_id`.
6. **Add `storyboard_entity_refs`** to the claim once shots/overlays are assigned.

### Enforcement

- The **Claim Compliance Auditor** validates that every source-backed claim has a visual reinforcement.
- The **Validator** checks that all `claim_refs` in shots and overlays resolve to valid `claim_id` values.
- Overlays with `source_label` type must reference a valid source-backed claim.

---

## 5. Visual Treatment Reference

| Treatment | When to use | Example |
|---|---|---|
| `literal_evidence` | The claim is best shown directly — a photo of the person, a screenshot of the study. | "GPT-4 scored 90th percentile" → show benchmark screenshot |
| `metaphorical` | An abstract or conceptual claim benefits from metaphor. | "Neural networks scale unexpectedly" → growing network visualization |
| `stat_display` | A specific number or percentage — use overlay with the number. | "72% of professionals..." → lower-third stat card |
| `diagram` | The claim describes a process or relationship. | "The forgetting curve" → annotated line chart |
| `source_label` | The claim needs a visible attribution. | "Per the 2023 study by Mollick & Mollick" → source citation lower-third |
| `quote_card` | A direct quote from a source. | Fullscreen quote overlay with attribution |
| `comparison` | The claim contrasts two things. | Split-screen comparison |
| `emotional_reset` | Used only when the audience needs a break. | Generic establishing shot, no claim-specific content |
| `no_visual_needed` | The claim is entirely narrative and needs no visual reinforcement. | Segue or transition beat |

---

## 6. Validation Rules

The `claim_inventory_validator.py` enforces:

1. **Schema conformance** — all required fields, types, enums.
2. **Source-backed requirement** — `statistic`, `study`, `person`, `date`, `fact`, `reference`, `source_quote`, `narrative_premise`, `definition`, `comparison`, `analogy`, `conclusion` claims must have `source_id`.
3. **Opinion exemption** — `opinion` and `original_argument` claims pass without `source_id`.
4. **Duplicate `claim_id`** — each `claim_id` must be unique.
5. **Valid `allowed_visual_treatment`** — must be one of the recognised treatment tokens.
6. **Claim refs resolve** — `claim_refs` in shots, overlays, and segment work orders must match an existing `claim_id`.
7. **Script segment refs resolve** — `script_segment_refs` must match known `segment_id` values (when segment list is provided).

---

## 7. Integration with Storyboard Schema

The `claim_inventory` field in `storyboard_v2.schema.json` references claim definitions. Each claim is validated by the claim inventory schema AND the storyboard schema's own definition. The two schemas are consistent — any change to one must be reflected in the other.
