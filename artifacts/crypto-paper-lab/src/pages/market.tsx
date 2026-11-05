import { MarketChart } from '@/components/market-chart';
import { MarketContextBar } from '@/components/market-context-bar';
import {
  LoadingPanel,
  PaperOnlyBanner,
  Panel,
  StatRow,
} from '@/components/state';
import type { MarketQuery } from '@/lib/api';
import { formatCount, formatTimestamp, shortHash } from '@/lib/format';
import { queryError, useMarket } from '@/lib/hooks';

// The same window size the Overview chart requests. There is no replay position to
// align to on this page, so the request passes no start or end and takes the API's
// default window.
const MARKET_QUERY: MarketQuery = { limit: 200 };

export function Market() {
  const market = useMarket(MARKET_QUERY, undefined);
  const marketError = queryError(market);
  const metadata = market.data?.metadata;

  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">
      <header className="border-b bg-card px-6 py-4 flex flex-col gap-1">
        <h1 className="font-bold text-lg tracking-tight">Market analysis</h1>
        <p className="text-xs text-muted-foreground font-mono uppercase tracking-wider">
          Frozen research dataset - read from the engine
        </p>
      </header>

      <MarketContextBar
        asset={metadata?.asset}
        timeframe={metadata?.timeframe}
        marketType={metadata?.market_type}
      />

      <PaperOnlyBanner />

      <main
        className="flex-1 p-6 flex flex-col gap-6 max-w-[1800px] mx-auto w-full"
        data-testid="market-page"
      >
        <p className="text-sm text-muted-foreground">
          Candles exactly as the engine serves them. This page is not aligned to the
          replay and draws no support or resistance lines; the Overview page shows
          the levels reported by the replay.
        </p>

        <section>
          <MarketChart
            market={market.data}
            isLoading={market.isLoading}
            error={marketError}
            signal={null}
            asset={metadata?.asset}
            timeframe={metadata?.timeframe}
            onRetry={() => void market.refetch()}
          />
        </section>

        {metadata ? (
          <Panel
            title="Dataset"
            description="As reported by GET /api/market. Nothing is computed here."
          >
            <div className="p-5 flex flex-col gap-0.5">
              <StatRow label="Asset" value={metadata.asset} />
              <StatRow label="Timeframe" value={metadata.timeframe} />
              <StatRow
                label="Market"
                value={metadata.market_type ?? 'unknown'}
                hint="absent is shown as unknown, never assumed"
              />
              <StatRow label="Source" value={metadata.source} />
              <StatRow label="Dataset SHA-256" value={shortHash(metadata.dataset_sha256, 16)} />
              <StatRow label="Candles in dataset" value={formatCount(metadata.dataset_candles)} />
              <StatRow label="First candle" value={formatTimestamp(metadata.dataset_first_timestamp)} mono={false} />
              <StatRow label="Last candle" value={formatTimestamp(metadata.dataset_last_timestamp)} mono={false} />
              <StatRow
                label="Candles shown"
                value={formatCount(metadata.returned_candles)}
                hint={
                  metadata.truncated
                    ? 'window truncated by the server limit'
                    : `request limit ${formatCount(metadata.limit)}`
                }
              />
            </div>
          </Panel>
        ) : market.isLoading ? (
          <LoadingPanel label="Loading dataset details" />
        ) : null}
      </main>
    </div>
  );
}