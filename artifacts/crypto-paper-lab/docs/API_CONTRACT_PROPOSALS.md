# API Contract Proposals

Status of every proposal in this file: PROPOSED, AWAITING BACKEND APPROVAL.
Nothing in the frontend depends on any proposal here, and no frontend code calls these endpoints. Paths, names and fields below are illustrative; the backend owner decides them.

## Proposal 1: Strategy signal history (read-only)

### Why
The Strategy signals page can show only the engine's last signal, taken from the replay state. There is no way to list earlier signals, so the page cannot show how signals changed over a replay.

### What the frontend would need (not a design)
- A read-only GET that returns the signals the engine has already recorded for the current replay, in bar order, for one mode.
- Each item reuses the existing ReplaySignal shape and adds the bar timestamp it belongs to.
- A bounded size: a limit parameter and a truncated flag in the response metadata, in the same style as GET /api/market.
- Metadata that identifies the run (replay id and dataset hash) so the page can show which replay the list belongs to.
- No computed fields: no hit rate, no expected return, and no score presented as a probability.
- Errors use the existing ApiError envelope.

### Constraints
- Paper and simulated only. The endpoint must not trigger a step, an order or any state change.
- Values come from the engine's own record; the frontend will not recompute levels or signals.
- It must not expose protected research data, evaluation windows or evidence.

### Illustrative shape (names are placeholders)
A response with a metadata object (mode, replay_id, dataset_sha256, returned_signals, truncated, limit) and a signals array of ReplaySignal items, each carrying a bar timestamp.

### Open questions for the backend owner
- Does the engine already persist per-bar signals, or would this need a new record?
- Should the list cover only bars with a non-empty signal, or every processed bar?
- Ordering and paging: oldest first with a cursor, or newest first with a limit?
- Which modes should it support?

### Frontend plan if approved
Add a read-only table to the Strategy signals page, behind the same loading, error and unavailable states. Until then the page says plainly that no history is available.