import { StandardPage } from '@/components/standard-page';
import {
  OpenPositionPanel,
  StandardAccountPanel,
  StatisticsPanel,
} from '@/components/standard-panels';
import { ErrorPanel, LoadingPanel } from '@/components/state';
import type { ModeInfo } from '@/lib/api';
import {
  queryError,
  useReplayState,
  useStandardAccount,
  useStatistics,
} from '@/lib/hooks';

function PortfolioBody({ mode }: { mode: ModeInfo }) {
  // Same gate the Overview page uses before it reads a replay.
  const controllable = Boolean(mode.available && mode.supports_execution);

  const replay = useReplayState(controllable ? mode : undefined, undefined);
  const account = useStandardAccount(true);
  const statistics = useStatistics(true);

  const replayError = queryError(replay);
  const accountError = queryError(account);
  const statisticsError = queryError(statistics);

  return (
    <div className="flex flex-col gap-6" data-testid="portfolio-page">
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