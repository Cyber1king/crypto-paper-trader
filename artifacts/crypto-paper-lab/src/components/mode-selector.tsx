/**
 * The mode selector (Phase 18C).
 *
 * ## Authority
 *
 * The list, the labels, the availability flags and the explanations all come from
 * `GET /api/modes`. Nothing here is hard-coded. In particular the component does
 * **not** decide which modes can trade: `supports_execution` from the API is the
 * answer, which is what keeps Alerts structurally free of execution controls and
 * the three reserved modes free of invented functionality.
 *
 * A reserved mode is selectable — the user needs to be able to look at it and read
 * why it is unavailable — but selecting one issues no execution request, and the
 * reason shown is the server's own `note` rather than a client-authored message.
 */

import { Ban, CircleCheck, Eye, FlaskConical, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui";
import type { ModeInfo, ModesResponse } from "@/lib/api";

function iconFor(mode: ModeInfo) {
  if (!mode.available) {
    return <Ban className="w-3.5 h-3.5" aria-hidden="true" />;
  }

  if (!mode.supports_execution) {
    return <Eye className="w-3.5 h-3.5" aria-hidden="true" />;
  }

  if (mode.mode === "ai_intelligence") {
    return <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />;
  }

  return <FlaskConical className="w-3.5 h-3.5" aria-hidden="true" />;
}

/**
 * A short capability tag.
 *
 * Three distinct words because three different things are being said: usable,
 * usable-but-cannot-trade, and not-built-yet. Collapsing them into "enabled" would
 * hide exactly the distinction the mode architecture exists to make.
 */
function capabilityTag(mode: ModeInfo) {
  if (!mode.available) {
    return (
      <Badge
        variant="outline"
        className="font-mono uppercase tracking-widest text-[9px] border-muted-foreground/40 text-muted-foreground"
      >
        Reserved
      </Badge>
    );
  }

  if (!mode.supports_execution) {
    return (
      <Badge
        variant="outline"
        className="font-mono uppercase tracking-widest text-[9px] border-warning/40 text-warning-foreground bg-warning/10"
      >
        Observation only
      </Badge>
    );
  }

  return (
    <Badge
      variant="outline"
      className="font-mono uppercase tracking-widest text-[9px] border-success/40 text-success bg-success/10"
    >
      <CircleCheck className="w-3 h-3 mr-1" aria-hidden="true" />
      Executable
    </Badge>
  );
}

export function ModeSelector({
  modes,
  selected,
  onSelect,
  disabled = false,
}: {
  modes: ModesResponse | undefined;
  selected: string;
  onSelect: (mode: string) => void;
  disabled?: boolean;
}) {
  if (!modes) {
    return (
      <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider">
        Loading modes…
      </div>
    );
  }

  return (
    <div
      className="flex flex-wrap gap-2"
      role="radiogroup"
      aria-label="Paper mode"
    >
      {modes.modes.map((mode) => {
        const isSelected = mode.mode === selected;

        return (
          <button
            key={mode.mode}
            type="button"
            role="radio"
            aria-checked={isSelected}
            data-testid={`mode-${mode.mode}`}
            data-available={String(mode.available)}
            data-executable={String(mode.supports_execution)}
            disabled={disabled}
            onClick={() => onSelect(mode.mode)}
            className={[
              "flex flex-col items-start gap-1 px-3 py-2 rounded-md border text-left transition-colors min-w-[150px]",
              "disabled:opacity-60 disabled:cursor-not-allowed",
              isSelected
                ? "border-primary bg-primary/10 text-foreground"
                : "border-border bg-background hover:border-primary/40 hover:bg-muted/40",
              !mode.available ? "opacity-80" : "",
            ].join(" ")}
          >
            <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide">
              {iconFor(mode)}
              {mode.label}
            </span>
            {capabilityTag(mode)}
          </button>
        );
      })}
    </div>
  );
}

/**
 * The selected mode's server-authored description.
 *
 * Rendered verbatim from `ModeInfo.note`. It is the API's explanation of what the
 * mode does, and rewriting it here would be the frontend taking over a contract
 * question it should not answer.
 */
export function ModeNote({ mode }: { mode: ModeInfo | undefined }) {
  if (!mode) {
    return null;
  }

  return (
    <div className="text-[11px] text-muted-foreground leading-relaxed border-l-2 border-border pl-3">
      <span className="font-mono uppercase tracking-wider text-[10px] text-foreground">
        {mode.label}
      </span>
      <p className="mt-0.5">{mode.note}</p>
      {mode.policy ? (
        <p className="mt-1 font-mono text-[10px] opacity-80">
          policy: {mode.policy.name}
          {mode.policy.max_positions !== undefined
            ? ` · max_positions ${mode.policy.max_positions}`
            : ""}
          {mode.policy.threshold !== undefined
            ? ` · threshold ${mode.policy.threshold}`
            : ""}
        </p>
      ) : (
        <p className="mt-1 font-mono text-[10px] opacity-80">
          policy: none — this mode cannot execute paper trades
        </p>
      )}
    </div>
  );
}