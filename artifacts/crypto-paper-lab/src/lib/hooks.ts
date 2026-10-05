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

import { useEffect } from "react";

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