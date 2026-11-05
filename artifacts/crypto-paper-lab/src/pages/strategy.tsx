import { useEffect, useState } from 'react';

import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/components/ui';
import { ErrorPanel, LoadingPanel } from '@/components/state';
import { describeError, type ModeInfo } from '@/lib/api';
import {
  queryError,
  useDailyTargetConfig,
  useDailyTargetState,
  useHighRiskConfig,
  useHighRiskState,
  useManualActions,
  useManualState,
  useModes,
} from '@/lib/hooks';

function displayValue(value: string | number | boolean | null | undefined): string {
  return value == null ? '—' : String(value);
}

function ModeCard({ mode }: { mode: ModeInfo }) {
  const daily = useDailyTargetState(mode.mode === 'daily_target');
  const dailyConfig = useDailyTargetConfig();
  const highRisk = useHighRiskState(mode.mode === 'high_risk');
  const highRiskConfig = useHighRiskConfig();
  const manual = useManualState(mode.mode === 'manual');
  const manualActions = useManualActions();
  const [targetAmount, setTargetAmount] = useState('');
  const [riskFraction, setRiskFraction] = useState('');

  useEffect(() => {
    if (daily.data) setTargetAmount(String(daily.data.daily_target_amount));
  }, [daily.data?.daily_target_amount]);
  useEffect(() => {
    if (highRisk.data) setRiskFraction(String(highRisk.data.risk_fraction));
  }, [highRisk.data?.risk_fraction]);

  const modeQuery = mode.mode === 'daily_target' ? daily : mode.mode === 'high_risk' ? highRisk : manual;
  const modeError = queryError(modeQuery);

  return (
    <Card data-testid={`strategy-mode-${mode.mode}`}>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="mr-auto">{mode.mode}</CardTitle>
          <Badge variant={mode.available ? 'default' : 'outline'}>
            {mode.available ? 'Available' : 'Not available'}
          </Badge>
          <Badge variant={mode.supports_execution ? 'secondary' : 'outline'}>
            {mode.supports_execution ? 'Execution supported' : 'Execution not supported'}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">{mode.note}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {modeError ? (
          <ErrorPanel error={modeError} title={`${mode.mode} state unavailable`} onRetry={() => void modeQuery.refetch()} />
        ) : null}

        {mode.mode === 'daily_target' ? (
          daily.isLoading && !daily.data ? <LoadingPanel label="Loading Daily Target configuration" /> : daily.data ? (
            <div className="space-y-4">
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <div><dt className="text-muted-foreground">Daily target amount</dt><dd>{displayValue(daily.data.daily_target_amount)}</dd></div>
                <div><dt className="text-muted-foreground">Target note</dt><dd>{displayValue(daily.data.target_note)}</dd></div>
                <div><dt className="text-muted-foreground">Waiting note</dt><dd>{displayValue(daily.data.waiting_note)}</dd></div>
                <div><dt className="text-muted-foreground">Overshoot note</dt><dd>{displayValue(daily.data.overshoot_note)}</dd></div>
                <div><dt className="text-muted-foreground">Overshoot possible</dt><dd>{displayValue(daily.data.overshoot_possible)}</dd></div>
                <div><dt className="text-muted-foreground">Target changed during day</dt><dd>{displayValue(daily.data.target_changed_during_day)}</dd></div>
              </dl>
              <div className="flex flex-wrap items-end gap-3">
                <label className="flex flex-col gap-1 text-sm">
                  Daily target amount
                  <Input type="number" min="0" step="any" value={targetAmount} onChange={(event) => setTargetAmount(event.target.value)} />
                </label>
                <Button disabled={dailyConfig.pending || targetAmount.trim() === ''} onClick={() => dailyConfig.apply.mutate(Number(targetAmount))}>
                  {dailyConfig.pending ? 'Saving…' : 'Save target'}
                </Button>
              </div>
              {dailyConfig.apply.error ? <p className="text-sm text-destructive">{describeError(dailyConfig.apply.error)}</p> : null}
            </div>
          ) : null
        ) : null}

        {mode.mode === 'high_risk' ? (
          highRisk.isLoading && !highRisk.data ? <LoadingPanel label="Loading High-Risk configuration" /> : highRisk.data ? (
            <div className="space-y-4">
              <p className="text-sm">Current risk fraction: {displayValue(highRisk.data.risk_fraction)}</p>
              <div className="flex flex-wrap items-end gap-3">
                <label className="flex flex-col gap-1 text-sm">
                  Risk fraction
                  <Input type="number" min="0" max={highRisk.data.max_risk_fraction} step="any" value={riskFraction} onChange={(event) => setRiskFraction(event.target.value)} />
                </label>
                <Button disabled={highRiskConfig.busy || riskFraction.trim() === ''} onClick={() => highRiskConfig.setFraction.mutate(Number(riskFraction))}>
                  {highRiskConfig.busy ? 'Saving…' : 'Save risk fraction'}
                </Button>
              </div>
              {highRiskConfig.setFraction.error ? <p className="text-sm text-destructive">{describeError(highRiskConfig.setFraction.error)}</p> : null}
            </div>
          ) : null
        ) : null}

        {mode.mode === 'manual' ? (
          manual.isLoading && !manual.data ? <LoadingPanel label="Loading Manual state" /> : manual.data ? (
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm">
                Pending action: {displayValue(manual.data.pending_action?.action)}
                {manual.data.pending_action ? ` · size_pct: ${displayValue(manual.data.pending_action.size_pct)}` : ''}
              </p>
              {manual.data.pending_action ? (
                <Button variant="outline" disabled={manualActions.cancel.isPending} onClick={() => manualActions.cancel.mutate()}>
                  {manualActions.cancel.isPending ? 'Cancelling…' : 'Cancel pending action'}
                </Button>
              ) : null}
              {manualActions.cancel.error ? <p className="text-sm text-destructive">{describeError(manualActions.cancel.error)}</p> : null}
            </div>
          ) : null
        ) : null}

        {mode.mode !== 'daily_target' && mode.mode !== 'high_risk' && mode.mode !== 'manual' ? (
          <p className="text-sm text-muted-foreground">No configurable parameters exposed by the backend for this mode.</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function Strategy() {
  const modes = useModes();
  const modesError = queryError(modes);

  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">
      <header className="border-b bg-card px-6 py-4 flex flex-col gap-1">
        <h1 className="font-bold text-lg tracking-tight">Strategy</h1>
        <p className="text-xs text-muted-foreground font-mono uppercase tracking-wider">
          Paper trading strategy configuration. All settings apply to the default BTC/USDT paper session. Per-instrument configuration will be available once the backend adds instrument support (Phase 5).
        </p>
      </header>
      <main className="flex-1 p-6 flex flex-col gap-6 max-w-[1800px] mx-auto w-full">
        <div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
          Paper trading only. Settings affect the simulated engine. Real-money settings will be added with the MT5 / Binance adapters in Phase 5.
        </div>
        {modesError ? (
          <ErrorPanel error={modesError} title="Modes unavailable" onRetry={() => void modes.refetch()} />
        ) : modes.isLoading && !modes.data ? (
          <LoadingPanel label="Loading modes" />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {modes.data?.modes.map((mode) => <ModeCard key={mode.mode} mode={mode} />)}
          </div>
        )}
      </main>
    </div>
  );
}
