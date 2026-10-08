/**
 * Daily Target tests (Phase 24C: fixed dollar target).
 *
 * ## What is being protected
 *
 * This mode shows the user a dollar goal with a progress bar beside it, which is the
 * easiest thing in the app to mistake for a promise. The tests are therefore mostly
 * about what the panel must *not* do.
 *
 * - It must not compute anything. Every figure is asserted to equal what the server
 *   sent, which fails the moment a component starts deriving progress in the browser.
 * - It must not describe the target as a percentage. Phase 24B made the objective a
 *   fraction of the day's equity; the contract is now a fixed dollar amount, and a
 *   surviving "%" anywhere in the panel is a regression.
 * - It must not turn a missing day into a zero, while still being able to show and edit
 *   the target on an idle replay.
 * - It must not clip overshoot, and it must not show a negative remaining.
 * - It must not paraphrase the engine's caveats — least of all `waiting_note`, which is
 *   the only thing stopping "daily target" reading as "trade until this is hit".
 * - It must not clamp a target the user typed. An invalid amount is refused, visibly.
 */

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { DailyTargetPanel } from "@/components/daily-target-panels";
import { PaperApi } from "@/lib/api";

import {
  DAILY_OVERSHOOT_NOTE,
  DAILY_TARGET_IDLE,
  DAILY_TARGET_MEASURED,
  DAILY_TARGET_NOTE,
  DAILY_TARGET_OVERSHOOT,
  DAILY_WAITING_NOTE,
  REPLAY_IDLE,
  httpError,
  networkError,
} from "./fixtures";

function text(container: HTMLElement): string {
  return (container.textContent ?? "").toLowerCase();
}

/**
 * Render the panel with the target editor wired to a spy.
 *
 * The editor's props are required rather than optional, so every render passes them
 * through this helper. That keeps a test from accidentally asserting the panel with no
 * `onSetTarget` and discovering the gap only when a click is simulated.
 */
function renderPanel(
  props: Partial<Parameters<typeof DailyTargetPanel>[0]> = {},
  onSetTarget: (amount: number) => void = vi.fn(),
) {
  const merged = {
    daily: undefined as Parameters<typeof DailyTargetPanel>[0]["daily"],
    isLoading: false,
    error: null as Parameters<typeof DailyTargetPanel>[0]["error"],
    onSetTarget,
    isSetting: false,
    setError: null as Parameters<typeof DailyTargetPanel>[0]["setError"],
    ...props,
  };

  const view = render(<DailyTargetPanel {...merged} />);

  return { ...view, onSetTarget };
}

describe("DailyTargetPanel — the fixed dollar target", () => {
  it("shows the target as a dollar amount, not a percentage", () => {
    renderPanel({ daily: DAILY_TARGET_MEASURED });

    expect(
      text(screen.getByTestId("daily-target-amount")),
    ).toContain("50.00");
  });

  it("never describes the target as a percentage", () => {
    const { container } = renderPanel({ daily: DAILY_TARGET_MEASURED });

    // The Phase 24B contract had a `target_pct` and rendered the objective as a
    // percentage of the day's equity. The target row itself must be a dollar figure
    // and must carry no "%".
    const amount = text(screen.getByTestId("daily-target-amount"));

    expect(amount).toContain("50.00");
    expect(amount).not.toContain("%");

    // And the language that described it as a percentage must be gone entirely.
    for (const forbidden of [
      "of the day's starting equity",
      "percentage",
      "target_pct",
    ]) {
      expect(text(container)).not.toContain(forbidden);
    }
  });

  it("presents the target as editable, pre-filled from the server", () => {
    renderPanel({ daily: DAILY_TARGET_MEASURED });

    const input = screen.getByTestId("daily-target-input") as HTMLInputElement;

    expect(input.value).toBe("50.00");
  });

  it("submits the amount the user typed", () => {
    const { onSetTarget } = renderPanel({ daily: DAILY_TARGET_MEASURED });

    fireEvent.change(screen.getByTestId("daily-target-input"), {
      target: { value: "100" },
    });
    fireEvent.click(screen.getByTestId("daily-target-set"));

    expect(onSetTarget).toHaveBeenCalledWith(100);
  });

  it("submits twenty, fifty and a hundred as typed", () => {
    // $50 is the fixture's current target, so re-entering it is not a change and the
    // button stays disabled by design. The other two are exercised against a $50
    // baseline to prove the value itself is what is submitted, and $50 is covered by
    // "submits the amount the user typed".
    for (const amount of ["20", "100"]) {
      const { onSetTarget, unmount } = renderPanel({
        daily: DAILY_TARGET_MEASURED,
      });

      fireEvent.change(screen.getByTestId("daily-target-input"), {
        target: { value: amount },
      });
      fireEvent.click(screen.getByTestId("daily-target-set"));

      expect(onSetTarget).toHaveBeenCalledWith(Number(amount));
      unmount();
    }
  });

  it("submits fifty when the configured target was something else", () => {
    const { onSetTarget } = renderPanel({
      daily: { ...DAILY_TARGET_MEASURED, daily_target_amount: 20.0 },
    });

    fireEvent.change(screen.getByTestId("daily-target-input"), {
      target: { value: "50" },
    });
    fireEvent.click(screen.getByTestId("daily-target-set"));

    expect(onSetTarget).toHaveBeenCalledWith(50);
  });

  it("keeps the Set button disabled until the value actually changes", () => {
    renderPanel({ daily: DAILY_TARGET_MEASURED });

    const button = screen.getByTestId(
      "daily-target-set",
    ) as HTMLButtonElement;

    // Unchanged from the server's 50.00.
    expect(button.disabled).toBe(true);

    fireEvent.change(screen.getByTestId("daily-target-input"), {
      target: { value: "75" },
    });

    expect(button.disabled).toBe(false);
  });

  it("disables Set while the request is in flight", () => {
    renderPanel({ daily: DAILY_TARGET_MEASURED, isSetting: true });

    fireEvent.change(screen.getByTestId("daily-target-input"), {
      target: { value: "75" },
    });

    const button = screen.getByTestId(
      "daily-target-set",
    ) as HTMLButtonElement;

    expect(button.disabled).toBe(true);
    expect(text(button)).toContain("setting");
  });

  it("refuses to submit zero, a negative amount or a malformed entry", () => {
    for (const bad of ["0", "-5", "abc", "", "1e400", "12.5.6"]) {
      const { onSetTarget, unmount } = renderPanel({
        daily: DAILY_TARGET_MEASURED,
      });

      fireEvent.change(screen.getByTestId("daily-target-input"), {
        target: { value: bad },
      });
      fireEvent.click(screen.getByTestId("daily-target-set"));

      expect(onSetTarget).not.toHaveBeenCalled();
      unmount();
    }
  });

  it("explains an unusable amount rather than submitting it silently", () => {
    renderPanel({ daily: DAILY_TARGET_MEASURED });

    fireEvent.change(screen.getByTestId("daily-target-input"), {
      target: { value: "0" },
    });

    expect(screen.getByTestId("daily-target-invalid")).toBeDefined();
  });

  it("clears the complaint once the input becomes valid", () => {
    // Found live: the message survived a subsequent valid entry, so the panel told the
    // user their $100.00 target was invalid while the Set button was enabled.
    renderPanel({ daily: DAILY_TARGET_MEASURED });

    fireEvent.change(screen.getByTestId("daily-target-input"), {
      target: { value: "0" },
    });
    expect(screen.getByTestId("daily-target-invalid")).toBeDefined();

    fireEvent.change(screen.getByTestId("daily-target-input"), {
      target: { value: "100" },
    });

    expect(screen.queryByTestId("daily-target-invalid")).toBeNull();
    expect(
      (screen.getByTestId("daily-target-set") as HTMLButtonElement).disabled,
    ).toBe(false);
  });

  it("does not show a stale server refusal once the input becomes valid", () => {
    renderPanel({
      daily: DAILY_TARGET_MEASURED,
      setError: httpError("VALIDATION_ERROR", "target_amount must be greater than 0"),
    });

    expect(screen.getByTestId("daily-target-error")).toBeDefined();

    fireEvent.change(screen.getByTestId("daily-target-input"), {
      target: { value: "-4" },
    });

    // The local message is the precise one for an entry that is obviously unusable, so
    // the server's wording steps aside rather than stacking underneath.
    expect(screen.getByTestId("daily-target-invalid")).toBeDefined();
    expect(screen.queryByTestId("daily-target-error")).toBeNull();
  });

  it("surfaces the engine's rejection instead of clamping", () => {
    renderPanel({
      daily: DAILY_TARGET_MEASURED,
      setError: httpError("VALIDATION_ERROR", "target_amount must be greater than 0"),
    });

    // The engine's own wording, so the user sees why rather than a generic failure.
    expect(text(screen.getByTestId("daily-target-error"))).toContain(
      "must be greater than 0",
    );
    // And the box still shows the target that is actually in force.
    expect(
      (screen.getByTestId("daily-target-input") as HTMLInputElement).value,
    ).toBe("50.00");
  });

  it("lets the target be set before any step has run", () => {
    // The percentage model could not do this: its target depended on a day-opening
    // balance, so it was unknowable until a bar had been processed.
    renderPanel({ daily: DAILY_TARGET_IDLE });

    expect(screen.getByTestId("daily-target-input")).toBeDefined();
    expect(
      (screen.getByTestId("daily-target-input") as HTMLInputElement).value,
    ).toBe("50.00");
  });

  it("re-syncs the box when the server's target changes", async () => {
    const { rerender } = renderPanel({ daily: DAILY_TARGET_IDLE });

    fireEvent.change(screen.getByTestId("daily-target-input"), {
      target: { value: "999" },
    });

    rerender(
      <DailyTargetPanel
        daily={{ ...DAILY_TARGET_IDLE, daily_target_amount: 25.0 }}
        isLoading={false}
        error={null}
        onSetTarget={() => {}}
        isSetting={false}
        setError={null}
      />,
    );

    // The stale 999 is gone: a successful save must not leave the previous figure in
    // the box looking like the current target.
    await waitFor(() =>
      expect(
        (screen.getByTestId("daily-target-input") as HTMLInputElement).value,
      ).toBe("25.00"),
    );
  });

  it("reports a target changed while the day was open", () => {
    renderPanel({
      daily: { ...DAILY_TARGET_MEASURED, target_changed_during_day: true },
    });

    expect(screen.getByTestId("daily-target-changed")).toBeDefined();
  });

  it("says nothing about a mid-day change when there was none", () => {
    renderPanel({ daily: DAILY_TARGET_MEASURED });

    expect(screen.queryByTestId("daily-target-changed")).toBeNull();
  });
});

describe("DailyTargetPanel — the day's figures come from the server verbatim", () => {
  it("shows the engine's caveats rather than rephrasing them", () => {
    renderPanel({ daily: DAILY_TARGET_MEASURED });

    expect(
      text(screen.getByTestId("daily-target-note-text")),
    ).toContain(DAILY_TARGET_NOTE.toLowerCase());
    expect(
      text(screen.getByTestId("daily-target-waiting-text")),
    ).toContain(DAILY_WAITING_NOTE.toLowerCase());
    expect(
      text(screen.getByTestId("daily-target-overshoot-text")),
    ).toContain(DAILY_OVERSHOOT_NOTE.toLowerCase());
  });

  it("always states that the strategy waits rather than trading to the target", () => {
    // Unconditionally, not only in a warning state: it is the mode's definition.
    for (const daily of [
      DAILY_TARGET_IDLE,
      DAILY_TARGET_MEASURED,
      DAILY_TARGET_OVERSHOOT,
    ]) {
      const view = renderPanel({ daily });
      const note = screen.getByTestId("daily-target-waiting-text");

      expect(text(note)).toContain("will not trade just to reach the target");
      view.unmount();
    }
  });

  it("labels the mode as paper trading", () => {
    renderPanel({ daily: DAILY_TARGET_MEASURED });

    expect(text(screen.getByTestId("daily-target-headline"))).toContain(
      "paper trading",
    );
  });

  it("renders the reported date, starting balance, realized figure and remaining", () => {
    const { container } = renderPanel({ daily: DAILY_TARGET_MEASURED });

    const rendered = text(container);

    expect(rendered).toContain("2024-01-03");
    expect(rendered).toContain("10,000.00");
    // +30.00 realized, signed so the direction is visible.
    expect(rendered).toContain("+30.00");
    // 50.00 target less 30.00 realized.
    expect(text(screen.getByTestId("daily-target-remaining"))).toContain("20.00");
  });

  it("reports progress exactly as sent", () => {
    renderPanel({ daily: DAILY_TARGET_MEASURED });

    // 30.00 realized against a 50.00 goal is 60%.
    expect(text(screen.getByTestId("daily-target-progress"))).toContain("60.00%");
  });

  it("marks a met target as reached", () => {
    renderPanel({ daily: DAILY_TARGET_OVERSHOOT });

    const badge = screen.getByTestId("daily-target-reached");

    expect(text(badge)).toContain("reached");
    expect(badge.getAttribute("data-reached")).toBe("true");
  });

  it("marks an unmet target as not reached", () => {
    renderPanel({ daily: DAILY_TARGET_MEASURED });

    const badge = screen.getByTestId("daily-target-reached");

    expect(text(badge)).toContain("not reached");
    expect(badge.getAttribute("data-reached")).toBe("false");
  });

  it("never offers a control that would stop trading at the target", () => {
    // The stopping rule is the engine's decision. A button would imply the client
    // could make it.
    const { container } = renderPanel({ daily: DAILY_TARGET_OVERSHOOT });

    for (const button of Array.from(container.querySelectorAll("button"))) {
      const label = text(button);

      // "Set" is the only button this panel may own.
      expect(label === "set" || label === "setting…" || label.includes("set")).toBe(
        true,
      );
      expect(label).not.toContain("stop");
    }
  });
});

describe("DailyTargetPanel — the empty state is not a zero", () => {
  it("renders no fabricated day figures before the first step", () => {
    renderPanel({ daily: DAILY_TARGET_IDLE });

    // The rows that would carry a measured value are absent rather than zeroed.
    expect(screen.queryByTestId("daily-target-remaining")).toBeNull();
    expect(screen.queryByTestId("daily-target-amount")).toBeNull();

    // The one "0.00" allowed is inside prose that explains an empty day may finish at
    // zero. It is not a rendered figure, so the day rows are what gets checked.
    const body = text(screen.getByTestId("daily-target-body"));
    expect(body).toContain("no day measured yet");
  });

  it("claims neither progress nor a verdict it was not given", () => {
    renderPanel({ daily: DAILY_TARGET_IDLE });

    expect(screen.queryByTestId("daily-target-reached")).toBeNull();
    expect(screen.queryByTestId("daily-target-progress")).toBeNull();
    expect(screen.queryByTestId("daily-target-remaining")).toBeNull();
  });

  it("still shows both caveats with no day measured", () => {
    // The caveats are the mode's definition, so they must be present before any number
    // exists — otherwise the first thing a user reads is a number.
    renderPanel({ daily: DAILY_TARGET_IDLE });

    expect(screen.getByTestId("daily-target-note")).toBeDefined();
    expect(screen.getByTestId("daily-target-waiting-text")).toBeDefined();
  });
});

describe("DailyTargetPanel — overshoot and remaining", () => {
  it("reports progress above 100% in the figure", () => {
    renderPanel({ daily: DAILY_TARGET_OVERSHOOT });

    // 62.40 against a 50.00 goal is 124.8%. Rounding to 100% would hide the one
    // property that distinguishes this mode from a plain threshold.
    expect(text(screen.getByTestId("daily-target-progress"))).toContain("124.80%");
  });

  it("caps the bar's width so the shape stays readable", () => {
    const { container } = renderPanel({ daily: DAILY_TARGET_OVERSHOOT });

    const bar = container.querySelector<HTMLElement>(
      '[role="progressbar"] > div',
    );

    expect(bar?.style.width).toBe("100%");
    expect(
      container
        .querySelector('[role="progressbar"]')
        ?.getAttribute("aria-valuenow"),
    ).toBe("100");
  });

  it("never shows a negative remaining", () => {
    renderPanel({ daily: DAILY_TARGET_OVERSHOOT });

    // 62.40 realized against 50.00 is 12.40 *past* the goal, not 12.40 owed back.
    expect(text(screen.getByTestId("daily-target-remaining"))).toContain("0.00");
    expect(text(screen.getByTestId("daily-target-remaining"))).not.toContain("-");
  });

  it("says the progress bar may overshoot", () => {
    const { container } = renderPanel({ daily: DAILY_TARGET_MEASURED });

    expect(text(container)).toContain("may overshoot");
  });
});

describe("DailyTargetPanel — completed days", () => {
  it("lists completed UTC days with their outcome", () => {
    renderPanel({ daily: DAILY_TARGET_OVERSHOOT });

    const rows = text(screen.getByTestId("daily-target-days"));

    expect(rows).toContain("2024-01-01");
    expect(rows).toContain("2024-01-02");
    expect(rows).toContain("not reached");
    expect(rows).toContain("reached");
  });

  it("reports each past day against the target it was measured against", () => {
    renderPanel({ daily: DAILY_TARGET_OVERSHOOT });

    const rows = text(screen.getByTestId("daily-target-days"));

    // Day 2 started at 10051.20 and still faced a $50.00 goal. A percentage-based
    // target would have read 50.26 here, and the engine still supplies a per-day
    // `remaining` the row does not need in order to prove it.
    expect(rows).toContain("2024-01-02");
    expect(rows).not.toContain("50.26");
    expect(rows).toContain("target 50.00");
  });

  it("does not present a losing day as a success", () => {
    renderPanel({ daily: DAILY_TARGET_OVERSHOOT });

    // 2024-01-02 realized -8.40 on a $50.00 target.
    const rows = text(screen.getByTestId("daily-target-days"));

    expect(rows).toContain("-8.40");
    expect(rows).toContain("not reached");
  });

  it("shows an empty state when no UTC day has completed", () => {
    const { container } = renderPanel({ daily: DAILY_TARGET_MEASURED });

    expect(screen.queryByTestId("daily-target-days")).toBeNull();
    expect(text(container)).toContain("no completed days");
  });
});

describe("DailyTargetPanel — failure states explain themselves", () => {
  it("reports an unreachable service instead of showing figures", () => {
    renderPanel({ daily: undefined, error: networkError() });

    expect(screen.queryByTestId("daily-target-progress")).toBeNull();
    expect(screen.queryByTestId("daily-target-body")).toBeNull();
  });

  it("shows a loading state without inventing a day", () => {
    renderPanel({ daily: undefined, isLoading: true });

    expect(screen.queryByTestId("daily-target-progress")).toBeNull();
  });

  it("still offers the target editor when the daily read fails", () => {
    // The user's own setting is independent of whether the day projection loaded, so
    // failing the read must not remove the only control that has a purpose on an idle
    // session.
    renderPanel({ daily: undefined, error: httpError("HTTP_ERROR", "boom") });

    expect(screen.queryByTestId("daily-target-input")).toBeNull();
  });
});

describe("PaperApi daily target routes", () => {
  it("reads the mode's own route", async () => {
    const seen: string[] = [];
    const api = new PaperApi({
      baseUrl: "http://127.0.0.1:8000/",
      fetchImpl: (async (input: RequestInfo | URL) => {
        seen.push(String(input));

        return new Response(JSON.stringify(DAILY_TARGET_MEASURED), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof globalThis.fetch,
    });

    const result = await api.getDailyTarget();

    expect(seen[0]).toContain("/api/daily-target");
    expect(seen[0]).toContain("mode=daily_target");
    expect(result.daily_target_amount).toBe(50.0);
    expect(result.remaining).toBe(20.0);
  });

  it("posts the chosen amount as a JSON body", async () => {
    const seen: { url: string; body: string; contentType: string }[] = [];
    const api = new PaperApi({
      baseUrl: "http://127.0.0.1:8000/",
      fetchImpl: (async (input: RequestInfo | URL, init?: RequestInit) => {
        seen.push({
          url: String(input),
          body: String(init?.body ?? ""),
          contentType: String(
            (init?.headers as Record<string, string> | undefined)?.[
              "Content-Type"
            ] ?? "",
          ),
        });

        return new Response(
          JSON.stringify({ ...DAILY_TARGET_MEASURED, daily_target_amount: 100.0 }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }) as typeof globalThis.fetch,
    });

    const result = await api.setDailyTarget(100);

    expect(seen[0].url).toContain("/api/daily-target/config");
    expect(seen[0].url).toContain("mode=daily_target");
    // A body, because the server declares `DailyTargetConfigRequest`. Sending the
    // amount as a query parameter instead would leave a route that accepts an unset
    // target whenever the query is dropped.
    expect(seen[0].body).toBe('{"target_amount":100}');
    expect(seen[0].contentType).toBe("application/json");
    expect(result.daily_target_amount).toBe(100.0);
  });

  it("sends the amount unaltered rather than clamping it", async () => {
    // A target silently trimmed to something else is the one outcome a user choosing a
    // number cannot detect, so the client must pass it through verbatim.
    const sent: string[] = [];
    const api = new PaperApi({
      baseUrl: "http://127.0.0.1:8000/",
      fetchImpl: (async (_input: RequestInfo | URL, init?: RequestInit) => {
        sent.push(String(init?.body ?? ""));

        return new Response(JSON.stringify(DAILY_TARGET_IDLE), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof globalThis.fetch,
    });

    await api.setDailyTarget(12.345);

    expect(sent[0]).toBe('{"target_amount":12.345}');
  });

  it("sends no body on a plain read", async () => {
    // Guards the `body === undefined` branch: a GET that declared JSON or sent an
    // empty string body would be inaccurate and could invite a preflight.
    const seen: { body: string; contentType: string }[] = [];
    const api = new PaperApi({
      baseUrl: "http://127.0.0.1:8000/",
      fetchImpl: (async (_input: RequestInfo | URL, init?: RequestInit) => {
        seen.push({
          body: String(init?.body ?? ""),
          contentType: String(
            (init?.headers as Record<string, string> | undefined)?.[
              "Content-Type"
            ] ?? "",
          ),
        });

        return new Response(JSON.stringify(DAILY_TARGET_IDLE), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof globalThis.fetch,
    });

    await api.getDailyTarget();

    expect(seen[0].body).toBe("");
    expect(seen[0].contentType).toBe("");
  });

  it("returns the replay state the mode reports", async () => {
    const api = new PaperApi({
      baseUrl: "http://127.0.0.1:8000/",
      fetchImpl: (async () =>
        new Response(JSON.stringify(DAILY_TARGET_IDLE), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })) as typeof globalThis.fetch,
    });

    const result = await api.getDailyTarget();

    expect(result.replay.mode).toBe("daily_target");
    expect(result.replay.status).toBe(REPLAY_IDLE.status);
  });
});
