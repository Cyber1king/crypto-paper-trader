/**
 * Typed client for the Python paper-trading API (Phase 18A).
 *
 * ## What this module is for
 *
 * A transport. It turns HTTP responses into typed values and HTTP failures into a
 * typed error, and it does nothing else. There is no arithmetic here that touches
 * a trading quantity: no price, no size, no P&L, no score, no fee, no target. Every
 * number the dashboard renders was produced by Python and arrives in a response
 * body.
 *
 * That is not stylistic. Phase 17's architecture makes Python authoritative for
 * candles, signals, sizing, fills, costs, positions, P&L and replay state, and
 * React a projection of it. A client that "helpfully" derived an unrealised P&L
 * from two numbers it received would create a second accounting truth that could
 * disagree with the engine's - which is the specific failure this project exists
 * to prevent.
 *
 * ## Types are transcribed, not generated
 *
 * The Python app sets `openapi_url=None` (`app.py:134-137`), so there is no
 * machine-readable schema to generate from. Every type below is transcribed by hand
 * from the verified response of a running server, and `npm run typecheck` will
 * catch a field that does not exist on a TypeScript object. It cannot catch a
 * field the server renamed, so the tests in `api.test.ts` assert the exact key set
 * of each response against the shapes declared here.
 *
 * ## Error handling
 *
 * The API uses three distinct error body shapes, and a client that assumed one of
 * them would silently lose the server's explanation:
 *
 * - `{detail: {code, message}}` — the engine's typed errors: `INVALID_MODE`,
 *   `MODE_NOT_AVAILABLE`, `POSITION_OPEN`, `REPLAY_FINISHED`, `INVALID_INTERVAL`
 * - `{detail: [{loc, msg, type}, ...]}` — FastAPI request-validation failures (422)
 * - `{detail: "Not Found"}` — router 404s, where `detail` is a bare string
 *
 * All three are normalised into {@link ApiError}. Nothing is ever converted into
 * fake data: a failure to reach the server produces an `ApiError` with code
 * `NETWORK_UNAVAILABLE`, and the UI renders that. It does not render a balance.
 */

/** Mode name, as reported by `GET /api/modes`. */
export type ModeName = string;

/**
 * Replay lifecycle state.
 *
 * `running` means the auto-run timer is *armed*. There is no server-side worker, so
 * the client drives progression with `/api/replay/step`. This is the Phase 17C
 * transition table, transcribed.
 */
export type ReplayStatus = "idle" | "running" | "paused" | "finished";

export type SignalSide = "long" | "short" | "flat";

export interface HealthResponse {
  readonly status: string;
  readonly service: string;
}

export interface ModePolicyIdentity {
  readonly name: string;
  readonly max_positions: number;
  /** Only present on the AI policy. Absent elsewhere, not defaulted to zero. */
  readonly threshold?: number;
  /**
   * Only present on the Daily Target policy (Phase 24C).
   *
   * The policy's **default** objective in dollars. It is *not* the target in force:
   * the user may have changed it, so the authoritative figure is
   * `DailyTargetResponse.daily_target_amount`. A client must never render this as the
   * current target.
   */
  readonly target_amount?: number;
}

export interface ModeInfo {
  readonly mode: ModeName;
  readonly label: string;
  /** Whether this mode may execute paper trades at all. False for Alerts. */
  readonly supports_execution: boolean;
  /**
   * Whether the mode is usable yet. False for the reserved modes — `manual` and
   * `high_risk` as of Phase 24B.
   */
  readonly available: boolean;
  /** Server-authored explanation. Rendered verbatim; never rewritten. */
  readonly note: string;
  /** Null for a brokerless mode, and that is deliberate rather than a gap. */
  readonly policy: ModePolicyIdentity | null;
}

export interface ModesResponse {
  readonly default_mode: ModeName;
  readonly modes: readonly ModeInfo[];
}

export interface DatasetIdentity {
  readonly asset: string;
  readonly timeframe: string;
  readonly sha256: string;
  readonly first_timestamp: string;
  readonly last_timestamp: string;
  readonly candle_count: number;
  readonly interval_seconds: number;
}

export interface StrategyIdentity {
  readonly config_repr: string;
  readonly config_hash: string;
}

export interface ExecutionIdentity {
  readonly execution_model: "cost_deduction" | "fill_price";
  readonly fee_rate: number;
  readonly slippage_rate: number;
  readonly spread_rate: number;
  readonly costs_repr: string;
  readonly costs_hash: string;
  readonly risk_fraction: number;
}

export interface ReplaySignal {
  readonly timestamp: string;
  readonly side: SignalSide;
  readonly reason: string;
  /**
   * The **signal bar's close**, not a fill price. The engine never rewrites it, so
   * it equals `signal_close`. A consumer must not read it as an execution price.
   */
  readonly price: number;
  readonly support: number;
  readonly resistance: number;
  readonly trend: "up" | "down" | "sideways";
  readonly breakout: boolean;
  readonly retest: boolean;
  readonly signal_close: number | null;
  readonly trend_state: "up" | "down" | "sideways" | null;
  readonly breakout_distance: number | null;
  readonly retest_distance: number | null;
  readonly realised_volatility: number | null;
  readonly mean_range: number | null;
}

export interface OpenPosition {
  readonly side: "long" | "short";
  readonly entry_time: string;
  readonly entry_price: number;
  readonly quantity: number;
  readonly reason: string;
  readonly raw_entry_price: number | null;
  readonly signal_close: number | null;
  readonly trend_state: "up" | "down" | "sideways" | null;
  readonly breakout_distance: number | null;
  readonly retest_distance: number | null;
  readonly realised_volatility: number | null;
  readonly mean_range: number | null;
  readonly support_at_entry: number | null;
  readonly resistance_at_entry: number | null;
}

/**
 * A faithful projection of the engine's `ReplayState`.
 *
 * Deliberately absent, because the engine cannot authoritatively produce them and a
 * client that invented one would create a second financial model: equity, mark
 * price, unrealised P&L, margin, buying power, notional, gearing.
 */
export interface ReplayState {
  readonly replay_id: string;
  readonly status: ReplayStatus;
  readonly dataset: DatasetIdentity;
  readonly strategy: StrategyIdentity;
  readonly execution: ExecutionIdentity;
  readonly cursor: number;
  readonly start_index: number;
  readonly bars_processed: number;
  /** Null before the first step. */
  readonly current_timestamp: string | null;
  /** Null once the dataset is exhausted. */
  readonly next_timestamp: string | null;
  readonly next_candle_available: boolean;
  readonly starting_balance: number;
  readonly balance: number;
  readonly realized_pnl: number;
  readonly trade_count: number;
  readonly has_open_position: boolean;
  readonly open_position: OpenPosition | null;
  readonly last_signal: ReplaySignal | null;
  readonly mode: ModeName;
}

export interface AccountResponse {
  readonly starting_balance: number;
  readonly balance: number;
  readonly realized_pnl: number;
  readonly trade_count: number;
}

export interface PositionResponse {
  readonly has_position: boolean;
  readonly position: OpenPosition | null;
}

export interface ClosedTrade {
  readonly side: "long" | "short";
  readonly entry_time: string;
  readonly exit_time: string | null;
  readonly entry_price: number;
  readonly exit_price: number | null;
  readonly quantity: number;
  readonly reason: string;
  readonly exit_reason: string;
  readonly bars_held: number;
  readonly raw_entry_price: number | null;
  readonly raw_exit_price: number | null;
  readonly costs: number;
  readonly fee_total: number;
  readonly slippage_total: number;
  readonly spread_total: number;
  readonly pnl: number | null;
  readonly net_pnl: number | null;
  readonly total_friction: number | null;
  readonly signal_close: number | null;
  readonly trend_state: "up" | "down" | "sideways" | null;
  readonly breakout_distance: number | null;
  readonly retest_distance: number | null;
  readonly realised_volatility: number | null;
  readonly mean_range: number | null;
  readonly support_at_entry: number | null;
  readonly resistance_at_entry: number | null;
}

export interface TradesResponse {
  readonly trade_count: number;
  readonly trades: readonly ClosedTrade[];
}

export interface CostTotals {
  readonly fee_total: number;
  readonly spread_total: number;
  readonly slippage_total: number;
  readonly total_friction: number;
  readonly deducted_costs: number;
}

export interface StatisticsResponse {
  readonly service: string;
  readonly basis: string;
  readonly trades: number;
  readonly net_pnl: number;
  readonly win_rate: number;
  /** Null when undefined; `profit_factor_infinite` distinguishes the two cases. */
  readonly profit_factor: number | null;
  readonly profit_factor_infinite: boolean;
  readonly average_pnl: number;
  readonly max_drawdown: number;
  readonly ending_balance: number;
  readonly costs: CostTotals;
  readonly strategy: StrategyIdentity;
  readonly execution: ExecutionIdentity;
}

export interface Candle {
  readonly timestamp: string;
  readonly open: number;
  readonly high: number;
  readonly low: number;
  readonly close: number;
  readonly volume: number;
}

export interface MarketMetadata {
  readonly asset: string;
  readonly timeframe: string;
  readonly source: string;
  readonly dataset_sha256: string;
  readonly dataset_candles: number;
  readonly dataset_first_timestamp: string;
  readonly dataset_last_timestamp: string;
  readonly returned_candles: number;
  readonly truncated: boolean;
  readonly start: string | null;
  readonly end: string | null;
  readonly limit: number;
}

export interface MarketResponse {
  readonly metadata: MarketMetadata;
  readonly candles: readonly Candle[];
}

export interface ScoreComponent {
  readonly name: string;
  readonly points: number;
  readonly weight: number;
  readonly reason: string;
}

/**
 * The AI Intelligence qualification score.
 *
 * `score` is a **qualification gate on a fixed 0-100 scale**, not a probability.
 * `qualified` means only that `score >= threshold`. The UI must not present either
 * field as a win rate, an expected return or a confidence percentage; the backend's
 * own note says so in as many words, and this type exists partly to make that
 * constraint hard to express wrongly.
 */
export interface IntelligenceScore {
  readonly score: number;
  readonly threshold: number;
  readonly qualified: boolean;
  readonly side: SignalSide;
  readonly components: readonly ScoreComponent[];
}

export interface AiPosition {
  readonly position_id: string;
  readonly side: "long" | "short";
  readonly state: "open" | "closed";
  readonly entry_index: number;
  readonly entry_timestamp: string;
  readonly entry_price: number;
  readonly quantity: number;
  readonly allocated_capital: number;
  readonly reason: string;
  readonly intelligence_score: number;
  readonly qualification_threshold: number;
  readonly exit_index: number | null;
  readonly exit_timestamp: string | null;
  readonly exit_price: number | null;
  readonly exit_reason: string | null;
  readonly bars_held: number | null;
  /** Null while the position is open. The engine computes it only at close. */
  readonly realized_pnl: number | null;
  readonly costs: number | null;
}

/**
 * AI Intelligence's paper account. Authoritative, and the *only* source for AI
 * capital figures.
 *
 * `/api/replay?mode=ai_intelligence` reports a permanently flat broker and must
 * never be used for any of these numbers.
 */
export interface AiAccount {
  readonly starting_capital: number;
  readonly committed_capital: number;
  readonly realized_balance: number;
  readonly available_capital: number;
  readonly realized_pnl: number;
  readonly open_position_count: number;
  readonly max_positions: number;
  readonly position_allocation: number;
  readonly signals_qualified: number;
  readonly signals_admitted: number;
  readonly signals_declined: number;
}

export interface AiState {
  readonly mode: string;
  readonly account: AiAccount;
  readonly positions: readonly AiPosition[];
  readonly journal: readonly AiPosition[];
  /** Null before the first step. Null is honest; zero would be a fabricated score. */
  readonly last_score: IntelligenceScore | null;
  readonly replay: ReplayState;
}

// ---------------------------------------------------------------------------
// Daily Target (Phase 24B)
// ---------------------------------------------------------------------------

/**
 * One finalized UTC day.
 *
 * Only **completed** days appear here. The current day is the top level of
 * {@link DailyTargetResponse}, so a client never has to work out which entry is
 * "today" from a list.
 */
export interface DailyResult {
  /** The UTC calendar date, `YYYY-MM-DD`. */
  readonly date: string;
  /** Equity when that day opened: the carried paper cash, never a reset. */
  readonly starting_balance: number;
  /** Realized paper P&L for the day, after costs. Never unrealized. */
  readonly realized_pnl: number;
  /**
   * The dollar objective that applied **on that day**.
   *
   * Recorded per day because the user may change the target mid-run, so a past day is
   * reported against the target it was actually measured against.
   */
  readonly target_amount: number;
  /** What that day still needed. Never negative. */
  readonly remaining: number;
  readonly reached: boolean;
  readonly trades_closed: number;
}

/**
 * Daily Target's authoritative daily state.
 *
 * ## The target is an objective, not a forecast
 *
 * `target_note`, `waiting_note` and `overshoot_note` are served by the **engine**, not
 * authored here. They are rendered verbatim so the non-guarantee wording cannot drift
 * between server and client, and so no component is left to phrase the caveat itself.
 *
 * `waiting_note` matters most: "daily target" otherwise reads as an instruction to
 * trade until a number is hit, and the engine is the only party that can state
 * truthfully that the strategy waits for valid signals instead.
 *
 * ## A fixed dollar amount, never a percentage
 *
 * `daily_target_amount` is the number the **user** chose. It is independent of the
 * account balance and does not change at a UTC day boundary. There is deliberately no
 * `target_pct` field: the Phase 24B percentage model made the objective scale with the
 * account, so a growing balance silently demanded more profit each day, which is not
 * what "I want to make $50 today" means.
 *
 * ## Null before the first step
 *
 * Every *day* field is `null` until the replay has stepped — there is no UTC date or
 * day-opening balance yet. `daily_target_amount` is the exception and is never null,
 * because it is a user setting rather than something derived from a day's activity.
 * That is what lets the goal be shown and changed on an idle session.
 *
 * ## There is no unrealized figure, on purpose
 *
 * No `unrealized_pnl`, `equity` or `mark_price` field exists. The engine has no live
 * price feed, so any such value would be invented, and the target is measured on
 * realized P&L only.
 */
export interface DailyTargetResponse {
  readonly mode: "daily_target";

  /** Today's objective in dollars of realized paper P&L. */
  readonly daily_target_amount: number;
  /** The non-guarantee statement, verbatim from the engine. */
  readonly target_note: string;
  /** That the target is an objective rather than a signal. */
  readonly waiting_note: string;
  /** Why the target may be exceeded: realized P&L moves in whole trades. */
  readonly overshoot_note: string;
  /** Always true. Present so a client cannot present the target as exact. */
  readonly overshoot_possible: boolean;

  readonly current_date: string | null;
  readonly day_starting_balance: number | null;
  readonly realized_daily_pnl: number | null;
  /** Never negative. Null before the first step. */
  readonly remaining: number | null;
  /** A fraction. May exceed 1 when a trade overshoots. Null before the first step. */
  readonly progress: number | null;
  readonly target_reached: boolean | null;

  /** True when the user re-pointed the target while this day was open. */
  readonly target_changed_during_day: boolean;

  readonly days_completed: readonly DailyResult[];
  readonly replay: ReplayState;
}

/**
 * The body of `POST /api/daily-target/config`.
 *
 * One field, and it is a number of **dollars**. The contract has no percentage and no
 * compounding option, because every one of those would make the target depend on the
 * account balance rather than on the user's decision.
 */
export interface DailyTargetConfigRequest {
  /** Finite and greater than 0. Rejected, never clamped. */
  readonly target_amount: number;
}

// ---------------------------------------------------------------------------
// Manual (Phase 25B)
// ---------------------------------------------------------------------------

/** The actions Manual accepts. `HOLD` is the absence of one and has no endpoint. */
export type ManualAction = "ENTER_LONG" | "ENTER_SHORT" | "EXIT";

/** An action waiting for a bar. */
export interface ManualIntent {
  readonly action: ManualAction;
  /** Fraction of paper cash, for an entry. Absent for an exit. */
  readonly size_pct: number | null;
}

/**
 * Manual's open paper position.
 *
 * The strategy instrumentation fields are present because they are part of the engine's
 * trade, and they are `null` for a manual entry — a user's decision has no signal behind
 * it, so the engine produced no trend state or breakout distance to record.
 */
export interface ManualPosition {
  readonly side: "long" | "short";
  readonly entry_time: string;
  readonly entry_price: number;
  readonly raw_entry_price: number | null;
  readonly quantity: number;
  readonly reason: string;
  readonly signal_close: number | null;
  readonly trend_state: string | null;
  readonly breakout_distance: number | null;
  readonly retest_distance: number | null;
  readonly realised_volatility: number | null;
  readonly mean_range: number | null;
  readonly support_at_entry: number | null;
  readonly resistance_at_entry: number | null;
}

/** One closed manual paper trade. */
export interface ManualTrade {
  readonly side: "long" | "short";
  readonly entry_time: string;
  readonly entry_price: number;
  readonly exit_time: string | null;
  readonly exit_price: number | null;
  readonly raw_entry_price: number | null;
  readonly raw_exit_price: number | null;
  readonly quantity: number;
  readonly reason: string;
  /** `manual` for a user exit. Never one of the engine's own rule labels. */
  readonly exit_reason: string;
  readonly bars_held: number;
  readonly pnl: number | null;
  readonly costs: number;
  readonly net_pnl: number | null;
  readonly fee_total: number;
  readonly slippage_total: number;
  readonly spread_total: number;
  readonly total_friction: number | null;
}

/**
 * Manual's authoritative paper state.
 *
 * ## An action is an intent, not a fill
 *
 * `pending_action` is a request the engine has recorded but not filled. It fills at the
 * **next** execution candle's open when the replay steps, because that price does not
 * exist until then. `execution_price_preview` is that bar's open — and
 * `preview_note` says, in the engine's own words, that it is not a fill price.
 *
 * ## No computed money value
 *
 * Every figure is read from the engine's broker. `paper_cash` is not equity: the engine
 * values no open position, so there is no unrealized figure to show.
 *
 * ## Served only from `/api/manual`
 *
 * Nothing on this interface appears on `/api/account`, `/api/position`, `/api/trades`,
 * `/api/statistics` or `/api/ai`, which keep describing Standard.
 */
export interface ManualStateResponse {
  readonly mode: "manual";
  /** The paper-only statement, verbatim from the engine. */
  readonly note: string;
  /** Actions permitted right now, derived from state. Empty when none are. */
  readonly available_actions: readonly ManualAction[];
  readonly pending_action: ManualIntent | null;
  /** Set when a pending action was replaced or dropped, so nothing is swallowed. */
  readonly paper_note: string | null;
  readonly paper_cash: number;
  readonly starting_balance: number;
  readonly realized_pnl: number;
  readonly trade_count: number;
  readonly open_position: ManualPosition | null;
  /** Bars the open position has been held. Null when flat. */
  readonly bars_held: number | null;
  /** Closed trades, newest first. */
  readonly journal: readonly ManualTrade[];
  readonly execution_price_preview: number | null;
  readonly execution_bar_timestamp: string | null;
  /** Largest fraction of cash this session accepts. Requests are refused, not clamped. */
  readonly max_size_pct: number;
  /** The wording a UI must show beside the preview. */
  readonly preview_note: string;
  readonly replay: ReplayState;
}

/** Engine error codes the UI handles by name rather than by status alone. */
export type ApiErrorCode =
  | "NETWORK_UNAVAILABLE"
  | "INVALID_RESPONSE"
  | "MODE_NOT_AVAILABLE"
  | "INVALID_MODE"
  | "POSITION_OPEN"
  | "REPLAY_FINISHED"
  | "INVALID_INTERVAL"
  | "INSUFFICIENT_HISTORY"
  | "INVALID_TRANSITION"
  | "VALIDATION_ERROR"
  // -- Manual (Phase 25B). Refusals from POST /api/manual/action.
  | "NO_NEXT_CANDLE"
  | "POSITION_ALREADY_OPEN"
  | "NO_POSITION_OPEN"
  | "UNSUPPORTED_REVERSAL"
  | "NO_PAPER_CASH"
  | "NOT_FOUND"
  | "HTTP_ERROR";

/**
 * Every failure this client can produce, as one type.
 *
 * A discriminated union rather than a loose object so a caller cannot read
 * `error.message` and assume it is the server's words: `message` on a
 * `NETWORK_UNAVAILABLE` failure is this module's, not the API's.
 */
export type ApiError =
  | {
      readonly kind: "http";
      readonly status: number;
      readonly code: ApiErrorCode;
      /** The server's own explanation, verbatim. Empty string if it sent none. */
      readonly message: string;
    }
  | {
      readonly kind: "network";
      readonly status: 0;
      readonly code: "NETWORK_UNAVAILABLE";
      readonly message: string;
    }
  | {
      readonly kind: "malformed";
      readonly status: number;
      readonly code: "INVALID_RESPONSE";
      readonly message: string;
    };

export function isApiError(value: unknown): value is ApiError {
  return (
    typeof value === "object" &&
    value !== null &&
    "kind" in value &&
    "code" in value &&
    "message" in value
  );
}

/** Whether a failure means "this mode cannot be used", as opposed to a fault. */
export function isModeUnavailable(error: ApiError): boolean {
  return error.code === "MODE_NOT_AVAILABLE" || error.code === "INVALID_MODE";
}

/** Whether a failure is the server refusing a lifecycle transition, not a fault. */
export function isLifecycleRefusal(error: ApiError): boolean {
  return (
    error.code === "REPLAY_FINISHED" ||
    error.code === "POSITION_OPEN" ||
    error.code === "INVALID_TRANSITION"
  );
}

/** A mode whose lifecycle the UI may drive: available and able to execute. */
export function isControllableMode(mode: ModeInfo): boolean {
  return mode.available && mode.supports_execution;
}

/** A mode that exists and is usable but deliberately cannot trade (Alerts). */
export function isObservationOnlyMode(mode: ModeInfo): boolean {
  return mode.available && !mode.supports_execution;
}

export interface PaperApiOptions {
  /**
   * Base URL of the Python service.
   *
   * Relative by default, so a same-origin dev server or a reverse proxy needs no
   * configuration. There is no environment variable and no key: this is a loopback
   * research tool and reading a credential from the browser would be the wrong
   * shape entirely.
   */
  readonly baseUrl?: string;
  /** Injectable for tests. Defaults to the global `fetch`. */
  readonly fetchImpl?: typeof fetch;
}

export interface MarketQuery {
  readonly limit?: number;
  readonly start?: string;
  readonly end?: string;
}

export interface StepQuery {
  readonly count?: number;
}

/**
 * The typed client.
 *
 * Constructed once and passed down, or used through {@link getDefaultApi}. Every
 * method resolves to the parsed body or throws an {@link ApiError}; nothing
 * resolves to a default, an empty array or a zero, because a caller that cannot
 * distinguish "the server said zero" from "the server was unreachable" will
 * eventually display one as the other.
 */
export class PaperApi {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: PaperApiOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "").replace(/\/$/, "");
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  // -- health & discovery -------------------------------------------------

  async getHealth(signal?: AbortSignal): Promise<HealthResponse> {
    return this.request<HealthResponse>("GET", "/healthz", undefined, signal);
  }

  async getModes(signal?: AbortSignal): Promise<ModesResponse> {
    return this.request<ModesResponse>("GET", "/api/modes", undefined, signal);
  }

  // -- replay lifecycle ---------------------------------------------------

  /**
   * Replay state for one mode.
   *
   * `mode` omitted selects Standard, matching the server's own default. Passing an
   * explicit mode is preferred in the UI so a request is self-describing.
   */
  async getReplay(mode?: ModeName, signal?: AbortSignal): Promise<ReplayState> {
    return this.request<ReplayState>(
      "GET",
      "/api/replay",
      { mode },
      signal,
    );
  }

  async startReplay(
    mode: ModeName | undefined,
    intervalMs?: number,
    signal?: AbortSignal,
  ): Promise<ReplayState> {
    return this.request<ReplayState>(
      "POST",
      "/api/replay/start",
      { mode, interval_ms: intervalMs },
      signal,
    );
  }

  async pauseReplay(
    mode?: ModeName,
    signal?: AbortSignal,
  ): Promise<ReplayState> {
    return this.request<ReplayState>(
      "POST",
      "/api/replay/pause",
      { mode },
      signal,
    );
  }

  async stepReplay(
    mode?: ModeName,
    count?: number,
    signal?: AbortSignal,
  ): Promise<ReplayState> {
    return this.request<ReplayState>(
      "POST",
      "/api/replay/step",
      { mode, count },
      signal,
    );
  }

  async resetReplay(
    mode?: ModeName,
    signal?: AbortSignal,
  ): Promise<ReplayState> {
    return this.request<ReplayState>(
      "POST",
      "/api/replay/reset",
      { mode },
      signal,
    );
  }

  // -- AI Intelligence ----------------------------------------------------

  /**
   * AI Intelligence's authoritative state: account, positions, journal, score.
   *
   * This is the **only** source for AI capital and AI P&L. The route carries no
   * `mode` parameter because the AI contract exists for exactly one mode.
   */
  async getAiState(signal?: AbortSignal): Promise<AiState> {
    return this.request<AiState>("GET", "/api/ai", undefined, signal);
  }

  // -- Daily Target -------------------------------------------------------

  /**
   * Daily Target's authoritative daily state.
   *
   * Read-only, and the **only** source for this mode's daily figures. The route
   * carries a `mode` parameter that defaults to `daily_target` rather than to
   * Standard, because it serves exactly one mode; it is sent explicitly anyway so a
   * reader is never left wondering which mode the response describes.
   *
   * Every value here comes from the engine. The client computes no target, measures no
   * progress and derives no P&L, so there is nothing in this method that could
   * disagree with the tracker that decided when to stop trading.
   */
  async getDailyTarget(signal?: AbortSignal): Promise<DailyTargetResponse> {
    return this.request<DailyTargetResponse>(
      "GET",
      "/api/daily-target",
      { mode: "daily_target" },
      signal,
    );
  }

  /**
   * Set today's dollar target.
   *
   * Returns the **same shape as `getDailyTarget`**, because the server answers with the
   * full daily projection. That is deliberate: a client sets the goal and renders the
   * result from one payload, so "before" and "after" cannot come from two different
   * contracts and disagree about what they mean.
   *
   * The amount is sent as typed rather than being clamped or rounded here. A target
   * silently trimmed to something the user did not type would be worse than a visible
   * rejection, so an invalid value is sent and the server's 422 is surfaced.
   */
  async setDailyTarget(
    targetAmount: number,
    signal?: AbortSignal,
  ): Promise<DailyTargetResponse> {
    const body: DailyTargetConfigRequest = { target_amount: targetAmount };

    return this.request<DailyTargetResponse>(
      "POST",
      "/api/daily-target/config",
      { mode: "daily_target" },
      signal,
      body,
    );
  }

  // -- Manual --------------------------------------------------------------

  /** Manual's authoritative paper state. */
  async getManual(signal?: AbortSignal): Promise<ManualStateResponse> {
    return this.request<ManualStateResponse>(
      "GET",
      "/api/manual",
      { mode: "manual" },
      signal,
    );
  }

  /**
   * Request a paper action.
   *
   * This **records an intent**; it does not fill anything. The engine fills it at the
   * next execution candle's open when the replay steps, so the response's `pending_action`
   * is non-null and `open_position` is unchanged.
   *
   * `sizePct` is sent exactly as typed. A target silently trimmed to something else is
   * the one outcome a user choosing a number cannot detect, so an invalid value goes to
   * the server and its 422 is surfaced instead.
   */
  async submitManualAction(
    action: ManualAction,
    sizePct?: number,
    signal?: AbortSignal,
  ): Promise<ManualStateResponse> {
    return this.request<ManualStateResponse>(
      "POST",
      "/api/manual/action",
      { mode: "manual" },
      signal,
      { action, ...(sizePct === undefined ? {} : { size_pct: sizePct }) },
    );
  }

  /** Discard the pending action, if any. Idempotent. */
  async cancelManualAction(
    signal?: AbortSignal,
  ): Promise<ManualStateResponse> {
    return this.request<ManualStateResponse>(
      "POST",
      "/api/manual/cancel",
      { mode: "manual" },
      signal,
      {},
    );
  }

  // -- projections --------------------------------------------------------

  async getAccount(signal?: AbortSignal): Promise<AccountResponse> {
    return this.request<AccountResponse>("GET", "/api/account", undefined, signal);
  }

  async getPosition(signal?: AbortSignal): Promise<PositionResponse> {
    return this.request<PositionResponse>(
      "GET",
      "/api/position",
      undefined,
      signal,
    );
  }

  async getTrades(signal?: AbortSignal): Promise<TradesResponse> {
    return this.request<TradesResponse>("GET", "/api/trades", undefined, signal);
  }

  async getStatistics(signal?: AbortSignal): Promise<StatisticsResponse> {
    return this.request<StatisticsResponse>(
      "GET",
      "/api/statistics",
      undefined,
      signal,
    );
  }

  /** Real candles from the frozen research dataset. Never synthesised. */
  async getMarket(
    query: MarketQuery = {},
    signal?: AbortSignal,
  ): Promise<MarketResponse> {
    return this.request<MarketResponse>("GET", "/api/market", { ...query }, signal);
  }

  // -- internals ----------------------------------------------------------

  private buildUrl(path: string, query?: Record<string, unknown>): string {
    const search = new URLSearchParams();

    for (const [key, value] of Object.entries(query ?? {})) {
      if (value === undefined || value === null) {
        continue;
      }
      search.set(key, String(value));
    }

    const suffix = search.toString();
    return `${this.baseUrl}${path}${suffix ? `?${suffix}` : ""}`;
  }

  private async request<T>(
    method: "GET" | "POST",
    path: string,
    query?: Record<string, unknown>,
    signal?: AbortSignal,
    /**
     * Optional JSON request body.
     *
     * Added for `POST /api/daily-target/config`. Every other route here is a
     * zero-argument command whose parameters all fit in the query string, so this is the
     * first call with something to *say*. Sending `target_amount` as a query parameter
     * instead would work only by accident of the server reading the query, and would
     * leave a route that accepts an unset target whenever the query is dropped.
     */
    body?: unknown,
  ): Promise<T> {
    let response: Response;

    try {
      response = await this.fetchImpl(this.buildUrl(path, query), {
        method,
        signal,
        // `Content-Type` is set only when there is a body: a GET declaring JSON would
        // be inaccurate, and some intermediaries treat it as a preflight signal.
        headers: {
          Accept: "application/json",
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch (cause) {
      // A server that is not running is the single most likely failure in local
      // development. It becomes a typed error so the UI can say so plainly rather
      // than render zeroes that look like real account figures.
      throw {
        kind: "network",
        status: 0,
        code: "NETWORK_UNAVAILABLE",
        message:
          cause instanceof Error
            ? `Could not reach the paper-trading API: ${cause.message}`
            : "Could not reach the paper-trading API.",
      } satisfies ApiError;
    }

    if (!response.ok) {
      throw await toApiError(response);
    }

    const text = await response.text();

    if (!text) {
      throw {
        kind: "malformed",
        status: response.status,
        code: "INVALID_RESPONSE",
        message: "The API returned an empty body where JSON was expected.",
      } satisfies ApiError;
    }

    try {
      return JSON.parse(text) as T;
    } catch {
      throw {
        kind: "malformed",
        status: response.status,
        code: "INVALID_RESPONSE",
        message:
          "The API returned a body that is not JSON. It may not be the paper-trading API.",
      } satisfies ApiError;
    }
  }
}

/**
 * Normalise the API's three error body shapes into one {@link ApiError}.
 *
 * Handled separately, because assuming one shape would silently discard the
 * server's explanation:
 *
 * - `{detail: {code, message}}` — engine typed errors
 * - `{detail: [...]}`           — FastAPI request validation
 * - `{detail: "..."}`           — router 404, `detail` is a bare string
 */
async function toApiError(response: Response): Promise<ApiError> {
  let detail: unknown;

  try {
    detail = (await response.json()) as { detail?: unknown };
    detail = (detail as { detail?: unknown } | null)?.detail;
  } catch {
    detail = undefined;
  }

  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const record = detail as { code?: unknown; message?: unknown };

    if (typeof record.code === "string") {
      return {
        kind: "http",
        status: response.status,
        code: record.code as ApiErrorCode,
        message:
          typeof record.message === "string" ? record.message : "",
      };
    }
  }

  if (Array.isArray(detail)) {
    // FastAPI validation errors. `msg` is its own explanation; there is no `code`.
    const messages = detail
      .map((item) => (item as { msg?: unknown })?.msg)
      .filter((msg): msg is string => typeof msg === "string");

    return {
      kind: "http",
      status: response.status,
      code: "VALIDATION_ERROR",
      message: messages.join("; ") || "The request was rejected as invalid.",
    };
  }

  if (typeof detail === "string") {
    return {
      kind: "http",
      status: response.status,
      code: response.status === 404 ? "NOT_FOUND" : "HTTP_ERROR",
      message: detail,
    };
  }

  return {
    kind: "http",
    status: response.status,
    code: "HTTP_ERROR",
    message: `The API responded with HTTP ${response.status}.`,
  };
}

let defaultApi: PaperApi | null = null;

/** The process-wide client. Created lazily so tests can substitute their own. */
export function getDefaultApi(): PaperApi {
  defaultApi ??= new PaperApi();
  return defaultApi;
}

/** Replace or clear the process-wide client. Tests only. */
export function setDefaultApi(api: PaperApi | null): void {
  defaultApi = api;
}

/**
 * The string a caller should show a user for a failure.
 *
 * A single place, so no component invents its own phrasing and one of them cannot
 * accidentally claim a failure was a zero balance.
 */
export function describeError(error: ApiError): string {
  switch (error.code) {
    case "NETWORK_UNAVAILABLE":
      return "Paper API unavailable. Start the Python service to see real state.";
    case "MODE_NOT_AVAILABLE":
      return error.message || "That mode is not available.";
    case "INVALID_MODE":
      return error.message || "That mode does not exist.";
    case "POSITION_OPEN":
      return error.message || "A paper position is open; reset is refused.";
    case "REPLAY_FINISHED":
      return error.message || "The replay has finished; reset to run again.";
    case "INVALID_INTERVAL":
      return error.message || "The auto-run interval was rejected.";
    case "VALIDATION_ERROR":
      return error.message || "The request was rejected as invalid.";
    default:
      return error.message || "The paper API returned an error.";
  }
}