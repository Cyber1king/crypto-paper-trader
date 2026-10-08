/**
 * Component tests (Phase 18K groups 3, 4, 5, 6, 7, 10, 11).
 *
 * Rendering is asserted against **text content and attributes**, not matchers from
 * an extra assertion library, because the approved dependency set did not include
 * one and adding a fifth package to make tests prettier would exceed it.
 *
 * Group 9 — no fake fallback data — is enforced two ways: positively, by asserting
 * that unreachable and refused states render an explanation instead of a number;
 * and negatively, by the static scan in `no-mock-data.test.ts`, which proves the
 * synthetic modules are gone from disk.
 */

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ModeNote, ModeSelector } from "@/components/mode-selector";
import { PaperControls, toRefusal } from "@/components/paper-controls";
import {
  LastSignalPanel,
  OpenPositionPanel,
  ReplayProgressPanel,
  StandardAccountPanel,
  StatisticsPanel,
  TradeJournalPanel,
} from "@/components/standard-panels";
import {
  AiAccountPanel,
  AiJournalPanel,
  AiPositionsPanel,
  IntelligenceScorePanel,
  SCORE_TERMINOLOGY_NOTE,
} from "@/components/ai-panels";
import { AlertsPanel } from "@/components/alerts-panel";
import { EngineConfigurationPanel, MarketChart } from "@/components/market-chart";
import {
  ApiUnavailablePanel,
  ErrorPanel,
  PaperOnlyBanner,
  UnavailableModePanel,
} from "@/components/state";

import {
  AI_STATE,
  AI_STATE_IDLE,
  MARKET,
  MODES,
  REPLAY_IDLE,
  REPLAY_STEPPED,
  STATISTICS,
  TRADES,
  httpError,
  modeNamed,
  networkError,
} from "./fixtures";

/** All text in the container, lowercased, for "does this string appear" checks. */
function text(container: HTMLElement): string {
  return (container.textContent ?? "").toLowerCase();
}

// ---------------------------------------------------------------------------
// 3. mode rendering
// ---------------------------------------------------------------------------

describe("mode rendering", () => {
  it("renders every mode the API reported, and no others", () => {
    render(
      <ModeSelector modes={MODES} selected="standard" onSelect={() => {}} />,
    );

    for (const mode of MODES.modes) {
      expect(screen.getByTestId(`mode-${mode.mode}`)).toBeTruthy();
    }

    expect(screen.getAllByRole("radio")).toHaveLength(MODES.modes.length);
  });

  it("labels each mode with the API's own label", () => {
    render(
      <ModeSelector modes={MODES} selected="standard" onSelect={() => {}} />,
    );

    for (const mode of MODES.modes) {
      expect(
        screen.getByTestId(`mode-${mode.mode}`).textContent,
      ).toContain(mode.label);
    }
  });

  it("marks the selected mode as checked", () => {
    render(
      <ModeSelector modes={MODES} selected="ai_intelligence" onSelect={() => {}} />,
    );

    expect(
      screen.getByTestId("mode-ai_intelligence").getAttribute("aria-checked"),
    ).toBe("true");
    expect(
      screen.getByTestId("mode-standard").getAttribute("aria-checked"),
    ).toBe("false");
  });

  it("carries availability and executability from the API as data attributes", () => {
    render(<ModeSelector modes={MODES} selected="standard" onSelect={() => {}} />);

    expect(
      screen.getByTestId("mode-alerts").getAttribute("data-executable"),
    ).toBe("false");
    // Phase 26B made high_risk the last reserved mode executable, so no mode is
    // reserved now. The assertion is inverted deliberately: it fails loudly if a
    // future phase reserves one, which is exactly when this selector's behaviour
    // needs re-examining.
    expect(
      screen.getByTestId("mode-high_risk").getAttribute("data-available"),
    ).toBe("true");
    expect(
      document.querySelectorAll('[data-available="false"]').length,
    ).toBe(0);
    expect(
      screen.getByTestId("mode-manual").getAttribute("data-available"),
    ).toBe("true");
    expect(
      screen.getByTestId("mode-daily_target").getAttribute("data-available"),
    ).toBe("true");
    expect(
      screen.getByTestId("mode-standard").getAttribute("data-executable"),
    ).toBe("true");
  });

  it("distinguishes reserved from observation-only from executable", () => {
    render(<ModeSelector modes={MODES} selected="standard" onSelect={() => {}} />);

    // Compared case-insensitively: the badge carries an `uppercase` CSS class,
    // which jsdom does not apply to `textContent`, so the DOM text is "Reserved"
    // while the rendered text is "RESERVED".
    const label = (mode: string) =>
      (screen.getByTestId(`mode-${mode}`).textContent ?? "").toLowerCase();

    expect(label("alerts")).toContain("observation only");
    expect(label("standard")).toContain("executable");
    // Phases 24, 25 and 26 modes are all executable now and must be labelled as
    // such rather than reserved.
    for (const mode of ["daily_target", "manual", "high_risk"]) {
      expect(label(mode)).toContain("executable");
      expect(label(mode)).not.toContain("reserved");
    }
  });

  it("selects a reserved mode without executing anything", () => {
    const onSelect = vi.fn();
    render(<ModeSelector modes={MODES} selected="standard" onSelect={onSelect} />);

    // `high_risk`, now that `manual` became executable in Phase 25B.
    fireEvent.click(screen.getByTestId("mode-high_risk"));

    expect(onSelect).toHaveBeenCalledWith("high_risk");
    // Selection is a read-only act; the parent decides whether to issue a request.
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("shows a placeholder before the mode list arrives", () => {
    render(<ModeSelector modes={undefined} selected="standard" onSelect={() => {}} />);

    expect(screen.getByText(/loading modes/i)).toBeTruthy();
  });

  it("renders the API's note verbatim, including the score caveat", () => {
    const mode = modeNamed("ai_intelligence");
    const { container } = render(<ModeNote mode={mode} />);

    expect(container.textContent).toContain(
      "The score is a research heuristic, not a probability or a profit forecast.",
    );
    expect(container.textContent).toContain("max_positions 5");
    expect(container.textContent).toContain("threshold 90");
  });

  it("says so when a mode has no policy at all", () => {
    const { container } = render(<ModeNote mode={modeNamed("alerts")} />);

    expect(container.textContent).toContain("cannot execute paper trades");
  });
});

// ---------------------------------------------------------------------------
// 4. unavailable mode behaviour
// ---------------------------------------------------------------------------

describe("unavailable mode behaviour", () => {
  it("shows the server's note for a reserved mode", () => {
    // `high_risk`, not `manual` or `daily_target`: both became executable (Phases
    // 24C and 25B), so neither reaches UnavailableModePanel any more.
    const mode = modeNamed("high_risk");
    const { container } = render(
      <UnavailableModePanel label={mode.label} note={mode.note} />,
    );

    expect(screen.getByText("Unavailable")).toBeTruthy();
    expect(container.textContent).toContain(mode.note);
  });

  it("states that no execution was attempted", () => {
    const mode = modeNamed("high_risk");
    const { container } = render(
      <UnavailableModePanel label={mode.label} note={mode.note} />,
    );

    expect(text(container)).toContain("no execution was attempted");
    expect(text(container)).toContain("no substitute mode was selected");
  });

  it("offers no control buttons at all", () => {
    render(
      <UnavailableModePanel label="High-Risk Paper" note="Reserved." />,
    );

    expect(screen.queryByTestId("control-start")).toBeNull();
    expect(screen.queryByTestId("control-step")).toBeNull();
    expect(screen.queryByTestId("control-reset")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 7. Alerts rendering
// ---------------------------------------------------------------------------

describe("Alerts rendering", () => {
  const mode = modeNamed("alerts");

  it("offers no execution controls", () => {
    render(<AlertsPanel mode={mode} />);

    expect(screen.queryByTestId("control-start")).toBeNull();
    expect(screen.queryByTestId("control-step")).toBeNull();
    expect(screen.queryByTestId("control-pause")).toBeNull();
    expect(screen.queryByTestId("control-reset")).toBeNull();
  });

  it("never renders a buy or sell button", () => {
    const { container } = render(<AlertsPanel mode={mode} />);
    const body = text(container);

    expect(body).not.toContain("paper buy");
    expect(body).not.toContain("paper sell");
  });

  it("never renders position sizing or capital allocation", () => {
    const { container } = render(<AlertsPanel mode={mode} />);
    const body = text(container);

    expect(body).not.toContain("position size (usd)");
    expect(body).not.toContain("available capital");
    expect(body).not.toContain("committed capital");
  });

  it("lists the capabilities the mode is refused, rather than implying any", () => {
    const { container } = render(<AlertsPanel mode={mode} />);
    const body = text(container);

    for (const refused of [
      "buy / sell execution",
      "position sizing",
      "capital allocation",
      "order controls",
    ]) {
      expect(body).toContain(refused);
    }
  });

  it("states that notification delivery is not implemented", () => {
    const { container } = render(<AlertsPanel mode={mode} />);

    expect(text(container)).toContain("not implemented");
    expect(text(container)).toContain("no alert feed is shown");
  });

  it("shows the API's own note", () => {
    render(<AlertsPanel mode={mode} />);

    expect(screen.getByTestId("alerts-note").textContent).toContain(
      "Notification-only. Holds no broker",
    );
  });
});

// ---------------------------------------------------------------------------
// 5. Standard state rendering
// ---------------------------------------------------------------------------

describe("Standard state rendering", () => {
  it("renders the engine's balance, not a frontend figure", () => {
    render(<StandardAccountPanel replay={REPLAY_STEPPED} account={undefined} />);

    // 10,000.00 starting less the engine's realised -0.1875...
    expect(screen.getByTestId("standard-balance").textContent).toBe("9,999.81");
  });

  it("renders realised P&L with the engine's own sign", () => {
    render(<StandardAccountPanel replay={REPLAY_STEPPED} account={undefined} />);

    // -0.1875... formats as -0.19. Not a fabricated positive.
    expect(screen.getByTestId("standard-balance").textContent).not.toContain(
      "+",
    );
  });

  it("shows an em dash rather than a zero when nothing has been read", () => {
    render(<StandardAccountPanel replay={undefined} account={undefined} />);

    expect(screen.getByTestId("standard-balance").textContent).toBe("—");
  });

  it("renders the starting balance alongside the current one", () => {
    render(<StandardAccountPanel replay={REPLAY_IDLE} account={undefined} />);

    expect(screen.getByText(/starting 10,000\.00/)).toBeTruthy();
  });

  it("shows the replay status the server reported", () => {
    render(<ReplayProgressPanel replay={{ ...REPLAY_IDLE, status: "running" }} />);

    expect(screen.getByText("Running")).toBeTruthy();
  });

  it("shows the nulls the engine sends, rather than inventing timestamps", () => {
    const { container } = render(<ReplayProgressPanel replay={REPLAY_IDLE} />);

    // current_timestamp is null before the first step.
    expect(container.textContent?.match(/—/g)?.length ?? 0).toBeGreaterThan(0);
  });

  it("reports the frozen config and dataset hashes", () => {
    const { container } = render(<ReplayProgressPanel replay={REPLAY_IDLE} />);

    expect(container.textContent).toContain(
      "2FBDB9A8814ABC81062C2B0A61DFDCFAC69C95CF1789D0BAE6BEE4B11ADC3BF7",
    );
    expect(container.textContent).toContain(
      "201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B",
    );
  });

  it("shows the open position's engine-computed fields", () => {
    render(<OpenPositionPanel replay={REPLAY_STEPPED} />);

    // The entry price appears as both a row value and part of the reason text, so
    // the assertion is on the row set rather than on a unique node.
    expect(screen.getAllByText(/43,728\.90/).length).toBeGreaterThan(0);
    expect(screen.getByText("downtrend breakdown")).toBeTruthy();
  });

  it("refuses to invent an unrealised P&L for an open position", () => {
    const { container } = render(<OpenPositionPanel replay={REPLAY_STEPPED} />);

    expect(text(container)).toContain("no unrealised p&l is shown");
    expect(text(container)).not.toContain("unrealized");
  });

  it("shows an explicit flat state, not a blank panel", () => {
    render(<OpenPositionPanel replay={REPLAY_IDLE} />);

    // "Flat" appears twice in this panel: as the state badge and as the empty
    // state's heading. Both are intentional, so the assertion is not unique-match.
    expect(screen.getAllByText("Flat").length).toBeGreaterThan(0);
    expect(screen.getByText(/no open paper position/i)).toBeTruthy();
  });

  it("shows the flat state honestly when the signal has not been produced yet", () => {
    render(<LastSignalPanel signal={null} />);

    expect(screen.getByText("No signal yet")).toBeTruthy();
  });

  it("labels the signal close as not being a fill price", () => {
    const { container } = render(<LastSignalPanel signal={REPLAY_STEPPED.last_signal} />);

    expect(text(container)).toContain("the signal bar's close, not a fill price");
  });

  it("renders the engine's statistics rather than aggregating the journal", () => {
    const { container } = render(<StatisticsPanel statistics={STATISTICS} />);

    expect(screen.getByText("∞ (no losing trades)")).toBeTruthy();

    // `basis` appears inside the panel's description sentence, so it is not a
    // standalone text node. Matched on the rendered container instead.
    expect(container.textContent).toContain("closed_trades");
    expect(container.textContent).toContain("No frontend aggregation");
  });

  it("renders the trade journal from the server's own rows", () => {
    render(<TradeJournalPanel trades={TRADES} />);

    const table = screen.getByTestId("trade-journal");
    expect(table.textContent).toContain("bullish retest");
    expect(table.textContent).toContain("opposite_signal");
    // The engine's net P&L, which is negative after friction.
    expect(table.textContent).toContain("-0.19");
  });

  it("shows an explicit empty state for an empty journal", () => {
    render(<TradeJournalPanel trades={{ trade_count: 0, trades: [] }} />);

    expect(screen.getByText("No closed trades")).toBeTruthy();
  });

  it("renders read-only engine configuration with no selectors", () => {
    const { container } = render(<EngineConfigurationPanel replay={REPLAY_IDLE} />);

    expect(screen.getByTestId("config-asset").textContent).toBe("BTC/USDT");
    expect(screen.getByTestId("config-timeframe").textContent).toBe("1h");
    expect(screen.getByTestId("config-strategy").textContent).toBe(
      "Breakout + Retest",
    );
    // No dropdown or button that could imply the values are changeable.
    expect(container.querySelector("select")).toBeNull();
    expect(container.querySelectorAll('input[type="text"]')).toHaveLength(0);
    expect(text(container)).toContain("not selectable");
  });
});

// ---------------------------------------------------------------------------
// 6. AI Intelligence state rendering
// ---------------------------------------------------------------------------

describe("AI Intelligence state rendering", () => {
  it("renders the AI account from /api/ai, not the replay", () => {
    render(<AiAccountPanel ai={AI_STATE} />);

    expect(screen.getByTestId("ai-starting-capital").textContent).toBe(
      "10,000.00",
    );
  });

  it("shows the capital accounting the engine owns", () => {
    const { container } = render(<AiAccountPanel ai={AI_STATE} />);
    const body = text(container);

    expect(body).toContain("committed capital");
    expect(body).toContain("available capital");
    expect(body).toContain("realised paper p&l");
    expect(screen.getByText("1 / 5")).toBeTruthy();
  });

  it("says the capital is not on credit", () => {
    const { container } = render(<AiAccountPanel ai={AI_STATE} />);

    expect(text(container)).toContain("never on credit");
    expect(text(container)).toContain("no gearing, no margin");
  });

  it("renders the score with its threshold and no percent sign", () => {
    render(<IntelligenceScorePanel score={AI_STATE.last_score} />);

    expect(screen.getByTestId("ai-score").textContent).toContain("91");
    expect(screen.getByTestId("ai-threshold").textContent).toBe("90");
    // "/ 100" is a scale, not a percentage.
    expect(screen.getByTestId("ai-score").textContent).not.toContain("%");
  });

  it("labels the qualification verdict rather than a success rate", () => {
    render(<IntelligenceScorePanel score={AI_STATE.last_score} />);

    expect(screen.getByTestId("ai-qualified").textContent).toBe("Qualified");
  });

  it("shows every score component with its own explanation", () => {
    render(<IntelligenceScorePanel score={AI_STATE.last_score} />);
    const components = screen.getByTestId("ai-score-components");

    expect(components.textContent).toContain("trend alignment");
    expect(components.textContent).toContain("breakout strength");
    expect(components.textContent).toContain("confirmation");
    expect(components.textContent).toContain("range quality");
    expect(components.textContent).toContain("direction");
    expect(components.textContent).toContain("0.2981%");
  });

  it("shows no score at all before one exists", () => {
    render(<IntelligenceScorePanel score={null} />);

    expect(screen.getByText("No score yet")).toBeTruthy();
    // Neither the score nor the threshold may be rendered from a null.
    expect(screen.queryByTestId("ai-score")).toBeNull();
    expect(screen.queryByTestId("ai-threshold")).toBeNull();
  });

  it("renders the open position and the closed one in separate panels", () => {
    render(
      <>
        <AiPositionsPanel ai={AI_STATE} />
        <AiJournalPanel ai={AI_STATE} />
      </>,
    );

    // AI_STATE carries one open position and one closed, so both panels render a
    // row: two in total, and neither is showing the other's.
    const rows = screen.getAllByTestId("ai-position");
    expect(rows).toHaveLength(2);

    const open = rows.find((row) => row.textContent?.includes("ai-3"));
    const closed = rows.find((row) => row.textContent?.includes("ai-1"));

    // Badge state text is lowercase in the DOM and uppercased by CSS.
    expect(open?.textContent?.toLowerCase()).toContain("open");
    expect(closed?.textContent?.toLowerCase()).toContain("closed");
    expect(closed?.textContent).toContain("ai_profit_target");
  });

  it("shows the signals qualified / admitted / declined counts", () => {
    const { container } = render(<AiAccountPanel ai={AI_STATE} />);

    expect(text(container)).toContain("signals qualified");
    expect(text(container)).toContain("signals admitted");
    expect(text(container)).toContain("signals declined");
  });

  it("shows nothing rather than zeros when the API is silent", () => {
    render(<AiAccountPanel ai={undefined} />);

    expect(screen.getByText("No account reported")).toBeTruthy();
    expect(screen.queryByTestId("ai-starting-capital")).toBeNull();
  });

  it("renders the idle AI state with full capital and no positions", () => {
    render(
      <>
        <AiAccountPanel ai={AI_STATE_IDLE} />
        <AiPositionsPanel ai={AI_STATE_IDLE} />
      </>,
    );

    expect(screen.getByTestId("ai-starting-capital").textContent).toBe(
      "10,000.00",
    );
    expect(screen.getByText("No open AI positions")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 8. replay control requests
// ---------------------------------------------------------------------------

describe("replay control bar", () => {
  const baseProps = {
    status: "idle" as const,
    modeLabel: "Standard",
    busy: false,
    stepCount: 1,
    onStepCountChange: vi.fn(),
    onStart: vi.fn(),
    onPause: vi.fn(),
    onStep: vi.fn(),
    onReset: vi.fn(),
    refusal: null,
  };

  it("renders the server's status", () => {
    render(<PaperControls {...baseProps} />);

    expect(screen.getByTestId("replay-status").textContent).toBe("Idle");
  });

  it("wires each button to its own handler", () => {
    const onStart = vi.fn();
    const onPause = vi.fn();
    const onStep = vi.fn();
    const onReset = vi.fn();

    render(
      <PaperControls
        {...baseProps}
        onStart={onStart}
        onPause={onPause}
        onStep={onStep}
        onReset={onReset}
      />,
    );

    fireEvent.click(screen.getByTestId("control-start"));
    fireEvent.click(screen.getByTestId("control-step"));
    fireEvent.click(screen.getByTestId("control-reset"));

    expect(onStart).toHaveBeenCalledTimes(1);
    expect(onStep).toHaveBeenCalledTimes(1);
    expect(onReset).toHaveBeenCalledTimes(1);
    expect(onPause).not.toHaveBeenCalled();
  });

  it("disables Pause unless the server says the replay is running", () => {
    render(<PaperControls {...baseProps} />);

    expect((screen.getByTestId("control-pause") as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("enables Pause once the server reports running", () => {
    render(<PaperControls {...baseProps} status="running" />);

    expect((screen.getByTestId("control-pause") as HTMLButtonElement).disabled).toBe(
      false,
    );
  });

  it("disables Start and Step when the replay has finished", () => {
    render(<PaperControls {...baseProps} status="finished" />);

    expect((screen.getByTestId("control-start") as HTMLButtonElement).disabled).toBe(
      true,
    );
    expect((screen.getByTestId("control-step") as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("keeps Reset available when a position is open, because the server refuses it", () => {
    // The engine answers 409 POSITION_OPEN. Hiding the button would misrepresent
    // that refusal as an absent capability.
    render(<PaperControls {...baseProps} status="paused" />);

    expect((screen.getByTestId("control-reset") as HTMLButtonElement).disabled).toBe(
      false,
    );
  });

  it("suppresses duplicate requests while one is in flight", () => {
    const onStep = vi.fn();
    render(<PaperControls {...baseProps} busy onStep={onStep} />);

    expect((screen.getByTestId("control-step") as HTMLButtonElement).disabled).toBe(
      true,
    );
    fireEvent.click(screen.getByTestId("control-step"));

    expect(onStep).not.toHaveBeenCalled();
  });

  it("disables everything when the mode cannot execute", () => {
    render(
      <PaperControls
        {...baseProps}
        disabled
        disabledReason="This mode cannot execute paper trades."
      />,
    );

    for (const id of ["control-start", "control-step", "control-pause", "control-reset"]) {
      expect((screen.getByTestId(id) as HTMLButtonElement).disabled).toBe(true);
    }
    expect(screen.getByTestId("controls-disabled-reason").textContent).toContain(
      "cannot execute",
    );
  });

  it("shows a server refusal verbatim, with its code", () => {
    render(
      <PaperControls
        {...baseProps}
        refusal={{
          code: "POSITION_OPEN",
          message: "cannot reset while a paper position is open",
        }}
      />,
    );

    const refusal = screen.getByTestId("control-refusal");
    expect(refusal.getAttribute("data-code")).toBe("POSITION_OPEN");
    expect(refusal.textContent).toContain("cannot reset while a paper position is open");
  });

  it("renders nothing in the refusal slot when there is no refusal", () => {
    render(<PaperControls {...baseProps} />);

    expect(screen.queryByTestId("control-refusal")).toBeNull();
  });

  it("rejects a step count outside the server's own bounds", () => {
    render(<PaperControls {...baseProps} stepCount={0} />);

    expect((screen.getByTestId("control-step") as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("converts an ApiError into a displayable refusal", () => {
    expect(
      toRefusal(httpError("REPLAY_FINISHED", "replay has reached the end")),
    ).toEqual({
      code: "REPLAY_FINISHED",
      message: "replay has reached the end",
    });
  });

  it("returns null for something that is not an ApiError", () => {
    expect(toRefusal(new Error("unexpected"))).toBeNull();
    expect(toRefusal(undefined)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 8b. the chart
// ---------------------------------------------------------------------------

describe("market chart", () => {
  it("names the real dataset as its source", () => {
    render(
      <MarketChart
        market={MARKET}
        isLoading={false}
        error={null}
        signal={null}
        asset="BTC/USDT"
        timeframe="1h"
      />,
    );

    const badge = screen.getByTestId("chart-data-source");
    expect(badge.textContent).toContain("Frozen research dataset");
    expect(badge.textContent).not.toContain("synthetic");
  });

  it("shows the dataset hash the server reported", () => {
    render(
      <MarketChart
        market={MARKET}
        isLoading={false}
        error={null}
        signal={null}
        asset="BTC/USDT"
        timeframe="1h"
      />,
    );

    expect(screen.getByTestId("chart-dataset-hash").getAttribute("title")).toBe(
      "201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B",
    );
  });

  it("shows the last real close", () => {
    const { container } = render(
      <MarketChart
        market={MARKET}
        isLoading={false}
        error={null}
        signal={null}
        asset="BTC/USDT"
        timeframe="1h"
      />,
    );

    expect(container.textContent).toContain("87,608.20");
  });

  it("refuses to draw a substitute series when no candles arrive", () => {
    render(
      <MarketChart
        market={{ ...MARKET, candles: [] }}
        isLoading={false}
        error={null}
        signal={null}
      />,
    );

    expect(screen.getByText("No candle data available")).toBeTruthy();
    expect(screen.getByText(/no substitute series is drawn/i)).toBeTruthy();
  });

  it("reports an unreachable API rather than charting nothing silently", () => {
    render(
      <MarketChart
        market={undefined}
        isLoading={false}
        error={networkError()}
        signal={null}
      />,
    );

    expect(screen.getByText("Paper API unavailable")).toBeTruthy();
  });

  it("passes the engine's levels to the chart, and nothing when it reported none", () => {
    // Asserted through a data attribute rather than the emitted SVG, because
    // recharts only creates a ReferenceLine once the chart has a non-zero size �
    // which never happens under jsdom, so the line itself is unobservable here.
    const signal = REPLAY_STEPPED.last_signal!;
    const withSignal = render(
      <MarketChart
        market={MARKET}
        isLoading={false}
        error={null}
        signal={signal}
      />,
    );

    const levels = screen.getByTestId("chart-engine-levels");
    expect(levels.getAttribute("data-support")).toBe(String(signal.support));
    expect(levels.getAttribute("data-resistance")).toBe(String(signal.resistance));
    withSignal.unmount();

    const without = render(
      <MarketChart
        market={MARKET}
        isLoading={false}
        error={null}
        signal={null}
      />,
    );

    const absent = screen.getByTestId("chart-engine-levels");
    expect(absent.getAttribute("data-support")).toBe("");
    expect(absent.getAttribute("data-resistance")).toBe("");
  });
});

// ---------------------------------------------------------------------------
// 9 / 11. loading and error states
// ---------------------------------------------------------------------------

describe("loading and error states", () => {
  it("always shows the paper-only statement", () => {
    render(<PaperOnlyBanner />);

    expect(screen.getByText(/paper trading only/i)).toBeTruthy();
    expect(screen.getByText(/no exchange, wallet or real capital/i)).toBeTruthy();
  });

  it("says the API is unavailable instead of showing a balance", () => {
    const { container } = render(<ApiUnavailablePanel error={networkError()} />);

    expect(screen.getByText("Paper API unavailable")).toBeTruthy();
    expect(text(container)).toContain("no figures are shown because none could be read");
    // The critical assertion: no dollar figure anywhere on an unreachable panel.
    expect(container.textContent).not.toContain("$");
  });

  it("offers a retry when one is supplied", () => {
    const onRetry = vi.fn();
    render(<ApiUnavailablePanel error={networkError()} onRetry={onRetry} />);

    fireEvent.click(screen.getByText("Retry"));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("shows a refusal with its status and code", () => {
    render(
      <ErrorPanel
        error={httpError("REPLAY_FINISHED", "replay has reached the end", 409)}
      />,
    );

    expect(screen.getByText("409 REPLAY_FINISHED")).toBeTruthy();
    expect(screen.getByText("replay has reached the end")).toBeTruthy();
  });

  it("routes a network error to the unavailable panel", () => {
    render(<ErrorPanel error={networkError()} />);

    expect(screen.getByText("Paper API unavailable")).toBeTruthy();
  });

  it("shows no dollar figure when a refused mutation leaves stale state", async () => {
    const { container } = render(
      <PaperControls
        status="idle"
        modeLabel="Standard"
        busy={false}
        stepCount={1}
        onStepCountChange={vi.fn()}
        onStart={vi.fn()}
        onPause={vi.fn()}
        onStep={vi.fn()}
        onReset={vi.fn()}
        refusal={{ code: "POSITION_OPEN", message: "cannot reset" }}
      />,
    );

    expect(container.textContent).not.toContain("$");
    await waitFor(() =>
      expect(screen.getByTestId("control-refusal")).toBeTruthy(),
    );
  });
});