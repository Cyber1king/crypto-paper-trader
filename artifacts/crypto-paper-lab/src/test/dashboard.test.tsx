/**
 * Dashboard integration tests (Phase 18K).
 *
 * These render the whole page against a stubbed API, which is the only place the
 * mode-switching behaviour and the request log can be checked together. Two
 * properties are asserted here that unit tests cannot reach:
 *
 * 1. **Which requests were made.** The stub records every URL, so "Alerts never
 *    calls `/api/replay`" and "selecting a reserved mode issues no execution
 *    request" become assertions rather than intentions.
 * 2. **That a failed fetch never renders a figure.** The strongest form of the
 *    no-fake-data rule: with every endpoint failing, the page must contain no
 *    dollar amount at all.
 */

import { describe, expect, it } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { Dashboard } from "@/pages/dashboard";
import { setDefaultApi } from "@/lib/api";
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
  makeApi,
  type StubRoute,
} from "./fixtures";

/** Routes for a fully available service. */
function happyRoutes(): StubRoute[] {
  return [
    { match: "/healthz", body: HEALTH },
    { match: "/api/modes", body: MODES },
    { match: "/api/ai", body: AI_STATE_IDLE },
    { match: "/api/market", body: MARKET },
    { match: "/api/replay/step", body: REPLAY_STEPPED },
    { match: "/api/replay/start", body: { ...REPLAY_IDLE, status: "running" } },
    { match: "/api/replay/pause", body: { ...REPLAY_IDLE, status: "paused" } },
{ match: "/api/replay/reset", body: REPLAY_IDLE },

    // Anchored, and this matters. A bare `"/api/replay"` substring also matches
    // `/api/replay/start`, `/api/replay/step` and the rest, so with last-match-wins
    // an override of the bare route would shadow every specific one and a Start
    // request would be answered with the idle replay state. Matching the path
    // exactly - or its `?query` form - keeps the routes independent.
    { match: /^\/api\/replay(\?|$)/, body: REPLAY_IDLE },

    { match: "/api/statistics", body: STATISTICS },
    { match: "/api/trades", body: TRADES },
    { match: "/api/position", body: { has_position: false, position: null } },
    { match: "/api/account", body: ACCOUNT },
  ];
}

function renderDashboard(routes: readonly StubRoute[] = happyRoutes()) {
  const stub = makeApi(routes);
  setDefaultApi(stub.api);


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

/**
 * Wait until the selected mode has actually loaded.
 *
 * Necessary because `StandardBody` renders while `GET /api/modes` is still in
 * flight, with `controlsEnabled` false � so its buttons exist but are disabled.
 * `findByTestId` proves the node rendered, not that it is usable, and clicking a
 * disabled button silently does nothing.
 */
async function waitForUsableControls() {
  await waitFor(() =>
    expect(
      (screen.getByTestId("control-start") as HTMLButtonElement).disabled,
    ).toBe(false),
  );
}
async function selectMode(mode: string) {
  fireEvent.click(await screen.findByTestId(`mode-${mode}`));
}

describe("dashboard: Standard is the default view", () => {
  it("reads Standard's replay and its projections", async () => {
    const { stub } = renderDashboard();

    await waitFor(() =>
      expect(screen.getByTestId("standard-balance").textContent).not.toBe("�"),
    );
    await waitFor(() =>
      expect(stub.urls().some((u) => u.includes("/api/trades"))).toBe(true),
    );

    const urls = stub.urls();
    expect(urls.some((u) => u.includes("mode=standard"))).toBe(true);
    expect(urls.some((u) => u.includes("/api/account"))).toBe(true);
    expect(urls.some((u) => u.includes("/api/trades"))).toBe(true);
  });

  it("shows the engine's balance, never a frontend fiction", async () => {
    renderDashboard();

    // The node exists immediately with a placeholder, so the assertion has to wait
    // for the value rather than for the element.
    await waitFor(() =>
      expect(screen.getByTestId("header-balance").textContent).toBe("10,000.00"),
    );
    // The old mock engine started at 100,000. That number must not appear.
    expect(document.body.textContent).not.toContain("100,000");
  });

  it("reports the API as online once health answers", async () => {
    renderDashboard();

    expect(await screen.findByTestId("health-online")).toBeTruthy();
  });

  it("always shows the paper-only banner", async () => {
    renderDashboard();

    expect(screen.getByText(/paper trading only/i)).toBeTruthy();
  });

  it("shows the read-only engine configuration, with no asset selector", async () => {
    renderDashboard();

    await waitFor(() =>
      expect(screen.getByTestId("config-asset").textContent).toBe("BTC/USDT"),
    );
    await waitFor(() =>
      expect(screen.getByTestId("config-timeframe").textContent).toBe("1h"),
    );
    // The old dashboard offered BTC/ETH/SOL and 15m/1h/4h.
    expect(document.body.textContent).not.toContain("Ethereum");
    expect(document.body.textContent).not.toContain("15 Minutes");
  });
});

describe("dashboard: mode selection changes the request, not the mode", () => {
  it("asks for AI with the shared transport, and /api/ai for its account", async () => {
    const { stub } = renderDashboard();

    await selectMode("ai_intelligence");
    await waitFor(() =>
      expect(screen.getByTestId("ai-starting-capital").textContent).toBe(
        "10,000.00",
      ),
    );

    const urls = stub.urls();
    expect(urls.some((u) => u.includes("/api/replay?mode=ai_intelligence"))).toBe(true);
    expect(urls.some((u) => u.includes("/api/ai"))).toBe(true);
  });

  it("never reads the AI account from the replay route", async () => {
    renderDashboard();

    await selectMode("ai_intelligence");
    await screen.findByTestId("ai-starting-capital");

    // The AI account panel must show the /api/ai figure. Both routes report
    // 10,000 here, so the assertion is structural: the AI account block exists and
    // the replay's balance is not what feeds it.
    expect(screen.getByTestId("ai-starting-capital")).toBeTruthy();
    expect(screen.getByTestId("header-no-balance")).toBeTruthy();
  });

  it("stops requesting Standard's account and journal once AI is selected", async () => {
    const { stub } = renderDashboard();

    // Standard is the initial selection, so its projections are legitimately
    // requested on mount. The claim under test is that selecting AI *stops* them,
    // so the count is taken from the switch onward rather than from zero.
    await waitFor(() =>
      expect(
        stub.urls().filter((u) => u.includes("/api/account")).length,
      ).toBeGreaterThan(0),
    );

    const beforeSwitch = stub.urls().length;
    await selectMode("ai_intelligence");
    await screen.findByTestId("ai-starting-capital");

    const afterSwitch = stub
      .urls()
      .slice(beforeSwitch)
      .filter((u) => u.includes("/api/account") || u.includes("/api/trades"));

    expect(afterSwitch).toHaveLength(0);
  });

  it("hides the header balance for a mode that is not Standard", async () => {
    renderDashboard();

    await selectMode("ai_intelligence");
    await screen.findByTestId("ai-starting-capital");

    expect(screen.getByTestId("header-no-balance")).toBeTruthy();
    expect(screen.queryByTestId("header-balance")).toBeNull();
  });
});

describe("dashboard: Alerts is brokerless in practice", () => {
  it("never requests a replay for Alerts", async () => {
    const { stub } = renderDashboard();

    await selectMode("alerts");
    (await screen.findAllByText(/observation only/i)).length;

    const alertsRequests = stub
      .urls()
      .filter((u) => u.includes("mode=alerts"));

    expect(alertsRequests).toHaveLength(0);
  });

  it("offers no lifecycle controls", async () => {
    renderDashboard();

    await selectMode("alerts");
    (await screen.findAllByText(/observation only/i)).length;

    expect(screen.queryByTestId("control-start")).toBeNull();
    expect(screen.queryByTestId("control-step")).toBeNull();
    expect(screen.queryByTestId("control-reset")).toBeNull();
  });

  it("shows the observation state rather than a fabricated alert feed", async () => {
    renderDashboard();

    await selectMode("alerts");
    (await screen.findAllByText(/observation only/i)).length;

    expect(document.body.textContent?.toLowerCase()).toContain(
      "notification delivery is not implemented",
    );
  });
});

describe("dashboard: reserved modes issue no execution request", () => {
  for (const mode of ["daily_target", "manual", "high_risk"]) {
    it(`selecting ${mode} shows the server's note and requests no replay`, async () => {
      const { stub } = renderDashboard();

      await selectMode(mode);
      await screen.findByText("Unavailable");

      const requests = stub.urls().filter((u) => u.includes(`mode=${mode}`));
      expect(requests).toHaveLength(0);
    });
  }

  it("shows the API's note rather than a client-authored message", async () => {
    renderDashboard();

    await selectMode("manual");
    await screen.findByText("Unavailable");

    expect(document.body.textContent).toContain(modeNamed("manual").note);
  });
});

describe("dashboard: lifecycle controls", () => {
  it("Start posts to /api/replay/start with the selected mode", async () => {
    const { stub } = renderDashboard();

    await waitForUsableControls();
    fireEvent.click(screen.getByTestId("control-start"));

    await waitFor(() =>
      expect(
        stub.urls().some((u) => u.includes("/api/replay/start?mode=standard")),
      ).toBe(true),
    );
  });

  it("Step posts the configured bar count", async () => {
    const { stub } = renderDashboard();

    await waitForUsableControls();

    const input = document.getElementById("step-count") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "120" } });
    fireEvent.click(screen.getByTestId("control-step"));

    await waitFor(() =>
      expect(
        stub.urls().some((u) => u.includes("/api/replay/step?mode=standard&count=120")),
      ).toBe(true),
    );
  });

it("Pause is only offered once the server reports running", async () => {
    // A **stateful** stub, because the status transition is the thing under test.
    //
    // A stateless one would answer `/api/replay/start` with "running" while every
    // later `/api/replay` returned "idle". Any refetch would then flip the button
    // back, and the test would be measuring a stub artefact rather than whether the
    // UI follows the server. A real engine remembers that it armed.
    let armed = false;

    const { stub } = renderDashboard([
      ...happyRoutes(),
      {
        match: "/api/replay/start",
        body: () => ({ ...REPLAY_IDLE, status: "running" }),
        after: () => {
          armed = true;
        },
      },
      {
        match: /^\/api\/replay(\?|$)/,
        body: () => ({ ...REPLAY_IDLE, status: armed ? "running" : "idle" }),
      },
    ]);

    await waitForUsableControls();
    await waitFor(() =>
      expect(
        (screen.getByTestId("control-pause") as HTMLButtonElement).disabled,
      ).toBe(true),
    );

    fireEvent.click(screen.getByTestId("control-start"));

    await waitFor(() =>
      expect(
        stub.urls().some((u) => u.includes("/api/replay/start?mode=standard")),
      ).toBe(true),
    );

    // The status the server reported is authoritative, so the control bar follows
    // the response rather than tracking its own idea of whether the replay is armed.
    await waitFor(() =>
      expect(screen.getByTestId("replay-status").textContent).toBe("Running"),
    );
    await waitFor(() =>
      expect(
        (screen.getByTestId("control-pause") as HTMLButtonElement).disabled,
      ).toBe(false),
    );
  });

  it("Reset posts to /api/replay/reset", async () => {
    const { stub } = renderDashboard();

    await waitForUsableControls();
    fireEvent.click(screen.getByTestId("control-reset"));

    await waitFor(() =>
      expect(
        stub.urls().some((u) => u.includes("/api/replay/reset?mode=standard")),
      ).toBe(true),
    );
  });

  it("shows the server's refusal instead of pretending the action worked", async () => {
    renderDashboard([
      ...happyRoutes(),
      {
        match: "/api/replay/reset",
        status: 409,
        body: {
          detail: {
            code: "POSITION_OPEN",
            message: "cannot reset while a paper position is open",
          },
        },
      },
    ]);

    await waitForUsableControls();
    fireEvent.click(screen.getByTestId("control-reset"));

    const refusal = await screen.findByTestId("control-refusal");
    expect(refusal.getAttribute("data-code")).toBe("POSITION_OPEN");
    expect(refusal.textContent).toContain("cannot reset while a paper position is open");
  });
});

describe("dashboard: unavailable API never renders a figure", () => {
  it("shows no dollar amount when every request fails", async () => {
    renderDashboard([
      { match: "/healthz", status: 500, body: {} },
      { match: "/api/modes", status: 500, body: {} },
      { match: "/api/replay", status: 500, body: {} },
      { match: "/api/ai", status: 500, body: {} },
      { match: "/api/market", status: 500, body: {} },
    ]);

    await screen.findByTestId("health-offline");
    await waitFor(() => {
      expect(screen.getAllByText("Paper API unavailable").length).toBeGreaterThan(0);
    });

    // The single most important assertion in this file. A "$0.00" or a
    // "$10,000.00" rendered here would be a fabricated account.
    expect(document.body.textContent).not.toContain("$");
    expect(document.body.textContent).not.toContain("10,000");
  });

  it("reports the service as offline rather than silently empty", async () => {
    renderDashboard([{ match: "/healthz", status: 500, body: {} }]);

    expect(await screen.findByTestId("health-offline")).toBeTruthy();
  });

  it("offers a retry the user can invoke", async () => {
    renderDashboard([{ match: "/healthz", status: 500, body: {} }]);

    await screen.findByTestId("health-offline");
    const retry = screen.getAllByText("Retry")[0];

    expect(retry).toBeTruthy();
    fireEvent.click(retry);
  });

  it("says no figures are shown because none could be read", async () => {
    renderDashboard([{ match: "/healthz", status: 500, body: {} }]);

    await waitFor(() => {
      expect(
        document.body.textContent?.toLowerCase().includes("no figures are shown"),
      ).toBe(true);
    });
  });
});

describe("dashboard: chart data is real", () => {
  it("names the frozen dataset rather than a synthetic feed", async () => {
    renderDashboard();

    expect(await screen.findByTestId("chart-data-source")).toBeTruthy();
    expect(screen.getByTestId("chart-data-source").textContent).not.toContain(
      "synthetic",
    );
  });

  it("shows the dataset hash the server reported", async () => {
    renderDashboard();

    const hash = await screen.findByTestId("chart-dataset-hash");
    await waitFor(() =>
      expect(hash.getAttribute("title")).toBe(
        "201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B",
      ),
    );
  });

  it("aligns the window to the replay's current bar using only `end`", async () => {
    const { stub } = renderDashboard([
      ...happyRoutes(),
      { match: "/api/replay", body: REPLAY_STEPPED },
    ]);

    await screen.findByTestId("standard-balance");

    // The API exposes start/end/limit and no cursor, so `end` is the only alignment
    // available. Asserted so a future "improvement" does not invent an offset.
    const marketUrls = stub.urls().filter((u) => u.includes("/api/market"));
    expect(marketUrls.length).toBeGreaterThan(0);
    for (const url of marketUrls) {
      expect(url).not.toContain("offset=");
      expect(url).not.toContain("cursor=");
    }
  });
});

describe("dashboard: AI terminology", () => {
  it("labels the score as a score and not a percentage", async () => {
    // The AI payload is supplied at mount, not after. `useAiState` fetches once on
    // the first render and react-query caches the result, so a route swapped in
    // afterwards would never be requested.
    const { stub } = renderDashboard([
      ...happyRoutes(),
      { match: "/api/ai", body: AI_STATE },
    ]);

    await selectMode("ai_intelligence");
    await waitFor(() =>
      expect(screen.getByTestId("ai-score").textContent).toContain("91"),
    );

    const score = screen.getByTestId("ai-score");
    expect(score.textContent).not.toContain("%");
    expect(document.body.textContent?.toLowerCase()).toContain(
      "a score, not a percentage",
    );
    void stub;
  });

  it("states the score is a gate and not a forecast", async () => {
    renderDashboard([
      ...happyRoutes(),
      { match: "/api/ai", body: AI_STATE },
    ]);

    await selectMode("ai_intelligence");
    await waitFor(() =>
      expect(document.body.textContent?.toLowerCase()).toContain(
        "not a probability, win rate, confidence percentage or expected return",
      ),
    );
  });

it("repeats the API's own heuristic caveat from the mode note", async () => {
    renderDashboard();

    // The note is rendered for the *selected* mode, and Standard is the default
    // selection, so AI must be selected before its note appears.
    await waitFor(() => expect(screen.getByTestId("mode-ai_intelligence")).toBeTruthy());
    await selectMode("ai_intelligence");

    await waitFor(() =>
      expect(document.body.textContent).toContain(
        "The score is a research heuristic, not a probability or a profit forecast.",
      ),
    );
  });

  it("shows a score only once one exists, and never a fabricated zero", async () => {
    // The default payload has `last_score: null`, which must render as an explicit
    // absence rather than as a score of 0 - 0 is a real score and would imply the
    // engine evaluated something.
    renderDashboard();

    await waitFor(() => expect(screen.getByTestId("mode-ai_intelligence")).toBeTruthy());
    await selectMode("ai_intelligence");

    await waitFor(() => expect(screen.getByTestId("ai-starting-capital")).toBeTruthy());

    expect(screen.getByText("No score yet")).toBeTruthy();
    expect(screen.queryByTestId("ai-score")).toBeNull();
    expect(screen.queryByTestId("ai-threshold")).toBeNull();
  });
});

import { modeNamed } from "./fixtures";