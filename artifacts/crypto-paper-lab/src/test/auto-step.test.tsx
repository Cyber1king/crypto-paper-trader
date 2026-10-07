/**
 * Auto-step tests (Phase 20).
 *
 * The Phase 19 audit found that `POST /api/replay/start` sets `status: "running"`
 * and the replay then never moves, because the engine runs no background worker by
 * design. These cover the client-side loop that closes that gap.
 *
 * ## Two harness approaches that did not work, and why
 *
 * 1. **Capturing `globalThis.setInterval` by hand.** A spy recorded zero timers
 *    while step requests still arrived, so the patch never reached the hook. Not
 *    worth debugging a global the test cannot reliably own.
 * 2. **`vi.useFakeTimers()` combined with `waitFor`.** `@testing-library`'s `waitFor`
 *    builds its retry loop on the same faked clock, so it never advances and every
 *    test times out before its first assertion.
 *
 * So: fake timers for the clock, and **no `waitFor`** — {@link settle} instead. That
 * satisfies both. React Query resolves on promises rather than timers, so advancing
 * by zero and flushing microtasks is enough to settle a render, and
 * `vi.getTimerCount()` gives an accurate count of live intervals, which is what the
 * duplicate-timer assertions need.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";

import { Dashboard } from "@/pages/dashboard";
import { PaperApi, setDefaultApi, type ReplayState } from "@/lib/api";
import {
  AUTO_STEP_BARS,
  AUTO_STEP_INTERVAL_MS,
  RUNNING_POLL_INTERVAL_MS,
  queryKeys,
} from "@/lib/hooks";
import {
  ACCOUNT,
  AI_STATE_IDLE,
  HEALTH,
  MARKET,
  MODES,
  REPLAY_IDLE,
  STATISTICS,
  TRADES,
  httpError,
  makeApi,
  type StubRoute,
} from "./fixtures";

/** A `running` state, so the loop's precondition holds without a Start click. */
function running(over: Partial<ReplayState> = {}): ReplayState {
  return { ...REPLAY_IDLE, status: "running", ...over };
}

/**
 * Routes for a fully available service, with the replay lifecycle stateful.
 *
 * `step` and the bare replay GET must both read the *same* `state` source. If the
 * GET returned a constant while the step advanced, the running poll would refetch
 * the constant and overwrite the stepped value — a stub artifact that looks exactly
 * like a loop that failed to write its result.
 */
function routes(state: () => ReplayState, step?: StubRoute): StubRoute[] {
  return [
    { match: "/healthz", body: HEALTH },
    { match: "/api/modes", body: MODES },
    { match: "/api/ai", body: AI_STATE_IDLE },
    { match: "/api/market", body: MARKET },
    step ?? { match: "/api/replay/step", body: state },
    // Start always answers `running`, independent of the read route. Tying it to
    // `state` would make a Start click on an idle replay answer "idle", which is not
    // the server's contract and hides the transition under test.
    { match: "/api/replay/start", body: running() },
    { match: "/api/replay/pause", body: { ...REPLAY_IDLE, status: "paused" } },
    { match: "/api/replay/reset", body: REPLAY_IDLE },
    { match: /^\/api\/replay(\?|$)/, body: state },
    { match: "/api/statistics", body: STATISTICS },
    { match: "/api/trades", body: TRADES },
    { match: "/api/position", body: { has_position: false, position: null } },
    { match: "/api/account", body: ACCOUNT },
  ];
}

/**
 * Let pending promises settle without touching `waitFor`.
 *
 * React Query resolves through microtasks, so zero-advance plus a microtask flush is
 * sufficient, and it keeps the faked clock still for any interval under test.
 */
async function settle(rounds = 12): Promise<void> {
  for (let i = 0; i < rounds; i += 1) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
  }
}

/**
 * Advance the clock by `count` auto-step periods, then settle.
 *
 * Whether the first period fires depends on when the loop armed, so tests are
 * written against measured request counts rather than periods advanced.
 *
 * The measured behaviour: on initial load the interval is registered by an effect
 * whose gate (the replay status) only reaches the cache once react-query settles the
 * replay read, which happens *during* the first advance. Six consecutive advances
 * after settling yielded 0, 1, 2, 3, 4, 5 requests — so the first is consumed
 * arming the loop. After an explicit Start click the status is already in the cache,
 * the loop arms within that click, and no period is lost.
 *
 * {@link periodsFor} encodes that difference explicitly so no assertion hides a
 * bare `+ 1`.
 */
async function tick(count = 1): Promise<void> {
  // One period per `act`, never several in one advance.
  //
  // This is not a style preference. Advancing 3000ms in a single act fires the
  // interval three times before any of those requests resolves, so the in-flight
  // guard correctly declines the second and third — which is the overlap protection
  // working, but it makes a multi-period advance report one request instead of three.
  // Advancing period by period with a settle between gives each request time to
  // complete, which is the situation the guard is meant to permit.
  for (let i = 0; i < count; i += 1) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(AUTO_STEP_INTERVAL_MS);
    });
    await settle(6);
  }
}

/** Periods to advance for `count` requests, when the loop is not yet armed. */
function periodsFor(count: number): number {
  return count + 1;
}

function renderDashboard(stubRoutes: StubRoute[], api?: PaperApi) {
  const stub = api ? null : makeApi(stubRoutes);
  setDefaultApi(api ?? stub!.api);

  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });

  const utils = render(
    <QueryClientProvider client={client}>
      <Dashboard />
    </QueryClientProvider>,
  );

  return { ...utils, stub, client };
}

/** Mount the dashboard over a custom client, for stubs `makeApi` cannot express. */
function renderWithApi(api: PaperApi) {
  setDefaultApi(api);
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
  const utils = render(
    <QueryClientProvider client={client}>
      <Dashboard />
    </QueryClientProvider>,
  );
  return { ...utils, client };
}

function stepCalls(urls: readonly string[]): string[] {
  return urls.filter((url) => url.includes("/api/replay/step"));
}

/** The cursor the dashboard currently holds, from the query cache. */
function cachedCursor(
  client: QueryClient,
  mode = "standard",
): number | undefined {
  return client.getQueryData<ReplayState>(queryKeys.replay(mode))?.cursor;
}

/** Click a control by test id and let the mutation settle. */
async function press(testid: string): Promise<void> {
  await act(async () => {
    screen.getByTestId(testid).click();
    await Promise.resolve();
  });
  await settle();
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
});

describe("Phase 20: START advances the replay", () => {
  it("issues automatic step requests while the server reports running", async () => {
    const { stub } = renderDashboard(routes(() => running()));
    await settle();

    await tick(periodsFor(3));

    const steps = stepCalls(stub!.urls());

    expect(steps).toHaveLength(3);
    // One bar per tick, and the mode explicit on every request.
    expect(steps.every((url) => url.includes("mode=standard"))).toBe(true);
    expect(steps.every((url) => url.includes("count=1"))).toBe(true);
  });

  it("steps on the cadence the dashboard already polls at", () => {
    // If these diverge, the engine advances at one rate and the panel reporting it
    // re-reads at another, which reads as the UI skipping bars.
    expect(AUTO_STEP_INTERVAL_MS).toBe(RUNNING_POLL_INTERVAL_MS);
    expect(AUTO_STEP_BARS).toBe(1);
  });

  it("advances the cursor the engine reports, one bar per tick", async () => {
    // The engine's own answer is the only thing that can move this cursor, so a
    // rendered advance proves the loop read the response rather than counting ticks
    // itself. A frontend that incremented a local counter would pass a request-count
    // assertion and fail here.
    let cursor = 22;
    /** One shared engine cursor: a step advances it and every read reports it. */
    const engine = (): ReplayState => running({ cursor, bars_processed: cursor - 22 });
    const stepping: StubRoute = {
      match: "/api/replay/step",
      body: () => {
        cursor += 1;
        return engine();
      },
    };

    const { client } = renderDashboard(routes(engine, stepping));
    await settle();

    expect(cachedCursor(client)).toBe(22);

    // `periodsFor` absorbs the documented one-period arming offset, so each of these
    // asserts one further bar and nothing else.
    await tick(periodsFor(1));
    expect(cachedCursor(client)).toBe(23);

    await tick(2);
    expect(cachedCursor(client)).toBe(25);
  });

  it("does not step at all while the replay is idle", async () => {
    const { stub } = renderDashboard(routes(() => REPLAY_IDLE));
    await settle();

    await tick(4);

    // The strongest form of the guard: an idle dashboard must not touch the engine.
    expect(stepCalls(stub!.urls())).toHaveLength(0);
  });

  it("begins stepping only after Start is pressed", async () => {
    // Reads report `idle`, but a step taken while running reports `running`. Using
    // one shared state for both would make the first step answer "idle", and the loop
    // would correctly tear itself down — measuring the stub instead of the loop.
    const { stub } = renderDashboard(
      routes(() => REPLAY_IDLE, { match: "/api/replay/step", body: running }),
    );
    await settle();

    expect(stepCalls(stub!.urls())).toHaveLength(0);

    await press("control-start");
    expect(screen.getByTestId("replay-status").textContent?.toLowerCase()).toBe(
      "running",
    );

    // No offset needed after an explicit Start: the click put `running` in the cache
    // itself, so every subsequent period fires. Measured directly — advances after
    // the click produced 1, 2, 3, 4, 5 requests. The on-load case is different and is
    // what {@link periodsFor} covers.
    await tick(2);

    expect(stepCalls(stub!.urls())).toHaveLength(2);
  });
});

describe("Phase 20: stepping stops on every terminal status", () => {
  it("PAUSE stops automatic stepping", async () => {
    const { stub } = renderDashboard(routes(() => running()));
    await settle();

    await press("control-start");
    await tick(2);

    const whileRunning = stepCalls(stub!.urls()).length;
    expect(whileRunning).toBeGreaterThanOrEqual(1);

    await press("control-pause");
    expect(screen.getByTestId("replay-status").textContent?.toLowerCase()).toBe(
      "paused",
    );

    const afterPause = stepCalls(stub!.urls()).length;

    // Five more periods: a loop that survived the pause adds one per period.
    await tick(5);

    expect(stepCalls(stub!.urls()).length).toBe(afterPause);
  });

  it("FINISHED stops automatic stepping", async () => {
    const { stub } = renderDashboard(
      routes(() => running({ status: "finished" })),
    );
    await settle();

    await tick(4);

    // The replay is reported finished, so the loop must never have started.
    expect(stepCalls(stub!.urls())).toHaveLength(0);
  });

  it("RESET stops automatic stepping and returns to idle", async () => {
    const { stub } = renderDashboard(routes(() => running()));
    await settle();

    await press("control-start");
    await tick(2);
    expect(stepCalls(stub!.urls()).length).toBeGreaterThanOrEqual(1);

    await press("control-reset");
    expect(screen.getByTestId("replay-status").textContent?.toLowerCase()).toBe(
      "idle",
    );

    const afterReset = stepCalls(stub!.urls()).length;
    await tick(5);

    expect(stepCalls(stub!.urls()).length).toBe(afterReset);
  });

  it("REPLAY_FINISHED halts the loop instead of retrying forever", async () => {
    const { stub } = renderDashboard([
      ...routes(() => running()),
      {
        match: "/api/replay/step",
        status: 409,
        body: {
          detail: httpError(
            "REPLAY_FINISHED",
            "replay has reached the end of the dataset; reset it before starting again",
          ),
        },
      },
    ]);
    await settle();

    await press("control-start");
    await tick(6);

    // The dataset is exhausted, so no later step can succeed. Spinning would only
    // produce guaranteed 409s, so exactly one attempt is made.
    expect(stepCalls(stub!.urls())).toHaveLength(1);
  });
});

describe("Phase 20: no duplicate timers, no overlapping requests", () => {
  it("fires exactly one step request per period", async () => {
    const { stub } = renderDashboard(routes(() => running()));
    await settle();

    // This is the assertion that actually detects a duplicated loop. An earlier
    // version counted live timers with `vi.getTimerCount()`, which turned out to be
    // unusable: the total includes react-query's retry and gc timers plus React's
    // scheduler work, and those expire on their own during the test, so the number
    // fell from 11 to 5 across four ticks and asserted nothing about this code.
    //
    // Request counts have no such problem. One interval produces exactly one step
    // per period; two produce two. Each tick also re-renders, which is precisely
    // what would leak an extra loop if the effect were keyed on something unstable.
    await tick(periodsFor(1));
    expect(stepCalls(stub!.urls())).toHaveLength(1);

    await tick(3);
    expect(stepCalls(stub!.urls())).toHaveLength(4);
  });

  it("stops issuing steps once it leaves running", async () => {
    const { stub } = renderDashboard(routes(() => running()));
    await settle();

    await tick(periodsFor(2));
    expect(stepCalls(stub!.urls())).toHaveLength(2);

    await press("control-pause");

    // Both intervals on this page are gated on `running`, so leaving it must silence
    // the loop. Asserted by waiting and counting, not by inspecting timer internals.
    const afterPause = stepCalls(stub!.urls()).length;
    await tick(6);

    expect(stepCalls(stub!.urls()).length).toBe(afterPause);
  });

  it("does not overlap step requests while one is still pending", async () => {
    // A step whose response is withheld until the test releases it. Every period
    // that elapses during the hold must decline to issue a second request.
    let release: (() => void) | null = null;
    let held = false;
    const urls: string[] = [];

    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });

    const inner = makeApi(routes(() => running())).fetchImpl;

    const delayed: typeof fetch = (async (input: RequestInfo | URL) => {
      const url = String(input);
      urls.push(url);

      if (url.includes("/api/replay/step")) {
        held = true;
        await pending;
      }

      return inner(input);
    }) as typeof fetch;

    renderWithApi(new PaperApi({ baseUrl: "", fetchImpl: delayed }));
    await settle();

    await press("control-start");

    // Six periods pass while the first response is still outstanding.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(AUTO_STEP_INTERVAL_MS * 6);
    });

    expect(held).toBe(true);
    expect(stepCalls(urls)).toHaveLength(1);

    // Released, the loop must resume rather than stay wedged shut.
    await act(async () => {
      release?.();
      await Promise.resolve();
    });
    await tick(2);

    expect(stepCalls(urls).length).toBeGreaterThan(1);
  });
});

describe("Phase 20: manual STEP is unaffected", () => {
  it("still steps one batch while idle", async () => {
    const { stub } = renderDashboard(routes(() => REPLAY_IDLE));
    await settle();

    await press("control-step");

    expect(stepCalls(stub!.urls())).toHaveLength(1);
  });

  it("still steps one batch while paused", async () => {
    const { stub } = renderDashboard(
      routes(() => ({ ...REPLAY_IDLE, status: "paused" })),
    );
    await settle();

    await press("control-step");

    // Exactly one: paused must not also drive the loop.
    expect(stepCalls(stub!.urls())).toHaveLength(1);

    // And no loop is running to add more, checked by waiting rather than by an
    // absolute timer count.
    const afterManual = stepCalls(stub!.urls()).length;
    await tick(4);
    expect(stepCalls(stub!.urls()).length).toBe(afterManual);
  });

  it("still steps the configured batch size", async () => {
    const { stub } = renderDashboard(routes(() => REPLAY_IDLE));
    await settle();

    // Identified by its visible label; the input carries no test id.
    const input = screen.getByLabelText(/bars per step/i) as HTMLInputElement;

    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value",
      )?.set;
      setter?.call(input, "25");
      input.dispatchEvent(new Event("input", { bubbles: true }));
      await Promise.resolve();
    });

    await press("control-step");

    expect(stepCalls(stub!.urls())).toHaveLength(1);
    expect(stepCalls(stub!.urls())[0]).toContain("count=25");
  });
});

describe("Phase 20: mode safety", () => {
  it("Alerts never issues a step request", async () => {
    const { stub } = renderDashboard(routes(() => running()));
    await settle();

    await act(async () => {
      screen.getByTestId("mode-alerts").click();
      await Promise.resolve();
    });
    await settle();
    await tick(4);

    expect(stepCalls(stub!.urls())).toHaveLength(0);
    expect(stub!.urls().some((u) => u.includes("mode=alerts"))).toBe(false);
  });

  it("switching away from Standard stops Standard's loop", async () => {
    const { stub } = renderDashboard(routes(() => running()));
    await settle();

    await press("control-start");
    await tick(2);

    const beforeSwitch = stepCalls(stub!.urls()).length;
    expect(beforeSwitch).toBeGreaterThanOrEqual(1);

    await act(async () => {
      screen.getByTestId("mode-alerts").click();
      await Promise.resolve();
    });
    await settle();

    const afterSwitch = stepCalls(stub!.urls()).length;
    await tick(5);

    expect(stepCalls(stub!.urls()).length).toBe(afterSwitch);
  });

  it("a reserved mode issues no step request", async () => {
    const { stub } = renderDashboard(routes(() => running()));
    await settle();

    await act(async () => {
      screen.getByTestId("mode-high_risk").click();
      await Promise.resolve();
    });
    await settle();
    await tick(4);

    expect(stepCalls(stub!.urls())).toHaveLength(0);
  });
});
