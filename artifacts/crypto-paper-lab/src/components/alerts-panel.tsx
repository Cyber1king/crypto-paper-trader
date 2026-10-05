/**
 * Alerts mode panel (Phase 18G).
 *
 * ## Brokerless, and that is a structural property
 *
 * Alerts has `supports_execution: false` and no broker reference anywhere in the
 * Python service. This component therefore:
 *
 * - renders **no** execution controls, **no** position sizing, **no** capital
 *   allocation and **no** order affordances of any kind;
 * - issues **no** request to `/api/replay`, because the mode has no replay session
 *   and the server would answer `409 MODE_NOT_AVAILABLE` on every call;
 * - shows the mode's own server-authored note rather than a list of alerts.
 *
 * ## Why there are no alerts to show
 *
 * There is no `/api/alerts` endpoint; the router answers `404`. Alerts' backend note
 * says notification delivery arrives in a later phase. So the honest rendering is
 * an explicit "observation only, delivery not implemented" state — not a fabricated
 * notification feed, which would be the exact failure Phase 17G's guard tests were
 * written to prevent.
 */

import { Bell, Eye, ShieldOff } from "lucide-react";

import { Badge } from "@/components/ui";
import { Panel } from "@/components/state";
import type { ModeInfo } from "@/lib/api";

/** Capabilities Alerts must never be shown as having. */
const REFUSED_CAPABILITIES = [
  "Buy / sell execution",
  "Position sizing",
  "Capital allocation",
  "Order controls",
  "Paper broker",
] as const;

export function AlertsPanel({ mode }: { mode: ModeInfo | undefined }) {
  return (
    <>
      <Panel
        title="Alerts — Observation Only"
        icon={<Bell className="w-4 h-4 text-primary" aria-hidden="true" />}
        badge={
          <Badge
            variant="outline"
            className="font-mono uppercase tracking-widest text-[10px] border-warning/40 text-warning-foreground bg-warning/10"
          >
            <Eye className="w-3 h-3 mr-1" aria-hidden="true" />
            No execution
          </Badge>
        }
        description="This mode holds no broker and cannot open, close or modify a position."
      >
        <div className="p-6 flex flex-col gap-5">
          <div className="border border-border rounded-md px-4 py-3 bg-muted/20">
            <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider mb-1">
              Server description
            </div>
            <p className="text-xs text-foreground leading-relaxed" data-testid="alerts-note">
              {mode?.note ??
                "Notification-only. Holds no broker and cannot execute paper trades."}
            </p>
          </div>

          <div>
            <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider mb-2 flex items-center gap-1.5">
              <ShieldOff className="w-3.5 h-3.5" aria-hidden="true" />
              Cannot be offered by this mode
            </div>
            <ul className="flex flex-col gap-1.5">
              {REFUSED_CAPABILITIES.map((capability) => (
                <li
                  key={capability}
                  className="flex items-center gap-2 text-xs text-muted-foreground font-mono"
                >
                  <span className="text-destructive" aria-hidden="true">
                    ✕
                  </span>
                  {capability}
                </li>
              ))}
            </ul>
          </div>

          <div className="border border-warning/30 bg-warning/5 rounded-md px-4 py-3">
            <div className="text-[10px] uppercase font-bold text-warning-foreground tracking-wider mb-1">
              Notification delivery is not implemented
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              The Python service exposes no alerts endpoint, and the mode's contract
              places notification delivery in a later phase. No alert feed is shown
              here because none exists — inventing one would present fabricated
              observations as real ones.
            </p>
          </div>

          <div>
            <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider mb-2">
              What this mode does instead
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              A signal is an observation, not an order. Standard and AI Intelligence
              both consume the same strategy observations; this mode is where a
              signal would be surfaced without anything acting on it. Until delivery
              exists, that role is served by the other modes' signal panels.
            </p>
          </div>
        </div>
      </Panel>
    </>
  );
}