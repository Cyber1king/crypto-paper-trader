import { StandardPage } from '@/components/standard-page';
import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui';
import {
  OpenPositionPanel,
  StandardAccountPanel,
  StatisticsPanel,
} from '@/components/standard-panels';
import { ErrorPanel, LoadingPanel } from '@/components/state';
import type { ModeInfo } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';
import {
  queryError,
  usePaperApi,
  useReplayState,
  useStandardAccount,
  useStatistics,
} from '@/lib/hooks';

function currency(value: number | null | undefined): string {
  if (value == null) return '—';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
}

function pnlClass(value: number | null | undefined): string {
  if (value == null || value === 0) return 'text-muted-foreground';
  return value > 0 ? 'text-success' : 'text-destructive';
}

function Metric({ label, children, className = '' }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={`mt-1 text-sm font-medium ${className}`}>{children}</dd>
    </div>
  );
}

function PortfolioBody({ mode }: { mode: ModeInfo }) {
  // Same gate the Overview page uses before it reads a replay.
  const controllable = Boolean(mode.available && mode.supports_execution);

  const replay = useReplayState(controllable ? mode : undefined, undefined);
  const account = useStandardAccount(true);
  const statistics = useStatistics(true);
  const api = usePaperApi();
  const position = useQuery({
    queryKey: ['position', mode.mode],
    queryFn: ({ signal }) => api.getPosition(signal),
    retry: false,
  });

  const replayError = queryError(replay);
  const accountError = queryError(account);
  const statisticsError = queryError(statistics);
  const positionError = queryError(position);
  const percentageChange = account.data && account.data.starting_balance !== 0
    ? ((account.data.balance - account.data.starting_balance) / account.data.starting_balance) * 100
    : null;
  const openPosition = position.data?.position;

  return (
    <div className="flex flex-col gap-6" data-testid="portfolio-page">
      <div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
        Portfolio figures from the default BTC/USDT paper session. Per-instrument portfolio will be added when the backend adds instrument support (Phase 5).
      </div>
      <p className="text-sm text-muted-foreground">
        Read-only view of the simulated Standard-mode account. Replay controls stay
        on the Overview page.
      </p>

      {replayError ? (
        <ErrorPanel
          error={replayError}
          title="Replay state unavailable"
          onRetry={() => void replay.refetch()}
        />
      ) : null}
      {accountError ? (
        <ErrorPanel
          error={accountError}
          title="Account unavailable"
          onRetry={() => void account.refetch()}
        />
      ) : null}
      {statisticsError ? (
        <ErrorPanel
          error={statisticsError}
          title="Statistics unavailable"
          onRetry={() => void statistics.refetch()}
        />
      ) : null}
      {positionError ? (
        <ErrorPanel
          error={positionError}
          title="Position unavailable"
          onRetry={() => void position.refetch()}
        />
      ) : null}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <Card data-testid="portfolio-account-card">
          <CardHeader><CardTitle>Account</CardTitle></CardHeader>
          <CardContent>
            {account.isLoading && !account.data ? <LoadingPanel label="Loading account" /> : account.data ? (
              <dl className="grid grid-cols-2 gap-4">
                <Metric label="Starting balance">{currency(account.data.starting_balance)}</Metric>
                <Metric label="Current balance">{currency(account.data.balance)}</Metric>
                <Metric label="Realized P&amp;L" className={pnlClass(account.data.realized_pnl)}>{currency(account.data.realized_pnl)}</Metric>
                <Metric label="Trade count">{String(account.data.trade_count)}</Metric>
                <Metric label="Change from start">{percentageChange == null ? '—' : `${percentageChange.toFixed(2)}%`}</Metric>
              </dl>
            ) : null}
          </CardContent>
        </Card>

        <Card data-testid="portfolio-open-position-card">
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle>Open Position</CardTitle>
              <Badge variant={openPosition ? 'default' : 'outline'}>{openPosition ? 'Open' : 'Flat'}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {position.isLoading && !position.data ? <LoadingPanel label="Loading position" /> : openPosition ? (
              <dl className="grid grid-cols-2 gap-4">
                <Metric label="Side" className={openPosition.side === 'long' ? 'text-success' : 'text-destructive'}>{openPosition.side.toUpperCase()}</Metric>
                <Metric label="Quantity">{String(openPosition.quantity)}</Metric>
                <Metric label="Entry price">{currency(openPosition.entry_price)}</Metric>
                <Metric label="Entry time">{openPosition.entry_time}</Metric>
              </dl>
            ) : position.data?.has_position === false ? (
              <p className="text-sm text-muted-foreground">No open position.</p>
            ) : null}
          </CardContent>
        </Card>

        <Card data-testid="portfolio-performance-card">
          <CardHeader><CardTitle>Performance</CardTitle></CardHeader>
          <CardContent>
            {statistics.isLoading && !statistics.data ? <LoadingPanel label="Loading performance" /> : statistics.data ? (
              <dl className="grid grid-cols-2 gap-4">
                <Metric label="Closed trades">{String(statistics.data.trades)}</Metric>
                <Metric label="Net P&amp;L" className={pnlClass(statistics.data.net_pnl)}>{currency(statistics.data.net_pnl)}</Metric>
                <Metric label="Win rate">{`${(statistics.data.win_rate * 100).toFixed(1)}%`}</Metric>
                <Metric label="Profit factor">{statistics.data.profit_factor_infinite ? '∞ (no losing trades)' : statistics.data.profit_factor == null ? '—' : statistics.data.profit_factor.toFixed(2)}</Metric>
                <Metric label="Average P&amp;L per trade" className={pnlClass(statistics.data.average_pnl)}>{currency(statistics.data.average_pnl)}</Metric>
                <Metric label="Max drawdown">{`${(statistics.data.max_drawdown * 100).toFixed(2)}%`}</Metric>
                <Metric label="Ending balance">{currency(statistics.data.ending_balance)}</Metric>
                {statistics.data.costs ? (
                  <Metric label="Total costs">{currency(statistics.data.costs.fee_total + statistics.data.costs.slippage_total + statistics.data.costs.spread_total)}</Metric>
                ) : null}
              </dl>
            ) : null}
          </CardContent>
        </Card>
      </div>

      {replay.isLoading && !replay.data ? (
        <LoadingPanel label="Loading replay state" />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-6 flex flex-col gap-6">
            <StandardAccountPanel replay={replay.data} account={account.data} />
            <OpenPositionPanel replay={replay.data} />
          </div>
          <div className="lg:col-span-6 flex flex-col gap-6">
            <StatisticsPanel statistics={statistics.data} />
          </div>
        </div>
      )}
    </div>
  );
}

export function Portfolio() {
  return (
    <StandardPage
      title="Standard paper portfolio"
      subtitle="Simulated account - read from the engine"
    >
      {(mode) => <PortfolioBody mode={mode} />}
    </StandardPage>
  );
}
