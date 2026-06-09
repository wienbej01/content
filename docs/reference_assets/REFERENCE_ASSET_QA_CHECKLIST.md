# Reference Asset QA Checklist

**Version:** 1.0
**Use:** Human review of every generated still before it enters the canonical reference set.

---

## Scoring Scale

| Score | Meaning |
|---|---|
| 5 | Excellent; strongly on-character/on-set; no issues |
| 4 | Good; on-brand; one minor note at most |
| 3 | Acceptable but weak; revision or supplementation recommended |
| 2 | Poor; significant issues; do not approve |
| 1 | Unusable; automatic fail |

---

## Pass/Reject Thresholds

| Result | Condition | Action |
|---|---|---|
| **Approved — canonical** | Average ≥ 4.0 AND no automatic fail | Promote to canonical reference set; update manifest status to `approved` |
| **Approved — secondary only** | Average 3.0–3.9 AND no automatic fail | Use as supplementary reference only; not canonical; mark `secondary_reference` |
| **Reject** | Average < 3.0 OR any automatic fail | Do not use; regenerate; mark `rejected` in manifest |

---

## QA Dimensions

Score each dimension 1–5. Any dimension scoring 1 = automatic fail regardless of average.

### For James Images

| Dimension | What to check |
|---|---|
| **James identity consistency** | Same face structure, age impression, hair as `JAMES_FRONT_DESK_001` base |
| **Age impression** | Reads as ~60 years old; not younger, not extremely older |
| **Hair** | Silver-grey, combed back; not dark, not white, not disheveled |
| **Wardrobe compliance** | Within approved palette (navy/charcoal/cream/grey); canonical outfit preferred |
| **Expression register** | Composed, attentive, or thoughtful; not grinning, not blank, not shocked |
| **Realism** | Natural skin texture; not over-smoothed; hands look real; no uncanny valley |
| **Lighting compliance** | Warm, directional; one motivated source; no ring light, no colored glow |
| **Color palette** | Warm neutrals; no neon, no cool-toned glow |
| **Background** | Study/library setting (if applicable); correct spatial context |
| **Crop safety** | James within center 56% of horizontal frame width for 9:16 |
| **No automatic fail conditions** | See list below |

### For Studio/Library Images

| Dimension | What to check |
|---|---|
| **Room identity** | Recognizable private executive study/library; not corporate, not futuristic |
| **Spatial consistency** | Desk position, bookshelf location, and lamp position match `STUDIO_LIBRARY_WIDE_001` |
| **Furniture** | Dark wood desk, bookshelves, lamp — correct and consistent |
| **Lighting** | Warm, directional, practical source; no seamless backdrop, no ring light |
| **Color palette** | Warm neutrals: navy, cream, dark wood, brass, leather |
| **Books** | Present; in soft focus; spines not readable; not decorative objects |
| **No technology** | No futuristic monitors, no visible screens unless off/turned away |
| **Cleanliness** | Tasteful order; no messy clutter; no visible logos |
| **Realism** | Looks like a real room; not an AI showroom or generated stage |
| **Crop safety** | Important elements center-safe if James is present; room can use full frame |
| **No automatic fail conditions** | See list below |

---

## Automatic Fail Conditions

Any of the following disqualifies the image regardless of other scores:

| Condition | Category |
|---|---|
| James looks like a different person (major face/age/hair change) | Identity |
| James appears to be a different ethnicity | Identity |
| James has a beard when base images are clean-shaven | Continuity |
| James has glasses not present in base images | Continuity |
| James is wearing a forbidden outfit (bright colors, casual, branded) | Wardrobe |
| James has distorted or malformed hands | Technical |
| Uncanny valley or heavily AI-smoothed face | Technical |
| Garbled or pseudo-text visible and prominent in frame | Content |
| Visible brand logos on any object | Legal |
| Cyberpunk, neon, or sci-fi elements present | Universe |
| Futuristic or unreal elements in the studio | Universe |
| Studio has a completely different layout from `STUDIO_LIBRARY_WIDE_001` | Continuity |
| Image contains a random different person posing as James | Identity |
| Studio is a white seamless backdrop or product-shoot space | Environment |

---

## Review Process

1. Generate the image
2. Score each dimension (1–5)
3. Calculate average
4. Check automatic fail conditions
5. Classify: approved / secondary / reject
6. Update `REFERENCE_ASSET_MANIFEST.md` with the result
7. If approved: copy file to `assets/reference/{category}/ASSET_ID.png`
8. If rejected: keep the file in a scratch folder; do not promote; regenerate
