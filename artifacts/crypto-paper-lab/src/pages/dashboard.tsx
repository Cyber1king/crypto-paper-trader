/**
 * The paper-trading dashboard (Phase 18).
 *
 * ## What changed, and why it is not a redesign
 *
 * The layout, theme tokens, typography and the Card/Badge vocabulary are the
 * original dashboard's. What changed is where every number comes from.
 *
 * Previously this page imported `usePaperEngine`, `analyzeCandles` and
 * `generateSignal` — a frontend reimplementation of the strategy, a
 * `Math.sin(Date.now())` confidence value, a `Math.random()`-jittered candle feed,
 * a $100,000 balance and a manual BUY/SELL panel. All of that is deleted.
 *
 * Now every figure is read from the Python paper engine, and where a figure is not
 * available the page says so instead of inventing one.
 *
 * ## Mode handling
 *
 * The selected mode is a per-request parameter, never a "current mode" the server
 * mutates — the same design the Python side uses, so switching modes here cannot
 * reset or transfer anything.
 *
 * - Standard: `/api/replay?mode=standard` plus the Phase 16 projections.
 * - AI Intelligence: `/api/ai` for the account, plus `/api/replay?mode=ai_intelligence`
 *   for lifecycle. The two are shown in separate panels and never merged.
 * - Alerts: `/api/modes` only. No replay request is issued, because the mode has no
 *   session and the server would refuse it.
 * - Daily Target: `/api/replay?mode=daily_target` for lifecycle, plus
 *   `/api/daily-target` for the day's figures. Kept separate for the same reason AI's
 *   is: the daily contract is not part of `ReplayStateResponse`.
 * - Reserved modes: `/api/modes` only. The server's note is shown; no execution is
 *   attempted and no substitute is chosen.
 */

import { useCallback, useMemo, useState } from "react";
import { Beaker, ShieldAlert, Wifi, WifiOff } from "lucide-react";

import { Badge } from "@/components/ui";
import { ErrorPanel, LoadingPanel, PaperOnlyBanner, UnavailableModePanel } from "@/components/state";
import { ModeNote, ModeSelector } from "@/components/mode-selector";
import { PaperControls, toRefusal } from "@/components/paper-controls";
import { EngineConfigurationPanel, MarketChart } from "@/components/market-chart";
import {
  LastSignalPanel,
  OpenPositionPanel,
  ReplayProgressPanel,
  StandardAccountPanel,
  StatisticsPanel,
  TradeJournalPanel,
} from "@/components/standard-panels";
import {
  AiAccountPanel,
  AiJournalPanel,
  AiPositionsPanel,
  AiReplayProgressPanel,
  IntelligenceScorePanel,
} from "@/components/ai-panels";
import { AlertsPanel } from "@/components/alerts-panel";
import { DailyTargetPanel } from "@/components/daily-target-panels";
import { HighRiskPanel } from "@/components/high-risk-panels";
import { ManualPanel } from "@/components/manual-panels";

import {
  describeError,
  isApiError,
  type ApiError,
  type MarketQuery,
  type ModeInfo,
  type ModesResponse,
} from "@/lib/api";
import {
  firstError,
  queryKeys,
  queryError,
  useAiState,
  useAutoStep,
  useDailyTargetConfig,
  useDailyTargetState,
  useHighRiskConfig,
  useHighRiskState,
  useManualActions,
  useManualState,
  useHealth,
  useMarket,
  useModes,
  useReplayControls,
  useReplayState,
  useRunningPolling,
  useSelectedMode,
  useStandardAccount,
  useStatistics,
  useTrades,
} from "@/lib/hooks";
import { useQueryClient } from "@tanstack/react-query";

/** Candles requested for the chart. The server's own maximum window. */
const CHART_LIMIT = 200;

export function Dashboard() {
  const queryClient = useQueryClient();

  const [selectedMode, setSelectedMode] = useState<string>("standard");
  const [stepCount, setStepCount] = useState(1);

  const health = useHealth();
  const modes = useModes();
  const mode: ModeInfo | undefined = useSelectedMode(modes.data, selectedMode);

  const isControllable = Boolean(mode?.available && mode.supports_execution);
  const isAi = mode?.mode === "ai_intelligence";
  const isAlerts = mode?.mode === "alerts";
  const isDailyTarget = mode?.mode === "daily_target";
  const isManual = mode?.mode === "manual";
  const isHighRisk = mode?.mode === "high_risk";

  // Alerts and reserved modes issue no replay request at all.
  const replay = useReplayState(isControllable ? mode : undefined);

  const ai = useAiState(isAi);

  // Daily Target's daily contract, like AI's, is not part of ReplayStateResponse and
  // so is read from its own route rather than by widening the shared one.
  const daily = useDailyTargetState(isDailyTarget);

  // The target editor's mutation. Created unconditionally so the hook order is stable
  // across mode switches; it only fires when Daily Target is selected.
  const dailyConfig = useDailyTargetConfig();

  // Manual's paper state and its action mutations. Created unconditionally so the hook
  // order stays stable across mode switches; neither fires unless Manual is selected.
  const manual = useManualState(isManual);
  const manualActions = useManualActions();

  // High-Risk's paper state and its one configuration mutation, created unconditionally
  // so the hook order stays stable across mode switches; neither fires unless
  // High-Risk is selected.
  const highRisk = useHighRiskState(isHighRisk);
  const highRiskConfig = useHighRiskConfig();

  const manualError = queryError(manual);
  const highRiskError = queryError(highRisk);

  const account = useStandardAccount(mode?.mode === "standard");
  const trades = useTrades(mode?.mode === "standard");
  const statistics = useStatistics(mode?.mode === "standard");

  // Keep the chart aligned to where the replay is, using the only parameter the
  // API offers for it. Absent for modes with no replay, which is correct: the chart
  // is dataset context, not mode state.
  const chartQuery = useMemo<MarketQuery>(() => {
    const end = replay.data?.current_timestamp ?? ai.data?.replay.current_timestamp;

    return end
      ? { limit: CHART_LIMIT, end }
      : { limit: CHART_LIMIT };
  }, [replay.data?.current_timestamp, ai.data?.replay.current_timestamp]);

  const market = useMarket(chartQuery);

  // Poll only while a replay is armed, so an idle dashboard makes no requests.
  const replayStatus = replay.data?.status ?? ai.data?.replay.status;

  useRunningPolling(replayStatus);

  /**
   * What a lifecycle call must refresh beyond the replay itself.
   *
   * `ReplayState` is authoritative for the replay, but it carries no mode-specific
   * book, so each mode's own projection has to be invalidated explicitly.
   *
   * Computed once and shared by the auto-step and the controls. These two used to
   * repeat the same ternary inline, which is how the Daily Target branch would have
   * been added to one and forgotten in the other — leaving the daily panel stale after
   * every step while the replay beside it updated. One list, two consumers.
   *
   * The branches are mutually exclusive and each names only its own mode's queries:
   * the Phase 16 projections are Standard-scoped (`/api/account` has no `mode`
   * parameter), and each mode owns a separate broker, so invalidating Standard's keys
   * while Daily Target is selected would refresh figures belonging to a different
   * account.
   */
  const refreshKeys = useMemo<readonly (readonly unknown[])[]>(
    () =>
      isAi
        ? [queryKeys.ai()]
        : isDailyTarget
          ? [queryKeys.dailyTarget()]
          : isManual
            ? [queryKeys.manual()]
            : isHighRisk
              ? [queryKeys.highRisk()]
              : [queryKeys.account(), queryKeys.trades(), queryKeys.statistics()],
    [isAi, isDailyTarget, isManual, isHighRisk],
  );

  // Advance the engine while it reports `running`. The server sets the flag on Start
  // and runs no worker, so without this the replay would hold its cursor and the UI
  // would look frozen while claiming to be running (Phase 20).
  useAutoStep({
    mode: isControllable ? mode : undefined,
    status: replayStatus,
    alsoRefresh: refreshKeys,
  });

  const controls = useReplayControls(isControllable ? mode : undefined, {
    alsoRefresh: refreshKeys,
  });

  const refusal = useMemo(
    () =>
      toRefusal(controls.start.error) ??
      toRefusal(controls.pause.error) ??
      toRefusal(controls.step.error) ??
      toRefusal(controls.reset.error),
    [
      controls.start.error,
      controls.pause.error,
      controls.step.error,
      controls.reset.error,
    ],
  );

  const handleStep = useCallback(() => {
    controls.step.mutate({ count: stepCount });
  }, [controls.step, stepCount]);

  const handleReset = useCallback(() => {
    controls.reset.mutate();
  }, [controls.reset]);

  const handleModeSelect = useCallback(
    (next: string) => {
      setSelectedMode(next);
      // Drop any cached read for the mode being left, so its figures cannot flash
      // under the new mode's name.
      void queryClient.removeQueries({ queryKey: queryKeys.replay(next) });
    },
    [queryClient],
  );

  const serviceError = firstError(health, modes);
  const replayError = queryError(replay);
  const aiError = queryError(ai);
  const dailyError = queryError(daily);
  const marketError = queryError(market);

  // `shrink-0` on every badge: each is `whitespace-nowrap inline-flex`, so as a flex
  // item it would otherwise be a candidate for shrinking and its label would clip.
  // "API online" is the liveness signal and must stay legible at every width.
  const healthBadge = health.isLoading ? (
    <Badge
      variant="outline"
      className="shrink-0 font-mono text-[10px] uppercase tracking-widest"
    >
      Checking…
    </Badge>
  ) : health.isError ? (
    <Badge
      variant="outline"
      data-testid="health-offline"
      className="shrink-0 font-mono text-[10px] uppercase tracking-widest border-destructive/40 text-destructive"
    >
      <WifiOff className="w-3 h-3 mr-1 shrink-0" aria-hidden="true" />
      API offline
    </Badge>
  ) : (
    <Badge
      variant="outline"
      data-testid="health-online"
      className="shrink-0 font-mono text-[10px] uppercase tracking-widest border-success/40 text-success bg-success/10"
    >
      <Wifi className="w-3 h-3 mr-1 shrink-0" aria-hidden="true" />
      API online
    </Badge>
  );

  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">
      {/*
       * `flex-wrap` on the header row.

       * On a 390px viewport the title group and the badge/balance group cannot both
       * fit side by side: the right group alone needs 231px of content and the row has
       * 342px after padding, so `min-w-0` alone was not enough — the groups shrank but
       * their contents escaped, and that escape is what produced the residual 45px of
       * document scroll. Wrapping moves the second group to its own line, which is the
       * only arrangement that shows all of it without clipping. Desktop is unaffected:
       * there is room, so nothing wraps and the layout is unchanged.
       */}
      <header className="border-b bg-card sticky top-0 z-10 px-6 py-4 flex flex-wrap items-center justify-between gap-4 shadow-sm">
        <div className="flex items-center gap-3 min-w-0">
          <div className="bg-primary/10 p-2 rounded-md border border-primary/20 shrink-0">
            <Beaker className="w-5 h-5 text-primary" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h1 className="font-bold text-lg tracking-tight">Crypto Paper Lab</h1>
            <p className="text-xs text-muted-foreground font-mono flex items-center gap-1 uppercase tracking-wider mt-0.5">
              <ShieldAlert className="w-3 h-3 shrink-0" aria-hidden="true" />
              <span className="truncate">Simulated Environment</span>
            </p>
          </div>
        </div>

        {/*
         * `min-w-0` and `shrink` on the right-hand group.
         *
         * As a flex item this defaulted to `min-width: auto`, so on a 390px viewport
         * the health badge and the balance together refused to shrink below their
         * content and pushed 6px past the header's own right edge. Allowing the group
         * to shrink lets the balance's own `min-w-0` (below) do its job, and the badge
         * keeps its size because it has `shrink-0`.
         */}
        <div className="flex items-center gap-4 min-w-0 shrink">
          {healthBadge}
          {StandardHeaderBalance(mode, replay.data, account.data)}
        </div>
      </header>

      <PaperOnlyBanner />

      <main className="flex-1 p-6 flex flex-col gap-6 max-w-[1800px] mx-auto w-full">
        {/* Mode selection, from GET /api/modes */}
        <section className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Paper mode
            </h2>
            <Badge
              variant="outline"
              className="font-mono text-[10px] uppercase tracking-widest"
              data-testid="default-mode-hint"
            >
              default: {modes.data?.default_mode ?? "—"}
            </Badge>
          </div>

          {modes.isLoading ? (
            <LoadingPanel label="Loading modes" />
          ) : modes.isError ? (
            <ErrorPanel
              error={queryError(modes) as ApiError}
              title="Mode list unavailable"
              onRetry={() => void modes.refetch()}
            />
          ) : (
            <>
              <ModeSelector
                modes={modes.data}
                selected={selectedMode}
                onSelect={handleModeSelect}
              />
              <ModeNote mode={mode} />
            </>
          )}
        </section>

        {/* The service must be reachable before anything else means anything */}
        {serviceError ? (
          <ErrorPanel
            error={serviceError}
            title="Paper API unreachable"
            onRetry={() => {
              void health.refetch();
              void modes.refetch();
            }}
          />
        ) : null}

        {/* Mode-specific body */}
        {mode && !mode.available ? (
          <UnavailableModePanel label={mode.label} note={mode.note} />
        ) : isAlerts ? (
          <AlertsPanel mode={mode} />
        ) : isAi ? (
          <AiBody
            ai={ai.data}
            isLoading={ai.isLoading}
            error={aiError}
            refusal={refusal}
            controlsEnabled={Boolean(mode?.available && mode.supports_execution)}
            modeLabel={mode?.label ?? "AI Intelligence"}
            status={ai.data?.replay.status}
            busy={controls.busy}
            stepCount={stepCount}
            onStepCountChange={setStepCount}
            onStart={() => controls.start.mutate(undefined)}
            onPause={() => controls.pause.mutate()}
            onStep={handleStep}
            onReset={handleReset}
          />
        ) : isDailyTarget ? (
          <DailyTargetBody
            daily={daily.data}
            isLoading={daily.isLoading}
            error={dailyError}
            onSetTarget={(amount) => dailyConfig.apply.mutate(amount)}
            isSetting={dailyConfig.pending}
            setError={dailyConfig.apply.error ?? null}
            refusal={refusal}
            controlsEnabled={Boolean(mode?.available && mode.supports_execution)}
            modeLabel={mode?.label ?? "Daily Target"}
            status={replay.data?.status}
            busy={controls.busy}
            stepCount={stepCount}
            onStepCountChange={setStepCount}
            onStart={() => controls.start.mutate(undefined)}
            onPause={() => controls.pause.mutate()}
            onStep={handleStep}
            onReset={handleReset}
          />
        ) : isHighRisk ? (
          <HighRiskBody
            highRisk={highRisk.data}
            isLoading={highRisk.isLoading}
            error={highRiskError}
            onSetFraction={(riskFraction) =>
              highRiskConfig.setFraction.mutate(riskFraction)
            }
            isSubmitting={highRiskConfig.setFraction.isPending}
            actionError={highRiskConfig.setFraction.error ?? null}
            refusal={refusal}
            controlsEnabled={Boolean(mode?.available && mode.supports_execution)}
            modeLabel={mode?.label ?? HIGH_RISK_FALLBACK_LABEL}
            status={replay.data?.status}
            busy={controls.busy}
            stepCount={stepCount}
            onStepCountChange={setStepCount}
            onStart={() => controls.start.mutate(undefined)}
            onPause={() => controls.pause.mutate()}
            onStep={handleStep}
            onReset={handleReset}
          />
        ) : isManual ? (
          <ManualBody
            manual={manual.data}
            isLoading={manual.isLoading}
            error={manualError}
            onSubmit={({ action, sizePct }) =>
              manualActions.submit.mutate({ action, sizePct })
            }
            onCancel={() => manualActions.cancel.mutate()}
            isSubmitting={manualActions.submit.isPending}
            isCancelling={manualActions.cancel.isPending}
            actionError={manualActions.submit.error ?? null}
            refusal={refusal}
            controlsEnabled={Boolean(mode?.available && mode.supports_execution)}
            modeLabel={mode?.label ?? "Manual"}
            status={replay.data?.status}
            busy={controls.busy}
            stepCount={stepCount}
            onStepCountChange={setStepCount}
            onStart={() => controls.start.mutate(undefined)}
            onPause={() => controls.pause.mutate()}
            onStep={handleStep}
            onReset={handleReset}
          />
        ) : (
          <StandardBody
            mode={mode}
            replay={replay.data}
            replayLoading={replay.isLoading}
            replayError={replayError}
            refusal={refusal}
            account={account.data}
            trades={trades.data}
            statistics={statistics.data}
            controlsEnabled={Boolean(mode?.available && mode.supports_execution)}
            modeLabel={mode?.label ?? "Standard"}
            busy={controls.busy}
            status={replay.data?.status}
            stepCount={stepCount}
            onStepCountChange={setStepCount}
            onStart={() => controls.start.mutate(undefined)}
            onPause={() => controls.pause.mutate()}
            onStep={handleStep}
            onReset={handleReset}
          />
        )}

        {/* Chart is dataset context, shared by every mode */}
        <section>
          <MarketChart
            market={market.data}
            isLoading={market.isLoading}
            error={marketError}
            signal={replay.data?.last_signal ?? ai.data?.replay.last_signal ?? null}
            asset={replay.data?.dataset.asset ?? ai.data?.replay.dataset.asset}
            timeframe={replay.data?.dataset.timeframe ?? ai.data?.replay.dataset.timeframe}
            onRetry={() => void market.refetch()}
          />
        </section>
      </main>
    </div>
  );
}

/**
 * The header balance.
 *
 * Shown only for Standard, because the header has one slot and the AI account must
 * not be labelled Standard's balance. When Standard is not selected, no balance
 * appears here at all rather than another mode's figure wearing its name.
 */
function StandardHeaderBalance(
  mode: ModeInfo | undefined,
  replay: { balance: number } | undefined,
  account: { balance: number } | undefined,
) {
  if (mode?.mode !== "standard") {
    return (
      <div className="text-right min-w-0" data-testid="header-no-balance">
        <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider break-words">
          Paper Balance
        </div>
        <div className="font-mono text-xl font-bold tracking-tight text-muted-foreground">
          —
        </div>
        <div className="text-[10px] text-muted-foreground font-mono">
          shown in the {mode?.label ?? "selected"} panel
        </div>
      </div>
    );
  }

  const balance = replay?.balance ?? account?.balance;

  return (
    <div className="text-right min-w-0">
      <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider break-words">
        Paper Balance
      </div>
      <div
        className="font-mono text-xl font-bold tracking-tight text-primary"
        data-testid="header-balance"
      >
        {balance === undefined
          ? "—"
          : balance.toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
      </div>
    </div>
  );
}

interface ControlsProps {
  refusal: { code: string; message: string } | null;
  controlsEnabled: boolean;
  modeLabel: string;
  status: "idle" | "running" | "paused" | "finished" | undefined;
  busy: boolean;
  stepCount: number;
  onStepCountChange: (count: number) => void;
  onStart: () => void;
  onPause: () => void;
  onStep: () => void;
  onReset: () => void;
}

function StandardBody({
  mode,
  replay,
  replayLoading,
  replayError,
  account,
  trades,
  statistics,
  ...controls
}: {
  mode: ModeInfo | undefined;
  replay: Parameters<typeof StandardAccountPanel>[0]["replay"];
  replayLoading: boolean;
  replayError: ApiError | null;
  account: Parameters<typeof StandardAccountPanel>[0]["account"];
  trades: Parameters<typeof TradeJournalPanel>[0]["trades"];
  statistics: Parameters<typeof StatisticsPanel>[0]["statistics"];
} & ControlsProps) {
  return (
    <div className="flex flex-col gap-6">
<div className="border border-border rounded-lg px-4 py-3 bg-card">
            <PaperControls
              status={controls.status}
              modeLabel={controls.modeLabel ?? mode?.label ?? "Standard"}
              busy={controls.busy}
              disabled={!controls.controlsEnabled}
              disabledReason={
                mode && !mode.supports_execution
                  ? "This mode cannot execute paper trades, so no lifecycle controls are offered."
                  : undefined
              }
          onStart={controls.onStart}
          onPause={controls.onPause}
          onStep={controls.onStep}
          onReset={controls.onReset}
          refusal={controls.refusal}
          stepCount={controls.stepCount}
          onStepCountChange={controls.onStepCountChange}
        />
      </div>

      {replayError ? (
        <ErrorPanel
          error={replayError}
          title="Replay state unavailable"
          onRetry={() => void undefined}
        />
      ) : replayLoading && !replay ? (
        <LoadingPanel label="Loading replay state" />
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-4 flex flex-col gap-6">
              <StandardAccountPanel replay={replay} account={account} />
              <OpenPositionPanel replay={replay} />
            </div>
            <div className="lg:col-span-4 flex flex-col gap-6">
              <LastSignalPanel signal={replay?.last_signal} />
              <StatisticsPanel statistics={statistics} />
            </div>
            <div className="lg:col-span-4 flex flex-col gap-6">
              <ReplayProgressPanel replay={replay} />
              <EngineConfigurationPanel replay={replay} />
            </div>
          </div>

          <TradeJournalPanel trades={trades} />
        </>
      )}
    </div>
  );
}

function AiBody({
  ai,
  isLoading,
  error,
  refusal,
  controlsEnabled,
  modeLabel,
  status,
  busy,
  stepCount,
  onStepCountChange,
  onStart,
  onPause,
  onStep,
  onReset,
}: {
  ai: Parameters<typeof AiAccountPanel>[0]["ai"];
  isLoading: boolean;
  error: ApiError | null;
} & ControlsProps) {
  return (
    <div className="flex flex-col gap-6">
      <div className="border border-border rounded-lg px-4 py-3 bg-card">
        <PaperControls
          status={status}
          modeLabel={modeLabel}
          busy={busy}
          disabled={!controlsEnabled}
          onStart={onStart}
          onPause={onPause}
          onStep={onStep}
          onReset={onReset}
          refusal={refusal}
          stepCount={stepCount}
          onStepCountChange={onStepCountChange}
        />
        <p className="text-[11px] text-muted-foreground mt-3 border-l-2 border-primary/40 pl-3 leading-relaxed">
          These controls drive the AI mode&apos;s own replay through the shared
          transport (<code className="font-mono">?mode=ai_intelligence</code>). Its
          paper account and positions are reported separately by{" "}
          <code className="font-mono">GET /api/ai</code> — never from this replay&apos;s
          broker, which the mode keeps permanently flat.
        </p>
      </div>

      {error ? (
        <ErrorPanel error={error} title="AI state unavailable" />
      ) : isLoading && !ai ? (
        <LoadingPanel label="Loading AI state" />
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-4 flex flex-col gap-6">
              <AiAccountPanel ai={ai} />
            </div>
            <div className="lg:col-span-4 flex flex-col gap-6">
              <IntelligenceScorePanel score={ai?.last_score} />
            </div>
            <div className="lg:col-span-4 flex flex-col gap-6">
              <AiReplayProgressPanel ai={ai} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <AiPositionsPanel ai={ai} />
            <AiJournalPanel ai={ai} />
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Daily Target's body.
 *
 * ## Why the shared controls, and not their own
 *
 * Daily Target is a controllable mode with exactly the same lifecycle as Standard and
 * AI: start, pause, step, reset against `/api/replay?mode=daily_target`. Its defining
 * behaviour lives entirely inside the engine's policy, so the dashboard needs no new
 * affordance for it — in particular there is **no** "stop at target" button, because
 * stopping is the engine's decision and offering a control for it would imply the
 * client could make it.
 *
 * That is also why the daily figures are not pushed into `PaperControls` or merged
 * into the Standard account panel: the mode's broker *is* the shared one, and two
 * components rendering the same balance two different ways is exactly the drift this
 * layout exists to prevent.
 *
 * The panel's own disclaimer and target editor sit below the controls rather than above
 * them, so the first thing a reader meets is the caveat, not the number.
 *
 * `onSetTarget` / `isSetting` / `setError` come from the dashboard's
 * `useDailyTargetConfig` mutation. It is passed in rather than created here so this
 * function stays a pure layout, and so the target control is driven by the same
 * mutation in tests as in the page.
 */
function DailyTargetBody({
  daily,
  isLoading,
  error,
  onSetTarget,
  isSetting,
  setError,
  refusal,
  controlsEnabled,
  modeLabel,
  status,
  busy,
  stepCount,
  onStepCountChange,
  onStart,
  onPause,
  onStep,
  onReset,
}: {
  daily: Parameters<typeof DailyTargetPanel>[0]["daily"];
  isLoading: boolean;
  error: ApiError | null;
  onSetTarget: Parameters<typeof DailyTargetPanel>[0]["onSetTarget"];
  isSetting: boolean;
  setError: ApiError | null;
} & ControlsProps) {
  return (
    <div className="flex flex-col gap-6">
      <div className="border border-border rounded-lg px-4 py-3 bg-card">
        <PaperControls
          status={status}
          modeLabel={modeLabel}
          busy={busy}
          disabled={!controlsEnabled}
          onStart={onStart}
          onPause={onPause}
          onStep={onStep}
          onReset={onReset}
          refusal={refusal}
          stepCount={stepCount}
          onStepCountChange={onStepCountChange}
        />
        <p className="text-[11px] text-muted-foreground mt-3 border-l-2 border-primary/40 pl-3 leading-relaxed">
          These controls drive the daily mode&apos;s replay through the shared
          transport (<code className="font-mono">?mode=daily_target</code>). The day,
          target and realized P&amp;L below come from{" "}
          <code className="font-mono">GET /api/daily-target</code>, and the target is
          set through <code className="font-mono">POST /api/daily-target/config</code> —
          nothing is computed here.
        </p>
      </div>

      <DailyTargetPanel
        daily={daily}
        isLoading={isLoading}
        error={error}
        onSetTarget={onSetTarget}
        isSetting={isSetting}
        setError={setError}
      />
    </div>
  );
}

/**
 * Manual's body.
 *
 * ## The shared lifecycle controls
 *
 * START, PAUSE, STEP and RESET are the same controls every controllable mode uses,
 * against `?mode=manual`. Manual needs no new affordance for its own behaviour, because
 * its distinguishing rule is an *absence*: nothing happens unless the user asks.
 *
 * That is also why there is no "auto-trade" toggle to disable. A switch labelled "don't
 * trade automatically" would imply trading automatically is the default somewhere, and
 * in Manual it never is.
 *
 * ## STEP is the only way an action fills
 *
 * The action panel says so, and it is the single most important sentence on the page: a
 * requested action is an intent, and the engine fills it against the bar the next step
 * reaches. A user who clicks Buy and sees nothing happen has been given the reason
 * rather than left to wonder whether the button is broken.
 */
function ManualBody({
  manual,
  isLoading,
  error,
  onSubmit,
  onCancel,
  isSubmitting,
  isCancelling,
  actionError,
  refusal,
  controlsEnabled,
  modeLabel,
  status,
  busy,
  stepCount,
  onStepCountChange,
  onStart,
  onPause,
  onStep,
  onReset,
}: {
  manual: Parameters<typeof ManualPanel>[0]["manual"];
  isLoading: boolean;
  error: ApiError | null;
  onSubmit: (request: {
    action: "ENTER_LONG" | "ENTER_SHORT" | "EXIT";
    sizePct?: number;
  }) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  isCancelling: boolean;
  actionError: ApiError | null;
} & ControlsProps) {
  return (
    <div className="flex flex-col gap-6">
      <div className="border border-border rounded-lg px-4 py-3 bg-card">
        <PaperControls
          status={status}
          modeLabel={modeLabel}
          busy={busy}
          disabled={!controlsEnabled}
          onStart={onStart}
          onPause={onPause}
          onStep={onStep}
          onReset={onReset}
          refusal={refusal}
          stepCount={stepCount}
          onStepCountChange={onStepCountChange}
        />
        <p className="text-[11px] text-muted-foreground mt-3 border-l-2 border-primary/40 pl-3 leading-relaxed">
          These controls drive the manual mode&apos;s replay through the shared
          transport (<code className="font-mono">?mode=manual</code>). Balance,
          position and journal come from{" "}
          <code className="font-mono">GET /api/manual</code>, and actions are sent to{" "}
          <code className="font-mono">POST /api/manual/action</code> — nothing is
          computed here.
        </p>
      </div>

      <ManualPanel
        manual={manual}
        isLoading={isLoading}
        error={error}
        onSubmit={(action, sizePct) => onSubmit({ action, sizePct })}
        onCancel={onCancel}
        isSubmitting={isSubmitting}
        isCancelling={isCancelling}
        actionError={actionError}
      />
    </div>
  );
}

/**
 * Fallback label, used only in the instant before `GET /api/modes` resolves.
 *
 * Carries "Paper Trading" for the same reason every other mode's label does: the mode
 * name must never reach the screen without the word that says what it is. A heading
 * reading only "High-Risk" would be the easiest thing on the page to misread as a
 * real leveraged position.
 */
const HIGH_RISK_FALLBACK_LABEL = "High-Risk — Paper Trading";

/**
 * High-Risk's body.
 *
 * ## The shared lifecycle controls
 *
 * START, PAUSE, STEP and RESET are the same controls every controllable mode uses,
 * against `?mode=high_risk`. High-Risk deliberately adds no lifecycle of its own:
 * there is no `/api/high-risk/step` route, because a second way to advance one
 * replay is a second thing to keep correct.
 *
 * ## There is no trade button
 *
 * This is the only automatic mode besides Standard, and that is the point. High-Risk
 * enters exactly the signals Standard enters — it adds no qualification rule — so it
 * needs no user affordance to trade. The *only* control it adds is the size setting,
 * and the engine refuses that while a position is open rather than reporting a size
 * that no longer describes the position above it.
 */
function HighRiskBody({
  highRisk,
  isLoading,
  error,
  onSetFraction,
  isSubmitting,
  actionError,
  refusal,
  controlsEnabled,
  modeLabel,
  status,
  busy,
  stepCount,
  onStepCountChange,
  onStart,
  onPause,
  onStep,
  onReset,
}: {
  highRisk: Parameters<typeof HighRiskPanel>[0]["highRisk"];
  isLoading: boolean;
  error: ApiError | null;
  onSetFraction: (riskFraction: number) => void;
  isSubmitting: boolean;
  actionError: ApiError | null;
} & ControlsProps) {
  return (
    <div className="flex flex-col gap-6">
      <div className="border border-border rounded-lg px-4 py-3 bg-card">
        <PaperControls
          status={status}
          modeLabel={modeLabel}
          busy={busy}
          disabled={!controlsEnabled}
          onStart={onStart}
          onPause={onPause}
          onStep={onStep}
          onReset={onReset}
          refusal={refusal}
          stepCount={stepCount}
          onStepCountChange={onStepCountChange}
        />
        <p className="text-[11px] text-muted-foreground mt-3 border-l-2 border-primary/40 pl-3 leading-relaxed">
          These controls drive the high-risk mode&apos;s replay through the shared
          transport (<code className="font-mono">?mode=high_risk</code>). Balance,
          exposure and P&amp;L come from{" "}
          <code className="font-mono">GET /api/high-risk</code>, and the size setting
          is sent to <code className="font-mono">POST /api/high-risk/config</code> —
          nothing is computed here.
        </p>
      </div>

      <HighRiskPanel
        highRisk={highRisk}
        isLoading={isLoading}
        error={error}
        onSetFraction={onSetFraction}
        isSubmitting={isSubmitting}
        actionError={actionError}
      />
    </div>
  );
}

export { describeError, isApiError };