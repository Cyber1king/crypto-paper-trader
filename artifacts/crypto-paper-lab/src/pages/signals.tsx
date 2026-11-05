import { StandardPage } from '@/components/standard-page';
import {
  LastSignalPanel,
  ReplayProgressPanel,
} from '@/components/standard-panels';
import { ErrorPanel, LoadingPanel } from '@/components/state';
import type { ModeInfo } from '@/lib/api';
import { queryError, useReplayState, useSignal } from '@/lib/hooks';

function SignalsBody({ mode }: { mode: ModeInfo }) {
  // Same gate the Portfolio page uses before it reads a replay.
  const controllable = Boolean(mode.available && mode.supports_execution);

  const replay = useReplayState(controllable ? mode : undefined, undefined);
  const replayError = queryError(replay);
  const signal = useSignal(undefined);
  const signalValue = signal.data;
  const displaySignalValue = (value: string | number | boolean | null | undefined) =>
    value == null ? '—' : String(value);
  const signalFields = signalValue
    ? [
        ['Asset', signalValue.asset],
        ['Timeframe', signalValue.timeframe],
        ['Timestamp', signalValue.timestamp],
        ['Signal', signalValue.signal],
        ['Reason', signalValue.reason],
        ['Price', signalValue.price],
        ['Support', signalValue.support],
        ['Resistance', signalValue.resistance],
        ['Trend', signalValue.trend],
        ['Breakout', signalValue.breakout],
        ['Retest', signalValue.retest],
        ['Breakout distance', signalValue.breakout_distance],
        ['Retest distance', signalValue.retest_distance],
        ['Realised volatility', signalValue.realised_volatility],
        ['Mean range', signalValue.mean_range],
        ['Strategy config hash', signalValue.strategy.config_hash.slice(0, 12)],
        ['Dataset sha256', signalValue.source.dataset_sha256.slice(0, 12)],
      ] as const
    : [];

  return (
    <div className="flex flex-col gap-6" data-testid="signals-page">
      <section className="border border-border rounded-lg px-4 py-3 bg-card" data-testid="live-signal-panel">
        <h2 className="font-semibold">Live Signal (BTC session)</h2>
        <p className="text-xs text-muted-foreground mt-1">
          Server-computed from /api/signal. Instrument-specific signals will be available once the backend adds instrument support (Phase 5). This panel always reflects the default BTC/USDT session.
        </p>
        {signal.isLoading && !signal.data ? (
          <p className="text-sm text-muted-foreground mt-4">Loading signal…</p>
        ) : signal.error ? (
          <p className="text-sm text-destructive mt-4">
            Signal unavailable <span className="text-muted-foreground">(status {signal.error.status})</span>
          </p>
        ) : signalValue ? (
          <dl className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mt-4">
            {signalFields.map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs text-muted-foreground">{label}</dt>
                <dd className="text-sm font-medium break-words">{displaySignalValue(value)}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </section>

      <p className="text-sm text-muted-foreground">
        Shows the most recent observation the engine reported, exactly as the replay
        returns it. The API offers no signal history, so no list or timeline of past
        signals is shown here. The signal changes only when the replay is stepped
        from the Overview page.
      </p>

      {replayError ? (
        <ErrorPanel
          error={replayError}
          title="Replay state unavailable"
          onRetry={() => void replay.refetch()}
        />
      ) : replay.isLoading && !replay.data ? (
        <LoadingPanel label="Loading replay state" />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <LastSignalPanel signal={replay.data?.last_signal} />
          <ReplayProgressPanel replay={replay.data} />
        </div>
      )}
    </div>
  );
}

export function Signals() {
  return (
    <StandardPage
      title="Strategy signals"
      subtitle="Last engine signal - read from the replay"
    >
      {(mode) => <SignalsBody mode={mode} />}
    </StandardPage>
  );
}
