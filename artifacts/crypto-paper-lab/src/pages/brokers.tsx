import { Badge, Card, CardContent, CardHeader, CardTitle } from '@/components/ui';
import type { AccountSnapshot, BrokerStatusResponse, Position } from '@/lib/api';
import { useBrokerBalance, useBrokerPositions } from '@/lib/hooks';

type BrokerName = 'paper' | 'mt5_demo' | 'binance_testnet';

const BROKERS: readonly { brokerName: BrokerName; label: string }[] = [
  { brokerName: 'paper', label: 'Paper' },
  { brokerName: 'mt5_demo', label: 'MT5 Demo' },
  { brokerName: 'binance_testnet', label: 'Binance Testnet' },
];

function isBrokerStatus(value: AccountSnapshot | BrokerStatusResponse): value is BrokerStatusResponse {
  return 'status' in value;
}

function isPositionsStatus(value: Position[] | BrokerStatusResponse): value is BrokerStatusResponse {
  return !Array.isArray(value);
}

const ISO_CURRENCIES = new Set([
  'USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'NZD', 'CAD',
  'INR', 'GHS', 'CNY', 'HKD', 'SGD', 'ZAR', 'SEK', 'NOK',
]);

function formatMoney(value: number, currency: string): string {
  if (ISO_CURRENCIES.has(currency.toUpperCase())) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency.toUpperCase(),
      maximumFractionDigits: 2,
    }).format(value);
  }
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  return `${formatted} ${currency.toUpperCase()}`;
}

function formatQuantity(value: number): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 8 }).format(value);
}

function formatTimestamp(value: string): string {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value;
  return `${timestamp.toLocaleTimeString('en-GB', {
    timeZone: 'UTC',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })} UTC`;
}

function StatusBadge({ status }: { status: BrokerStatusResponse['status'] }) {
  const label = status === 'disabled'
    ? 'Disabled'
    : status === 'unavailable'
      ? 'Unavailable'
      : 'Error';
  const color = status === 'error'
    ? 'border-destructive/30 bg-destructive/10 text-destructive'
    : 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300';
  return <Badge variant="outline" className={color}>{label}</Badge>;
}

function BrokerCard({ brokerName, label }: { brokerName: BrokerName; label: string }) {
  const balance = useBrokerBalance(brokerName);
  const positions = useBrokerPositions(brokerName);
  const requestError = balance.error ?? positions.error;

  if (requestError) {
    return (
      <Card className="border-destructive/50" data-testid={`broker-card-${brokerName}`}>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <CardTitle>{label}</CardTitle>
            <Badge variant="destructive">Connection error</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{requestError.message}</p>
        </CardContent>
      </Card>
    );
  }

  if (balance.isLoading || !balance.data) {
    return (
      <Card data-testid={`broker-card-${brokerName}`}>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <CardTitle>{label}</CardTitle>
            <Badge variant="outline">Loading</Badge>
          </div>
        </CardHeader>
        <CardContent><p className="text-sm text-muted-foreground">Loading broker account…</p></CardContent>
      </Card>
    );
  }

  if (isBrokerStatus(balance.data)) {
    return (
      <Card data-testid={`broker-card-${brokerName}`}>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <CardTitle>{label}</CardTitle>
            <StatusBadge status={balance.data.status} />
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{balance.data.reason}</p>
        </CardContent>
      </Card>
    );
  }

  const account = balance.data;
  const positionData = positions.data;

  return (
    <Card data-testid={`broker-card-${brokerName}`}>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle>{label}</CardTitle>
          <Badge className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" variant="outline">
            Connected
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <dl className="grid grid-cols-2 gap-4">
          <div><dt className="text-xs text-muted-foreground">Balance</dt><dd className="mt-1 text-sm font-medium">{formatMoney(account.balance, account.currency)}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Equity</dt><dd className="mt-1 text-sm font-medium">{formatMoney(account.equity, account.currency)}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Free margin</dt><dd className="mt-1 text-sm font-medium">{formatMoney(account.free_margin, account.currency)}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Used margin</dt><dd className="mt-1 text-sm font-medium">{formatMoney(account.used_margin, account.currency)}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Leverage</dt><dd className="mt-1 text-sm font-medium">{account.leverage == null ? '—' : `${account.leverage}:1`}</dd></div>
        </dl>
        <p className="text-xs text-muted-foreground">Last updated: {formatTimestamp(account.timestamp)}</p>

        <section aria-label={`${label} positions`} className="border-t pt-4">
          <h4 className="mb-3 text-sm font-semibold">Positions</h4>
          {positions.isLoading && !positionData ? (
            <p className="text-sm text-muted-foreground">Loading positions…</p>
          ) : positionData && isPositionsStatus(positionData) ? (
            <p className="text-sm text-muted-foreground">{positionData.reason}</p>
          ) : positionData && positionData.length === 0 ? (
            <p className="text-sm text-muted-foreground">No open positions</p>
          ) : positionData ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-muted-foreground">
                  <tr>
                    <th scope="col" className="pb-2 pr-2 font-medium">Instrument</th>
                    <th scope="col" className="pb-2 pr-2 font-medium">Side</th>
                    <th scope="col" className="pb-2 pr-2 font-medium">Quantity</th>
                    <th scope="col" className="pb-2 pr-2 font-medium">Entry price</th>
                    <th scope="col" className="pb-2 font-medium">Unrealized P&amp;L</th>
                  </tr>
                </thead>
                <tbody>
                  {positionData.map((position, index) => (
                    <tr key={position.broker_position_id ?? `${position.instrument}-${index}`} className="border-t">
                      <td className="py-2 pr-2">{position.instrument}</td>
                      <td className={`py-2 pr-2 ${position.side === 'long' ? 'text-emerald-600' : 'text-destructive'}`}>{position.side}</td>
                      <td className="py-2 pr-2">{formatQuantity(position.quantity)}</td>
                      <td className="py-2 pr-2">{formatMoney(position.entry_price, account.currency)}</td>
                      <td className="py-2">{position.unrealized_pnl == null ? '—' : formatMoney(position.unrealized_pnl, account.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </CardContent>
    </Card>
  );
}

export function Brokers() {
  return (
    <div className="min-h-screen bg-background font-sans">
      <header className="border-b bg-card px-6 py-4 flex flex-col gap-1">
        <h1 className="font-bold text-lg tracking-tight">Live Brokers</h1>
        <p className="text-xs text-muted-foreground font-mono">Read-only account status</p>
      </header>
      <main className="p-6">
        <div className="mb-6 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
          Live broker read-only view. Balances shown here come directly from the broker or paper engine. No order placement or position modification is possible from this page. The Real Account Balance on the Money Management page is manually declared and is separate from all of these.
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {BROKERS.map((broker) => <BrokerCard key={broker.brokerName} {...broker} />)}
        </div>
      </main>
    </div>
  );
}
