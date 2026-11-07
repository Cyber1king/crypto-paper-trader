import { useState } from 'react';

import { StandardPage } from '@/components/standard-page';
import { Badge, Card, CardContent, CardHeader, CardTitle, Select } from '@/components/ui';
import { ErrorPanel, LoadingPanel } from '@/components/state';
import type { ClosedTrade } from '@/lib/api';
import { queryError, useTrades } from '@/lib/hooks';

type SideFilter = 'all' | 'long' | 'short';

function currency(value: number | null): string {
  return value == null
    ? '—'
    : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
}

function decimal(value: number | null, digits = 6): string {
  return value == null ? '—' : value.toFixed(digits);
}

function pnlClass(value: number): string {
  if (value === 0) return 'text-muted-foreground';
  return value > 0 ? 'text-success' : 'text-destructive';
}

function sumTrades(trades: readonly ClosedTrade[], select: (trade: ClosedTrade) => number | null): number {
  return trades.reduce((total, trade) => total + (select(trade) ?? 0), 0);
}

function Detail({ label, value, className = '' }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={`mt-1 text-sm ${className}`}>{value}</dd>
    </div>
  );
}

function JournalBody() {
  const tradesQuery = useTrades(true);
  const tradesError = queryError(tradesQuery);
  const [sideFilter, setSideFilter] = useState<SideFilter>('all');
  const [exitReasonFilter, setExitReasonFilter] = useState('all');
  const trades = tradesQuery.data?.trades ?? [];
  const exitReasons = Array.from(new Set(trades.map((trade) => trade.exit_reason)));
  const visibleTrades = trades.filter((trade) =>
    (sideFilter === 'all' || trade.side === sideFilter) &&
    (exitReasonFilter === 'all' || trade.exit_reason === exitReasonFilter),
  );
  const grossPnl = sumTrades(trades, (trade) => trade.pnl);
  const netPnl = sumTrades(trades, (trade) => trade.net_pnl);
  const totalFriction = sumTrades(trades, (trade) => trade.total_friction);
  const totalFees = sumTrades(trades, (trade) => trade.fee_total);
  const totalSlippage = sumTrades(trades, (trade) => trade.slippage_total);
  const totalSpread = sumTrades(trades, (trade) => trade.spread_total);
  const wins = trades.filter((trade) => trade.net_pnl != null && trade.net_pnl > 0).length;

  return (
    <div className="flex flex-col gap-6" data-testid="journal-page">
      <div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
        Closed trades from the default BTC/USDT paper session. Per-instrument trade history will be added when the backend adds instrument support (Phase 5).
      </div>
      <p className="text-sm text-muted-foreground">
        Closed simulated trades as recorded by the engine. Trade values and details
        are shown from the API response; filters apply locally to the loaded trades.
      </p>

      {tradesError ? (
        <ErrorPanel
          error={tradesError}
          title="Trade journal unavailable"
          onRetry={() => void tradesQuery.refetch()}
        />
      ) : tradesQuery.isLoading && !tradesQuery.data ? (
        <LoadingPanel label="Loading trade journal" />
      ) : (
        <>
          <Card data-testid="journal-summary">
            <CardHeader><CardTitle>Trade Summary</CardTitle></CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Detail label="Total trades" value={String(tradesQuery.data?.trade_count ?? 0)} />
                <Detail label="Total gross P&amp;L" value={currency(grossPnl)} className={pnlClass(grossPnl)} />
                <Detail label="Total net P&amp;L" value={currency(netPnl)} className={pnlClass(netPnl)} />
                <Detail label="Total friction" value={currency(totalFriction)} />
                <Detail label="Total fees" value={currency(totalFees)} />
                <Detail label="Total slippage" value={currency(totalSlippage)} />
                <Detail label="Total spread" value={currency(totalSpread)} />
                <Detail label="Win rate" value={trades.length === 0 ? '—' : `${((wins / trades.length) * 100).toFixed(1)}%`} />
              </dl>
            </CardContent>
          </Card>

          {trades.length === 0 ? (
            <Card><CardContent className="py-6 text-sm text-muted-foreground">
              No closed trades yet. Start a replay on the Overview page and step through it to generate trades.
            </CardContent></Card>
          ) : (
            <Card data-testid="journal-trade-table">
              <CardHeader><CardTitle>Closed Trades</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-4">
                  <label className="flex items-center gap-2 text-sm">
                    Side
                    <Select value={sideFilter} onChange={(event) => setSideFilter(event.target.value as SideFilter)}>
                      <option value="all">All</option>
                      <option value="long">Long</option>
                      <option value="short">Short</option>
                    </Select>
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    Exit reason
                    <Select value={exitReasonFilter} onChange={(event) => setExitReasonFilter(event.target.value)}>
                      <option value="all">All</option>
                      {exitReasons.map((reason) => <option key={reason} value={reason}>{reason}</option>)}
                    </Select>
                  </label>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-xs text-muted-foreground">
                        <th className="p-2">Side</th>
                        <th className="p-2">Entry time</th>
                        <th className="p-2">Exit time</th>
                        <th className="p-2">Entry price</th>
                        <th className="p-2">Exit price</th>
                        <th className="p-2">Quantity</th>
                        <th className="p-2">Bars held</th>
                        <th className="p-2">Gross P&amp;L</th>
                        <th className="p-2">Net P&amp;L</th>
                        <th className="p-2">Friction</th>
                        <th className="p-2">Exit reason</th>
                        <th className="p-2">Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleTrades.map((trade, index) => (
                        <tr key={`${trade.entry_time}-${index}`} className="border-b align-top">
                          <td className="p-2">
                            <Badge variant="outline" className={trade.side === 'long' ? 'border-success/40 text-success' : 'border-destructive/40 text-destructive'}>
                              {trade.side.toUpperCase()}
                            </Badge>
                          </td>
                          <td className="p-2 whitespace-nowrap">{trade.entry_time}</td>
                          <td className="p-2 whitespace-nowrap">{trade.exit_time ?? '—'}</td>
                          <td className="p-2 whitespace-nowrap">{currency(trade.entry_price)}</td>
                          <td className="p-2 whitespace-nowrap">{currency(trade.exit_price)}</td>
                          <td className="p-2">{decimal(trade.quantity)}</td>
                          <td className="p-2">{String(trade.bars_held)}</td>
                          <td className={`p-2 whitespace-nowrap ${trade.pnl == null ? 'text-muted-foreground' : pnlClass(trade.pnl)}`}>{currency(trade.pnl)}</td>
                          <td className={`p-2 whitespace-nowrap ${trade.net_pnl == null ? 'text-muted-foreground' : pnlClass(trade.net_pnl)}`}>{currency(trade.net_pnl)}</td>
                          <td className="p-2 whitespace-nowrap">{currency(trade.total_friction)}</td>
                          <td className="p-2">{trade.exit_reason}</td>
                          <td className="p-2">
                            <details>
                              <summary className="cursor-pointer text-primary">Details</summary>
                              <dl className="mt-3 grid min-w-[320px] grid-cols-2 gap-3 rounded-md bg-muted/30 p-3">
                                <Detail label="Reason" value={trade.reason} />
                                <Detail label="Signal close at entry" value={currency(trade.signal_close)} />
                                <Detail label="Trend state" value={trade.trend_state ?? '—'} />
                                <Detail label="Breakout distance" value={decimal(trade.breakout_distance)} />
                                <Detail label="Retest distance" value={decimal(trade.retest_distance)} />
                                <Detail label="Realised volatility" value={decimal(trade.realised_volatility)} />
                                <Detail label="Mean range" value={decimal(trade.mean_range)} />
                                <Detail label="Support at entry" value={currency(trade.support_at_entry)} />
                                <Detail label="Resistance at entry" value={currency(trade.resistance_at_entry)} />
                                <Detail label="Raw entry price" value={currency(trade.raw_entry_price)} />
                                <Detail label="Raw exit price" value={currency(trade.raw_exit_price)} />
                                <Detail label="Fees" value={currency(trade.fee_total)} />
                                <Detail label="Slippage" value={currency(trade.slippage_total)} />
                                <Detail label="Spread" value={currency(trade.spread_total)} />
                              </dl>
                            </details>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {visibleTrades.length === 0 ? <p className="py-4 text-sm text-muted-foreground">No trades match these filters.</p> : null}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

export function Journal() {
  return (
    <StandardPage
      title="Standard trade journal"
      subtitle="Simulated trades - read from the engine"
    >
      {() => <JournalBody />}
    </StandardPage>
  );
}
