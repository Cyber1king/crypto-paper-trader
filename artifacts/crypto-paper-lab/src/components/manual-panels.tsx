/**
 * Manual's panels (Phase 25B).
 *
 * ## What this renders
 *
 * Only what `GET /api/manual` returned, plus the size the user typed. There is no
 * client-side P&L, no client-side fill price and no client-side account state anywhere
 * in this file. If a figure is not in the response, it is not shown.
 *
 * ## Three things this panel must not do
 *
 * 1. **Present the preview as a quote.** `execution_price_preview` is the next
 *    execution candle's open, and it is the easiest number in this mode to misread as
 *    something already agreed. The engine's `preview_note` is rendered beside it, and it
 *    is rendered **verbatim** rather than reworded — a locally phrased caveat is a
 *    second claim to keep in step with the server.
 *
 * 2. **Compute an estimated notional as if it were a result.** The size preview below is
 *    arithmetic the user can do in their head from two numbers the engine supplied, and
 *    it is labelled *estimate*. It is never presented as a committed position: nothing
 *    is committed until the replay steps and the broker books a fill.
 *
 * 3. **Hide that nothing is automatic.** Manual opens nothing and closes nothing unless
 *    the user asks, which is the one behaviour that differs from every other mode. The
 *    panel states it, so a position that survives a thousand bars does not read as a
 *    frozen dashboard.
 *
 * ## PAPER, everywhere
 *
 * Every action button carries the word. This mode places simulated fills on historical
 * candles, and a button labelled only "BUY" would be the easiest thing on the screen to
 * misread as a real order.
 *
 * ## No client-side arithmetic on money
 *
 * The only arithmetic here is the size *estimate* (`cash * sizePct`) and a progress bar
 * width. Neither produces a P&L, a balance or a fill price.
 */

import { useEffect, useState } from "react";
import { Hand, TrendingDown, TrendingUp } from "lucide-react";

import {
  EmptyPanel,
  ErrorPanel,
  LoadingPanel,
  Panel,
  PaperOnlyBanner,
  Rule,
  StatRow,
} from "@/components/state";
import {
  formatMoney,
  formatPrice,
  formatQuantity,
  formatSignedMoney,
  formatTimestamp,
  isAbsent,
} from "@/lib/format";
import type {
  ApiError,
  ManualStateResponse,
  ManualTrade,
} from "@/lib/api";

/**
 * Parse the size the user typed, and convert it to the engine's fraction.
 *
 * The field is labelled in **percent** because that is how a position size is
 * described, but the engine's contract is a fraction of cash: `0.25` means 25%. The
 * division is the load-bearing line here — sending `25` for a field the user read as
 * "25%" would request twenty-five times the intended position, and the engine would
 * accept it as a valid fraction only if the ceiling were above 25. Since the ceiling is
 * 1.0 it would be refused, so the mistake would surface — but the conversion must be
 * right regardless, and it is asserted below.
 *
 * Returns `null` for anything that is not a number in `(0, max]` percent, which
 * disables the action buttons. Duplicated rather than shared with the server on purpose:
 * the server is the authority, but refusing an obviously invalid entry locally gives
 * faster feedback than a round-trip 422.
 *
 * A blank field is **not** coerced to zero. Zero is a rejected size, and silently
 * submitting it would show a refusal for a number the user never chose.
 */
function parseSize(raw: string, max: number): number | null {
  const trimmed = raw.trim();

  if (trimmed === "") {
    return null;
  }

  // Reject before Number(), so "1e400" (infinity) and "12abc" cannot slip through.
  if (!/^\d*\.?\d+$/.test(trimmed)) {
    return null;
  }

  const percent = Number(trimmed);

  if (!Number.isFinite(percent) || percent <= 0 || percent > max * 100) {
    return null;
  }

  return percent / 100;
}

/** The estimated notional, clearly an estimate and never a committed position. */
function estimateNotional(cash: number, sizePct: number | null): string {
  if (sizePct === null) {
    return "—";
  }

  return formatMoney(cash * sizePct);
}

/** One closed trade. */
function TradeRow({ trade }: { trade: ManualTrade }) {
  const won = (trade.net_pnl ?? 0) >= 0;

  return (
    <div className="flex items-baseline justify-between gap-4 py-1">
      <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider shrink-0">
        {trade.side} · {trade.exit_reason}
        <span className="block normal-case font-normal tracking-normal text-[10px] opacity-70">
          held {trade.bars_held}
          {trade.bars_held === 1 ? " bar" : " bars"}
        </span>
      </span>
      <span
        className={`min-w-0 break-all font-mono font-semibold text-sm text-right ${
          won ? "text-success" : "text-destructive"
        }`}
      >
        {formatSignedMoney(trade.net_pnl)}
        <span className="block text-[10px] font-normal text-muted-foreground">
          entry {formatPrice(trade.entry_price)} · exit{" "}
          {/* `exit_price` is nullable on the engine's type even though a journal entry
              is always closed, so it is narrowed here rather than cast. */}
          {trade.exit_price === null ? "—" : formatPrice(trade.exit_price)}
        </span>
        <span className="block text-[10px] font-normal text-muted-foreground opacity-70">
          costs {formatMoney(trade.costs)}
        </span>
      </span>
    </div>
  );
}

export function ManualPanel({
  manual,
  isLoading,
  error,
  onSubmit,
  onCancel,
  isSubmitting,
  isCancelling,
  actionError,
}: {
  manual: ManualStateResponse | undefined;
  isLoading: boolean;
  error: ApiError | null;
  onSubmit: (action: "ENTER_LONG" | "ENTER_SHORT" | "EXIT", sizePct?: number) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  isCancelling: boolean;
  actionError: ApiError | null;
}) {
  const [draft, setDraft] = useState("");

  const max = manual?.max_size_pct ?? 1;
  const parsed = parseSize(draft, max);
  const busy = isSubmitting || isCancelling;

  // Re-seed the field whenever the authoritative ceiling changes. Keyed on the ceiling
  // rather than on the object so an unrelated refetch does not wipe what the user is
  // typing.
  useEffect(() => {
    setDraft("");
  }, [max]);

  if (error) {
    return <ErrorPanel error={error} title="Manual state unavailable" />;
  }

  if (isLoading) {
    return <LoadingPanel label="Loading manual state" />;
  }

  if (!manual) {
    return (
      <div className="flex flex-col gap-6" data-testid="manual-body">
        <PaperOnlyBanner>Manual paper trading</PaperOnlyBanner>
        <EmptyPanel
          title="No manual state yet"
          hint="The engine reports this mode's paper balance, position and journal."
        />
      </div>
    );
  }

  const actions = manual.available_actions;
  const canEnter = actions.includes("ENTER_LONG");
  const canExit = actions.includes("EXIT");
  const pending = manual.pending_action;

  /*
   * The refusal message. Pydantic reports a malformed *body* as a list of errors while
   * the engine reports a refused *action* as `{code, message}`, so both shapes are read
   * here rather than assuming one. A client that assumed a single shape would render
   * nothing for the failures that matter most — a size the server would not accept.
   */
  const refusalText = (() => {
    if (!actionError) {
      return null;
    }

    const detail = (actionError as unknown as { detail?: unknown }).detail;

    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: string } | undefined;

      return first?.msg ?? "The engine refused that action.";
    }

    return actionError.message;
  })();

  return (
    <div className="flex flex-col gap-6" data-testid="manual-body">
      <PaperOnlyBanner>
        Every action below is a simulated fill on historical candles. No exchange, no
        wallet, no real order.
      </PaperOnlyBanner>

      <Panel
        title="What this mode is"
        icon={<Hand className="w-4 h-4 text-primary" aria-hidden="true" />}
      >
        <div className="p-5 flex flex-col gap-3" data-testid="manual-note">
          <p className="text-xs text-muted-foreground" data-testid="manual-note-text">
            {manual.note}
          </p>
          <Rule />
          <ul className="text-[11px] text-muted-foreground flex flex-col gap-1">
            <li>
              · Nothing opens or closes unless you ask it to. The strategy&apos;s own
              entry and exit rules are switched off.
            </li>
            <li>
              · One paper position, long or short, sized as a percentage of paper cash.
            </li>
            <li>
              · An action is a request. It fills at the next candle&apos;s open when the
              replay steps, and the realised fill is the engine&apos;s.
            </li>
            <li>
              · Capital is never reserved and there is no credit facility, so a position
              cannot be larger than the cash behind it.
            </li>
          </ul>
        </div>
      </Panel>

      {pending ? (
        <Panel
          title="Pending action"
          icon={<Hand className="w-4 h-4 text-warning-foreground" aria-hidden="true" />}
          badge={
            <span
              className="font-mono text-[10px] uppercase tracking-widest text-warning-foreground"
              data-testid="manual-pending-badge"
            >
              Awaiting a bar
            </span>
          }
          description="Requested, not yet filled."
        >
          <div className="p-5 flex flex-col gap-3" data-testid="manual-pending">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <span className="font-mono text-sm font-semibold">
                {pending.action}
                {pending.size_pct === null
                  ? ""
                  : ` at ${(pending.size_pct * 100).toFixed(2)}% of cash`}
              </span>
              <button
                type="button"
                data-testid="manual-cancel"
                onClick={onCancel}
                disabled={busy}
                className="py-1.5 px-3 rounded-md border border-border text-[10px] font-bold uppercase tracking-wider disabled:opacity-40"
              >
                {isCancelling ? "Cancelling…" : "Cancel (PAPER)"}
              </button>
            </div>

            {/*
              The preview, and the caveat that makes it safe to show. Both are the
              engine's numbers: the price is `execution_price_preview` and the wording is
              `preview_note`, rendered verbatim so a client cannot drop it.
            */}
            <div
              className="border-l-2 border-warning/50 pl-3 flex flex-col gap-1"
              data-testid="manual-preview"
            >
              <p className="text-[11px] text-muted-foreground">
                Next execution bar opens at{" "}
                <span
                  className="font-mono font-semibold text-foreground"
                  data-testid="manual-preview-price"
                >
                  {manual.execution_price_preview === null
                    ? "—"
                    : formatPrice(manual.execution_price_preview)}
                </span>
              </p>
              <p
                className="text-[11px] font-semibold text-warning-foreground"
                data-testid="manual-preview-note"
              >
                {manual.preview_note}
              </p>
            </div>

            <p className="text-[11px] text-muted-foreground">
              The replay must step for this action to fill. Stepping is what reaches the
              bar above.
            </p>
          </div>
        </Panel>
      ) : null}

      {manual.paper_note ? (
        <p
          className="text-[11px] text-warning-foreground"
          data-testid="manual-paper-note"
        >
          {manual.paper_note}
        </p>
      ) : null}

      <Panel
        title="Paper account"
        icon={<Hand className="w-4 h-4 text-primary" aria-hidden="true" />}
        badge={
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            Paper
          </span>
        }
      >
        <div className="p-5 flex flex-col gap-3">
          <StatRow
            label="Paper cash"
            value={formatMoney(manual.paper_cash)}
            testId="manual-cash"
            hint="available to commit; never reserved"
          />
          <StatRow
            label="Starting balance"
            value={formatMoney(manual.starting_balance)}
          />
          <StatRow
            label="Realized P&L"
            value={formatSignedMoney(manual.realized_pnl)}
            tone={
              manual.realized_pnl > 0
                ? "success"
                : manual.realized_pnl < 0
                  ? "destructive"
                  : "muted"
            }
            hint="after fees and slippage"
            testId="manual-realized"
          />
          <StatRow
            label="Trades closed"
            value={String(manual.trade_count)}
            testId="manual-trade-count"
          />
        </div>
      </Panel>

      <Panel
        title="Action"
        icon={<Hand className="w-4 h-4 text-primary" aria-hidden="true" />}
        description="Choose a side and a size, then step the replay to fill."
      >
        <div className="p-5 flex flex-col gap-4" data-testid="manual-controls">
          <label className="flex flex-col gap-1 max-w-[220px]">
            <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
              Size (% of paper cash)
            </span>
            <div className="flex items-center gap-1 border border-border rounded-md px-2 focus-within:ring-1 focus-within:ring-ring">
              <input
                type="text"
                inputMode="decimal"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="1.00"
                aria-label="Position size as a percentage of paper cash"
                data-testid="manual-size-input"
                className="w-24 bg-transparent py-2 font-mono text-sm outline-none min-w-0"
              />
              <span className="font-mono text-xs text-muted-foreground">%</span>
            </div>
          </label>

          {/*
            The estimate. Two engine-supplied numbers multiplied, labelled as an
            estimate, and never described as a committed position — nothing is
            committed until the broker books a fill.

            Deliberately called an "estimated size" rather than a notional: the engine
            holds no position value and reports no notional anywhere, so naming one here
            would introduce a figure the rest of the app never shows.
          */}
          <p className="text-[11px] text-muted-foreground" data-testid="manual-estimate">
            Estimated size:{" "}
            <span
              className="font-mono font-semibold text-foreground"
              data-testid="manual-estimate-value"
            >
              {estimateNotional(manual.paper_cash, parsed)}
            </span>{" "}
            of cash — an estimate from the size above. No position is opened until the
            replay steps.
          </p>

          {draft.trim() !== "" && parsed === null ? (
            <p
              className="text-[11px] text-destructive"
              data-testid="manual-size-invalid"
            >
              Enter a percentage greater than 0 and at most {(max * 100).toFixed(0)}.
            </p>
          ) : null}

          {refusalText ? (
            <p className="text-[11px] text-destructive" data-testid="manual-error">
              {refusalText}
            </p>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              data-testid="manual-buy"
              onClick={() => parsed !== null && onSubmit("ENTER_LONG", parsed)}
              disabled={!canEnter || parsed === null || busy}
              className="inline-flex items-center gap-2 py-2 px-4 rounded-md bg-primary text-primary-foreground text-xs font-bold uppercase tracking-wider disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <TrendingUp className="w-4 h-4" aria-hidden="true" />
              Buy (paper)
            </button>
            <button
              type="button"
              data-testid="manual-sell"
              onClick={() => parsed !== null && onSubmit("ENTER_SHORT", parsed)}
              disabled={!canEnter || parsed === null || busy}
              className="inline-flex items-center gap-2 py-2 px-4 rounded-md border border-border text-xs font-bold uppercase tracking-wider disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <TrendingDown className="w-4 h-4" aria-hidden="true" />
              Sell (paper)
            </button>
            <button
              type="button"
              data-testid="manual-exit"
              onClick={() => onSubmit("EXIT")}
              disabled={!canExit || busy}
              className="py-2 px-4 rounded-md border border-border text-xs font-bold uppercase tracking-wider disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Exit (paper)
            </button>
          </div>

          {/*
            Why a button is unavailable, stated rather than left silent. A disabled
            control with no reason is indistinguishable from a broken one.
          */}
          {!canEnter && !canExit ? (
            <p className="text-[11px] text-muted-foreground" data-testid="manual-unavailable">
              {manual.replay.status === "finished"
                ? "This replay has reached the end of the dataset. Reset it to act again."
                : "No actions are available in the current state."}
            </p>
          ) : null}
          {canExit && !canEnter ? (
            <p className="text-[11px] text-muted-foreground">
              A position is open. Exit it before entering the other side — Manual does not
              support a direct reversal.
            </p>
          ) : null}
        </div>
      </Panel>

      <Panel
        title="Current position"
        icon={<Hand className="w-4 h-4 text-primary" aria-hidden="true" />}
      >
        <div className="p-5 flex flex-col gap-3" data-testid="manual-position">
          {manual.open_position === null ? (
            <EmptyPanel
              title="Flat"
              hint="No paper position is open."
            />
          ) : (
            <>
              <StatRow
                label="Side"
                value={manual.open_position.side.toUpperCase()}
                mono={false}
              />
              <StatRow
                label="Entry price"
                value={formatPrice(manual.open_position.entry_price)}
                testId="manual-entry-price"
              />
              <StatRow
                label="Quantity"
                value={formatQuantity(manual.open_position.quantity)}
              />
              <StatRow
                label="Entry time"
                value={formatTimestamp(manual.open_position.entry_time)}
                mono={false}
              />
              <StatRow
                label="Bars held"
                value={isAbsent(manual.bars_held) ? "—" : String(manual.bars_held)}
                testId="manual-bars-held"
                hint="bars since this position filled"
              />
              <StatRow
                label="Reason"
                value={manual.open_position.reason}
                mono={false}
              />
              {/*
                Deliberately absent: any mark price, unrealized P&L or equity. The engine
                has no live price feed, so such a figure would have to be invented. The
                position panel reports only what the broker recorded at entry.
              */}
            </>
          )}
        </div>
      </Panel>

      <Panel
        title="Trade history"
        icon={<Hand className="w-4 h-4 text-primary" aria-hidden="true" />}
        description="Manual trades, newest first. Every entry is one you requested."
      >
        <div className="p-5 flex flex-col gap-0.5">
          {manual.journal.length === 0 ? (
            <EmptyPanel
              title="No closed trades"
              hint="A trade appears here once you exit the position."
            />
          ) : (
            <div data-testid="manual-journal">
              {manual.journal.slice(0, 14).map((trade) => (
                <TradeRow key={`${trade.entry_time}-${trade.exit_time}`} trade={trade} />
              ))}
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}