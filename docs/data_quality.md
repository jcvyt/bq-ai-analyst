## DQ-001: Future-dated events in raw snapshot
- raw_thelook.events created 2026-10-16 20:51:55; rows exist dated 2026-10-17..2026-10-19 (low volume: 529/426/231)
- 2026-10-16 itself is low (680 vs 17,786 on 10-15): generator lag, not a partial load
- Decision: curated.events unchanged (no filter). Golden set v1 anchored at 2026-10-16 so windows avoid the tail.
- Revisit: Phase 2 data contract (reject event_date > load date) → requires golden set v2 re-freeze


## DQ-002: Parsed URI fields are event-type specific
- category: department events only (591,195); brand: department only (590,710; 485 dept rows have category, no brand)
- product_id: product events only (840,836); cart/purchase/cancel/home carry none of the three
- Impact: "brands by cart/purchase" is not answerable from semantic.web_events; needs a product_id → products join (Phase 2 semantic model)
- Eval: G11 uses department views; G13 is a data-limitation test; G15 filters brand IS NOT NULL

## DQ-003: Country value inconsistency
- 'Spain' and 'España' both present in users.country (also 'Brasil' for Brazil)
- Impact: country-level aggregates split Spain into two rows (G01)
- Decision: curated unchanged for v1; glossary notes both spellings. Phase 2: canonical country mapping in curated (→ golden set v2)