/**
 * React Query bindings for the paper-trading API (Phase 18A / 18I).
 *
 * ## Why react-query
 *
 * It is already a dependency, `QueryClientProvider` already wraps the app in
 * `App.tsx`, and it is what the generated `@workspace/api-client-react` package is
 * built on. Adding a second state manager would be the frontend's own version of a
 * second accounting truth.
 *
 * ## The one rule this layer exists to enforce
 *
 * **Nothing is derived here.** These hooks read API responses and hand them
 * untouched. There is no P&L arithmetic, no position valuation, no score
 * recalculation, no price interpolation and no total across trades. If a figure is
 * not in a response, the dashboard does not show it.
 *
 * ## Mode safety
 *
 * `useReplayState` is **disabled** for any mode that is not available or cannot
 * execute. That is not an optimisation: Alerts holds no broker, so asking for its
 * replay would produce a `409` on every render. Disabled means the request is never
 * issued, which is also the honest behaviour — the mode has no replay to show.
 *
 * `useAiState` is separate and unconditional, because `/api/ai` is the AI mode's
 * account of record. It is never merged with `/api/replay?mode=ai_intelligence`,
 * whose broker is permanently flat by design.
 */

import { useEffect, useRef, useState } from "react";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import {
  getDefaultApi,
  isApiError,
  type AccountResponse,
  type AiState,
  type DailyTargetResponse,
  type ApiError,
  type HealthResponse,
  type MarketQuery,
  type MarketResponse,
  type ModeInfo,
  type ModesResponse,
  type ReplayState,
  type ReplayStatus,
  type StatisticsResponse,
  type StepQuery,
  type TradesResponse,
} from "./api";

/** Query keys, centralised so an invalidation cannot miss one. */
export const queryKeys = {
  health: () => ["health"] as const,
  modes: () => ["modes"] as const,
  replay: (mode: string | undefined) => ["replay", mode ?? "standard"] as const,
  ai: () => ["ai"] as const,
  dailyTarget: () => ["daily-target"] as const,
  account: () => ["account"] as const,
  trades: () => ["trades"] as const,
  statistics: () => ["statistics"] as const,
  market: (query: MarketQuery) => ["market", query] as const,
};

/** The client the hooks use. Tests install a stub via `setDefaultApi`. */
export function usePaperApi() {
  return getDefaultApi();
}

// ---------------------------------------------------------------------------
// Discovery
// ---------------------------------------------------------------------------

export function useHealth(): UseQueryResult<HealthResponse, ApiError> {
  const api = usePaperApi();

  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: ({ signal }) => api.getHealth(signal),
    // Liveness is cheap and the banner reports it, but there is no value in
    // re-asking on an interval the user did not ask for.
    staleTime: 15_000,
    retry: false,
  });
}

export function useModes(): UseQueryResult<ModesResponse, ApiError> {
  const api = usePaperApi();

  return useQuery({
    queryKey: queryKeys.modes(),
    queryFn: ({ signal }) => api.getModes(signal),
    // Mode configuration is static for a process lifetime.
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/**
 * The selected mode's own entry in `GET /api/modes`.
 *
 * Resolved from the server's list rather than from a local constant, so the UI
 * cannot claim a capability the API does not report.
 */
export function useSelectedMode(
  modes: ModesResponse | undefined,
  modeId: string | undefined,
): ModeInfo | undefined {
  if (!modes || !modeId) {
    return undefined;
  }

  return modes.modes.find((entry) => entry.mode === modeId);
}

// ---------------------------------------------------------------------------
// Replay state
// ---------------------------------------------------------------------------

/**
 * Replay state for one mode.
 *
 * `enabled` is false unless the mode is available **and** can execute. For Alerts
 * and the three reserved modes no request is issued at all.
 */
export function useReplayState(
  mode: ModeInfo | undefined,
): UseQueryResult<ReplayState, ApiError> {
  const api = usePaperApi();
  const enabled = Boolean(mode?.available && mode.supports_execution);

  return useQuery({
    queryKey: queryKeys.replay(mode?.mode),
    queryFn: ({ signal }) => api.getReplay(mode?.mode, signal),
    enabled,
    retry: false,
  });
}

/** AI Intelligence's authoritative account, positions, journal and score. */
export function useAiState(
  enabled: boolean,
): UseQueryResult<AiState, ApiError> {
  const api = usePaperApi();

  return useQuery({
    queryKey: queryKeys.ai(),
    queryFn: ({ signal }) => api.getAiState(signal),
    enabled,
    retry: false,
  });
}

/**
 * Daily Target's authoritative daily state (Phase 24B).
 *
 * Separate from {@link useReplayState} for the same reason `useAiState` is: the daily
 * contract is not part of `ReplayStateResponse`, and widening that response would make
 * every mode carry fields that are false for all of them.
 *
 * `enabled` is supplied by the caller rather than derived from the mode here, matching
 * {@link useAiState}, so this hook holds no opinion about which mode is selected.
 *
 * `refetchInterval` is **not** set. While the replay is auto-running the Phase 20
 * interval is already invalidating the replay key on every tick, and this projection
 * has to agree with it; a second independent interval would be a second refresh
 * cadence for one mode's state, which is the kind of drift this layer exists to
 * prevent. The daily figures are refreshed through the `alsoRefresh` keys on the
 * lifecycle mutations instead.
 */
export function useDailyTargetState(
  enabled: boolean,
): UseQueryResult<DailyTargetResponse, ApiError> {
  const api = usePaperApi();

  return useQuery({
    queryKey: queryKeys.dailyTarget(),
    queryFn: ({ signal }) => api.getDailyTarget(signal),
    enabled,
    retry: false,
  });
}

/** What {@link useDailyTargetConfig} exposes. */
export interface DailyTargetConfigControl {
  /**
   * Set today's dollar target. Resolves to the server's own daily projection.
   *
   * The mutation is **not** auto-applied on success: `setQueryData` writes the
   * response because the server returns the authoritative projection, which is already
   * the state the UI should render. No refetch follows.
   *
   * Failures are typed and surfaced verbatim, so a rejected target shows the engine's
   * reason ("must be greater than 0") rather than a generic message. Nothing is
   * clamped locally, because a silently altered target is the one outcome a user
   * choosing a number cannot detect.
   */
  readonly apply: UseMutationResult<DailyTargetResponse, ApiError, number>;
  /** True while the request is in flight, so the control can disable itself. */
  readonly pending: boolean;
}

/**
 * The mutation behind the target control.
 *
 * Separate from the replay lifecycle on purpose: a target change is a **setting**, not
 * a step. It must not advance the cursor, and it must be refusable for reasons that
 * have nothing to do with whether a position is open.
 */
export function useDailyTargetConfig(): DailyTargetConfigControl {
  const api = usePaperApi();
  const queryClient = useQueryClient();

  const apply = useMutation<DailyTargetResponse, ApiError, number>({
    mutationFn: (targetAmount: number) => api.setDailyTarget(targetAmount),
    onSuccess: (state) => {
      queryClient.setQueryData(queryKeys.dailyTarget(), state);
    },
  });

  return { apply, pending: apply.isPending };
}

// ---------------------------------------------------------------------------
// Standard-mode projections
// ---------------------------------------------------------------------------

/**
 * The Phase 16 account projection.
 *
 * Standard-only: these routes carry no `mode` parameter, so they describe
 * Standard. The dashboard therefore never shows them while another mode is
 * selected, rather than labelling Standard's figures with another mode's name.
 */
export function useStandardAccount(
  enabled: boolean,
): UseQueryResult<AccountResponse, ApiError> {
  const api = usePaperApi();

  return useQuery({
    queryKey: queryKeys.account(),
    queryFn: ({ signal }) => api.getAccount(signal),
    enabled,
    retry: false,
  });
}

export function useTrades(
  enabled: boolean,
): UseQueryResult<TradesResponse, ApiError> {
  const api = usePaperApi();

  return useQuery({
    queryKey: queryKeys.trades(),
    queryFn: ({ signal }) => api.getTrades(signal),
    enabled,
    retry: false,
  });
}

export function useStatistics(
  enabled: boolean,
): UseQueryResult<StatisticsResponse, ApiError> {
  const api = usePaperApi();

  return useQuery({
    queryKey: queryKeys.statistics(),
    queryFn: ({ signal }) => api.getStatistics(signal),
    enabled,
    retry: false,
  });
}

// ---------------------------------------------------------------------------
// Market data
// ---------------------------------------------------------------------------

/**
 * Real candles from the frozen research dataset.
 *
 * Never synthesised. The API has no cursor or offset parameter, only
 * `start`/`end`/`limit`, so the window is expressed with those and nothing more.
 */
export function useMarket(
  query: MarketQuery,
  enabled = true,
): UseQueryResult<MarketResponse, ApiError> {
  const api = usePaperApi();
  const key = queryKeys.market(query);

  return useQuery({
    queryKey: key,
    queryFn: ({ signal }) => api.getMarket(query, signal),
    enabled,
    staleTime: 60_000,
    retry: false,
  });
}

// ---------------------------------------------------------------------------
// Lifecycle controls
// ---------------------------------------------------------------------------

export interface ReplayControl {
  readonly start: UseMutationResult<ReplayState, ApiError, number | undefined>;
  readonly pause: UseMutationResult<ReplayState, ApiError, void>;
  readonly step: UseMutationResult<ReplayState, ApiError, StepQuery | undefined>;
  readonly reset: UseMutationResult<ReplayState, ApiError, void>;
  /** True while any control request is in flight. Used to disable the buttons. */
  readonly busy: boolean;
}

export interface ReplayControlOptions {
  /**
   * Extra query keys to refresh after a successful mutation.
   *
   * The mutation response is authoritative for the replay itself, so
   * `onSuccess` needs no refetch. Anything the replay state does not contain —
   * AI's book, the account projection, the journal — must be listed here.
   */
  readonly alsoRefresh?: readonly (readonly unknown[])[];
}

/**
 * The four lifecycle mutations, scoped to one mode.
 *
 * Each returns the engine's own `ReplayState`, so a caller can render the new
 * state immediately rather than showing the previous one until a refetch lands.
 * That is why no `onSuccess` refetch is needed for the replay itself.
 *
 * The error type is declared explicitly on every call. react-query defaults its
 * error generic to `Error`, and `ApiError` is a plain union rather than a subclass,
 * so leaving it to inference would both fail to compile and obscure the contract
 * that these rejections are always typed.
 *
 * Refusals are **not** caught. `POSITION_OPEN`, `REPLAY_FINISHED` and
 * `MODE_NOT_AVAILABLE` arrive as typed errors and are shown verbatim: the UI must
 * report that the server refused rather than optimistically implying the action
 * succeeded.
 */
export function useReplayControls(
  mode: ModeInfo | undefined,
  options: ReplayControlOptions = {},
): ReplayControl {
  const api = usePaperApi();
  const queryClient = useQueryClient();
  const enabled = Boolean(mode?.available && mode.supports_execution);
  const modeId = mode?.mode;

  /**
   * Adopt the mutation's response, then refresh what it does not contain.
   *
   * The server returns the authoritative `ReplayState` from every lifecycle call, so
   * writing it into the cache makes the UI reflect the new status immediately
   * rather than showing the previous one until a refetch lands. Without this a
   * client that clicks Start sees `idle` for a beat and the Pause button stays
   * disabled — which reads as the click having done nothing.
   *
   * `setQueryData` rather than `invalidateQueries`, because the value is already
   * known and authoritative. A refetch would be a second request for a state the
   * server just handed over.
   */
  const adopt = async (state: ReplayState) => {
    queryClient.setQueryData(queryKeys.replay(modeId), state);
    await Promise.all(
      (options.alsoRefresh ?? []).map((key) =>
        queryClient.invalidateQueries({ queryKey: key }),
      ),
    );
  };

  // Defence in depth. The control buttons are already disabled for a mode the
  // server cannot serve, but a mutation must not be issuable at all for one: the
  // server would answer 409, and refusing locally with the same typed error keeps
  // the two paths from disagreeing about what is permitted.
  const requireEnabled = () => {
    if (!enabled) {
      throw {
        kind: "http",
        status: 409,
        code: "MODE_NOT_AVAILABLE",
        message: `mode ${modeId ?? "<unknown>"} cannot execute paper trades`,
      } satisfies ApiError;
    }
  };

  const start = useMutation<ReplayState, ApiError, number | undefined>({
    mutationFn: (intervalMs?: number) => {
      requireEnabled();
      return api.startReplay(modeId, intervalMs);
    },
    onSuccess: adopt,
  });

  const pause = useMutation<ReplayState, ApiError, void>({
    mutationFn: () => {
      requireEnabled();
      return api.pauseReplay(modeId);
    },
    onSuccess: adopt,
  });

  const step = useMutation<ReplayState, ApiError, StepQuery | undefined>({
    mutationFn: (query?: StepQuery) => {
      requireEnabled();
      return api.stepReplay(modeId, query?.count ?? 1);
    },
    onSuccess: adopt,
  });

  const reset = useMutation<ReplayState, ApiError, void>({
    mutationFn: () => {
      requireEnabled();
      return api.resetReplay(modeId);
    },
    onSuccess: adopt,
  });

  return {
    start,
    pause,
    step,
    reset,
    busy: start.isPending || pause.isPending || step.isPending || reset.isPending,
  };
}

// ---------------------------------------------------------------------------
// Polling
// ---------------------------------------------------------------------------

/**
 * Poll while the replay is armed, and only then.
 *
 * `running` means the server has armed its auto-run timer; it has no background
 * worker, so progression is driven by the client. Without polling the cursor would
 * appear frozen while armed, and with unconditional polling the dashboard would
 * re-request forever while idle.
 *
 * The interval is a fixed constant rather than anything derived from state, so the
 * refresh cadence is deterministic and cannot drift with the data.
 */
export const RUNNING_POLL_INTERVAL_MS = 1_000;

/**
 * Poll while the replay is armed, and only then.
 *
 * `running` means the server has armed its auto-run timer; it has no background
 * worker, so progression is driven by the client. Without polling the cursor would
 * appear frozen while armed, and with unconditional polling the dashboard would
 * re-request forever while idle.
 *
 * The interval is a fixed constant rather than anything derived from state, so the
 * refresh cadence is deterministic and cannot drift with the data. The effect tears
 * the timer down whenever the status leaves `running`, so pausing or finishing
 * stops polling immediately rather than one interval later.
 */
export function useRunningPolling(status: ReplayStatus | undefined): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (status !== "running") {
      return;
    }

    const timer = setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: ["replay"] });
    }, RUNNING_POLL_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [status, queryClient]);
}

// ---------------------------------------------------------------------------
// Client-driven advancement (Phase 20)
// ---------------------------------------------------------------------------

/**
 * One bar per tick, on the same cadence as the running poll above.
 *
 * Deliberately the same constant: the replay's visible rate of change and the rate
 * at which the UI re-reads it should agree, or the dashboard appears to skip bars
 * between refreshes. A faster step would advance the engine faster than the panel
 * that reports it could keep up, which reads as the UI losing figures rather than
 * the replay running quickly.
 */
export const AUTO_STEP_INTERVAL_MS = RUNNING_POLL_INTERVAL_MS;

/** Batches per tick. One, so each tick is one bar and the cadence is legible. */
export const AUTO_STEP_BARS = 1;

export interface AutoStepOptions {
  /** The mode whose replay is being driven. `undefined` disables the effect. */
  readonly mode: ModeInfo | undefined;
  /** The server's status. Stepping happens only while this is `running`. */
  readonly status: ReplayStatus | undefined;
  /** Extra query keys to refresh after each successful tick. */
  readonly alsoRefresh?: readonly (readonly unknown[])[];
}

/**
 * Advance the replay one bar per tick while the server reports `running`.
 *
 * ## Why the client drives this
 *
 * `POST /api/replay/start` sets the lifecycle flag and returns. The engine runs no
 * background worker and no timer - `replaysession.py` states this is deliberate, so
 * Phase 17D's prohibition on threads is not violated by omission. The consequence
 * is that `running` on its own moves nothing: the cursor stays put until something
 * calls `/api/replay/step`. This hook is that something.
 *
 * The alternative - a `setInterval` per bar in the engine - was rejected because it
 * would put a thread in a package whose design explicitly excludes one, and would
 * make replay results depend on wall-clock timing rather than on the number of bars
 * requested. Driving from the client keeps the engine a pure function of
 * `bars_processed`, so the same total bar count produces the same journal whether it
 * arrived as one batch, several, or one at a time.
 *
 * ## Why the guard conditions are what they are
 *
 * `inFlight` is a ref rather than state on purpose. State would re-render on every
 * tick, and the interval's own teardown reads as a duplicate timer; a ref mutates
 * without scheduling a render, so the interval is created exactly once per running
 * period. It also outlives the mutation: `step.isPending` is false in the same tick
 * a request resolves, which is the window in which a second request would overlap
 * the first and let two bars advance in one interval.
 *
 * `REPLAY_FINISHED` stops the loop rather than being retried. The engine reached the
 * end of the dataset; every subsequent step is a guaranteed `409`, so continuing
 * would spin a timer that can only fail. `POSITION_OPEN` does *not* stop the loop,
 * because the engine steps past an open position as part of its normal operation and
 * refusing to continue would strand the replay.
 */
export function useAutoStep({
  mode,
  status,
  alsoRefresh,
}: AutoStepOptions): void {
  const api = usePaperApi();
  const queryClient = useQueryClient();

  const modeId = mode?.mode;
  const enabled = Boolean(mode?.available && mode.supports_execution);

  const inFlight = useRef(false);
  const halted = useRef(false);

  /**
   * `alsoRefresh` through a ref, and this is load-bearing rather than tidiness.
   *
   * The dashboard builds that array inline, so a new identity arrives on every
   * render. Listed as an effect dependency it would tear down and rebuild the
   * interval on each one, restarting the countdown every time any unrelated state
   * changed — the loop would then fire at unpredictable times, and in the worst
   * case never, if renders came faster than the tick. A ref keeps the latest value
   * readable by the interval without making it a reason to re-run the effect.
   */
  const refreshKeys = useRef(alsoRefresh);
  refreshKeys.current = alsoRefresh;

  useEffect(() => {
    if (!enabled || status !== "running" || !modeId) {
      return;
    }

    /**
     * One bar, then adopt the engine's own response.
     *
     * `setQueryData` rather than `invalidateQueries`, for the same reason the manual
     * controls do it: the response is authoritative, so a refetch would be a second
     * request for state the server just handed over.
     */
    const advance = async () => {
      const state = await api.stepReplay(modeId, AUTO_STEP_BARS);

      queryClient.setQueryData(queryKeys.replay(modeId), state);

      await Promise.all(
        (refreshKeys.current ?? []).map((key) =>
          queryClient.invalidateQueries({ queryKey: key }),
        ),
      );
    };

    const timer = setInterval(() => {
      // A request already in flight owns this tick. Without this a slow response
      // would let two intervals' worth of work overlap, and two bars would advance
      // in one interval.
      if (inFlight.current || halted.current) {
        return;
      }

      inFlight.current = true;

      void advance()
        .catch((error: unknown) => {
          // A refusal carries no new state, so `status` is still `running` in the
          // cache and the effect's dependency has not changed. Left alone, the
          // timer would keep firing into a guaranteed `409`. `REPLAY_FINISHED` is
          // therefore terminal for the loop: the dataset is exhausted and no later
          // step can succeed. `POSITION_OPEN` deliberately does not halt, because
          // the engine steps through an open position as normal operation and
          // halting would strand the replay.
          if (isApiError(error) && error.code === "REPLAY_FINISHED") {
            halted.current = true;
          }
        })
        .finally(() => {
          inFlight.current = false;
        });
    }, AUTO_STEP_INTERVAL_MS);

    return () => {
      clearInterval(timer);
      inFlight.current = false;
      // Reset per running period, not per tick, so a fresh Start clears a halt left
      // by the previous one.
      halted.current = false;
    };
  }, [api, enabled, modeId, queryClient, status]);
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/**
 * The error to display for a query, or `null` when it succeeded.
 *
 * `error` is typed `ApiError` because the client only ever rejects with one, but a
 * react-query cache can hold anything, so this narrows defensively rather than
 * casting.
 */
export function queryError(
  result: { error: unknown } | undefined,
): ApiError | null {
  if (!result?.error) {
    return null;
  }

  return isApiError(result.error) ? result.error : null;
}

/** The first error across several results, for a single banner. */
export function firstError(
  ...results: ({ error: unknown } | undefined)[]
): ApiError | null {
  for (const result of results) {
    const error = queryError(result);
    if (error) {
      return error;
    }
  }

  return null;
}