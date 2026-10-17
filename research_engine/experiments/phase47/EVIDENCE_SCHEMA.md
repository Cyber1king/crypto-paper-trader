# Phase 47 Evidence Schema

**Date:** 2026-10-09

Implemented in `src/crypto_paper_lab/evidence.py`. This document explains the
schema and the reasoning; the code is the contract.

Nothing here fetches data, calls a provider, or holds a credential.

---

## 1. The central distinction

**Publication time and retrieval time are different facts.**

A syndicated article may be published on Tuesday and retrieved on Friday.
Presenting it as "Friday news" misrepresents it by three days. Every record
therefore carries both, and freshness is computed from `published_at` — never
from `retrieved_at`.

```python
@property
def age_hours(self) -> float | None:
    """Hours since publication, or None when undated."""
    if self.published_at is None:
        return None
    return (self.retrieved_at - self.published_at).total_seconds() / 3600.0
```

`None` is a meaningful return, not a failure: an undated item **cannot be shown
to be fresh**, and therefore should not drive a decision.

---

## 2. `EvidenceItem`

| Field | Required | Purpose |
|---|---|---|
| `evidence_id` | yes | Stable identity |
| `kind` | yes | One of 8 declared kinds |
| `publisher` | yes | Who published it |
| `canonical_url` | yes | Traceable source, http(s) only |
| `headline` | yes | The claim, as published |
| `retrieved_at` | yes | When this project obtained it |
| `published_at` | no | When the publisher says it was published |
| `instruments` | no | Relevance, declared not inferred |
| `summary` | no | |
| `licence_note` | no | Required when `attribution_required` |
| `attribution_required` | yes | Defaults `True` |
| `cluster_id` | no | Story grouping |
| `is_syndicated_copy` | no | Distinguishes copies from originals |
| `original_source_id` | no | Required when syndicated |
| `source_credibility_note` | no | Why this source is trusted |

### Declared kinds

```
news_article  news_broadcast  regulatory_notice  exchange_notice
central_bank_statement  research_note  aggregator_summary  social_post
```

`aggregator_summary` exists as a distinct kind precisely so a summary can never
be mistaken for original reporting.

### Rules enforced at construction

- Blank `evidence_id`, `kind`, `publisher`, `canonical_url` or `headline` → refused
- Non-http `canonical_url` → refused
- Unknown `kind` → refused
- Naive timestamps → refused (§3)
- `is_syndicated_copy` without `original_source_id` → refused
- `original_source_id == evidence_id` → refused

### Freshness

```python
FRESHNESS_THRESHOLDS = {Freshness.FRESH: 24.0, Freshness.STALE: 168.0}
```

| Age | State | Usable |
|---|---|---|
| ≤ 24 h | `FRESH` | yes |
| ≤ 168 h | `STALE` | yes, flagged |
| > 168 h | `EXPIRED` | no |
| no `published_at` | `UNDATED` | no |
| negative age | `UNDATED` | no |

A future-dated item is **not** treated as fresh. Clock skew and embargoes are
real; silently accepting them would let a bad timestamp bypass the staleness
check entirely.

Thresholds are pinned by test so a policy change is a visible edit:

```python
def test_freshness_thresholds_are_the_documented_ones():
    assert FRESHNESS_THRESHOLDS[Freshness.FRESH] == 24.0
```

### Licensing

`is_usable()` returns `False` when `attribution_required` is set and
`licence_note` is empty. A URL proves traceability; it does **not** grant
redistribution rights. A missing licence is a licensing problem, not a
formality, so it refuses.

---

## 3. Timestamps

Naive timestamps are **refused**, not assumed to be UTC.

```python
if moment.tzinfo is None:
    raise EvidenceError(
        f"{field_name} must be timezone-aware. A naive timestamp is "
        "ambiguous, and guessing its zone would corrupt the freshness "
        "calculation it feeds."
    )
```

This is stricter than the Phase 41 dataset loader, which accepts naive timestamps
as UTC by documented convention. The difference is deliberate: dataset
timestamps come from a source whose convention is recorded, while evidence
timestamps come from many publishers with different conventions. A naive value
here is genuinely ambiguous.

---

## 4. `EconomicEvent`

| Field | Required | Notes |
|---|---|---|
| `event_id`, `name`, `authority` | yes | Who published it |
| `kind` | yes | `SCHEDULED` or `UNSCHEDULED` |
| `scheduled_at` | conditional | Required for scheduled; **forbidden** for unscheduled |
| `retrieved_at` | yes | |
| `timezone_note` | yes | Publisher's stated convention |
| `actual` / `forecast` / `previous` | no | Only when genuinely supplied |
| `values_source` | conditional | Required when `actual` or `forecast` is set |
| `revised`, `revision_note` | conditional | Note required when revised |
| `cancelled`, `postponement_note` | conditional | Note required when cancelled |
| `unit`, `source_url` | no | |

### Rules

- An unscheduled event carrying `scheduled_at` is **refused** — it would imply
  an announced time that did not exist.
- `actual`/`forecast` without `values_source` is **refused**: *a number with no
  stated provenance is not evidence*.
- `revised=True` without `revision_note` is refused.
- `cancelled=True` without `postponement_note` is refused.

### Values are never inferred from text

```python
def test_event_values_not_inferred_from_headline():
    record = event(name="CPI came in at 3.1 percent", values_source="BLS release")
    assert record.as_record()["actual"] is None
```

There is no free-text field from which a value could be parsed. An event can
carry a headline in `name` and still have `actual=None`.

### `has_occurred`

False for unscheduled events, cancelled events, and events whose scheduled time
has not passed.

### Verified against a real source

The BLS schedule marks preliminary and revised releases distinctly — e.g.
`Productivity and Costs (P)` then `(R)`. So `revised` is a real, source-expressible
distinction, not a hypothetical field. BLS also documents a **one-day lag**
between publication and API availability, which any pipeline must account for.

---

## 5. `SentimentObservation`

| Field | Required |
|---|---|
| `observation_id`, `instrument_id`, `source_name` | yes |
| `methodology_note` | yes |
| `observed_at`, `retrieved_at` | yes, aware |
| `value`, `scale_min`, `scale_max` | yes |
| `methodology_url`, `licence_note`, `is_contrarian_index` | no |

### Deliberate omissions

There is **no** `probability`, `expected_return`, `win_rate`, or `confidence`
field. Their absence is the design:

```python
def normalised(self) -> float:
    """Position within the scale, in [0, 1].

    A description of where a reading sits, not a probability.
    """
```

`normalised` is a *position*, not a forecast. Renaming it would be a
misrepresentation, so the docstring is explicit and
`test_normalised_is_a_position_not_a_probability` pins it.

### Enforcement

```python
FORBIDDEN_FORECAST_FIELDS = (
    "probability", "win_rate", "expected_return", "edge",
    "confidence_score", "likely_up",
)

def assert_not_a_forecast(record: dict[str, Any]) -> None:
    """Refuse any record presenting sentiment as a forecast."""
```

This is the Phase 47 requirement made executable: a record carrying any of those
fields is **refused**, not reinterpreted.

`None` values are not violations — a record that explicitly has
`probability=None` is fine.

### Inverted and out-of-range values refused

`scale_min >= scale_max` is refused; a `value` outside its declared scale is
refused. A reading whose scale contradicts its value cannot be interpreted.

`is_contrarian_index` exists because some widely-used indices are constructed
so that **high means pessimistic**. Reading one as conventional sentiment
inverts its meaning.

---

## 6. `EvidenceCluster` and independent corroboration

Five syndicated copies of one wire story are **one claim**, not five.

```python
@property
def independent_count(self) -> int:
    """Distinct claims: the representative plus any conflicts.

    Not len(members) + 1.
    """
    return 1 + len(self.conflicting_ids)
```

This addresses a well-documented failure mode in news-driven analysis:
apparent corroboration built from syndication. A system that treats five
republished items as five independent confirmations will read consensus into
what is a single unreplicated claim.

### Rules

- The representative must not also appear in `members`.
- An id may not be in both `members` and `conflicting_ids`. A copy of the same
  story cannot simultaneously contradict itself; listing it in both would
  inflate `independent_count` while claiming agreement.

### Representative selection

`conflicting_evidence()` picks the **earliest published**, tie-broken by id.
Not "most popular" and not "first retrieved" — either would import a provider's
ranking into this project's reasoning.

### Conflict detection

An item is flagged as conflicting when its `source_credibility_note` contains
"conflict". Deliberately crude and explicit: this phase provides the structure,
not a claim-detection model. Nothing here infers that two reports disagree.

---

## 7. What the schema does not do

- **No provider integration.** No HTTP client, no credentials, no retry logic.
- **No scraping.** The BLS schedule is HTML; parsing it would be scraping and is
  not implemented.
- **No sentiment model.** `SentimentObservation` records a *published* reading
  with its stated methodology. It does not compute sentiment.
- **No newsworthiness or impact scoring.** Deliberately absent.
- **No connection to strategy execution.** Nothing in this module is imported by
  `backtest.py`, `replay.py` or `walkforward.py`, and nothing here can influence
  a trade.

---

## 8. Why sentiment must not be treated as a probability

Three reasons, stated so they are not quietly forgotten:

1. **Index construction is proprietary.** Published indices do not disclose their
   component weights, so a reading cannot be independently reproduced or audited.
2. **The population is unclear.** "Social sentiment" means different things to
   different providers — different sources, different sampling, different
   language coverage. Comparing two indices is not comparing like with like.
3. **No validated calibration exists in this project.** Turning a sentiment
   reading into a trade probability would require demonstrating, out of sample,
   that the mapping holds. That work has not been done and cannot be assumed.

The schema reflects this: no probability field exists, `normalised` is a position
rather than a forecast, and `assert_not_a_forecast` refuses records that blur the
line. A sentiment reading is **context for a human reviewing evidence**, not an
input to a trading decision.

Passing these tests says the records are well-formed. It says nothing about
whether sentiment has predictive value for any instrument.