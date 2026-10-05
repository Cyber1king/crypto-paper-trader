/**
 * Standard mode dashboard (Phase 18E).
 *
 * ## Every figure comes from the API
 *
 * Balance, realised P&L, trade count, timestamps, position, last signal, status
 * and bars processed are all read from `/api/replay`, `/api/account`,
 * `/api/trades` and `/api/statistics`. No panel derives one from another: there is
 * no "unrealised P&L" row, because the engine has no mark price and computing one
 * from the last close would invent a figure the engine deliberately does not
 * produce.
 *
 * In particular this component does **not** compute a total across the trade
 * journal. The `Total PnL` and `Win rate` figures shown are the server's own
 * `/api/statistics` values over the same closed trades.
 */

import { Activity, BarChart2, Clock, Layers, Radio, TrendingDown, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui";
import { EmptyPanel, Panel, StatRow } from "@/components/state";
import type { AccountResponse, ReplaySignal, ReplayState, StatisticsResponse, TradesResponse } from "@/lib/api";
import {
  formatCount,
  formatFractionAsPercent,
  formatMoney,
  formatPercent,
  formatPrice,
  formatQuantity,
  formatSignedMoney,
  formatTimestamp,
  sideClass,
  sideLabel,
  statusLabel,
} from "@/lib/format";

export function StandardAccountPanel({
  replay,
  account,
}: {
  replay: ReplayState | undefined;
  account: AccountResponse | undefined;
}) {
  // Prefer the replay's own fields; the account projection exists for the Phase 16
  // routes and must agree with them. Both are read, never reconciled.
  const balance = replay?.balance ?? account?.balance;
  const starting = replay?.starting_balance ?? account?.starting_balance;
  const realized = replay?.realized_pnl ?? account?.realized_pnl;
  const trades = replay?.trade_count ?? account?.trade_count;

  const pnlTone =
    realized === undefined || realized === 0
      ? "muted"
      : realized > 0
        ? "success"
        : "destructive";

  return (
    <Panel
      title="Paper Account"
      icon={<Layers className="w-4 h-4 text-primary" aria-hidden="true" />}
      badge={
        <Badge variant="outline" className="font-mono uppercase text-[10px] tracking-widest">
          {replay?.mode ?? "standard"}
        </Badge>
      }
      description="Simulated capital. Read from the engine; never computed here."
    >
      <div className="p-5 flex flex-col gap-1">
        <div className="pb-3">
          <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
            Balance
          </div>
          <div
            className="font-mono text-3xl font-bold tracking-tight text-primary"
            data-testid="standard-balance"
          >
            {balance === undefined ? "—" : formatMoney(balance)}
          </div>
          {starting !== undefined ? (
            <div className="text-[11px] text-muted-foreground font-mono mt-0.5">
              starting {formatMoney(starting)}
            </div>
          ) : null}
        </div>

        <div className="border-t border-border pt-2 flex flex-col gap-0.5">
          <StatRow
            label="Realized P&L"
            tone={pnlTone}
            value={realized === undefined ? "—" : formatSignedMoney(realized)}
            hint="balance minus starting balance, the engine's own definition"
          />
          <StatRow
            label="Trade count"
            value={trades === undefined ? "—" : formatCount(trades)}
            hint="closed trades in the broker's journal"
          />
          <StatRow
            label="Bars processed"
            value={replay ? formatCount(replay.bars_processed) : "—"}
            hint="cursor minus start index"
          />
          <StatRow
            label="Cursor"
            value={replay ? formatCount(replay.cursor) : "—"}
            hint="index of the next execution bar"
          />
        </div>
      </div>
    </Panel>
  );
}

export function ReplayProgressPanel({ replay }: { replay: ReplayState | undefined }) {
  return (
    <Panel
      title="Replay Lifecycle"
      icon={<Clock className="w-4 h-4 text-primary" aria-hidden="true" />}
      badge={
        <Badge
          variant={replay?.status === "running" ? "default" : "outline"}
          className="font-mono uppercase text-[10px] tracking-widest"
        >
          {statusLabel(replay?.status ?? "unknown")}
        </Badge>
      }
      description="The Python replay is the state machine. This panel only reports it."
    >
      <div className="p-5 flex flex-col gap-0.5">
        <StatRow
          label="Current bar"
          value={formatTimestamp(replay?.current_timestamp)}
          mono={false}
          hint="null until the first step"
        />
        <StatRow
          label="Next bar"
          value={formatTimestamp(replay?.next_timestamp)}
          mono={false}
          hint="null once the dataset is exhausted"
        />
        <StatRow
          label="Next candle available"
          value={
            replay ? (replay.next_candle_available ? "yes" : "no") : "—"
          }
        />
        <StatRow
          label="Replay id"
          value={replay?.replay_id ?? "—"}
        />
        <StatRow
          label="Strategy config hash"
          value={replay?.strategy.config_hash ?? "—"}
          hint="SHA-256 of the frozen StrategyConfig"
        />
        <StatRow
          label="Dataset SHA-256"
          value={replay?.dataset.sha256 ?? "—"}
          hint={`${replay?.dataset.candle_count ?? "?"} candles, ${replay?.dataset.asset ?? "?"} ${replay?.dataset.timeframe ?? "?"}`}
        />
        <StatRow
          label="Execution model"
          value={replay?.execution.execution_model ?? "—"}
          hint={`fee ${replay?.execution.fee_rate ?? "?"} · slippage ${replay?.execution.slippage_rate ?? "?"} · risk fraction ${replay?.execution.risk_fraction ?? "?"}`}
        />
      </div>
    </Panel>
  );
}

export function OpenPositionPanel({
  replay,
}: {
  replay: ReplayState | undefined;
}) {
  const position = replay?.open_position;

  return (
    <Panel
      title="Open Position"
      icon={
        replay?.has_open_position ? (
          <TrendingUp className="w-4 h-4 text-success" aria-hidden="true" />
        ) : (
          <TrendingDown className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
        )
      }
      badge={
        <Badge
          variant={replay?.has_open_position ? "default" : "outline"}
          className="font-mono uppercase text-[10px] tracking-widest"
        >
          {replay?.has_open_position ? "Open" : "Flat"}
        </Badge>
      }
      description="At most one: the broker's single-position rule is unchanged."
    >
      {!position ? (
        <EmptyPanel
          title="Flat"
          hint={
            replay
              ? "The engine reports no open paper position."
              : "Reading position state from the engine."
          }
        />
      ) : (
        <div className="p-5 flex flex-col gap-0.5">
          <div className="flex items-center gap-2 pb-3">
            <Badge
              variant="outline"
              className={`font-mono uppercase tracking-wider text-[10px] ${sideClass(position.side)}`}
            >
              {sideLabel(position.side)}
            </Badge>
            <span className="text-xs text-muted-foreground font-mono">
              {position.reason}
            </span>
          </div>

          <StatRow label="Entry price" value={formatPrice(position.entry_price)} />
          <StatRow
            label="Quantity"
            value={formatQuantity(position.quantity)}
            hint="computed by the engine from cash and the risk fraction"
          />
          <StatRow label="Entry time" value={formatTimestamp(position.entry_time)} mono={false} />
          <StatRow label="Signal close" value={formatPrice(position.signal_close ?? Number.NaN)} />
          <StatRow label="Support at entry" value={formatPrice(position.support_at_entry ?? Number.NaN)} />
          <StatRow label="Resistance at entry" value={formatPrice(position.resistance_at_entry ?? Number.NaN)} />
          <StatRow
            label="Breakout distance"
            value={formatFractionAsPercent(position.breakout_distance)}
          />
          <StatRow
            label="Retest distance"
            value={formatFractionAsPercent(position.retest_distance)}
          />
          <StatRow
            label="Realised volatility"
            value={formatFractionAsPercent(position.realised_volatility)}
            hint="hourly stdev of simple returns, not annualised"
          />

          <div className="mt-3 border border-border rounded-md px-3 py-2 bg-muted/20">
            <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
              No unrealised P&amp;L is shown
            </p>
            <p className="text-[11px] text-muted-foreground mt-1 leading-relaxed">
              The engine has no live mark price, so an unrealised figure would have
              to be invented. Realised P&amp;L appears only when a trade closes.
            </p>
          </div>
        </div>
      )}
    </Panel>
  );
}

export function LastSignalPanel({
  signal,
}: {
  signal: ReplaySignal | undefined | null;
}) {
  if (!signal) {
    return (
      <Panel
        title="Last Signal"
        icon={<Radio className="w-4 h-4 text-primary" aria-hidden="true" />}
        description="The engine's own observation. Not an order and not a fill."
      >
        <EmptyPanel
          title="No signal yet"
          hint="The engine reports no observation until the replay has stepped."
        />
      </Panel>
    );
  }

  return (
    <Panel
      title="Last Signal"
      icon={<Radio className="w-4 h-4 text-primary" aria-hidden="true" />}
      badge={
        <Badge
          variant="outline"
          className={`font-mono uppercase tracking-wider text-[10px] ${
            signal.side === "flat"
              ? "border-muted-foreground/40 text-muted-foreground"
              : sideClass(signal.side as "long" | "short")
          }`}
        >
          {sideLabel(signal.side)}
        </Badge>
      }
      description="The engine's own observation. Not an order and not a fill."
    >
      <div className="p-5 flex flex-col gap-0.5">
        <StatRow label="Reason" value={signal.reason} mono={false} />
        <StatRow label="Side" value={sideLabel(signal.side)} mono={false} />
        <StatRow
          label="Signal close"
          value={formatPrice(signal.price)}
          hint="the signal bar's close, not a fill price"
        />
        <StatRow label="Support" value={formatPrice(signal.support)} />
        <StatRow label="Resistance" value={formatPrice(signal.resistance)} />
        <StatRow
          label="Trend"
          value={signal.trend}
          mono={false}
          hint={`trend_state: ${signal.trend_state ?? "—"}`}
        />
        <StatRow
          label="Breakout / retest flags"
          value={`${signal.breakout ? "breakout" : "—"} / ${signal.retest ? "retest" : "—"}`}
          mono={false}
        />
        <StatRow
          label="Breakout distance"
          value={formatFractionAsPercent(signal.breakout_distance)}
        />
        <StatRow
          label="Retest distance"
          value={formatFractionAsPercent(signal.retest_distance)}
        />
        <StatRow
          label="Realised volatility"
          value={formatFractionAsPercent(signal.realised_volatility)}
        />
        <StatRow label="Mean range" value={formatPrice(signal.mean_range ?? Number.NaN)} />
      </div>
    </Panel>
  );
}

export function StatisticsPanel({
  statistics,
}: {
  statistics: StatisticsResponse | undefined;
}) {
  return (
    <Panel
      title="Closed-Trade Statistics"
      icon={<BarChart2 className="w-4 h-4 text-primary" aria-hidden="true" />}
      description={`Server-computed over ${statistics?.basis ?? "closed_trades"}. No frontend aggregation.`}
    >
      {!statistics ? (
        <EmptyPanel title="No statistics" hint="The server has reported none yet." />
      ) : (
        <div className="p-5 flex flex-col gap-0.5">
          <StatRow label="Trades" value={formatCount(statistics.trades)} />
          <StatRow
            label="Net P&L"
            tone={statistics.net_pnl > 0 ? "success" : statistics.net_pnl < 0 ? "destructive" : "muted"}
            value={formatSignedMoney(statistics.net_pnl)}
          />
          <StatRow label="Win rate" value={formatPercent(statistics.win_rate)} />
          <StatRow
            label="Profit factor"
            value={
              statistics.profit_factor_infinite
                ? "∞ (no losing trades)"
                : formatPercent(statistics.profit_factor)
            }
            mono={!statistics.profit_factor_infinite}
          />
          <StatRow label="Average P&L" value={formatSignedMoney(statistics.average_pnl)} />
          <StatRow label="Max drawdown" value={formatSignedMoney(statistics.max_drawdown)} />
          <StatRow label="Ending balance" value={formatMoney(statistics.ending_balance)} />

          <div className="mt-3 border-t border-border pt-2 flex flex-col gap-0.5">
            <StatRow label="Fee total" value={formatMoney(statistics.costs.fee_total)} />
            <StatRow label="Slippage total" value={formatMoney(statistics.costs.slippage_total)} />
            <StatRow label="Spread total" value={formatMoney(statistics.costs.spread_total)} />
            <StatRow
              label="Total friction"
              value={formatMoney(statistics.costs.total_friction)}
              hint="reported, never deducted twice"
            />
          </div>
        </div>
      )}
    </Panel>
  );
}

export function TradeJournalPanel({
  trades,
}: {
  trades: TradesResponse | undefined;
}) {
  const rows = trades?.trades ?? [];

  return (
    <Panel
      title="Trade Journal"
      icon={<Activity className="w-4 h-4 text-primary" aria-hidden="true" />}
      badge={
        <Badge variant="secondary" className="font-mono text-[10px]">
          {formatCount(trades?.trade_count ?? 0)}
        </Badge>
      }
      description="The broker's own append order. P&L and friction are engine figures."
    >
      {rows.length === 0 ? (
        <EmptyPanel
          title="No closed trades"
          hint="Step the replay until an exit rule fires; the trade appears here with its realised P&L."
        />
      ) : (
        <div className="w-full overflow-x-auto">
          <table className="w-full text-sm text-left" data-testid="trade-journal">
            <thead className="text-[10px] text-muted-foreground uppercase tracking-widest bg-muted/30 border-b">
              <tr>
                <th className="px-5 py-3 font-bold">Side</th>
                <th className="px-5 py-3 font-bold">Reason</th>
                <th className="px-5 py-3 font-bold">Entry</th>
                <th className="px-5 py-3 font-bold">Exit</th>
                <th className="px-5 py-3 font-bold text-right">Quantity</th>
                <th className="px-5 py-3 font-bold text-right">Net P&L</th>
                <th className="px-5 py-3 font-bold text-right">Friction</th>
                <th className="px-5 py-3 font-bold text-right">Bars</th>
                <th className="px-5 py-3 font-bold">Exit reason</th>
              </tr>
            </thead>
            <tbody className="font-mono text-xs">
              {rows.map((trade, index) => (
                <tr
                  key={`${trade.entry_time}-${index}`}
                  className="border-b last:border-0 hover:bg-muted/10 transition-colors"
                >
                  <td className="px-5 py-3">
                    <Badge
                      variant="outline"
                      className={`font-sans font-bold uppercase tracking-wider text-[10px] ${sideClass(trade.side)}`}
                    >
                      {sideLabel(trade.side)}
                    </Badge>
                  </td>
                  <td className="px-5 py-3 font-sans text-muted-foreground">{trade.reason}</td>
                  <td className="px-5 py-3 text-right">{formatPrice(trade.entry_price)}</td>
                  <td className="px-5 py-3 text-right text-muted-foreground">
                    {trade.exit_price === null ? "—" : formatPrice(trade.exit_price)}
                  </td>
                  <td className="px-5 py-3 text-right">{formatQuantity(trade.quantity)}</td>
                  <td
                    className={`px-5 py-3 text-right font-bold ${
                      (trade.net_pnl ?? 0) >= 0 ? "text-success" : "text-destructive"
                    }`}
                  >
                    {formatSignedMoney(trade.net_pnl)}
                  </td>
                  <td className="px-5 py-3 text-right text-muted-foreground">
                    {formatMoney(trade.total_friction ?? Number.NaN)}
                  </td>
                  <td className="px-5 py-3 text-right">{trade.bars_held}</td>
                  <td className="px-5 py-3 font-sans text-muted-foreground">
                    {trade.exit_reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}