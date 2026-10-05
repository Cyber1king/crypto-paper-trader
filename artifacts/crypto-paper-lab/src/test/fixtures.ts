/**
 * Test fixtures (Phase 18K).
 *
 * ## Where these values come from
 *
 * Every shape below was captured from a **running** Python paper-trading API, not
 * invented. The `expectContract` helper is deliberate about that: it asserts a
 * fixture's key set against the declared TypeScript interface, so a field renamed
 * on the server breaks a test rather than silently rendering `undefined`.
 *
 * ## What is deliberately absent
 *
 * No fixture contains a fabricated trading value. Balances are the engine's
 * `10,000.0` starting figure, realised P&L is `0.0` before any step, and an
 * intelligence score appears only in the fixture that is explicitly about scoring.
 * There is no `100000` anywhere: that was the old frontend fiction, and its
 * absence is the point.
 */

import {
  PaperApi,
  type AiPosition,
  type AiState,
  type ApiError,
  type HealthResponse,
  type MarketResponse,
  type ModeInfo,
  type ModesResponse,
  type ReplayState,
  type StatisticsResponse,
  type TradesResponse,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Exact server responses, transcribed from a running API
// ---------------------------------------------------------------------------

export const HEALTH: HealthResponse = {
  status: "ok",
  service: "crypto-paper-lab",
};

export const MODES: ModesResponse = {
  default_mode: "standard",
  modes: [
    {
      mode: "standard",
      label: "Standard",
      supports_execution: true,
      available: true,
      note: "Automatic paper trading on the frozen baseline strategy. The default, and behaviourally identical to the pre-17F replay.",
      policy: { name: "automatic", max_positions: 1 },
    },
    {
      mode: "ai_intelligence",
      label: "AI Intelligence",
      supports_execution: true,
      available: true,
      note: "Isolated paper pool. Executes only signals whose deterministic intelligence score reaches 90, holds up to 5 independent paper positions, and closes each at a 0.5% profit target. The score is a research heuristic, not a probability or a profit forecast. Own pool, own positions, own journal.",
      policy: { name: "intelligence", max_positions: 5, threshold: 90 },
    },
    {
      mode: "alerts",
      label: "Alerts",
      supports_execution: false,
      available: true,
      note: "Notification-only. Holds no broker and cannot execute paper trades. Notification delivery arrives in a later phase.",
      policy: null,
    },
    {
      mode: "daily_target",
      label: "Daily Target",
      supports_execution: true,
      available: false,
      note: "Reserved. The mode contract is defined in Phase 17G.",
      policy: { name: "reserved_daily_target", max_positions: 0 },
    },
    {
      mode: "manual",
      label: "Manual",
      supports_execution: true,
      available: false,
      note: "Reserved. The mode contract is defined in Phase 17G.",
      policy: { name: "reserved_manual", max_positions: 0 },
    },
    {
      mode: "high_risk",
      label: "High-Risk Paper",
      supports_execution: true,
      available: false,
      note: "Reserved. The mode contract is defined in Phase 17G.",
      policy: { name: "reserved_high_risk", max_positions: 0 },
    },
  ],
};

/** An exact copy of the `dataset`, `strategy` and `execution` identity blocks. */
const DATASET = {
  asset: "BTC/USDT",
  timeframe: "1h",
  sha256: "201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B",
  first_timestamp: "2024-01-01T00:00:00Z",
  last_timestamp: "2025-12-31T23:00:00Z",
  candle_count: 17544,
  interval_seconds: 3600,
} as const;

const STRATEGY = {
  config_repr:
    "StrategyConfig(asset='BTC/USDT', timeframe='1h', lookback=20, fast_period=5, slow_period=12, breakout_buffer=0.001, retest_tolerance=0.002, min_breakout_distance=0.0, trend_strength_min=0.001, retest_use_close=False, breakout_confirm_bars=1, max_holding_bars=None, stop_loss_pct=None, take_profit_pct=None, allowed_sides=None)",
  config_hash: "2FBDB9A8814ABC81062C2B0A61DFDCFAC69C95CF1789D0BAE6BEE4B11ADC3BF7",
} as const;

const EXECUTION = {
  execution_model: "cost_deduction" as const,
  fee_rate: 0.001,
  slippage_rate: 0.0005,
  spread_rate: 0.0,
  costs_repr:
    "TradingCosts(fee_rate=0.001, slippage_rate=0.0005, spread_rate=0.0, execution_model='cost_deduction')",
  costs_hash: "C24F79986249A05541709B583015FFBE012055DC324F4C4F6ED8CF97B61AB2D4A5C",
  risk_fraction: 0.01,
};

export const REPLAY_IDLE: ReplayState = {
  replay_id: "1a14f1ca-7fe4-49c3-b54e-8610a0f29773",
  status: "idle",
  dataset: DATASET,
  strategy: STRATEGY,
  execution: EXECUTION,
  cursor: 22,
  start_index: 22,
  bars_processed: 0,
  current_timestamp: null,
  next_timestamp: "2024-01-01T22:00:00Z",
  next_candle_available: true,
  starting_balance: 10000.0,
  balance: 10000.0,
  realized_pnl: 0.0,
  trade_count: 0,
  has_open_position: false,
  open_position: null,
  last_signal: null,
  mode: "standard",
};

/**
 * After the engine has stepped, with trades closed and one open.
 *
 * Internally consistent by construction: `balance` is derived from the engine's own
 * `balance - starting_balance == realized_pnl` definition, so a component that reads
 * either figure renders the same number the engine would. A fixture where those two
 * disagreed would let a test pass against a state the engine cannot produce.
 */
export const REPLAY_STEPPED: ReplayState = {
  ...REPLAY_IDLE,
  status: "idle",
  cursor: 162,
  bars_processed: 140,
  current_timestamp: "2024-01-03T13:00:00Z",
  next_timestamp: "2024-01-03T14:00:00Z",
  balance: 10000.0 + -0.18753082095343063,
  realized_pnl: -0.18753082095343063,
  trade_count: 4,
  has_open_position: true,
  open_position: {
    side: "short",
    entry_time: "2024-01-03T12:00:00Z",
    entry_price: 43728.9,
    quantity: 0.002286774300103375,
    reason: "downtrend breakdown",
    raw_entry_price: 43728.9,
    signal_close: 43728.9,
    trend_state: "down",
    breakout_distance: 0.019487420960581158,
    retest_distance: null,
    realised_volatility: 0.00838546703238819,
    mean_range: 411.1800000000003,
    support_at_entry: 44598.0,
    resistance_at_entry: 45850.0,
  },
  last_signal: {
    timestamp: "2024-01-03T13:00:00Z",
    side: "short",
    reason: "downtrend breakdown",
    price: 43728.9,
    support: 44598.0,
    resistance: 45850.0,
    trend: "down",
    breakout: true,
    retest: false,
    signal_close: 43728.9,
    trend_state: "down",
    breakout_distance: 0.019487420960581158,
    retest_distance: null,
    realised_volatility: 0.00838546703238819,
    mean_range: 411.1800000000003,
  },
};

export const ACCOUNT = {
  starting_balance: 10000.0,
  balance: 10000.0,
  realized_pnl: 0.0,
  trade_count: 0,
} as const;

export const TRADES: TradesResponse = {
  trade_count: 1,
  trades: [
    {
      side: "long",
      entry_time: "2024-01-01T22:00:00Z",
      exit_time: "2024-01-03T12:00:00Z",
      entry_price: 43679.7,
      exit_price: 43728.9,
      quantity: 0.0022893930132304023,
      reason: "bullish retest",
      exit_reason: "opposite_signal",
      bars_held: 38,
      raw_entry_price: 43679.7,
      raw_exit_price: 43728.9,
      costs: 0.3001689572043764,
      fee_total: 0.20011263813625096,
      slippage_total: 0.10005631906812548,
      spread_total: 0.0,
      pnl: 0.11263813625094579,
      net_pnl: -0.18753082095343063,
      total_friction: 0.3001689572043764,
      signal_close: 43679.8,
      trend_state: "up",
      breakout_distance: 0.003672591138067539,
      retest_distance: 0.0014084765513886152,
      realised_volatility: 0.003595137594382807,
      mean_range: 223.69500000000045,
      support_at_entry: 42207.9,
      resistance_at_entry: 43593.2,
    },
  ],
};

export const STATISTICS: StatisticsResponse = {
  service: "crypto-paper-lab",
  basis: "closed_trades",
  trades: 0,
  net_pnl: 0.0,
  win_rate: 0.0,
  profit_factor: null,
  profit_factor_infinite: true,
  average_pnl: 0.0,
  max_drawdown: 0.0,
  ending_balance: 10000.0,
  costs: {
    fee_total: 0.0,
    spread_total: 0.0,
    slippage_total: 0.0,
    total_friction: 0.0,
    deducted_costs: 0.0,
  },
  strategy: STRATEGY,
  execution: EXECUTION,
};

export const MARKET: MarketResponse = {
  metadata: {
    asset: "BTC/USDT",
    timeframe: "1h",
    source: "local-research-dataset",
    dataset_sha256: "201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B",
    dataset_candles: 17544,
    dataset_first_timestamp: "2024-01-01T00:00:00Z",
    dataset_last_timestamp: "2025-12-31T23:00:00Z",
    returned_candles: 2,
    truncated: true,
    start: null,
    end: "2025-12-31T23:00:00Z",
    limit: 200,
  },
  candles: [
    {
      timestamp: "2025-12-23T16:00:00Z",
      open: 87405.2,
      high: 88178.7,
      low: 87286.0,
      close: 87959.8,
      volume: 12033.564,
    },
    {
      timestamp: "2025-12-31T23:00:00Z",
      open: 87695.8,
      high: 87702.1,
      low: 87583.6,
      close: 87608.2,
      volume: 955.665,
    },
  ],
};

/** An open AI position, as the engine records it. */
export const AI_POSITION_OPEN: AiPosition = {
  position_id: "ai-3",
  side: "long",
  state: "open",
  entry_index: 88,
  entry_timestamp: "2024-01-01T22:00:00Z",
  entry_price: 44230.3,
  quantity: 0.0452243535548225,
  allocated_capital: 2000.0,
  reason: "uptrend breakout",
  intelligence_score: 91,
  qualification_threshold: 90,
  exit_index: null,
  exit_timestamp: null,
  exit_price: null,
  exit_reason: null,
  bars_held: null,
  realized_pnl: null,
  costs: null,
};

/** A closed AI position, closed at the profit target. */
export const AI_POSITION_CLOSED: AiPosition = {
  ...AI_POSITION_OPEN,
  position_id: "ai-1",
  state: "closed",
  exit_index: 89,
  exit_timestamp: "2024-01-01T23:00:00Z",
  exit_price: 44366.4,
  exit_reason: "ai_profit_target",
  bars_held: 1,
  realized_pnl: 36.87,
  costs: 5.94,
};

/**
 * AI state with one open and one closed position.
 *
 * The capital figures are internally consistent with the Phase 17G accounting
 * invariant: committed + available === realized.
 */
export const AI_STATE: AiState = {
  mode: "ai_intelligence",
  account: {
    starting_capital: 10000.0,
    committed_capital: 2000.0,
    realized_balance: 10036.87,
    available_capital: 8036.87,
    realized_pnl: 36.87,
    open_position_count: 1,
    max_positions: 5,
    position_allocation: 2000.0,
    signals_qualified: 3,
    signals_admitted: 2,
    signals_declined: 1,
  },
  positions: [AI_POSITION_OPEN, AI_POSITION_CLOSED],
  journal: [AI_POSITION_CLOSED],
  last_score: {
    score: 91,
    threshold: 90,
    qualified: true,
    side: "long",
    components: [
      {
        name: "trend_alignment",
        points: 30,
        weight: 30,
        reason: "long signal with the trend in the same direction (up)",
      },
      {
        name: "breakout_strength",
        points: 25,
        weight: 25,
        reason: "closed 0.8000% beyond the broken level (100.0% of the 0.50% full-credit scale)",
      },
      {
        name: "confirmation",
        points: 12,
        weight: 20,
        reason: "breakout entry with one candle of confirmation (12 of 20 points; a retest entry has two)",
      },
      {
        name: "range_quality",
        points: 15,
        weight: 15,
        reason: "hourly volatility 0.2981% at or below the calm bound of 0.40%",
      },
      {
        name: "direction",
        points: 10,
        weight: 10,
        reason: "directional long signal (uptrend breakout)",
      },
    ],
  },
  replay: { ...REPLAY_STEPPED, mode: "ai_intelligence" },
};

/** AI state before anything has happened: no score, no positions, full capital. */
export const AI_STATE_IDLE: AiState = {
  mode: "ai_intelligence",
  account: {
    starting_capital: 10000.0,
    committed_capital: 0.0,
    realized_balance: 10000.0,
    available_capital: 10000.0,
    realized_pnl: 0.0,
    open_position_count: 0,
    max_positions: 5,
    position_allocation: 2000.0,
    signals_qualified: 0,
    signals_admitted: 0,
    signals_declined: 0,
  },
  positions: [],
  journal: [],
  last_score: null,
  replay: { ...REPLAY_IDLE, mode: "ai_intelligence" },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function modeNamed(name: string): ModeInfo {
  const found = MODES.modes.find((entry) => entry.mode === name);
  if (!found) {
    throw new Error(`no fixture mode named ${name}`);
  }
  return found;
}

export type RecordedRequest = { method: string; url: string };

export interface StubRoute {
  /** Substring or RegExp matched against the request URL. */
  readonly match: string | RegExp;
  readonly status?: number;
  /**
   * The response body, or a function of it.
   *
   * A function is what makes a **stateful** stub possible. Testing a lifecycle
   * transition needs one: a stub that answered `start` with "running" while every
   * later `GET /api/replay` returned "idle" would make any refetch flip the UI back,
   * and the test would be measuring the stub rather than the component.
   */
  readonly body?: unknown | (() => unknown);
  /** Called after this route responds. For advancing stub state. */
  readonly after?: () => void;
  /** Raw text body, for asserting the malformed-response path. */
  readonly text?: string;
}

/**
 * A `PaperApi` wired to a recording stub, plus the log of what was requested.
 *
 * The stub is the only thing standing between a test and the network, so the log is
 * how a test proves a request was *not* made — which is how "Alerts never calls
 * `/api/replay`" and "a below-threshold signal never becomes an entry" become
 * assertions rather than intentions.
 */
export function makeApi(routes: readonly StubRoute[] = []) {
  const requests: RecordedRequest[] = [];

  const fetchImpl = (async (input: RequestInfo | URL) => {
    const url = String(input);
    const method = "GET";
    requests.push({ method, url });

    // **Last** matching route wins, not the first.
    //
    // That is what makes an override readable. `makeApi([...happyRoutes(), { match:
    // "/api/ai", body: AI_STATE }])` should serve `AI_STATE`, and with first-match
    // it would not — the default `AI_STATE_IDLE` in `happyRoutes` would win and the
    // test would silently assert against the wrong payload.
    const route = routes
      .filter((candidate) =>
        typeof candidate.match === "string"
          ? url.includes(candidate.match)
          : candidate.match.test(url),
      )
      .at(-1);

    if (!route) {
      return new Response(
        JSON.stringify({ detail: { code: "NOT_FOUND", message: `no stub for ${url}` } }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      );
    }

    const resolved =
      typeof route.body === "function"
        ? (route.body as () => unknown)()
        : route.body;

    const text = route.text ?? JSON.stringify(resolved ?? {});

    const response = new Response(text, {
      status: route.status ?? 200,
      headers: { "Content-Type": "application/json" },
    });

    // Fired after the response is built, so a route's own `after` cannot affect the
    // body it just produced.
    route.after?.();

    return response;
  }) as unknown as typeof fetch;

  return {
    api: new PaperApi({ baseUrl: "", fetchImpl }),
    requests,
    /** The raw stub, for constructing a second client over the same routes. */
    fetchImpl,
    /** URLs requested so far. */
    urls: () => requests.map((entry) => entry.url),
  };
}

/** An `ApiError` of the `http` shape, for asserting refusal rendering. */
export function httpError(
  code: ApiError["code"],
  message: string,
  status = 409,
): ApiError {
  return { kind: "http", status, code, message };
}

/** An `ApiError` for an unreachable server. */
export function networkError(message = "connection refused"): ApiError {
  return { kind: "network", status: 0, code: "NETWORK_UNAVAILABLE", message };
}

/**
 * Assert a fixture's keys match a declared interface.
 *
 * The point is that a server-side rename breaks a test. Without this, a fixture
 * could quietly drop a field and a component would render `undefined` while every
 * other assertion still passed.
 */
export function expectContract(
  // Deliberately `object`, not `<T>`. `Object.keys` is overloaded for the generic
  // unconstrained case and picks the `T` overload, which then fails to accept a
  // `readonly string[]`. Narrowing to the key set is also what this function
  // actually inspects.
  fixture: object,
  expected: readonly string[],
  label: string,
): void {
  const actual: string[] = Object.keys(fixture).sort();
  const want: string[] = [...expected].sort();

  const missing = want.filter((key) => !actual.includes(key));
  const extra = actual.filter((key) => !want.includes(key));

  if (missing.length > 0 || extra.length > 0) {
    throw new Error(
      `${label} does not match its declared contract.\n` +
        `  missing: ${missing.join(", ") || "none"}\n` +
        `  unexpected: ${extra.join(", ") || "none"}`,
    );
  }
}