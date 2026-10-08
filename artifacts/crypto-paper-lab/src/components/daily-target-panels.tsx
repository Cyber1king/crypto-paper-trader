/**
 * Daily Target's panel (Phase 24C: fixed dollar target).
 *
 * ## What this renders
 *
 * Only what `GET /api/daily-target` returned, plus whatever the user typed into the
 * target field. There is no client-side target, no client-side progress calculation
 * and no client-side P&L anywhere in this file. If a figure is not in the response, the
 * panel does not show it.
 *
 * ## The target is an objective, not a forecast
 *
 * This mode adds the first figure in the app that could be mistaken for a promise: a
 * dollar goal with a progress bar beside it. Four things guard against it, and all four
 * are rendered unconditionally rather than only in a warning state:
 *
 * 1. the label carries "Paper Trading";
 * 2. `target_note` — the engine's own non-guarantee sentence — is shown in full;
 * 3. `waiting_note` — that the strategy waits for valid signals rather than trading to
 *    reach the goal — is shown beside it, because "daily target" otherwise reads as an
 *    instruction;
 * 4. the progress bar is captioned "may overshoot", because it genuinely can.
 *
 * All three notes come from the engine. A locally worded caveat would be a second claim
 * to keep in step with the server, and would eventually drift.
 *
 * ## No percentage anywhere
 *
 * The Phase 24B objective was a percentage of the day's starting equity, which made the
 * goal scale with the account. The contract is now a fixed number of dollars the user
 * chose, so this file contains no percentage target, no "of the day's starting equity"
 * phrasing, and no way to express a fraction. The day starting balance is still shown —
 * it is where the day's P&L is measured from — but it never multiplies anything.
 *
 * ## Null is not zero
 *
 * Before the replay's first step the *day* fields are `null`, and this panel renders the
 * empty state rather than a starting balance of `0.00`. The **target** is the
 * exception: it is a user setting, known before any bar runs, which is what allows it to
 * be shown and changed on an idle session.
 */

import { useEffect, useState } from "react";
import { CalendarClock, Flag, Target, TrendingUp } from "lucide-react";

import {
  EmptyPanel,
  ErrorPanel,
  LoadingPanel,
  Panel,
  StatRow,
  Rule,
} from "@/components/state";
import {
  formatCount,
  formatFractionAsPercent,
  formatMoney,
  formatSignedMoney,
  isAbsent,
} from "@/lib/format";
import type { ApiError, DailyResult, DailyTargetResponse } from "@/lib/api";

/** The mode name as the UI presents it. Mirrors the engine's own label. */
const HEADLINE = "Daily Target — Paper Trading";

/**
 * The caveats, from the engine.
 *
 * Fallbacks exist only for a payload that omitted them, which the server should never
 * send. Each fallback still denies a guarantee and still denies that the mode trades to
 * reach the goal, so a partial response cannot imply either.
 */
function targetNote(response: DailyTargetResponse | undefined): string {
  return (
    response?.target_note ??
    "Paper-trading objective only. Not a guaranteed return."
  );
}

function waitingNote(response: DailyTargetResponse | undefined): string {
  return (
    response?.waiting_note ??
    "The strategy may wait for valid signals. It will not trade just to reach the target."
  );
}

function overshootNote(response: DailyTargetResponse | undefined): string {
  return (
    response?.overshoot_note ??
    "Realized paper P&L moves in whole trades, so the target can be overshot."
  );
}

/**
 * Progress as a percentage for the bar's **width**.
 *
 * Capped at 100 because a bar wider than its track is not a readable shape. The
 * uncapped figure is rendered as text beside it, so an overshoot stays visible rather
 * than being visually clipped away — which would misrepresent the one property that
 * distinguishes this mode from an exact threshold.
 */
function barWidth(progress: number | null): number {
  if (progress === null || progress <= 0) {
    return 0;
  }

  return Math.min(100, progress * 100);
}

/**
 * Parse the target the user typed.
 *
 * Returns `null` for anything that is not a positive, finite number, which is what the
 * Set button uses to refuse to submit. The check is duplicated rather than shared with
 * the server on purpose: the server is the authority, but disabling an obviously
 * invalid button gives the user faster feedback than a round-trip 422.
 *
 * A blank or malformed field is **not** coerced to zero. Zero is a rejected target, and
 * silently submitting it would replace the user's real goal with an error.
 */
function parseTarget(raw: string): number | null {
  const trimmed = raw.trim();

  if (trimmed === "") {
    return null;
  }

  // Reject anything that is not a plain decimal number before parsing, so `1e400`
  // (infinity) and `12abc` cannot slip through Number().
  if (!/^\d*\.?\d+$/.test(trimmed)) {
    return null;
  }

  const value = Number(trimmed);

  if (!Number.isFinite(value) || value <= 0) {
    return null;
  }

  return value;
}

/**
 * The target editor.
 *
 * The value shown starts from the server's figure and is replaced by whatever the user
 * types. It resets to the server's value whenever that value changes, so a rejected
 * save or a switch to another mode cannot leave a stale number in the box looking like
 * the current target.
 */
function TargetEditor({
  daily,
  onSubmit,
  pending,
  error,
}: {
  daily: DailyTargetResponse | undefined;
  onSubmit: (amount: number) => void;
  pending: boolean;
  error: ApiError | null;
}) {
  const serverAmount = daily?.daily_target_amount ?? null;
  const [draft, setDraft] = useState("");

  // Re-sync whenever the authoritative figure changes, including after a successful
  // save. Keyed on the number, not on the object, so an unrelated refetch of the same
  // target does not wipe what the user is typing.
  useEffect(() => {
    setDraft(serverAmount === null ? "" : serverAmount.toFixed(2));
  }, [serverAmount]);

  const parsed = parseTarget(draft);
  const dirty = parsed !== null && serverAmount !== null && parsed !== serverAmount;
  const rejected = error && error.code !== "NETWORK_UNAVAILABLE" ? error : null;

  /*
   * The local validity message is cleared as soon as the input becomes usable, rather
   * than waiting for the next submit.
   *
   * It has to be derived, not stored: a message left over from a bad entry would sit
   * under a now-valid `100.00`, telling the user their target is invalid while the Set
   * button is enabled. Deriving it from the current draft makes that state
   * unreachable, whereas clearing it on change would need a second piece of state that
   * could itself drift from the input.
   */
  const showInvalid = draft.trim() !== "" && parsed === null;

  return (
    <Panel
      title="Target"
      icon={<Target className="w-4 h-4 text-primary" aria-hidden="true" />}
      description="How much realized paper profit you want today, in dollars."
    >
      <div className="p-5 flex flex-col gap-3" data-testid="daily-target-editor">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();

            if (parsed !== null && dirty && !pending) {
              onSubmit(parsed);
            }
          }}
        >
          <label className="flex flex-col gap-1 min-w-0">
            <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
              Daily target
            </span>
            <div className="flex items-center gap-1 border border-border rounded-md px-2 focus-within:ring-1 focus-within:ring-ring">
              <span className="font-mono text-muted-foreground">$</span>
              <input
                type="text"
                inputMode="decimal"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="50.00"
                aria-label="Daily target in dollars"
                data-testid="daily-target-input"
                className="w-24 bg-transparent py-2 font-mono text-sm outline-none min-w-0"
              />
            </div>
          </label>

          <button
            type="submit"
            data-testid="daily-target-set"
            disabled={!dirty || pending}
            className="py-2 px-4 rounded-md bg-primary text-primary-foreground text-xs font-bold uppercase tracking-wider disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {pending ? "Setting…" : "Set"}
          </button>
        </form>

        {/*
          The local validity message. Says nothing about the outcome, only that the
          typed text is not a usable amount.
        */}
        {showInvalid ? (
          <p
            className="text-[11px] text-destructive"
            data-testid="daily-target-invalid"
          >
            Enter a dollar amount greater than zero.
          </p>
        ) : null}

        {/*
          A server refusal. Suppressed while the input is also locally invalid, because
          showing "must be greater than 0" under a box the user is still editing is
          noise — and the engine's own reason is the more precise of the two.
        */}
        {rejected && !showInvalid ? (
          <p
            className="text-[11px] text-destructive"
            data-testid="daily-target-error"
          >
            {rejected.message}
          </p>
        ) : null}
      </div>
    </Panel>
  );
}

/** One completed UTC day, as a row. */
function DayRow({ day }: { day: DailyResult }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1">
      <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider shrink-0">
        {day.date}
        <span className="block normal-case font-normal tracking-normal text-[10px] opacity-70">
          {day.trades_closed} closed
        </span>
      </span>
      <span className="min-w-0 break-all font-mono font-semibold text-sm text-right">
        <span className={day.reached ? "text-success" : "text-muted-foreground"}>
          {formatSignedMoney(day.realized_pnl)}
        </span>
        {/*
          A day that fell short says so in words, not only by showing a gap. "not
          reached" next to a losing figure is what stops a completed day reading as a
          neutral result.
        */}
        <span className="block text-[10px] font-normal text-muted-foreground">
          target {formatMoney(day.target_amount)} ·{" "}
          {day.reached ? "reached" : "not reached"}
        </span>
      </span>
    </div>
  );
}

export function DailyTargetPanel({
  daily,
  isLoading,
  error,
  onSetTarget,
  isSetting,
  setError,
}: {
  daily: DailyTargetResponse | undefined;
  isLoading: boolean;
  error: ApiError | null;
  onSetTarget: (amount: number) => void;
  isSetting: boolean;
  setError: ApiError | null;
}) {
  if (error) {
    return <ErrorPanel error={error} title="Daily target unavailable" />;
  }

  if (isLoading) {
    return <LoadingPanel label="Loading daily target" />;
  }

  /*
   * The editor is rendered even with no daily state at all. The target is a user
   * setting that exists before the replay runs, so an idle session must still be able
   * to show and change the goal — that is the practical difference between a
   * user-entered dollar target and the Phase 24B percentage, which was unknowable
   * until a bar had been processed.
   */
  const editor = (
    <TargetEditor
      daily={daily}
      onSubmit={onSetTarget}
      pending={isSetting}
      error={setError}
    />
  );

  if (!daily) {
    return (
      <div className="flex flex-col gap-6" data-testid="daily-target-body">
        {editor}
        <Panel
          title="What this target is"
          icon={<Flag className="w-4 h-4 text-primary" aria-hidden="true" />}
        >
          <div
            className="p-5 flex flex-col gap-3"
            data-testid="daily-target-note"
          >
            <p className="text-sm font-semibold" data-testid="daily-target-headline">
              {HEADLINE}
            </p>
            <p className="text-xs text-muted-foreground">{targetNote(daily)}</p>
            <p className="text-xs text-muted-foreground">{waitingNote(daily)}</p>
          </div>
        </Panel>
        <EmptyPanel
          title="No day measured yet"
          hint="Step the replay and the engine reports this UTC day's starting balance, realized P&L and what is still outstanding."
        />
      </div>
    );
  }

  // Before the first step the engine reports nulls, not zeroes. Both are checked so a
  // partial payload cannot render a fabricated day. The date is a string, so it gets a
  // plain presence check rather than the numeric null test.
  const hasDay =
    Boolean(daily.current_date) && !isAbsent(daily.realized_daily_pnl);

  const reached = daily.target_reached === true;

  const money = (value: number | null): string =>
    value === null ? "—" : formatMoney(value);

  return (
    <div className="flex flex-col gap-6" data-testid="daily-target-body">
      {/*
        The disclaimer. Its own panel rather than a footnote on the target, because a
        caveat attached to a number is easy to read as part of it.
      */}
      <Panel
        title="What this target is"
        icon={<Flag className="w-4 h-4 text-primary" aria-hidden="true" />}
      >
        {/*
          The test ids live on this div, not on `Panel`: `Panel` takes a fixed prop
          list and forwards none of its own, so a `data-testid` passed to it is dropped
          at runtime. TypeScript does not catch this, because hyphenated JSX attribute
          names are exempt from prop checking — the attribute compiles and vanishes.
        */}
        <div className="p-5 flex flex-col gap-3" data-testid="daily-target-note">
          <p className="text-sm font-semibold" data-testid="daily-target-headline">
            {HEADLINE}
          </p>
          <p
            className="text-xs text-muted-foreground"
            data-testid="daily-target-note-text"
          >
            {targetNote(daily)}
          </p>
          <p
            className="text-xs text-muted-foreground"
            data-testid="daily-target-waiting-text"
          >
            {waitingNote(daily)}
          </p>
          {/*
            The engine's overshoot wording, rendered verbatim like the other two. A
            locally worded version would be a third claim to keep in step with the
            server, and "may overshoot" is precisely the thing that must not be lost —
            it is why the progress bar is capped while the figure beside it is not.
          */}
          <p
            className="text-xs text-muted-foreground"
            data-testid="daily-target-overshoot-text"
          >
            {overshootNote(daily)}
          </p>
          <Rule />
          <ul className="text-[11px] text-muted-foreground flex flex-col gap-1">
            <li>· A fixed dollar amount you choose. It does not scale with the balance.</li>
            <li>· Measured from realized paper P&amp;L only, after costs.</li>
            <li>
              · No unrealized figure is shown, because the engine has no live price
              feed to produce one.
            </li>
            <li>
              · The same target applies to each new UTC day until you change it.
            </li>
            <li>
              · Meeting the target stops new positions for that day. It does not close
              an open one, and it does not reset the account.
            </li>
          </ul>
        </div>
      </Panel>

      {editor}

      {daily.target_changed_during_day ? (
        <p className="text-[11px] text-warning-foreground" data-testid="daily-target-changed">
          The target was changed while this day was open, so today&apos;s figures span
          two objectives.
        </p>
      ) : null}

      {!hasDay ? (
        <Panel
          title="Today"
          icon={<Target className="w-4 h-4 text-primary" aria-hidden="true" />}
        >
          <EmptyPanel
            title="No day measured yet"
            hint="Step the replay and the engine reports this UTC day's starting balance, realized P&L and what is still outstanding."
          />
        </Panel>
      ) : (
        <Panel
          title="Today"
          icon={<Target className="w-4 h-4 text-primary" aria-hidden="true" />}
          badge={
            <span
              data-testid="daily-target-reached"
              data-reached={String(reached)}
              className={[
                "font-mono text-[10px] uppercase tracking-widest",
                reached ? "text-success" : "text-muted-foreground",
              ].join(" ")}
            >
              {reached ? "Target reached" : "Target not reached"}
            </span>
          }
          description="This UTC day, measured against your target."
        >
          <div className="p-5 flex flex-col gap-4">
            <StatRow
              label="Current UTC day"
              value={daily.current_date ?? "—"}
              mono={false}
            />
            <StatRow
              label="Starting balance"
              value={money(daily.day_starting_balance)}
              hint="carried from previous days, never reset"
            />
            <StatRow
              label="Target"
              value={money(daily.daily_target_amount)}
              testId="daily-target-amount"
              hint="the amount you chose"
            />
            <StatRow
              label="Realized today"
              value={formatSignedMoney(daily.realized_daily_pnl)}
              tone={
                (daily.realized_daily_pnl ?? 0) > 0
                  ? "success"
                  : (daily.realized_daily_pnl ?? 0) < 0
                    ? "destructive"
                    : "muted"
              }
              hint="after costs; unrealized excluded"
            />
            <StatRow
              label="Remaining"
              value={money(daily.remaining)}
              testId="daily-target-remaining"
              hint="target minus realized today, never negative"
            />

            {/*
              The bar. Width capped at 100 so the shape stays readable, while the
              figure beside it is uncapped — a mode that overshoots must show that
              rather than look like it stopped at the line.
            */}
            <div className="flex flex-col gap-2">
              <div className="flex items-baseline justify-between gap-4">
                <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                  Progress
                </span>
                <span
                  className="font-mono text-sm font-semibold"
                  data-testid="daily-target-progress"
                >
                  {formatFractionAsPercent(daily.progress, 2)}
                </span>
              </div>
              <div
                className="h-2 w-full rounded-full bg-muted/40 overflow-hidden"
                role="progressbar"
                aria-valuenow={Math.round(barWidth(daily.progress))}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Realized progress toward the daily target"
              >
                <div
                  className={[
                    "h-full rounded-full transition-all",
                    reached ? "bg-success" : "bg-primary",
                  ].join(" ")}
                  style={{ width: `${barWidth(daily.progress)}%` }}
                />
              </div>
              <p className="text-[10px] text-muted-foreground">
                Progress is measured from realized P&amp;L and may overshoot the
                target.
              </p>
            </div>
          </div>
        </Panel>
      )}

      <Panel
        title="Completed UTC days"
        icon={
          <CalendarClock className="w-4 h-4 text-primary" aria-hidden="true" />
        }
        description="Each day is finalized when the replay crosses into the next UTC date."
      >
        <div className="p-5 flex flex-col gap-0.5">
          {daily.days_completed.length === 0 ? (
            <EmptyPanel
              title="No completed days yet"
              hint="A day is recorded once the replay advances past its final UTC date."
            />
          ) : (
            <div data-testid="daily-target-days">
              {[...daily.days_completed]
                .reverse()
                .slice(0, 14)
                .map((day) => (
                  <DayRow key={day.date} day={day} />
                ))}
              {daily.days_completed.length > 14 ? (
                <p className="text-[10px] text-muted-foreground pt-2">
                  Showing the 14 most recent of{" "}
                  {formatCount(daily.days_completed.length)} completed days.
                </p>
              ) : null}
            </div>
          )}
        </div>
      </Panel>

      {/*
        What this mode is not, stated explicitly because the omission is otherwise
        confusing. Daily Target owns a **separate** paper broker, and the Phase 16
        projections (`/api/account`, `/api/trades`, `/api/statistics`) carry no `mode`
        parameter — they describe Standard, not this session. So the balance and journal
        for this mode are not available here, and are not restated from Standard's,
        which would be a different account presented as this one.
      */}
      <Panel
        title="How this mode trades"
        icon={<TrendingUp className="w-4 h-4 text-primary" aria-hidden="true" />}
      >
        <div className="p-5 flex flex-col gap-2 text-[11px] text-muted-foreground">
          <p>
            Runs the same frozen strategy as every other mode, on its own paper account.
            It differs in one respect: it stops opening positions once a UTC
            day&apos;s realized P&amp;L reaches your target.
          </p>
          <p>
            It will keep looking for valid signals after partial progress, and it may
            overshoot. An open position is <strong>not</strong> closed when the target is
            met — that would be a trading operation, and it would change the very figure
            being measured. The position exits by the engine&apos;s own rules.
          </p>
          <p>
            If no valid setup appears during a day, that day finishes at $0.00 with the
            target unreached. That is a valid outcome, not a failure.
          </p>
        </div>
      </Panel>
    </div>
  );
}
