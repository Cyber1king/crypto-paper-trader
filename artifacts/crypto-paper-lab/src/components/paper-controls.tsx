/**
 * The paper replay control bar (Phase 18D).
 *
 * ## Authority
 *
 * Each button is one POST to one endpoint. There is no client-side state machine:
 * the component renders whatever `status` the server last reported and issues no
 * request it was not asked for. This is why the Python `Replay` remains the state
 * machine rather than the dashboard reimplementing a subset of it.
 *
 * ## Enabled states
 *
 * The disabled logic reads the server's status, not a local guess, and it is
 * deliberately conservative:
 *
 * - `finished` disables Start and Step, because the server answers `409
 *   REPLAY_FINISHED` for both and a refusal should not be a surprise.
 * - Reset stays enabled while a position is open, because the server *will* refuse
 *   it with `POSITION_OPEN`. Hiding the button would misrepresent what the engine
 *   does; the refusal is the contract.
 *
 * Every refusal is surfaced verbatim rather than swallowed, so a failed action is
 * never rendered as a successful one.
 */

import { Pause, Play, RotateCcw, SkipForward } from "lucide-react";

import { Button } from "@/components/ui";
import { describeError, isApiError, type ApiError, type ReplayStatus } from "@/lib/api";
import { statusLabel } from "@/lib/format";

/** The server's bound on a single batch. Mirrors `app.py:MAX_STEP_COUNT`. */
export const MAX_STEP_COUNT = 5000;

export interface ControlRefusal {
  readonly code: string;
  readonly message: string;
}

export function PaperControls({
  status,
  modeLabel,
  busy,
  disabled = false,
  disabledReason,
  onStart,
  onPause,
  onStep,
  onReset,
  refusal,
  stepCount,
  onStepCountChange,
}: {
  status: ReplayStatus | undefined;
  modeLabel: string;
  busy: boolean;
  /** True for Alerts and reserved modes, where no control may be offered. */
  disabled?: boolean;
  disabledReason?: string;
  onStart: () => void;
  onPause: () => void;
  onStep: () => void;
  onReset: () => void;
  refusal: ControlRefusal | null;
  stepCount: number;
  onStepCountChange: (count: number) => void;
}) {
  const finished = status === "finished";
  const running = status === "running";

  const blocked = disabled || busy;

  const stepDisabled = blocked || finished || stepCount < 1 || stepCount > MAX_STEP_COUNT;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
            Mode
          </span>
          <div className="font-mono text-sm font-semibold">{modeLabel}</div>
        </div>

        <div className="space-y-1.5">
          <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
            Replay status
          </span>
          <div
            className="font-mono text-sm font-semibold"
            data-testid="replay-status"
          >
            {statusLabel(status ?? "unknown")}
          </div>
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="step-count"
            className="block text-[10px] uppercase font-bold text-muted-foreground tracking-wider"
          >
            Bars per step (1–{MAX_STEP_COUNT})
          </label>
          <input
            id="step-count"
            type="number"
            min={1}
            max={MAX_STEP_COUNT}
            value={stepCount}
            disabled={blocked}
            onChange={(event) => onStepCountChange(Number(event.target.value))}
            className="w-28 h-9 px-2 font-mono text-sm bg-muted/30 border border-input rounded-md"
          />
        </div>

        <div className="flex flex-wrap gap-2 ml-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={onStart}
            disabled={blocked || finished}
            data-testid="control-start"
            className="font-mono text-xs uppercase tracking-wider h-9"
          >
            <Play className="w-3.5 h-3.5 mr-1.5" aria-hidden="true" />
            Start
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={onPause}
            disabled={blocked || !running}
            data-testid="control-pause"
            className="font-mono text-xs uppercase tracking-wider h-9"
          >
            <Pause className="w-3.5 h-3.5 mr-1.5" aria-hidden="true" />
            Pause
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={onStep}
            disabled={stepDisabled}
            data-testid="control-step"
            className="font-mono text-xs uppercase tracking-wider h-9"
          >
            <SkipForward className="w-3.5 h-3.5 mr-1.5" aria-hidden="true" />
            Step
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={onReset}
            disabled={blocked}
            data-testid="control-reset"
            className="font-mono text-xs uppercase tracking-wider h-9"
          >
            <RotateCcw className="w-3.5 h-3.5 mr-1.5" aria-hidden="true" />
            Reset
          </Button>
        </div>
      </div>

      {disabled && disabledReason ? (
        <p className="text-[11px] text-muted-foreground" data-testid="controls-disabled-reason">
          {disabledReason}
        </p>
      ) : null}

      {refusal ? (
        <div
          role="alert"
          data-testid="control-refusal"
          data-code={refusal.code}
          className="text-[11px] border border-destructive/30 bg-destructive/5 rounded-md px-3 py-2"
        >
          <span className="font-mono font-bold uppercase tracking-wider text-destructive">
            {refusal.code}
          </span>
          <span className="ml-2 text-muted-foreground">{refusal.message}</span>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Turn a mutation failure into something displayable.
 *
 * Returns `null` for a non-ApiError so a component cannot accidentally render
 * `[object Object]` as a refusal message.
 */
export function toRefusal(error: unknown): ControlRefusal | null {
  if (!isApiError(error)) {
    return null;
  }

  const apiError: ApiError = error;

  return { code: apiError.code, message: describeError(apiError) };
}