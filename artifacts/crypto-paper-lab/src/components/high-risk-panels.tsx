/**
 * High-Risk's panels (Phase 26B).
 *
 * ## What this renders
 *
 * Only what `GET /api/high-risk` returned, plus the percentage the user typed. Every
 * money figure below is read from the response and formatted — never derived.
 *
 * ## No client-side arithmetic on money
 *
 * This is stronger than Manual's rule and deliberate. Manual may show a *size
 * estimate*, because the user is about to choose a size and the estimate is that
 * choice's echo. High-Risk has no user-chosen size in the trading path at all: the
 * strategy decides when to trade, and the only setting is a ceiling. So there is
 * nothing to preview.
 *
 * Concretely, this file does not compute P&L, fees, slippage, quantity, profit or
 * loss, and it does not compute `exposure`. Both `exposure` and `exposure_fraction`
 * arrive from the engine as `entry_price * quantity` of the broker's own trade, and
 * are displayed verbatim. Reproducing the broker's arithmetic in TypeScript would be
 * a second implementation that could disagree with the one that booked the fill.
 *
 * The one arithmetic performed is percent-to-fraction on the *configuration input*:
 * the field is labelled in percent because that is how a fraction is described to a
 * person, and the engine's contract is a fraction. That is unit conversion, not
 * accounting.
 *
 * ## Three things this panel must not do
 *
 * 1. **Let "High-Risk" imply borrowing.** The mode commits a larger share of the
 *    paper cash you already hold. It is not leverage, not margin and not a credit
 *    facility, and `exposure` can never exceed `paper_cash`. The panel states that in
 *    words rather than leaving it to be inferred from the name, because the name is
 *    the thing most likely to be misread.
 *
 * 2. **Drop the inherited-signal-set statement.** `inherits_note` is rendered
 *    verbatim from the engine. High-Risk adds no qualification rule, so it trades
 *    exactly the signals Standard trades — a fact a user comparing the two modes
 *    needs and one a client could easily omit.
 *
 * 3. **Present a percentage as an outcome.** `caution` is rendered verbatim. Measured
 *    on the frozen dataset, fees and slippage are more than half the loss at the
 *    maximum setting, and "more paper capital per position" is not "more return".
 *
 * ## PAPER, everywhere
 *
 * The heading carries it, the shared banner carries it, and every panel badge
 * repeats it. This mode places simulated fills on historical candles; a heading
 * reading only "HIGH-RISK" would be the easiest thing on the screen to misread as a
 * real leveraged position.
 */

import { useState } from "react";
import { Gauge, ShieldAlert, TrendingDown, TrendingUp } from "lucide-react";

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
  formatFractionAsPercent,
  formatMoney,
  formatPrice,
  formatQuantity,
  formatSignedMoney,
  formatTimestamp,
} from "@/lib/format";
import type { ApiError, HighRiskStateResponse } from "@/lib/api";

/**
 * Parse the percentage the user typed and convert it to the engine's fraction.
 *
 * The field is labelled in **percent** — `25` reads as "a quarter of my paper cash" —
 * while the engine's contract is a fraction of cash, where `0.25` means 25%. The
 * division is the load-bearing line: sending `25` would request a position requiring
 * twenty-five times the account, which the engine refuses, so the mistake would
 * surface as a 422 rather than silently doing something. The conversion is asserted
 * in the tests regardless.
 *
 * Returns `null` for anything that is not a number in `(0, max * 100]` percent, which
 * disables the control. Refusing locally gives faster feedback than a round trip, and
 * the server remains the authority either way.
 *
 * A blank field is **not** coerced to zero. Zero is a rejected size, and silently
 * submitting it would show a refusal for a number the user never chose.
 */
function parsePercent(raw: string, max: number): number | null {
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

/**
 * High-Risk's dashboard panels.
 *
 * `highRisk` is the engine's projection, `error`/`isLoading` come from the query hook,
 * and `onSetFraction` performs the one configuration change the mode allows.
 */
export function HighRiskPanel({
  highRisk,
  isLoading,
  error,
  onSetFraction,
  isSubmitting,
  actionError,
}: {
  highRisk: HighRiskStateResponse | undefined;
  isLoading: boolean;
  error: ApiError | null;
  onSetFraction: (riskFraction: number) => void;
  isSubmitting: boolean;
  actionError: ApiError | null;
}) {
  const [draft, setDraft] = useState("");

  const max = highRisk?.max_risk_fraction ?? 1;

  if (error) {
    return <ErrorPanel error={error} title="High-Risk is unavailable" />;
  }

  if (isLoading || highRisk === undefined) {
    return <LoadingPanel label="Loading High-Risk paper state" />;
  }

  const position = highRisk.open_position;
  const signal = highRisk.last_signal;

  const parsed = parsePercent(draft, max);
  const dirty = parsed !== null && parsed !== highRisk.risk_fraction;

  // A position was sized by the fraction in force when it opened. The engine refuses a
  // change in that state, and this disables the control for the same reason rather than
  // letting the user discover it through a 409.
  const lockedByPosition = highRisk.position_count > 0;

  const canSubmit =
    parsed !== null && dirty && !lockedByPosition && !isSubmitting;

  const exposureLabel = highRisk.position_count === 0
    ? "No open position, so no paper capital is committed."
    : `${formatFractionAsPercent(highRisk.exposure_fraction, 2)} of paper cash committed.`;

  return (
    <div className="flex flex-col gap-5" data-testid="high-risk-panels">
      <PaperOnlyBanner />

      <Panel
        title="High-Risk — Paper Trading"
        icon={<Gauge className="w-4 h-4 text-primary" aria-hidden="true" />}
        badge={
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            Paper
          </span>
        }
        description={highRisk.note}
      >
        <div className="p-5 flex flex-col gap-3">
          {/*
            Rendered verbatim, both of them. `inherits_note` is the scope boundary -
            High-Risk adds no qualification rule - and `caution` is the measured
            friction finding. Neither is reworded locally: a client-authored caveat is
            a second claim to keep in step with the server, and a client that dropped
            the first would make the mode look like it traded signals Standard rejects.
          */}
          <p
            className="text-[11px] text-muted-foreground"
            data-testid="high-risk-inherits-note"
          >
            {highRisk.inherits_note}
          </p>

          <p
            className="text-[11px] text-warning-foreground flex items-start gap-2"
            data-testid="high-risk-caution"
          >
            <ShieldAlert className="w-3.5 h-3.5 mt-px shrink-0" aria-hidden="true" />
            <span>{highRisk.caution}</span>
          </p>

          <Rule />
        </div>
      </Panel>

      <Panel
        title="Paper account"
        icon={<Gauge className="w-4 h-4 text-primary" aria-hidden="true" />}
        badge={
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            Paper
          </span>
        }
      >
        <div className="p-5 flex flex-col gap-3">
          <StatRow
            label="Paper balance"
            value={formatMoney(highRisk.paper_cash)}
            testId="high-risk-cash"
            hint="cash only; the engine values no open position"
          />
          <StatRow
            label="Starting balance"
            value={formatMoney(highRisk.starting_balance)}
          />
          <StatRow
            label="Realized P&L"
            value={formatSignedMoney(highRisk.realized_pnl)}
            tone={
              highRisk.realized_pnl > 0
                ? "success"
                : highRisk.realized_pnl < 0
                  ? "destructive"
                  : "muted"
            }
            hint="after fees and slippage"
            testId="high-risk-realized"
          />
          <StatRow
            label="Positions open"
            value={`${highRisk.position_count} of ${highRisk.max_positions}`}
            testId="high-risk-position-count"
            hint="the broker holds one position at most"
          />
          <StatRow
            label="Trades closed"
            value={String(highRisk.trade_count)}
            testId="high-risk-trade-count"
          />
        </div>
      </Panel>

      <Panel
        title="Paper exposure"
        icon={<ShieldAlert className="w-4 h-4 text-primary" aria-hidden="true" />}
        description="How much of your own paper cash a position commits."
      >
        <div className="p-5 flex flex-col gap-3">
          {/*
            Both figures are displayed exactly as the engine computed them. This does
            not multiply a price by a quantity: the broker owns that, and a second
            implementation in TypeScript could disagree with the one that booked the
            fill.
          */}
          <StatRow
            label="Paper exposure"
            value={formatMoney(highRisk.exposure)}
            testId="high-risk-exposure"
            hint={exposureLabel}
          />
          <StatRow
            label="Exposure of cash"
            value={formatFractionAsPercent(highRisk.exposure_fraction, 2)}
            testId="high-risk-exposure-fraction"
            hint="never more than the paper cash you hold"
          />
          <StatRow
            label="Risk fraction in force"
            value={formatFractionAsPercent(highRisk.risk_fraction, 2)}
            testId="high-risk-fraction"
            hint={`applies to the next entry; ceiling ${formatFractionAsPercent(max, 0)}`}
          />
        </div>
      </Panel>

      <Panel
        title="Risk configuration"
        icon={<Gauge className="w-4 h-4 text-primary" aria-hidden="true" />}
        description="More paper capital per position. Not leverage, not margin, not borrowing."
      >
        <div className="p-5 flex flex-col gap-4" data-testid="high-risk-config">
          <label className="flex flex-col gap-1 max-w-[220px]">
            <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
              Cash per position (% of paper cash)
            </span>
            <input
              type="text"
              inputMode="decimal"
              data-testid="high-risk-percent-input"
              value={draft}
              placeholder="25.00"
              onChange={(event) => setDraft(event.target.value)}
              className="font-mono text-sm px-3 py-2 rounded-md border border-input bg-background"
            />
          </label>

          {draft.trim() !== "" && parsed === null ? (
            <p
              className="text-[11px] text-destructive"
              data-testid="high-risk-percent-invalid"
            >
              Enter a percentage greater than 0 and at most{" "}
              {(max * 100).toFixed(0)}.
            </p>
          ) : null}

          {lockedByPosition ? (
            <p
              className="text-[11px] text-muted-foreground"
              data-testid="high-risk-config-locked"
            >
              A paper position is open, so it was sized by the current fraction. Exit
              it before changing this.
            </p>
          ) : null}

          {actionError ? (
            <p className="text-[11px] text-destructive" data-testid="high-risk-error">
              {actionError.message}
            </p>
          ) : null}

          <div>
            <button
              type="button"
              data-testid="high-risk-apply"
              onClick={() => parsed !== null && onSetFraction(parsed)}
              disabled={!canSubmit}
              className="inline-flex items-center gap-2 py-2 px-4 rounded-md bg-primary text-primary-foreground text-xs font-bold uppercase tracking-wider disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Apply cash per position
            </button>
          </div>

          {/*
            Stated in words on the panel as well as being provable from the code:
            a mode called High-Risk that quietly used borrowed money would be a very
            different thing, and nothing else on screen would say so.
          */}
          <p className="text-[11px] text-muted-foreground">
            High-Risk uses more paper capital per position. It does not use leverage
            or margin, and exposure never exceeds the paper cash you hold.
          </p>
        </div>
      </Panel>

      <Panel
        title="Strategy signal"
        icon={
          signal && signal.side === "short" ? (
            <TrendingDown className="w-4 h-4 text-primary" aria-hidden="true" />
          ) : (
            <TrendingUp className="w-4 h-4 text-primary" aria-hidden="true" />
          )
        }
        description="The same signal Standard sees at this bar."
      >
        <div className="p-5 flex flex-col gap-3">
          {signal === null ? (
            <p className="text-[11px] text-muted-foreground">
              No signal observed yet. Step the replay to produce one.
            </p>
          ) : (
            <>
              <StatRow
                label="Signal"
                value={signal.side}
                testId="high-risk-signal"
                hint={signal.reason}
              />
              <StatRow
                label="Signal bar"
                value={formatTimestamp(signal.timestamp)}
              />
              {/*
                Deliberately *not* the entry price of the next bar. This is the
                signal bar's own observation; High-Risk has no pending action and no
                preview, because nothing here is waiting to be filled.
              */}
              <StatRow
                label="Signal close"
                value={signal.price === null ? "-" : String(signal.price)}
              />
            </>
          )}
        </div>
      </Panel>

      <Panel
        title="Open position"
        icon={<TrendingUp className="w-4 h-4 text-primary" aria-hidden="true" />}
        description="At most one, held until the strategy produces an opposite signal."
      >
        <div className="p-5" data-testid="high-risk-position">
          {position === null ? (
            <EmptyPanel title="Flat" hint="No paper position is open." />
          ) : (
            <div className="flex flex-col gap-3">
              <StatRow label="Side" value={position.side.toUpperCase()} />
              <StatRow
                label="Entry price"
                value={formatPrice(position.entry_price)}
                testId="high-risk-entry-price"
              />
              <StatRow
                label="Quantity"
                value={formatQuantity(position.quantity)}
              />
              <StatRow label="Entry time" value={formatTimestamp(position.entry_time)} />
              <StatRow label="Reason" value={position.reason} mono={false} />
            </div>
          )}
        </div>
      </Panel>

      {/*
        The trade journal, as the mode's own contract defines it.

        `GET /api/high-risk` exposes `trade_count` and `exit_counts` rather than a
        list of closed trades, so that is what is rendered: the count and the
        engine's own tally. Individual rows are **not** reconstructed here. Doing so
        would mean either adding a journal field to the mode contract, which Phase
        26B did not approve, or making the shared `/api/trades` query mode-aware —
        and that query is shared with every other mode, so pointing it at High-Risk
        would put one mode's journal on another's screen. The tally is the honest
        subset: it is what the engine reports, and it is where this mode's exit
        behaviour is visible.
      */}
      <Panel
        title="Closed paper trades"
        icon={<TrendingDown className="w-4 h-4 text-primary" aria-hidden="true" />}
        description="Count and exit-reason tally, exactly as the engine reports them."
      >
        <div className="p-5 flex flex-col gap-3" data-testid="high-risk-journal">
          <StatRow
            label="Trades closed"
            value={String(highRisk.trade_count)}
            testId="high-risk-journal-count"
          />
          <ExitTally exitCounts={highRisk.exit_counts} />
        </div>
      </Panel>
    </div>
  );
}

/**
 * The exit-reason tally, straight from `Replay`.
 *
 * Rendered as its own block because it is the one place the mode's *exit behaviour*
 * is visible: `opposite_signal` and `end_of_data` are the only keys the frozen
 * baseline can produce, and seeing that is how a user confirms this mode has no
 * stop-loss, take-profit or max-holding rule of its own.
 */
function ExitTally({ exitCounts }: { exitCounts: Readonly<Record<string, number>> }) {
  const entries = Object.entries(exitCounts);

  if (entries.length === 0) {
    return (
      <p className="text-[11px] text-muted-foreground" data-testid="high-risk-journal-empty">
        No closed trades yet. Step the replay to let the strategy trade.
      </p>
    );
  }

  return (
    <div
      className="flex flex-col gap-1"
      data-testid="high-risk-exit-counts"
    >
      {entries.map(([reason, count]) => (
        <div
          key={reason}
          className="flex items-baseline justify-between gap-4 text-[11px]"
        >
          <span className="text-muted-foreground">{reason}</span>
          <span className="font-mono font-semibold">{count}</span>
        </div>
      ))}
    </div>
  );
}