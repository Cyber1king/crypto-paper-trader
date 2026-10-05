/**
 * API client tests (Phase 18K groups 1 and 2).
 *
 * Covers success for every endpoint the dashboard uses, and — more importantly —
 * that every documented failure shape becomes a typed error rather than a
 * fabricated value. A client that returned `0` on failure would pass the success
 * tests and quietly lie in production.
 */

import { describe, expect, it } from "vitest";

import {
  PaperApi,
  describeError,
  isApiError,
  isControllableMode,
  isLifecycleRefusal,
  isModeUnavailable,
  isObservationOnlyMode,
  setDefaultApi,
} from "@/lib/api";
import {
  ACCOUNT,
  AI_STATE,
  AI_STATE_IDLE,
  HEALTH,
  MARKET,
  MODES,
  REPLAY_IDLE,
  REPLAY_STEPPED,
  STATISTICS,
  TRADES,
  expectContract,
  httpError,
  makeApi,
  networkError,
} from "./fixtures";

// ---------------------------------------------------------------------------
// 1. success
// ---------------------------------------------------------------------------

describe("PaperApi: successful responses", () => {
  it("reads health", async () => {
    const { api } = makeApi([{ match: "/healthz", body: HEALTH }]);

    await expect(api.getHealth()).resolves.toEqual(HEALTH);
  });

  it("reads the mode list", async () => {
    const { api } = makeApi([{ match: "/api/modes", body: MODES }]);

    const modes = await api.getModes();

    expect(modes.default_mode).toBe("standard");
    expect(modes.modes).toHaveLength(6);
    expect(modes.modes.map((m) => m.mode)).toContain("alerts");
  });

  it("passes the mode as a query parameter on the replay route", async () => {
    const { api, urls } = makeApi([
      { match: "/api/replay", body: REPLAY_IDLE },
    ]);

    await api.getReplay("ai_intelligence");

    expect(urls()[0]).toBe("/api/replay?mode=ai_intelligence");
  });

  it("omits the mode parameter entirely when none is given", async () => {
    const { api, urls } = makeApi([
      { match: "/api/replay", body: REPLAY_IDLE },
    ]);

    await api.getReplay();

    expect(urls()[0]).toBe("/api/replay");
  });

  it("sends step count and mode together", async () => {
    const { api, urls } = makeApi([
      { match: "/api/replay/step", body: REPLAY_STEPPED },
    ]);

    const state = await api.stepReplay("standard", 250);

    expect(urls()[0]).toBe("/api/replay/step?mode=standard&count=250");
    expect(state.trade_count).toBe(4);
  });

  it("omits the count so the server's own default of one applies", async () => {
    const { api, urls } = makeApi([
      { match: "/api/replay/step", body: REPLAY_STEPPED },
    ]);

    await api.stepReplay("standard");

    // `count` defaults to 1 on the server (`app.py`), so sending nothing is both
    // correct and keeps the client's default and the engine's from drifting apart.
    expect(urls()[0]).toBe("/api/replay/step?mode=standard");
  });

  it("omits interval_ms when starting without one", async () => {
    const { api, urls } = makeApi([
      { match: "/api/replay/start", body: REPLAY_IDLE },
    ]);

    await api.startReplay("standard");

    expect(urls()[0]).toBe("/api/replay/start?mode=standard");
  });

  it("sends interval_ms when one is given", async () => {
    const { api, urls } = makeApi([
      { match: "/api/replay/start", body: { ...REPLAY_IDLE, status: "running" } },
    ]);

    const state = await api.startReplay("standard", 500);

    expect(urls()[0]).toBe("/api/replay/start?mode=standard&interval_ms=500");
    expect(state.status).toBe("running");
  });

  it("pauses and resets without inventing parameters", async () => {
    const { api, urls } = makeApi([
      { match: "/api/replay/pause", body: REPLAY_IDLE },
      { match: "/api/replay/reset", body: REPLAY_IDLE },
    ]);

    await api.pauseReplay("standard");
    await api.resetReplay("standard");

    expect(urls()).toEqual([
      "/api/replay/pause?mode=standard",
      "/api/replay/reset?mode=standard",
    ]);
  });

  it("reads AI state, and sends no mode parameter", async () => {
    const { api, urls } = makeApi([{ match: "/api/ai", body: AI_STATE }]);

    const ai = await api.getAiState();

    expect(urls()[0]).toBe("/api/ai");
    expect(ai.account.starting_capital).toBe(10000);
    expect(ai.last_score?.score).toBe(91);
  });

  it("reads market candles and forwards the window", async () => {
    const { api, urls } = makeApi([{ match: "/api/market", body: MARKET }]);

    const market = await api.getMarket({ limit: 200, end: "2025-12-31T23:00:00Z" });

    expect(urls()[0]).toBe("/api/market?limit=200&end=2025-12-31T23%3A00%3A00Z");
    expect(market.candles).toHaveLength(2);
    expect(market.metadata.source).toBe("local-research-dataset");
  });

  it("reads the Standard projections", async () => {
    const { api } = makeApi([
      { match: "/api/account", body: ACCOUNT },
      { match: "/api/trades", body: TRADES },
      { match: "/api/statistics", body: STATISTICS },
    ]);

    await expect(api.getAccount()).resolves.toEqual(ACCOUNT);
    await expect(api.getTrades()).resolves.toEqual(TRADES);
    await expect(api.getStatistics()).resolves.toEqual(STATISTICS);
  });

  it("honours a configured base URL", async () => {
    const stub = makeApi([{ match: "/api/modes", body: MODES }]);
    const api = new PaperApi({
      baseUrl: "http://127.0.0.1:8000/",
      fetchImpl: stub.fetchImpl,
    });

    await api.getModes();

    expect(stub.urls()[0]).toBe("http://127.0.0.1:8000/api/modes");
  });
});

// ---------------------------------------------------------------------------
// 1b. the declared contracts match the captured responses
// ---------------------------------------------------------------------------

describe("PaperApi: fixtures match the declared contracts", () => {
  it("the replay state key set is exactly what the interface declares", () => {
    expectContract(
      REPLAY_IDLE,
      [
        "replay_id", "status", "dataset", "strategy", "execution", "cursor",
        "start_index", "bars_processed", "current_timestamp", "next_timestamp",
        "next_candle_available", "starting_balance", "balance", "realized_pnl",
        "trade_count", "has_open_position", "open_position", "last_signal", "mode",
      ],
      "ReplayState",
    );
  });

  it("the AI state key set is exactly what the interface declares", () => {
    expectContract(
      AI_STATE,
      ["mode", "account", "positions", "journal", "last_score", "replay"],
      "AiState",
    );
  });

  it("the AI account key set is exactly what the interface declares", () => {
    expectContract(
      AI_STATE.account,
      [
        "starting_capital", "committed_capital", "realized_balance",
        "available_capital", "realized_pnl", "open_position_count",
        "max_positions", "position_allocation", "signals_qualified",
        "signals_admitted", "signals_declined",
      ],
      "AiAccount",
    );
  });

  it("the modes key set is exactly what the interface declares", () => {
    expectContract(MODES.modes[0], [
      "mode", "label", "supports_execution", "available", "note", "policy",
    ], "ModeInfo");
  });
});

// ---------------------------------------------------------------------------
// 2. error handling
// ---------------------------------------------------------------------------

describe("PaperApi: error handling", () => {
  it("turns a typed engine error into a typed ApiError", async () => {
    const { api } = makeApi([
      {
        match: "/api/replay",
        status: 409,
        body: {
          detail: {
            code: "POSITION_OPEN",
            message: "cannot reset while a paper position is open",
          },
        },
      },
    ]);

    await expect(api.resetReplay("standard")).rejects.toMatchObject({
      kind: "http",
      status: 409,
      code: "POSITION_OPEN",
      message: "cannot reset while a paper position is open",
    });
  });

  it("handles an unknown mode as 422 INVALID_MODE", async () => {
    const { api } = makeApi([
      {
        match: "/api/replay",
        status: 422,
        body: { detail: { code: "INVALID_MODE", message: "unknown mode 'nope'" } },
      },
    ]);

    await expect(api.getReplay("nope")).rejects.toMatchObject({
      status: 422,
      code: "INVALID_MODE",
    });
  });

  it("handles a reserved or brokerless mode as 409 MODE_NOT_AVAILABLE", async () => {
    const { api } = makeApi([
      {
        match: "/api/replay",
        status: 409,
        body: {
          detail: {
            code: "MODE_NOT_AVAILABLE",
            message: "mode 'alerts' has no paper execution session",
          },
        },
      },
    ]);

    const error = await api.getReplay("alerts").catch((e) => e);

    expect(isModeUnavailable(error)).toBe(true);
    expect(error.message).toContain("alerts");
  });

  it("handles the array-shaped FastAPI validation body", async () => {
    const { api } = makeApi([
      {
        match: "/api/replay/step",
        status: 422,
        body: {
          detail: [
            {
              type: "greater_than_equal",
              loc: ["query", "count"],
              msg: "Input should be greater than or equal to 1",
              input: "0",
            },
          ],
        },
      },
    ]);

    const error = await api.stepReplay("standard", 0).catch((e) => e);

    expect(error.code).toBe("VALIDATION_ERROR");
    expect(error.message).toContain("greater than or equal to 1");
  });

  it("handles the bare-string 404 body a router produces", async () => {
    const { api } = makeApi([
      { match: "/api/replay", status: 404, body: { detail: "Not Found" } },
    ]);

    const error = await api.getReplay("alerts").catch((e) => e);

    // `detail` here is a string, not the `{code, message}` object, so this asserts
    // the third body shape is handled rather than coerced.
    expect(error).toMatchObject({ status: 404, code: "NOT_FOUND" });
    expect(error.message).toBe("Not Found");
  });

  it("handles a 400 INVALID_INTERVAL", async () => {
    const { api } = makeApi([
      {
        match: "/api/replay/start",
        status: 400,
        body: {
          detail: {
            code: "INVALID_INTERVAL",
            message: "interval_ms must be between 100 and 60000, got 1",
          },
        },
      },
    ]);

    const error = await api.startReplay("standard", 1).catch((e) => e);

    expect(error.code).toBe("INVALID_INTERVAL");
    expect(isLifecycleRefusal(error)).toBe(false);
  });

  it("recognises a lifecycle refusal", async () => {
    expect(
      isLifecycleRefusal(httpError("REPLAY_FINISHED", "finished")),
    ).toBe(true);
    expect(isLifecycleRefusal(httpError("POSITION_OPEN", "open"))).toBe(true);
    expect(isLifecycleRefusal(networkError())).toBe(false);
  });

  it("reports an unreachable server as NETWORK_UNAVAILABLE, never as data", async () => {
    const fetchImpl = (async () => {
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;
    const api = new PaperApi({ fetchImpl });

    const error = await api.getReplay("standard").catch((e) => e);

    expect(error).toMatchObject({
      kind: "network",
      status: 0,
      code: "NETWORK_UNAVAILABLE",
    });
    expect(error.message).toContain("Failed to fetch");
  });

  it("never resolves a failed request with a default value", async () => {
    const { api } = makeApi([
      { match: "/api/ai", status: 500, body: {} },
    ]);

    // The dangerous failure mode for this project: a client that answers with an
    // empty object on error would render a $0 balance that looks real.
    const result = await api.getAiState().then(
      (value) => ({ resolved: value }),
      (error) => ({ rejected: error }),
    );

    expect("resolved" in result).toBe(false);
    expect("rejected" in result).toBe(true);
  });

  it("reports a non-JSON body as INVALID_RESPONSE", async () => {
    const { api } = makeApi([
      { match: "/api/ai", status: 200, text: "<html>not json</html>" },
    ]);

    const error = await api.getAiState().catch((e) => e);

    expect(error).toMatchObject({ code: "INVALID_RESPONSE" });
    expect(error.kind).toBe("malformed");
  });

  it("reports an empty body as INVALID_RESPONSE", async () => {
    const { api } = makeApi([{ match: "/api/ai", status: 200, text: "" }]);

    await expect(api.getAiState()).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
    });
  });

  it("falls back to a status-derived message when the body carries none", async () => {
    const { api } = makeApi([{ match: "/api/ai", status: 502, body: {} }]);

    const error = await api.getAiState().catch((e) => e);

    expect(error.code).toBe("HTTP_ERROR");
    expect(error.message).toContain("502");
  });

  it("isApiError discriminates the three kinds", () => {
    expect(isApiError(httpError("POSITION_OPEN", "x"))).toBe(true);
    expect(isApiError(networkError())).toBe(true);
    expect(isApiError(new Error("not ours"))).toBe(false);
    expect(isApiError(null)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// mode capability predicates
// ---------------------------------------------------------------------------

describe("mode capability predicates", () => {
  it("treats Standard and AI as controllable", () => {
    for (const mode of MODES.modes) {
      const expected =
        mode.available && mode.supports_execution && mode.mode !== "alerts";
      expect(isControllableMode(mode)).toBe(
        mode.available && mode.supports_execution,
      );
      expect(isControllableMode(mode)).toBe(expected);
    }
  });

  it("treats Alerts as observation-only, never controllable", () => {
    const alerts = MODES.modes.find((m) => m.mode === "alerts")!;

    expect(isObservationOnlyMode(alerts)).toBe(true);
    expect(isControllableMode(alerts)).toBe(false);
  });

  it("treats the three reserved modes as neither", () => {
    for (const name of ["daily_target", "manual", "high_risk"]) {
      const mode = MODES.modes.find((m) => m.mode === name)!;

      expect(mode.available).toBe(false);
      expect(isControllableMode(mode)).toBe(false);
      expect(isObservationOnlyMode(mode)).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
// error descriptions
// ---------------------------------------------------------------------------

describe("describeError", () => {
  it("says the service is unavailable rather than showing zeroes", () => {
    expect(describeError(networkError())).toContain("unavailable");
  });

  it("passes the server's own words through for a mode refusal", () => {
    expect(describeError(httpError("MODE_NOT_AVAILABLE", "mode is reserved"))).toBe(
      "mode is reserved",
    );
  });

  it("has a distinct message for an open position", () => {
    expect(describeError(httpError("POSITION_OPEN", ""))).toContain("reset");
  });

  it("falls back to something readable for an unknown code", () => {
    expect(describeError(httpError("HTTP_ERROR", ""))).toBe(
      "The paper API returned an error.",
    );
  });
});

// ---------------------------------------------------------------------------
// default-client lifecycle
// ---------------------------------------------------------------------------

describe("default client", () => {
  it("can be replaced and cleared, so a test cannot leak into the next", () => {
    const { api } = makeApi([{ match: "/api/modes", body: MODES }]);

    setDefaultApi(api);
    setDefaultApi(null);
  });

  it("creates a usable client when none was installed", async () => {
    setDefaultApi(null);

    const { getDefaultApi } = await import("@/lib/api");
    const client = getDefaultApi();

    expect(client).toBeInstanceOf(PaperApi);
  });
});

describe("AI fixtures reflect the engine's accounting invariant", () => {
  it("committed plus available equals the realised balance", () => {
    for (const state of [AI_STATE, AI_STATE_IDLE]) {
      const { account } = state;

      expect(account.committed_capital + account.available_capital).toBeCloseTo(
        account.realized_balance,
        6,
      );
      expect(account.realized_balance - account.starting_capital).toBeCloseTo(
        account.realized_pnl,
        6,
      );
    }
  });

  it("open position count matches the open positions listed", () => {
    for (const state of [AI_STATE, AI_STATE_IDLE]) {
      const open = state.positions.filter((p) => p.state === "open");
      expect(open.length).toBe(state.account.open_position_count);
    }
  });

  it("never carries an unrealised P&L field", () => {
    // The engine has no mark price, so any such field would have to be invented.
    for (const position of [...AI_STATE.positions, ...AI_STATE.journal]) {
      expect(Object.keys(position)).not.toContain("unrealized_pnl");
      expect(Object.keys(position)).not.toContain("equity");
    }
  });
});