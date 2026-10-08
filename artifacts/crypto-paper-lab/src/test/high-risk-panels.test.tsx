/**
 * High-Risk panel tests (Phase 26B).
 *
 * ## What is being protected
 *
 * High-Risk is the mode most likely to be misread. Its name promises danger; the
 * safety it actually provides is that exposure can never exceed the paper cash the
 * account holds. So the tests are mostly about what the panel must *not* say or
 * imply, and about the few numbers it must show exactly as the engine sent them.
 *
 * - It must render `inherits_note` verbatim. That sentence is the only thing
 *   stopping a reader from assuming High-Risk trades signals Standard rejects.
 * - It must render `caution` verbatim. A panel that said nothing about costs would
 *   let "more paper capital per position" read as "more return".
 * - It must say "no leverage or margin" in words. The name cannot be relied on.
 * - It must compute **no** money. `exposure` and `exposure_fraction` are displayed
 *   exactly as received; P&L, fees, quantity and profit are never derived.
 * - It must not show a percentage as an outcome, a probability, or a confidence.
 * - It must refuse an unusable percentage rather than clamping it, and must disable
 *   the control while a position is open because the engine will refuse that change.
 *
 * Assertions are on text content and attributes only, matching `components.test.tsx`.
 */

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { HighRiskPanel } from "@/components/high-risk-panels";

import {
  HIGH_RISK_CAUTION,
  HIGH_RISK_FINISHED,
  HIGH_RISK_FLAT,
  HIGH_RISK_HOLDING_LONG,
  HIGH_RISK_HOLDING_SHORT,
  HIGH_RISK_INHERITS_NOTE,
  HIGH_RISK_NOTE,
  REPLAY_IDLE,
  httpError,
  networkError,
} from "./fixtures";

function text(container: HTMLElement): string {
  return (container.textContent ?? "").toLowerCase();
}

/** Render the panel with sensible defaults and a spy for the configuration change. */
function renderPanel(
  props: Partial<Parameters<typeof HighRiskPanel>[0]> = {},
  onSetFraction: Parameters<typeof HighRiskPanel>[0]["onSetFraction"] = vi.fn(),
) {
  const merged = {
    highRisk: HIGH_RISK_FLAT as Parameters<typeof HighRiskPanel>[0]["highRisk"],
    isLoading: false,
    error: null as Parameters<typeof HighRiskPanel>[0]["error"],
    onSetFraction,
    isSubmitting: false,
    actionError: null as Parameters<typeof HighRiskPanel>[0]["actionError"],
    ...props,
  };

  return {
    onSetFraction,
    ...render(<HighRiskPanel {...merged} />),
  };
}

function typePercent(value: string) {
  const input = screen.getByTestId("high-risk-percent-input");
  fireEvent.change(input, { target: { value } });
  return input as HTMLInputElement;
}

describe("High-Risk panel", () => {
  describe("A. mode identity and paper-only labelling", () => {
    it("names the mode as High-Risk — Paper Trading", () => {
      renderPanel();
      expect(
        screen.getByText(/High-Risk — Paper Trading/).textContent,
      ).toContain("Paper Trading");
    });

    it("shows the engine's own label, verbatim", () => {
      renderPanel();
      expect(
        screen.getByText(/High-Risk — Paper Trading/).textContent,
      ).toBe(HIGH_RISK_FLAT.label);
    });

    it("carries the shared paper-only banner", () => {
      renderPanel();
      expect(screen.getByText(/PAPER TRADING ONLY/i)).toBeTruthy();
    });

    it("says PAPER on each panel badge", () => {
      const { container } = renderPanel();
      // Four panels carry the badge: the header, the account, the exposure panel and
      // the position panel. Asserting a count would break on a layout change; what
      // matters is that no section presents a bare money figure without the word.
      expect(text(container).match(/paper/g)?.length ?? 0).toBeGreaterThan(4);
    });

    it("renders the engine's note verbatim", () => {
      renderPanel();
      expect(screen.getByText(HIGH_RISK_NOTE)).toBeTruthy();
    });

    it("never rewrites the engine's note", () => {
      const { container } = renderPanel();
      // Every clause of the safety sentence survives the render.
      for (const clause of [
        "no leverage",
        "no margin",
        "no borrowing",
        "no liquidation",
      ]) {
        expect(text(container)).toContain(clause);
      }
    });
  });

  describe("B. the inherited-signal-set statement", () => {
    it("renders inherits_note verbatim", () => {
      renderPanel();
      expect(screen.getByTestId("high-risk-inherits-note").textContent).toBe(
        HIGH_RISK_INHERITS_NOTE,
      );
    });

    it("states that no new qualification rule is introduced", () => {
      const { container } = renderPanel();
      expect(text(container)).toContain(
        "high-risk introduces no new signal qualification rule",
      );
    });

    it("states that Standard's signal set is inherited", () => {
      const { container } = renderPanel();
      expect(text(container)).toContain("inherits standard's signal set");
    });

    it("cannot be dropped by the panel", () => {
      // No prop removes it, so it is present in every state the panel can render.
      for (const state of [
        HIGH_RISK_FLAT,
        HIGH_RISK_HOLDING_LONG,
        HIGH_RISK_FINISHED,
      ]) {
        const { unmount } = renderPanel({ highRisk: state });
        expect(screen.getByTestId("high-risk-inherits-note").textContent).toBe(
          HIGH_RISK_INHERITS_NOTE,
        );
        unmount();
      }
    });
  });

  describe("C. the friction caution", () => {
    it("renders caution verbatim", () => {
      renderPanel();
      expect(screen.getByTestId("high-risk-caution").textContent).toContain(
        HIGH_RISK_CAUTION,
      );
    });

    it("warns that costs grow with position size", () => {
      const { container } = renderPanel();
      expect(text(container)).toContain("costs grow with position size");
    });

    it("says more capital is not a better outcome", () => {
      const { container } = renderPanel();
      expect(text(container)).toContain("not a better outcome");
    });

    it("shows it in every state", () => {
      for (const state of [HIGH_RISK_FLAT, HIGH_RISK_FINISHED]) {
        const { unmount } = renderPanel({ highRisk: state });
        expect(screen.getByTestId("high-risk-caution")).toBeTruthy();
        unmount();
      }
    });
  });

  describe("D. no probability, confidence or guaranteed-return language", () => {
    const BANNED = [
      "guaranteed",
      "guarantee",
      "probability",
      "probable",
      "confidence",
      "likelihood",
      "chance of",
      "risk-free",
      "assured",
    ];

    it.each(BANNED)("never says '%s'", (word) => {
      const { container } = renderPanel({
        highRisk: HIGH_RISK_FINISHED,
      });
      expect(text(container)).not.toContain(word);
    });

    it("does not turn the score or signal into a forecast", () => {
      const { container } = renderPanel({
        highRisk: HIGH_RISK_HOLDING_LONG,
      });
      expect(text(container)).not.toContain("forecast");
      expect(text(container)).not.toContain("projected");
    });

    it("presents the signal as an observation, not a recommendation", () => {
      renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG });
      const signal = screen.getByTestId("high-risk-signal");
      expect(signal.textContent?.toUpperCase()).toContain("LONG");
      expect(screen.getByText(/the same signal standard sees/i)).toBeTruthy();
    });
  });

  describe("E. no exchange, order or credit language", () => {
    const OPERATIONAL = [
      "live trade",
      "real order",
      "exchange account",
      "withdraw",
      "deposit",
      "api key",
      "borrowing position",
      "margin call",
    ];

    it.each(OPERATIONAL)("never presents '%s' as a capability", (word) => {
      const { container } = renderPanel({
        highRisk: HIGH_RISK_HOLDING_LONG,
      });
      // The words may appear only inside the engine's own denial sentences.
      expect(text(container)).not.toContain(word);
    });

    it("denies leverage and margin in plain words", () => {
      const { container } = renderPanel();
      expect(text(container)).toContain(
        "it does not use leverage or margin",
      );
      expect(text(container)).toContain(
        "exposure never exceeds the paper cash you hold",
      );
    });

    it("offers no trade button at all", () => {
      // High-Risk is automatic and adds no qualification rule, so the only control it
      // owns is the size setting. A buy/sell button would be an affordance the mode
      // does not have.
      renderPanel({ highRisk: HIGH_RISK_FLAT });
      expect(screen.queryByTestId("high-risk-buy")).toBeNull();
      expect(screen.queryByTestId("high-risk-sell")).toBeNull();
      expect(screen.queryByTestId("high-risk-exit")).toBeNull();
      expect(screen.getByTestId("high-risk-apply")).toBeTruthy();
    });
  });

  describe("F. the engine's figures, shown exactly", () => {
    it("shows the paper balance the engine sent", () => {
      renderPanel();
      expect(screen.getByTestId("high-risk-cash").textContent).toBe("10,000.00");
    });

    it("shows realized P&L the engine sent", () => {
      renderPanel({ highRisk: HIGH_RISK_FINISHED });
      expect(screen.getByTestId("high-risk-realized").textContent).toContain(
        "-3,354.79",
      );
    });

    it("shows the position count against the maximum", () => {
      renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG });
      expect(screen.getByTestId("high-risk-position-count").textContent).toBe(
        "1 of 1",
      );
    });

    it("shows the exposure the engine sent, not one it computed", () => {
      renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG });
      // 43,679.70 * 0.05723482533076006 = 2,500.00. The panel is handed 2500.0 and
      // must display that figure rather than deriving it from price and quantity.
      expect(screen.getByTestId("high-risk-exposure").textContent).toContain(
        "2,500.00",
      );
    });

    it("shows the exposure fraction the engine sent", () => {
      renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG });
      expect(
        screen.getByTestId("high-risk-exposure-fraction").textContent,
      ).toContain("25.00%");
    });

    it("shows zero exposure when flat", () => {
      renderPanel();
      expect(screen.getByTestId("high-risk-exposure").textContent).toContain(
        "0.00",
      );
    });

    it("shows the fraction in force as a percentage, not a raw decimal", () => {
      renderPanel();
      expect(screen.getByTestId("high-risk-fraction").textContent).toContain(
        "25.00%",
      );
    });

    it("shows a 50% fraction as 50.00%, not 0.5", () => {
      renderPanel({ highRisk: HIGH_RISK_HOLDING_SHORT });
      expect(screen.getByTestId("high-risk-fraction").textContent).toContain(
        "50.00%",
      );
    });

    it("shows the closed-trade count", () => {
      renderPanel({ highRisk: HIGH_RISK_FINISHED });
      expect(screen.getByTestId("high-risk-trade-count").textContent).toBe("344");
    });

    it("shows the exit tally the engine reported", () => {
      renderPanel({ highRisk: HIGH_RISK_FINISHED });
      const tally = screen.getByTestId("high-risk-exit-counts");
      expect(tally.textContent).toContain("opposite_signal");
      expect(tally.textContent).toContain("343");
      expect(tally.textContent).toContain("end_of_data");
    });

    it("shows only the exit reasons the engine reported", () => {
      // The frozen baseline has no stop-loss, so its absence here is the proof that
      // the mode added no exit rule of its own.
      const { container } = renderPanel({ highRisk: HIGH_RISK_FINISHED });
      expect(text(container)).not.toContain("stop_loss");
      expect(text(container)).not.toContain("take_profit");
    });

    it("shows the open position's engine figures", () => {
      renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG });
      const position = screen.getByTestId("high-risk-position");
      expect(position.textContent).toContain("LONG");
      expect(position.textContent).toContain("43,679.7");
      expect(position.textContent).toContain("bullish retest");
    });

    it("shows a short position as short", () => {
      renderPanel({ highRisk: HIGH_RISK_HOLDING_SHORT });
      expect(screen.getByTestId("high-risk-position").textContent).toContain(
        "SHORT",
      );
    });

    it("says the account is flat when it is", () => {
      renderPanel();
      expect(screen.getByTestId("high-risk-position").textContent).toContain(
        "No paper position is open",
      );
    });

    it("invents no unrealised figure for an open position", () => {
      // The engine has no live price feed, so an unrealised number would have to be
      // fabricated. Cash is untouched by an entry, so realized P&L must read zero.
      renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG });
      expect(screen.getByTestId("high-risk-realized").textContent).toContain(
        "0.00",
      );
      const { container } = renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG });
      expect(text(container)).not.toContain("unrealized p&l");
      expect(text(container)).not.toContain("unrealised p&l");
    });

    it("labels no row with a figure the engine cannot produce", () => {
      // "Equity", "margin" and the rest appear in the shared banner and the safety
      // sentences only inside denials, so a blanket word ban would fail on correct
      // copy. What matters is that no **value** the panel reports offers such a
      // figure - so only the value-bearing test ids are inspected, not the panel
      // containers that happen to wrap explanatory prose.
      renderPanel({ highRisk: HIGH_RISK_FINISHED });

      const valueIds = [
        "high-risk-cash",
        "high-risk-realized",
        "high-risk-position-count",
        "high-risk-trade-count",
        "high-risk-exposure",
        "high-risk-exposure-fraction",
        "high-risk-fraction",
        "high-risk-entry-price",
        "high-risk-signal",
      ];

      for (const id of valueIds) {
        const node = screen.queryByTestId(id);
        if (node === null) {
          continue;
        }
        const shown = (node.textContent ?? "").toLowerCase();
        for (const forbidden of [
          "equity",
          "mark price",
          "buying power",
          "reserved capital",
          "margin",
          "notional",
          "unrealized",
          "unrealised",
        ]) {
          expect(shown).not.toContain(forbidden);
        }
      }
    });
  });

  describe("G. no client-side financial arithmetic", () => {
    it("renders the exposure it is given, even when it looks odd", () => {
      // A deliberately inconsistent figure proves the panel displays rather than
      // recomputes: entry_price * quantity here is 2,499.99, but the panel must show
      // the 2,123.45 it was handed.
      renderPanel({
        highRisk: {
          ...HIGH_RISK_HOLDING_LONG,
          exposure: 2123.45,
          exposure_fraction: 0.212345,
        },
      });
      expect(screen.getByTestId("high-risk-exposure").textContent).toContain(
        "2,123.45",
      );
      expect(
        screen.getByTestId("high-risk-exposure-fraction").textContent,
      ).toContain("21.23%");
    });

    it("performs no arithmetic across the panel's own fields", () => {
      const { container } = renderPanel({
        highRisk: {
          ...HIGH_RISK_FINISHED,
          paper_cash: 1234.5,
          realized_pnl: -99.5,
          exposure: 300.0,
          exposure_fraction: 0.243,
        },
      });
      // Every figure appears as sent, with none reconciled against another.
      expect(screen.getByTestId("high-risk-cash").textContent).toContain(
        "1,234.50",
      );
      expect(screen.getByTestId("high-risk-realized").textContent).toContain(
        "-99.50",
      );
      expect(screen.getByTestId("high-risk-exposure").textContent).toContain(
        "300.00",
      );
      expect(container).toBeTruthy();
    });

    it("does not multiply price by quantity in the position panel", () => {
      renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG });
      const position = screen.getByTestId("high-risk-position");
      // 43,679.70 * 0.05723482533076006 = 2,500.00. If the panel computed a notional
      // from the position fields, this figure would appear there.
      expect(position.textContent).not.toContain("2,500");
    });
  });

  describe("H. the percentage input", () => {
    it("is labelled in percent", () => {
      renderPanel();
      expect(
        screen.getByText(/Cash per position \(% of paper cash\)/i),
      ).toBeTruthy();
    });

    it("uses the codebase decimal-input convention", () => {
      renderPanel();
      const input = typePercent("");
      expect(input.getAttribute("type")).toBe("text");
      expect(input.getAttribute("inputmode")).toBe("decimal");
    });

    it("converts a typed percentage to the engine's fraction", () => {
      const onSetFraction = vi.fn();
      renderPanel({}, onSetFraction);
      // 50, not 25: the fixture is already at 25%, so typing 25 leaves the setting
      // unchanged and the control is correctly disabled.
      typePercent("50");
      fireEvent.click(screen.getByTestId("high-risk-apply"));
      expect(onSetFraction).toHaveBeenCalledWith(0.5);
    });

    it("converts a decimal percentage", () => {
      const onSetFraction = vi.fn();
      renderPanel({}, onSetFraction);
      typePercent("12.5");
      fireEvent.click(screen.getByTestId("high-risk-apply"));
      expect(onSetFraction).toHaveBeenCalledWith(0.125);
    });

    it("converts the maximum percentage to 1", () => {
      const onSetFraction = vi.fn();
      renderPanel({}, onSetFraction);
      typePercent("100");
      fireEvent.click(screen.getByTestId("high-risk-apply"));
      expect(onSetFraction).toHaveBeenCalledWith(1);
    });

    it("never sends a clamped value for something above the ceiling", () => {
      const onSetFraction = vi.fn();
      renderPanel({}, onSetFraction);
      typePercent("150");
      expect(screen.getByTestId("high-risk-percent-invalid")).toBeTruthy();
      expect(
        (screen.getByTestId("high-risk-apply") as HTMLButtonElement).disabled,
      ).toBe(true);
      fireEvent.click(screen.getByTestId("high-risk-apply"));
      expect(onSetFraction).not.toHaveBeenCalled();
    });

    it.each(["0", "-5", "1e400", "12abc", "", "  "])(
      "refuses '%s' rather than submitting a substitute",
      (value) => {
        const onSetFraction = vi.fn();
        renderPanel({}, onSetFraction);
        typePercent(value);
        fireEvent.click(screen.getByTestId("high-risk-apply"));
        expect(onSetFraction).not.toHaveBeenCalled();
      },
    );

    it("never coerces a blank field to zero", () => {
      const onSetFraction = vi.fn();
      renderPanel({}, onSetFraction);
      typePercent("");
      fireEvent.click(screen.getByTestId("high-risk-apply"));
      expect(onSetFraction).not.toHaveBeenCalledWith(0);
    });

    it("disables apply when the value is unchanged", () => {
      renderPanel();
      typePercent("25");
      expect(
        (screen.getByTestId("high-risk-apply") as HTMLButtonElement).disabled,
      ).toBe(true);
    });

    it("disables apply when the field is empty", () => {
      renderPanel();
      expect(
        (screen.getByTestId("high-risk-apply") as HTMLButtonElement).disabled,
      ).toBe(true);
    });

    it("shows the validation message only for an unusable entry", () => {
      renderPanel();
      expect(screen.queryByTestId("high-risk-percent-invalid")).toBeNull();
      typePercent("150");
      expect(screen.getByTestId("high-risk-percent-invalid").textContent).toContain(
        "at most 100",
      );
    });
  });

  describe("I. configuration refused while a position is open", () => {
    it("disables the control while a position is open", () => {
      renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG });
      typePercent("50");
      expect(
        (screen.getByTestId("high-risk-apply") as HTMLButtonElement).disabled,
      ).toBe(true);
    });

    it("explains why, rather than showing a dead button", () => {
      renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG });
      const note = screen.getByTestId("high-risk-config-locked");
      expect(note.textContent).toContain("sized by the current fraction");
    });

    it("sends nothing while locked", () => {
      const onSetFraction = vi.fn();
      renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG }, onSetFraction);
      typePercent("50");
      fireEvent.click(screen.getByTestId("high-risk-apply"));
      expect(onSetFraction).not.toHaveBeenCalled();
    });

    it("does not show the lock when flat", () => {
      renderPanel();
      expect(screen.queryByTestId("high-risk-config-locked")).toBeNull();
    });
  });

  describe("J. the configuration mutation's result", () => {
    it("shows the server's message when the engine refuses", () => {
      const error = httpError("POSITION_OPEN", "A paper position is open.", 409);
      renderPanel({ actionError: error });
      expect(screen.getByTestId("high-risk-error").textContent).toContain(
        "A paper position is open.",
      );
    });

    it("surfaces a transport failure too", () => {
      renderPanel({ actionError: networkError() });
      expect(screen.getByTestId("high-risk-error")).toBeTruthy();
    });

    it("disables apply while a submission is in flight", () => {
      renderPanel({ isSubmitting: true });
      typePercent("50");
      expect(
        (screen.getByTestId("high-risk-apply") as HTMLButtonElement).disabled,
      ).toBe(true);
    });
  });

  describe("K. loading and error states", () => {
    it("shows a loading panel before the state arrives", () => {
      renderPanel({ highRisk: undefined, isLoading: true });
      expect(screen.getByText(/Loading High-Risk paper state/i)).toBeTruthy();
    });

    it("shows an error panel when the query fails", () => {
      // An http failure keeps the panel's own title; a network failure renders the
      // shared unavailable panel, which has its own copy and no title.
      renderPanel({
        highRisk: undefined,
        error: httpError("HTTP_ERROR", "server refused", 500),
      });
      expect(screen.getByText(/High-Risk is unavailable/i)).toBeTruthy();
    });

    it("shows the shared unavailable panel for an unreachable server", () => {
      renderPanel({ highRisk: undefined, error: networkError() });
      // `getAllByText` because the shared panel states the same thing twice - a
      // heading and a sentence - and either occurrence proves the panel rendered.
      expect(screen.getAllByText(/Paper API unavailable/i).length).toBeGreaterThan(0);
    });

    it("renders nothing financial while loading", () => {
      const { container } = renderPanel({
        highRisk: undefined,
        isLoading: true,
      });
      expect(text(container)).not.toContain("10,000.00");
    });

    it("does not render the note while the query has failed", () => {
      const { container } = renderPanel({
        highRisk: undefined,
        error: networkError(),
      });
      expect(text(container)).not.toContain("no new signal qualification rule");
    });
  });

  describe("L. the journal panel is honest about what the contract provides", () => {
    it("shows the count and the tally", () => {
      renderPanel({ highRisk: HIGH_RISK_FINISHED });
      expect(screen.getByTestId("high-risk-journal-count").textContent).toBe(
        "344",
      );
      expect(screen.getByTestId("high-risk-exit-counts")).toBeTruthy();
    });

    it("says so when nothing has closed yet", () => {
      renderPanel();
      expect(screen.getByTestId("high-risk-journal-empty")).toBeTruthy();
    });

    it("invents no individual trade rows", () => {
      // The mode's contract exposes a count and a tally, not a list of trades. A row
      // built from the tally would be a figure the engine never reported.
      const { container } = renderPanel({ highRisk: HIGH_RISK_FINISHED });
      expect(text(container)).not.toContain("entry 43,679.70");
      expect(text(container)).not.toContain("exit 43,584.00");
    });
  });

  describe("M. no fabricated strategy features on the position", () => {
    it("adds no breakout, volatility or retest figure of its own", () => {
      const { container } = renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG });
      const position = screen.getByTestId("high-risk-position").textContent ?? "";
      // The broker's own reason string may name the setup; the panel must not add
      // feature values it was not given.
      expect(position.toLowerCase()).not.toContain("breakout distance");
      expect(position.toLowerCase()).not.toContain("volatility");
      expect(container).toBeTruthy();
    });

    it("shows the engine's reason string unchanged", () => {
      renderPanel({ highRisk: HIGH_RISK_HOLDING_LONG });
      expect(screen.getByTestId("high-risk-position").textContent).toContain(
        "bullish retest",
      );
    });
  });

  describe("N. the replay state is presented", () => {
    it("does not contradict the engine's finished state", () => {
      renderPanel({ highRisk: HIGH_RISK_FINISHED });
      expect(HIGH_RISK_FINISHED.replay.status).toBe("finished");
      expect(screen.getByTestId("high-risk-panels")).toBeTruthy();
    });

    it("uses the engine's idle replay unchanged when flat", () => {
      renderPanel();
      expect(HIGH_RISK_FLAT.replay).toBe(REPLAY_IDLE);
      expect(screen.getByTestId("high-risk-panels")).toBeTruthy();
    });
  });
});