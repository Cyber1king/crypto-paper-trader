import { StandardPage } from '@/components/standard-page';
import { TradeJournalPanel } from '@/components/standard-panels';
import { ErrorPanel, LoadingPanel } from '@/components/state';
import { queryError, useTrades } from '@/lib/hooks';

function JournalBody() {
  const trades = useTrades(true);
  const tradesError = queryError(trades);

  return (
    <div className="flex flex-col gap-6" data-testid="journal-page">
      <p className="text-sm text-muted-foreground">
        Closed simulated trades as recorded by the engine. This page shows them and
        does not total or recompute anything.
      </p>

      {tradesError ? (
        <ErrorPanel
          error={tradesError}
          title="Trade journal unavailable"
          onRetry={() => void trades.refetch()}
        />
      ) : trades.isLoading && !trades.data ? (
        <LoadingPanel label="Loading trade journal" />
      ) : (
        <TradeJournalPanel trades={trades.data} />
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