/**
 * Manual panel tests (Phase 25B).
 *
 * ## What is being protected
 *
 * Manual shows the user a price and three buttons that place simulated trades. That is
 * the combination most likely to be misread as a broker, so the tests are mostly about
 * what the panel must *not* do or imply.
 *
 * - It must not present the execution preview as a quote. The engine's `preview_note`
 *   says "Preview — not a fill price" and the panel renders it **verbatim**; a locally
 *   reworded caveat would be a second claim to keep in step with the server.
 * - It must not present the size estimate as a committed position. Nothing is committed
 *   until the replay steps.
 * - It must say PAPER on every action button, and carry the paper-only banner.
 * - It must compute no P&L, no balance and no fill price.
 * - It must refuse to submit an unusable size rather than clamping it.
 * - It must state *why* a button is disabled. A disabled control with no reason is
 *   indistinguishable from a broken one.
 *
 * Assertions are on text content and attributes only, matching `components.test.tsx`.
 */

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ManualPanel } from "@/components/manual-panels";
import { PaperApi } from "@/lib/api";

import {
  MANUAL_FINISHED,
  MANUAL_FLAT,
  MANUAL_HOLDING_LONG,
  MANUAL_NOTE,
  MANUAL_PENDING,
  MANUAL_PREVIEW_NOTE,
  MANUAL_WITH_TRADE,
  REPLAY_IDLE,
  httpError,
  networkError,
} from "./fixtures";

function text(container: HTMLElement): string {
  return (container.textContent ?? "").toLowerCase();
}

/** Render the panel with sensible defaults and a spy for submissions. */
function renderPanel(
  props: Partial<Parameters<typeof ManualPanel>[0]> = {},
  onSubmit: Parameters<typeof ManualPanel>[0]["onSubmit"] = vi.fn(),
) {
  const merged = {
    manual: MANUAL_FLAT as Parameters<typeof ManualPanel>[0]["manual"],
    isLoading: false,
    error: null as Parameters<typeof ManualPanel>[0]["error"],
    onSubmit,
    onCancel: vi.fn(),
    isSubmitting: false,
    isCancelling: false,
    actionError: null as Parameters<typeof ManualPanel>[0]["actionError"],
    ...props,
  };

  const view = render(<ManualPanel {...merged} />);

  return { ...view, onSubmit, onCancel: merged.onCancel };
}

describe("ManualPanel — the paper-only framing", () => {
  it("carries the paper-only banner", () => {
    const { container } = renderPanel();

    expect(text(container)).toContain("paper");
  });

  it("labels every action button PAPER", () => {
    renderPanel({ manual: MANUAL_FLAT });

    for (const id of ["manual-buy", "manual-sell"]) {
      expect(text(screen.getByTestId(id))).toContain("paper");
    }
  });

  it("labels the exit button PAPER as well", () => {
    renderPanel({ manual: MANUAL_HOLDING_LONG });

    expect(text(screen.getByTestId("manual-exit"))).toContain("paper");
  });

  it("renders the engine's paper-only note verbatim", () => {
    renderPanel();

    expect(screen.getByTestId("manual-note-text").textContent).toBe(MANUAL_NOTE);
  });

  it("states that nothing happens unless the user asks", () => {
    // The one behaviour that differs from every other mode. Without it, a position
    // that survives a thousand bars reads as a frozen dashboard.
    const { container } = renderPanel();

    const rendered = text(container);

    expect(rendered).toContain("unless you ask");
    expect(rendered).toContain("switched off");
  });

  it("mentions no exchange, wallet or real order", () => {
    const { container } = renderPanel();
    const rendered = text(container);

    expect(rendered).toContain("no real order");
    for (const forbidden of ["binance", "coinbase", "api key", "withdraw", "deposit"]) {
      expect(rendered).not.toContain(forbidden);
    }
  });
});

describe("ManualPanel — the preview is not a quote", () => {
  it("renders the engine's preview note verbatim", () => {
    renderPanel({ manual: MANUAL_PENDING });

    expect(screen.getByTestId("manual-preview-note").textContent).toBe(
      MANUAL_PREVIEW_NOTE,
    );
  });

  it("says explicitly that it is not a fill price", () => {
    renderPanel({ manual: MANUAL_PENDING });

    expect(
      text(screen.getByTestId("manual-preview-note")),
    ).toContain("not a fill price");
  });

  it("shows the engine's preview price unchanged", () => {
    renderPanel({ manual: MANUAL_PENDING });

    expect(
      text(screen.getByTestId("manual-preview-price")),
    ).toContain("43,679.70");
  });

  it("explains that stepping is what fills the action", () => {
    const { container } = renderPanel({ manual: MANUAL_PENDING });

    expect(text(container)).toContain("must step");
  });

  it("shows no preview when no bar remains", () => {
    renderPanel({ manual: MANUAL_FINISHED });

    expect(screen.queryByTestId("manual-preview")).toBeNull();
  });
});

describe("ManualPanel — an action is a request, not a fill", () => {
  it("shows the pending action and its size", () => {
    renderPanel({ manual: MANUAL_PENDING });

    const pending = screen.getByTestId("manual-pending");

    expect(text(pending)).toContain("enter_long");
    expect(text(pending)).toContain("25.00%");
  });

  it("shows no position while an action is pending", () => {
    // The fixture's `open_position` is null, and the panel must not imply otherwise.
    renderPanel({ manual: MANUAL_PENDING });

    expect(screen.getByTestId("manual-position")).toBeDefined();
    expect(text(screen.getByTestId("manual-position"))).toContain("flat");
  });

  it("does not show a pending panel when nothing is pending", () => {
    renderPanel({ manual: MANUAL_FLAT });

    expect(screen.queryByTestId("manual-pending")).toBeNull();
  });

  it("offers a cancel control while an action is pending", () => {
    renderPanel({ manual: MANUAL_PENDING });

    expect(screen.getByTestId("manual-cancel")).toBeDefined();
  });

  it("reports a replaced pending action", () => {
    renderPanel({
      manual: { ...MANUAL_PENDING, paper_note: "a pending ENTER_LONG was replaced" },
    });

    expect(text(screen.getByTestId("manual-paper-note"))).toContain("replaced");
  });
});

describe("ManualPanel — sizing", () => {
  it("starts with no size and therefore no enabled entry", () => {
    renderPanel({ manual: MANUAL_FLAT });

    expect((screen.getByTestId("manual-size-input") as HTMLInputElement).value).toBe(
      "",
    );
    expect((screen.getByTestId("manual-buy") as HTMLButtonElement).disabled).toBe(true);
  });

  it("enables both entries once a size is typed", () => {
    renderPanel({ manual: MANUAL_FLAT });

    fireEvent.change(screen.getByTestId("manual-size-input"), {
      target: { value: "10" },
    });

    expect((screen.getByTestId("manual-buy") as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByTestId("manual-sell") as HTMLButtonElement).disabled).toBe(false);
  });

  it("submits the typed size as a fraction, not a percentage number", () => {
    const { onSubmit } = renderPanel({ manual: MANUAL_FLAT });

    fireEvent.change(screen.getByTestId("manual-size-input"), {
      target: { value: "25" },
    });
    fireEvent.click(screen.getByTestId("manual-buy"));

    // 25% submitted as 0.25, matching the engine's contract.
    expect(onSubmit).toHaveBeenCalledWith("ENTER_LONG", 0.25);
  });

  it("submits the short side too", () => {
    const { onSubmit } = renderPanel({ manual: MANUAL_FLAT });

    fireEvent.change(screen.getByTestId("manual-size-input"), {
      target: { value: "10" },
    });
    fireEvent.click(screen.getByTestId("manual-sell"));

    expect(onSubmit).toHaveBeenCalledWith("ENTER_SHORT", 0.1);
  });

  it.each([
  ["0"],
  ["-1"],
  // 150% of cash, above the ceiling. Note 1.5 is NOT invalid: read as a percent it is
  // 1.5% of cash, which the engine accepts as the fraction 0.015.
  ["150"],
  ["abc"],
  [""],
  ["1e400"],
  ["12.5.6"],
])("refuses to submit an unusable size (%s)", (value) => {
  const { onSubmit } = renderPanel({ manual: MANUAL_FLAT });

  fireEvent.change(screen.getByTestId("manual-size-input"), {
    target: { value },
  });
  fireEvent.click(screen.getByTestId("manual-buy"));

  expect(onSubmit).not.toHaveBeenCalled();
});

it("accepts a fractional percentage and converts it to the engine's fraction", () => {
  const { onSubmit } = renderPanel({ manual: MANUAL_FLAT });

  fireEvent.change(screen.getByTestId("manual-size-input"), {
    target: { value: "1.5" },
  });
  fireEvent.click(screen.getByTestId("manual-buy"));

  // 1.5% read as a percent, sent as the fraction 0.015. Sending 1.5 would ask for
  // 150% of cash.
  expect(onSubmit).toHaveBeenCalledWith("ENTER_LONG", 0.015);
});

  it("explains an unusable size instead of submitting it silently", () => {
    renderPanel({ manual: MANUAL_FLAT });

    fireEvent.change(screen.getByTestId("manual-size-input"), {
      target: { value: "0" },
    });

    expect(screen.getByTestId("manual-size-invalid")).toBeDefined();
  });

  it("shows an estimated notional, labelled as an estimate", () => {
    renderPanel({ manual: MANUAL_FLAT });

    fireEvent.change(screen.getByTestId("manual-size-input"), {
      target: { value: "50" },
    });

    const estimate = screen.getByTestId("manual-estimate");

    // 50% of 10,000.
    expect(text(screen.getByTestId("manual-estimate-value"))).toContain("5,000.00");
    expect(text(estimate)).toContain("estimate");
  });

  it("does not present the estimate as an open position", () => {
    const { container } = renderPanel({ manual: MANUAL_FLAT });

    fireEvent.change(screen.getByTestId("manual-size-input"), {
      target: { value: "50" },
    });

    expect(text(screen.getByTestId("manual-estimate"))).toContain(
      "no position is opened until the replay steps",
    );
    expect(text(screen.getByTestId("manual-position"))).toContain("flat");
    expect(container).toBeDefined();
  });

  it("shows no estimate before a size is typed", () => {
    renderPanel({ manual: MANUAL_FLAT });

    expect(text(screen.getByTestId("manual-estimate-value"))).toContain("—");
  });
});

describe("ManualPanel — the action set follows engine state", () => {
  it("offers both entries and no exit when flat", () => {
    renderPanel({ manual: MANUAL_FLAT });

    expect((screen.getByTestId("manual-buy") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId("manual-exit") as HTMLButtonElement).disabled).toBe(true);
  });

  it("offers only the exit while a position is open", () => {
    renderPanel({ manual: MANUAL_HOLDING_LONG });

    expect((screen.getByTestId("manual-exit") as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByTestId("manual-buy") as HTMLButtonElement).disabled).toBe(true);
  });

  it("explains that a direct reversal is not supported", () => {
    const { container } = renderPanel({ manual: MANUAL_HOLDING_LONG });

    const rendered = text(container);

    expect(rendered).toContain("does not support a direct reversal");
    expect(rendered).toContain("exit it before entering the other side");
  });

  it("submits an exit with no size", () => {
    const { onSubmit } = renderPanel({ manual: MANUAL_HOLDING_LONG });

    fireEvent.click(screen.getByTestId("manual-exit"));

    // No size argument at all: the engine refuses a size on an exit rather than
    // ignoring one, so the client must not invent it.
    expect(onSubmit).toHaveBeenCalledWith("EXIT");
  });

  it("disables everything on a finished replay", () => {
    renderPanel({ manual: MANUAL_FINISHED });

    for (const id of ["manual-buy", "manual-sell", "manual-exit"]) {
      expect((screen.getByTestId(id) as HTMLButtonElement).disabled).toBe(true);
    }
  });

  it("explains that a finished replay needs a reset", () => {
    renderPanel({ manual: MANUAL_FINISHED });

    expect(text(screen.getByTestId("manual-unavailable"))).toContain("reset");
  });
});

describe("ManualPanel — figures come from the API", () => {
  it("shows the engine's cash, realized P&L and trade count", () => {
    renderPanel({ manual: MANUAL_WITH_TRADE });

    expect(text(screen.getByTestId("manual-cash"))).toContain("10,029.52");
    expect(text(screen.getByTestId("manual-realized"))).toContain("+29.52");
    expect(text(screen.getByTestId("manual-trade-count"))).toContain("1");
  });

  it("shows the open position's entry price and quantity", () => {
    renderPanel({ manual: MANUAL_HOLDING_LONG });

    expect(text(screen.getByTestId("manual-entry-price"))).toContain("43,679.70");
    expect(text(screen.getByTestId("manual-bars-held"))).toContain("3");
  });

  it("shows no unrealized or equity figure anywhere", () => {
    // The engine has no live price feed, so any such number would have to be invented.
    const { container } = renderPanel({ manual: MANUAL_HOLDING_LONG });
    const rendered = text(container);

    for (const forbidden of [
      "unrealized",
      "unrealised",
      "equity",
      "mark price",
      "notional",
    ]) {
      expect(rendered).not.toContain(forbidden);
    }
  });

  it("shows no fabricated strategy features on a manual position", () => {
    renderPanel({ manual: MANUAL_HOLDING_LONG });

    const position = text(screen.getByTestId("manual-position"));

    expect(position).not.toContain("breakout");
    expect(position).not.toContain("volatility");
  });

  it("renders the journal with the user's exit reason", () => {
    renderPanel({ manual: MANUAL_WITH_TRADE });

    const journal = text(screen.getByTestId("manual-journal"));

    expect(journal).toContain("manual");
    expect(journal).toContain("held 1 bar");
    expect(journal).toContain("+118.54");
  });

  it("shows an empty state when nothing has been closed", () => {
    const { container } = renderPanel({ manual: MANUAL_FLAT });

    expect(screen.queryByTestId("manual-journal")).toBeNull();
    expect(text(container)).toContain("no closed trades");
  });
});

describe("ManualPanel — refusals are shown, not swallowed", () => {
  it("shows the engine's refusal message verbatim", () => {
    renderPanel({
      manual: MANUAL_FLAT,
      actionError: httpError("NO_PAPER_CASH", "paper cash is zero or below", 409),
    });

    expect(text(screen.getByTestId("manual-error"))).toContain(
      "paper cash is zero or below",
    );
  });

  it("shows a Pydantic body error, which arrives as a list", () => {
    // Two error shapes reach this panel: the engine's `{code, message}` and, for a
    // malformed body, FastAPI's list. The panel reads both, because `toApiError` folds
    // the list into `message` but a hand-built error carrying `detail` must not render
    // as a blank box.
    renderPanel({
      manual: MANUAL_FLAT,
      actionError: {
        kind: "http",
        status: 422,
        code: "VALIDATION_ERROR",
        message: "size_pct must be a fraction, not a boolean",
      },
    });

    expect(text(screen.getByTestId("manual-error"))).toContain(
      "size_pct must be a fraction",
    );
  });

  it("reports an unreachable service instead of showing figures", () => {
    renderPanel({ manual: undefined, error: networkError() });

    expect(screen.queryByTestId("manual-cash")).toBeNull();
    expect(screen.queryByTestId("manual-body")).toBeNull();
  });

  it("shows a loading state without inventing an account", () => {
    renderPanel({ manual: undefined, isLoading: true });

    expect(screen.queryByTestId("manual-cash")).toBeNull();
  });
});

describe("PaperApi manual routes", () => {
  it("reads the mode's own route", async () => {
    const seen: string[] = [];
    const api = new PaperApi({
      baseUrl: "http://127.0.0.1:8000/",
      fetchImpl: (async (input: RequestInfo | URL) => {
        seen.push(String(input));

        return new Response(JSON.stringify(MANUAL_FLAT), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof globalThis.fetch,
    });

    const result = await api.getManual();

    expect(seen[0]).toContain("/api/manual");
    expect(seen[0]).toContain("mode=manual");
    expect(result.mode).toBe("manual");
    expect(result.replay.status).toBe(REPLAY_IDLE.status);
  });

  it("posts an action as a JSON body carrying the size", async () => {
    const seen: { url: string; body: string }[] = [];
    const api = new PaperApi({
      baseUrl: "http://127.0.0.1:8000/",
      fetchImpl: (async (input: RequestInfo | URL, init?: RequestInit) => {
        seen.push({ url: String(input), body: String(init?.body ?? "") });

        return new Response(JSON.stringify(MANUAL_PENDING), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof globalThis.fetch,
    });

    const result = await api.submitManualAction("ENTER_LONG", 0.25);

    expect(seen[0].url).toContain("/api/manual/action");
    expect(seen[0].body).toBe('{"action":"ENTER_LONG","size_pct":0.25}');
    expect(result.pending_action).not.toBeNull();
  });

  it("omits the size entirely for an exit", async () => {
    const seen: string[] = [];
    const api = new PaperApi({
      baseUrl: "http://127.0.0.1:8000/",
      fetchImpl: (async (_input: RequestInfo | URL, init?: RequestInit) => {
        seen.push(String(init?.body ?? ""));

        return new Response(JSON.stringify(MANUAL_FLAT), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof globalThis.fetch,
    });

    await api.submitManualAction("EXIT");

    // Not `size_pct: null` and not `size_pct: 0`. The engine refuses a size on an exit
    // rather than ignoring it, so the client must not invent one.
    expect(seen[0]).toBe('{"action":"EXIT"}');
  });

  it("sends an out-of-range size unaltered rather than clamping it", async () => {
    // A silently trimmed size is the one outcome a user choosing a number cannot
    // detect, so the value goes to the server and its refusal is surfaced.
    const sent: string[] = [];
    const api = new PaperApi({
      baseUrl: "http://127.0.0.1:8000/",
      fetchImpl: (async (_input: RequestInfo | URL, init?: RequestInit) => {
        sent.push(String(init?.body ?? ""));

        return new Response(JSON.stringify(MANUAL_FLAT), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof globalThis.fetch,
    });

    await api.submitManualAction("ENTER_LONG", 1.5);

    expect(sent[0]).toBe('{"action":"ENTER_LONG","size_pct":1.5}');
  });

  it("cancels through its own route", async () => {
    const seen: string[] = [];
    const api = new PaperApi({
      baseUrl: "http://127.0.0.1:8000/",
      fetchImpl: (async (input: RequestInfo | URL) => {
        seen.push(String(input));

        return new Response(JSON.stringify(MANUAL_FLAT), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof globalThis.fetch,
    });

    await api.cancelManualAction();

    expect(seen[0]).toContain("/api/manual/cancel");
  });
});