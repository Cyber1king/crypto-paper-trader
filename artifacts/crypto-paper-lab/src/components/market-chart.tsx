/**
 * Market chart (Phase 18H).
 *
 * ## Real candles only
 *
 * The data is `GET /api/market` — BTC/USDT 1h OHLCV from the frozen research
 * dataset, served by the engine's own loader. Nothing here generates a price,
 * interpolates a bar, jitters a close or seeds a random walk. The previous
 * implementation's `Math.sin`/`Math.cos` feed and its three-second jitter are gone,
 * and the badge that used to read "Synthetic OHLCV Feed" now names the actual
 * dataset and its hash.
 *
 * Support and resistance are drawn from `ReplaySignal` / `OpenPosition` when the
 * engine has reported them. Those are the strategy's own levels. They are not
 * recomputed here — the previous chart called a frontend `analyzeCandles` whose
 * support and resistance were `min`/`max` over the last 20 closes, which is a
 * different calculation from the engine's and disagreed with it.
 *
 * ## Windowing
 *
 * The API exposes `start`, `end` and `limit` but no cursor or offset. So the only
 * alignment available is passing `end` at the replay's current bar, which makes the
 * chart's last candle correspond to where the replay is. That is a genuine
 * improvement over a dataset-wide tail, and it is the whole of what the contract
 * allows — adding an offset parameter would be a backend change, which Phase 18
 * forbids.
 */

import { useMemo } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Fingerprint } from "lucide-react";

import { Badge } from "@/components/ui";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui";
import { ApiUnavailablePanel, LoadingPanel, Panel } from "@/components/state";
import type { ApiError, MarketResponse, ReplaySignal } from "@/lib/api";
import { chartLabel, formatPrice, formatQuoted, shortHash } from "@/lib/format";

interface ChartPoint {
  readonly label: string;
  readonly open: number;
  readonly high: number;
  readonly low: number;
  readonly close: number;
  readonly volume: number;
  readonly timestamp: string;
}

function toPoints(market: MarketResponse | undefined): ChartPoint[] {
  if (!market) {
    return [];
  }

  // The label is derived from the candle's own timestamp. No date is invented for
  // a candle that lacks one; the point simply renders unlabelled.
  return market.candles.map((candle) => ({
    label: chartLabel(candle.timestamp),
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
    volume: candle.volume,
    timestamp: candle.timestamp,
  }));
}

export function MarketChart({
  market,
  isLoading,
  error,
  signal,
  asset,
  timeframe,
  onRetry,
}: {
  market: MarketResponse | undefined;
  isLoading: boolean;
  error: ApiError | null;
  signal: ReplaySignal | null | undefined;
  asset?: string;
  timeframe?: string;
  onRetry?: () => void;
}) {
  const points = useMemo(() => toPoints(market), [market]);

  const lastClose = points.length > 0 ? points[points.length - 1].close : null;

  // Only draw levels the engine has actually reported. Absent levels produce no
  // reference line rather than a line at zero.
  const levels = useMemo(() => {
    if (!signal) {
      return { support: null, resistance: null };
    }

    return { support: signal.support, resistance: signal.resistance };
  }, [signal]);

  if (error) {
    return (
      <Card>
        <CardHeader className="py-3 border-b bg-muted/20">
          <CardTitle className="text-sm font-bold uppercase tracking-wide flex items-center gap-2">
            <Activity className="w-4 h-4 text-primary" aria-hidden="true" />
            Price History
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ApiUnavailablePanel error={error} onRetry={onRetry} />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="flex-1 min-h-[440px] flex flex-col overflow-hidden">
      {/*
       * `flex-wrap` on the header row.

       * This row carries two groups that must not shrink: the asset title, the last
       * close, the timeframe, and the dataset badge. Together they are roughly 570px,
       * which no narrow viewport can hold. Rather than clip any of them or drop one
       * below a legible size, the groups wrap onto a second line once they no longer
       * fit. At desktop widths there is ample room, so this changes nothing there —
       * it only engages when the alternative was overflow.

       * The title wraps rather than truncating. An earlier pass used `truncate` here
       * and it did remove the overflow, but at 390px it clipped the panel's own name to
       * "BTC/USDT Price His…" — trading a layout defect for a content one, which is not
       * a fix. `break-words` plus a wrapping basis lets the title occupy two lines and
       * stay fully readable. `basis-full` at the narrowest breakpoint puts the price
       * badge on its own line, so the title has the full card width to itself.
       */}
      <CardHeader className="py-4 border-b flex flex-row flex-wrap items-center justify-between gap-3 bg-muted/20">
        <div className="flex items-center gap-4 min-w-0 basis-full sm:basis-auto">
          <CardTitle className="text-lg flex items-center gap-2 min-w-0">
            <Activity className="w-5 h-5 text-primary shrink-0" aria-hidden="true" />
            <span className="break-words">{asset ?? "—"} Price History</span>
          </CardTitle>
          {lastClose !== null ? (
            <Badge variant="outline" className="font-mono text-sm shrink-0">
              {formatQuoted(lastClose)}
            </Badge>
          ) : null}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {timeframe ? (
            <Badge variant="secondary" className="uppercase font-mono text-[10px] tracking-widest text-muted-foreground">
              {timeframe}
            </Badge>
          ) : null}
          <Badge
            variant="outline"
            className="uppercase font-mono text-[10px] tracking-widest border-success/40 text-success bg-success/10"
            data-testid="chart-data-source"
          >
            Frozen research dataset
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="p-0 flex-1 relative bg-card">
        {/*
          The engine's levels, mirrored onto a non-visual node.

          Deliberately outside the chart: recharts renders nothing until its
          container has a non-zero size, which never happens under jsdom, so a node
          inside the chart would be absent from the DOM rather than merely
          unlabelled. Here the values are observable — and the point is that they
          are the *engine's*, present when it reported a signal and absent when it
          did not.
        */}
        <div
          data-testid="chart-engine-levels"
          data-support={levels.support === null ? "" : String(levels.support)}
          data-resistance={levels.resistance === null ? "" : String(levels.resistance)}
          className="hidden"
          aria-hidden="true"
        />

        {isLoading && points.length === 0 ? (
          <LoadingPanel label="Loading candles" />
        ) : points.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-center text-muted-foreground py-20 px-6">
            <p className="text-sm font-bold uppercase tracking-wider">
              No candle data available
            </p>
            <p className="text-xs mt-2 max-w-[380px]">
              The engine returned no candles for this window. No substitute series is
              drawn — a synthetic chart would misrepresent simulated research data as
              market history.
            </p>
          </div>
        ) : (
          <div className="absolute inset-0 p-4">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={points as ChartPoint[]}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} vertical={false} />
                <XAxis
                  dataKey="label"
                  opacity={0.5}
                  tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }}
                  tickMargin={10}
                  axisLine={false}
                  tickLine={false}
                  minTickGap={40}
                />
                <YAxis
                  yAxisId="price"
                  domain={["auto", "auto"]}
                  orientation="right"
                  tick={{ fontSize: 11, fontFamily: "var(--font-mono)" }}
                  strokeOpacity={0}
                  tickFormatter={(value: number) => formatPrice(value)}
                  width={72}
                />
                <YAxis yAxisId="volume" orientation="left" hide />

                {levels.resistance !== null ? (
                  <ReferenceLine
                    y={levels.resistance}
                    yAxisId="price"
                    stroke="hsl(var(--destructive))"
                    strokeDasharray="4 4"
                    label={{
                      position: "insideTopLeft",
                      value: "RESISTANCE (engine)",
                      fill: "hsl(var(--destructive))",
                      fontSize: 10,
                      fontFamily: "var(--font-mono)",
                    }}
                    opacity={0.7}
                  />
                ) : null}

                {levels.support !== null ? (
                  <ReferenceLine
                    y={levels.support}
                    yAxisId="price"
                    stroke="hsl(var(--success))"
                    strokeDasharray="4 4"
                    label={{
                      position: "insideBottomLeft",
                      value: "SUPPORT (engine)",
                      fill: "hsl(var(--success))",
                      fontSize: 10,
                      fontFamily: "var(--font-mono)",
                    }}
                    opacity={0.7}
                  />
                ) : null}

                {/*
                  The levels are mirrored onto a non-visual node so they can be
                  asserted. It sits *outside* the chart on purpose: recharts renders
                  nothing at all until its container has a non-zero size, which never
                  happens under jsdom, so anything inside would be absent from the
                  DOM rather than merely unlabelled.
                */}

                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    borderColor: "hsl(var(--border))",
                    fontFamily: "var(--font-mono)",
                    fontSize: "12px",
                    borderRadius: "8px",
                    boxShadow: "0 4px 12px -2px rgb(0 0 0 / 0.1)",
                  }}
                  itemStyle={{ color: "hsl(var(--foreground))" }}
                  labelStyle={{ color: "hsl(var(--muted-foreground))", marginBottom: "4px" }}
                />
                <Bar yAxisId="volume" dataKey="volume" fill="hsl(var(--primary))" opacity={0.15} />
                <Line
                  yAxisId="price"
                  type="monotone"
                  dataKey="close"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{
                    r: 6,
                    fill: "hsl(var(--primary))",
                    stroke: "hsl(var(--background))",
                    strokeWidth: 3,
                  }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>

      <div className="border-t px-4 py-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-muted-foreground font-mono">
        <span className="flex items-center gap-1">
          <Fingerprint className="w-3 h-3" aria-hidden="true" />
          dataset SHA-256
        </span>
        <span title={market?.metadata.dataset_sha256 ?? ""} data-testid="chart-dataset-hash">
          {shortHash(market?.metadata.dataset_sha256, 16)}
        </span>
        <span>·</span>
        <span>
          {formatCount(market?.metadata.returned_candles ?? 0)} of{" "}
          {formatCount(market?.metadata.dataset_candles ?? 0)} candles
        </span>
        {market?.metadata.truncated ? (
          <>
            <span>·</span>
            <span>window truncated by the server limit</span>
          </>
        ) : null}
        <span>·</span>
        <span>source: {market?.metadata.source ?? "—"}</span>
      </div>
    </Card>
  );
}

function formatCount(value: number): string {
  return Number.isFinite(value) ? value.toLocaleString("en-US") : "—";
}

/**
 * Read-only authoritative configuration (Phase 18, Decision 2).
 *
 * The asset, timeframe and strategy selectors the dashboard used to offer are
 * replaced by this. The engine supports exactly one configuration — BTC/USDT on 1h
 * with one frozen `StrategyConfig` — so offering a choice was offering four
 * settings of which three were fiction. These values are read from
 * `ReplayState.dataset` and `ReplayState.strategy`, so they cannot drift from what
 * the engine is actually running.
 */
export function EngineConfigurationPanel({
  replay,
}: {
  replay:
    | {
        dataset?: { asset?: string; timeframe?: string; sha256?: string; candle_count?: number };
        strategy?: { config_repr?: string; config_hash?: string };
        execution?: { execution_model?: string; fee_rate?: number; slippage_rate?: number; spread_rate?: number; risk_fraction?: number };
      }
    | undefined;
}) {
  return (
    <Panel
      title="Engine Configuration"
      icon={<Fingerprint className="w-4 h-4 text-primary" aria-hidden="true" />}
      description="Read-only. The engine supports one frozen configuration."
    >
      <div className="p-4 grid grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-0.5">
        <ConfigRow label="Asset" value={replay?.dataset?.asset ?? "—"} testId="config-asset" />
        <ConfigRow
          label="Timeframe"
          value={replay?.dataset?.timeframe ?? "—"}
          testId="config-timeframe"
        />
        <ConfigRow
          label="Strategy"
          value="Breakout + Retest"
          hint="trend-filtered level breaks and retests, per the engine's gates"
          testId="config-strategy"
        />
        <ConfigRow
          label="Strategy config hash"
          value={shortHash(replay?.strategy?.config_hash, 16)}
          title={replay?.strategy?.config_hash}
          testId="config-strategy-hash"
        />
        <ConfigRow
          label="Dataset SHA-256"
          value={shortHash(replay?.dataset?.sha256, 16)}
          title={replay?.dataset?.sha256}
          testId="config-dataset-hash"
        />
        <ConfigRow
          label="Candles in dataset"
          value={
            replay?.dataset?.candle_count === undefined
              ? "—"
              : replay.dataset.candle_count.toLocaleString("en-US")
          }
          testId="config-candle-count"
        />
        <ConfigRow
          label="Execution model"
          value={replay?.execution?.execution_model ?? "—"}
          testId="config-execution-model"
        />
        <ConfigRow
          label="Fee / slippage"
          value={`${replay?.execution?.fee_rate ?? "—"} / ${replay?.execution?.slippage_rate ?? "—"}`}
          testId="config-costs"
        />
        <ConfigRow
          label="Risk fraction"
          value={replay?.execution?.risk_fraction === undefined ? "—" : String(replay.execution.risk_fraction)}
          hint="position size as a fraction of cash, set by the engine"
          testId="config-risk-fraction"
        />
      </div>

      <p className="px-4 pb-4 text-[11px] text-muted-foreground border-t pt-3 leading-relaxed">
        Asset, timeframe and strategy are not selectable. The research engine is
        single-asset and single-timeframe, and its configuration is a frozen
        research artifact — a switch that could change them would imply a capability
        the engine does not have.
      </p>
    </Panel>
  );
}

function ConfigRow({
  label,
  value,
  hint,
  title,
  testId,
}: {
  label: string;
  value: string;
  hint?: string;
  title?: string;
  testId?: string;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
        {label}
      </div>
      <div className="font-mono text-sm font-semibold" title={title} data-testid={testId}>
        {value}
      </div>
      {hint ? <div className="text-[10px] text-muted-foreground leading-snug">{hint}</div> : null}
    </div>
  );
}