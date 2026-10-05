/**
 * AI Intelligence dashboard (Phase 18F).
 *
 * ## One source, and only one
 *
 * Every figure on this page comes from `GET /api/ai`. In particular the AI
 * **account** block reads `AiState.account` and nothing else.
 *
 * `/api/replay?mode=ai_intelligence` is deliberately *not* used for any capital
 * figure. That route's broker is permanently flat by construction, because the AI
 * position book is the sole owner of AI capital; its `balance`, `trade_count` and
 * `open_position` describe an inert broker, not the AI account. Reading them here
 * would display a constant $10,000 next to real AI positions.
 *
 * The replay lifecycle *is* read from `AiState.replay`, which is the AI mode's own
 * replay state — kept visually separate from the account block so the two are
 * never confused.
 *
 * ## The score is a gate, not a forecast
 *
 * The UI uses the words "Intelligence Score" and "Qualification threshold". It
 * never renders the score with a percent sign, never calls it confidence,
 * probability or expected return, and never shows a gauge that implies "90% likely
 * to profit". The backend's own note says the score is a research heuristic, and
 * this component quotes that note rather than paraphrasing it.
 */

import { Brain, Gauge, Layers, Target, TrendingDown, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui";
import { EmptyPanel, Panel, StatRow } from "@/components/state";
import type { AiPosition, AiState, IntelligenceScore } from "@/lib/api";
import {
  formatCount,
  formatFractionAsPercent,
  formatMoney,
  formatMoneyCompact,
  formatPrice,
  formatQuantity,
  formatSignedMoney,
  formatTimestamp,
  sideClass,
  sideLabel,
  statusLabel,
} from "@/lib/format";

/** The one place the terminology is fixed, so it cannot drift between panels. */
export const SCORE_TERMINOLOGY_NOTE =
  "Intelligence Score is a deterministic qualification gate on a 0–100 scale, not a " +
  "probability, win rate, confidence percentage or expected return. Reaching the " +
  "threshold means the setup met the mode's criteria; it does not predict profit.";

function scoreTone(score: IntelligenceScore) {
  if (score.qualified) {
    return "text-success";
  }

  // Near-miss styling is about reading the number, not about forecasting it.
  return score.score >= score.threshold - 10 ? "text-warning-foreground" : "text-muted-foreground";
}

export function AiAccountPanel({ ai }: { ai: AiState | undefined }) {
  const account = ai?.account;
  const pnlTone =
    account === undefined || account.realized_pnl === 0
      ? "muted"
      : account.realized_pnl > 0
        ? "success"
        : "destructive";

  return (
    <Panel
      title="AI Paper Account"
      icon={<Layers className="w-4 h-4 text-primary" aria-hidden="true" />}
      badge={
        <Badge variant="outline" className="font-mono uppercase text-[10px] tracking-widest">
          isolated pool
        </Badge>
      }
      description="Source: GET /api/ai. Never the replay's inert broker."
    >
      {!account ? (
        <EmptyPanel title="No account reported" hint="Reading the AI account." />
      ) : (
        <div className="p-5 flex flex-col gap-1">
          <div className="pb-3">
            <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
              Simulated starting capital
            </div>
            <div
              className="font-mono text-3xl font-bold tracking-tight text-primary"
              data-testid="ai-starting-capital"
            >
              {formatMoney(account.starting_capital)}
            </div>
          </div>

          <div className="border-t border-border pt-2 flex flex-col gap-0.5">
            <StatRow
              label="Committed capital"
              value={formatMoney(account.committed_capital)}
              hint="held by open positions; released on close"
            />
            <StatRow
              label="Available capital"
              value={formatMoney(account.available_capital)}
              hint="uncommitted paper cash, not buying power"
            />
            <StatRow
              label="Realised balance"
              value={formatMoney(account.realized_balance)}
              hint="starting capital plus every closed position's net P&L"
            />
            <StatRow
              label="Realised paper P&L"
              tone={pnlTone}
              value={formatSignedMoney(account.realized_pnl)}
            />
            <StatRow
              label="Open positions"
              value={`${formatCount(account.open_position_count)} / ${formatCount(account.max_positions)}`}
              hint="concurrent position limit"
            />
            <StatRow
              label="Position allocation"
              value={formatMoney(account.position_allocation)}
              hint="starting capital divided by the maximum"
            />
            <StatRow
              label="Signals qualified"
              value={formatCount(account.signals_qualified)}
              hint="reached the threshold, whether or not they found room"
            />
            <StatRow
              label="Signals admitted"
              value={formatCount(account.signals_admitted)}
            />
            <StatRow
              label="Signals declined"
              value={formatCount(account.signals_declined)}
              hint="qualified but no free slot or no free capital"
            />
          </div>

          <p className="text-[11px] text-muted-foreground mt-3 border-l-2 border-border pl-3 leading-relaxed">
            Capital is committed, never on credit. A position's notional cannot
            exceed the paper cash allocated to it, so there is no gearing, no margin
            and no borrowing anywhere in this mode.
          </p>
        </div>
      )}
    </Panel>
  );
}

export function IntelligenceScorePanel({
  score,
}: {
  score: IntelligenceScore | null | undefined;
}) {
  return (
    <Panel
      title="Intelligence Score"
      icon={<Brain className="w-4 h-4 text-primary" aria-hidden="true" />}
      badge={
        score ? (
          <Badge
            variant={score.qualified ? "default" : "outline"}
            className="font-mono uppercase text-[10px] tracking-widest"
            data-testid="ai-qualified"
          >
            {score.qualified ? "Qualified" : "Below threshold"}
          </Badge>
        ) : null
      }
      description="Qualification gate, read from the engine."
    >
      {!score ? (
        <EmptyPanel
          title="No score yet"
          hint="Null until the engine has evaluated a signal. No score is invented."
        />
      ) : (
        <div className="p-5 flex flex-col gap-4">
          <div className="flex items-end gap-4">
            <div>
              <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                Intelligence score
              </div>
              <div
                className={`font-mono text-4xl font-bold tracking-tighter ${scoreTone(score)}`}
                data-testid="ai-score"
              >
                {score.score}
                <span className="text-lg text-muted-foreground font-sans font-bold ml-1.5">
                  / 100
                </span>
              </div>
              <div className="text-[10px] text-muted-foreground mt-0.5">
                a score, not a percentage
              </div>
            </div>

            <div className="flex-1">
              <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                Qualification threshold
              </div>
              <div
                className="font-mono text-2xl font-bold tracking-tight text-foreground"
                data-testid="ai-threshold"
              >
                {score.threshold}
              </div>
              <div className="text-[10px] text-muted-foreground mt-0.5">
                a score cutoff, not a success rate
              </div>
            </div>
          </div>

          <div className="border border-border rounded-md px-3 py-2 bg-muted/20">
            <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
              Last signal side
            </p>
            <div className="flex items-center gap-2 mt-1">
              {score.side === "long" ? (
                <TrendingUp className="w-4 h-4 text-success" aria-hidden="true" />
              ) : score.side === "short" ? (
                <TrendingDown className="w-4 h-4 text-destructive" aria-hidden="true" />
              ) : null}
              <span className="font-mono text-sm font-semibold">
                {sideLabel(score.side)}
              </span>
            </div>
          </div>

          <div>
            <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider mb-2 flex items-center gap-1.5">
              <Gauge className="w-3.5 h-3.5" aria-hidden="true" />
              Score components
            </div>
            <div className="flex flex-col gap-2" data-testid="ai-score-components">
              {score.components.map((component) => {
                const fraction =
                  component.weight > 0 ? component.points / component.weight : 0;

                return (
                  <div key={component.name}>
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-[11px] font-mono uppercase tracking-wide">
                        {component.name.replace(/_/g, " ")}
                      </span>
                      <span className="text-[11px] font-mono text-muted-foreground">
                        {component.points.toFixed(1)} / {component.weight}
                      </span>
                    </div>
                    {/* A bar showing what the component earned of its weight. */}
                    <div className="h-1.5 rounded-full bg-muted mt-1 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${Math.max(0, Math.min(1, fraction)) * 100}%` }}
                      />
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-1 leading-snug">
                      {component.reason}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          <p className="text-[11px] text-muted-foreground border-l-2 border-warning/50 pl-3 leading-relaxed">
            {SCORE_TERMINOLOGY_NOTE}
          </p>
        </div>
      )}
    </Panel>
  );
}

function AiPositionRow({ position }: { position: AiPosition }) {
  const pnl = position.realized_pnl;

  return (
    <div className="p-4 border-b last:border-0" data-testid="ai-position">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <Badge
            variant="outline"
            className={`font-mono uppercase tracking-wider text-[10px] shrink-0 ${sideClass(position.side)}`}
          >
            {sideLabel(position.side)}
          </Badge>
          <span className="font-mono text-xs text-muted-foreground truncate">
            {position.position_id}
          </span>
        </div>
        <Badge
          variant={position.state === "open" ? "default" : "outline"}
          className="font-mono uppercase text-[10px] shrink-0"
        >
          {position.state}
        </Badge>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 mt-2">
        <StatRow label="Entry price" value={formatPrice(position.entry_price)} />
        <StatRow label="Quantity" value={formatQuantity(position.quantity)} />
        <StatRow
          label="Allocated"
          value={formatMoneyCompact(position.allocated_capital)}
          hint="capital this position holds"
        />
        <StatRow
          label="Score at entry"
          value={`${position.intelligence_score} / ${position.qualification_threshold}`}
        />
        <StatRow label="Entry index" value={formatCount(position.entry_index)} />
        <StatRow label="Entry time" value={formatTimestamp(position.entry_timestamp)} mono={false} />
        <StatRow label="Exit price" value={formatPrice(position.exit_price ?? Number.NaN)} />
        <StatRow label="Exit reason" value={position.exit_reason ?? "—"} mono={false} />
        <StatRow
          label="Realised net P&L"
          tone={
            pnl === null || pnl === 0 ? "muted" : pnl > 0 ? "success" : "destructive"
          }
          value={formatSignedMoney(pnl)}
          hint={pnl === null ? "computed by the engine only at close" : undefined}
        />
        <StatRow label="Costs" value={formatMoney(position.costs ?? Number.NaN)} />
        <StatRow label="Bars held" value={position.bars_held === null ? "—" : formatCount(position.bars_held)} />
      </div>
    </div>
  );
}

export function AiPositionsPanel({ ai }: { ai: AiState | undefined }) {
  const open = (ai?.positions ?? []).filter((position) => position.state === "open");

  return (
    <Panel
      title="Open AI Positions"
      icon={<Target className="w-4 h-4 text-primary" aria-hidden="true" />}
      badge={
        <Badge variant="secondary" className="font-mono text-[10px]">
          {formatCount(open.length)} / {formatCount(ai?.account.max_positions ?? 0)}
        </Badge>
      }
      description="Each position is independent and holds its own capital."
    >
      {open.length === 0 ? (
        <EmptyPanel
          title="No open AI positions"
          hint="The engine opens one only when a signal's score reaches the threshold, a slot is free, and capital is available."
        />
      ) : (
        <div className="max-h-[520px] overflow-y-auto">
          {open.map((position) => (
            <AiPositionRow key={position.position_id} position={position} />
          ))}
        </div>
      )}
    </Panel>
  );
}

export function AiJournalPanel({ ai }: { ai: AiState | undefined }) {
  const journal = ai?.journal ?? [];

  return (
    <Panel
      title="AI Position Journal"
      icon={<Target className="w-4 h-4 text-primary" aria-hidden="true" />}
      badge={
        <Badge variant="secondary" className="font-mono text-[10px]">
          {formatCount(journal.length)}
        </Badge>
      }
      description="Closed positions in close order. P&L is the engine's net figure."
    >
      {journal.length === 0 ? (
        <EmptyPanel
          title="No closed AI positions"
          hint="Positions appear here once the profit target closes them, or at end of data."
        />
      ) : (
        <div className="max-h-[520px] overflow-y-auto">
          {journal.map((position) => (
            <AiPositionRow key={position.position_id} position={position} />
          ))}
        </div>
      )}
    </Panel>
  );
}

/**
 * The AI mode's own replay lifecycle, kept visually apart from its account.
 *
 * Nested inside `/api/ai`, so it is the AI session's real replay state rather than
 * a separately-fetched Standard one. Only lifecycle fields are shown — no balance,
 * because the replay's broker is inert and its balance is not the AI account.
 */
export function AiReplayProgressPanel({ ai }: { ai: AiState | undefined }) {
  const replay = ai?.replay;

  return (
    <Panel
      title="AI Replay Lifecycle"
      icon={<Target className="w-4 h-4 text-muted-foreground" aria-hidden="true" />}
      badge={
        <Badge
          variant="outline"
          className="font-mono uppercase text-[10px] tracking-widest"
          data-testid="ai-replay-status"
        >
          {statusLabel(replay?.status ?? "unknown")}
        </Badge>
      }
      description="Lifecycle only. Capital lives in the AI account panel above."
    >
      <div className="p-5 flex flex-col gap-0.5">
        <StatRow
          label="Current bar"
          value={formatTimestamp(replay?.current_timestamp)}
          mono={false}
        />
        <StatRow
          label="Next bar"
          value={formatTimestamp(replay?.next_timestamp)}
          mono={false}
        />
        <StatRow
          label="Bars processed"
          value={replay ? formatCount(replay.bars_processed) : "—"}
        />
        <StatRow label="Cursor" value={replay ? formatCount(replay.cursor) : "—"} />
        <StatRow label="Replay id" value={replay?.replay_id ?? "—"} />
        <StatRow
          label="Dataset SHA-256"
          value={replay?.dataset.sha256 ?? "—"}
          hint={`${replay?.dataset.candle_count ?? "?"} candles`}
        />
      </div>
    </Panel>
  );
}

/**
 * Deliberately **not** exported: a list of forbidden phrases.
 *
 * An earlier draft carried `FORBIDDEN_SCORE_PHRASES` here so a test could assert
 * against it. That was wrong in a specific way — production code carrying a list of
 * phrases it avoids is a list that must itself be maintained, and it would have
 * tripped the terminology guard it was meant to help. The list belongs to
 * `test/no-mock-data.test.ts`, where it is data rather than shipped surface.
 *
 * The caveat in {@link SCORE_TERMINOLOGY_NOTE} does have to name what the score is
 * not, because "90 is not a 90% chance" is the whole point. That is why the
 * terminology guard scans code with string literals stripped: a deliberate,
 * reviewed caveat is a string constant, while an accidental framing in JSX or in an
 * identifier is not.
 */