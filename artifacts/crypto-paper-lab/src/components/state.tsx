/**
 * Shared presentation components for real API state (Phase 18).
 *
 * These exist so that "loading", "unavailable" and "no data" are **explicit
 * states** rather than something a component improvises with a zero, an empty
 * string or a fabricated default. That distinction is the point of Phase 18: a
 * dashboard that cannot reach the engine must say so, because a `$0.00` balance
 * and a `$10,000` balance are both numbers and only one of them is real.
 *
 * Every component here is presentational. None fetches, and none computes.
 */

import type { ReactNode } from "react";
import { AlertTriangle, Loader2, ServerCrash, WifiOff } from "lucide-react";

import { Badge, Card, CardContent, CardHeader, CardTitle } from "@/components/ui";
import { describeError, type ApiError } from "@/lib/api";

/**
 * The persistent paper-only banner.
 *
 * Always rendered, in every state including error. The engine is simulated, so
 * the statement is a property of the system rather than a warning about one
 * session.
 */
export function PaperOnlyBanner({ children }: { children?: ReactNode }) {
  return (
    <div className="bg-warning/10 border-b border-warning/20 px-6 py-2 flex items-center justify-center gap-2 text-warning-foreground text-sm font-medium">
      <AlertTriangle className="w-4 h-4 shrink-0" />
      <span>
        PAPER TRADING ONLY — every balance, position and P&amp;L here is simulated.
        No exchange, wallet or real capital is connected.
      </span>
      {children}
    </div>
  );
}

/** Placeholder shown while a first request is in flight. */
export function LoadingPanel({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center text-center text-muted-foreground py-16 px-6">
      <Loader2 className="w-8 h-8 mb-4 stroke-1 animate-spin" aria-hidden="true" />
      <p className="text-sm font-bold uppercase tracking-wider">{label}</p>
      <p className="text-xs mt-2 max-w-[320px]">
        Reading authoritative state from the Python paper engine.
      </p>
    </div>
  );
}

/**
 * The API is unreachable.
 *
 * Distinct from {@link ErrorPanel} because the remedy differs: this one needs the
 * service started, that one needs the request changed. Neither substitutes data.
 */
export function ApiUnavailablePanel({
  error,
  onRetry,
}: {
  error: ApiError;
  onRetry?: () => void;
}) {
  return (
    <Card className="border-destructive/30">
      <CardContent className="p-8 flex flex-col items-center text-center gap-3">
        <WifiOff className="w-8 h-8 stroke-1 text-destructive" aria-hidden="true" />
        <p className="font-bold uppercase tracking-wider text-sm">
          Paper API unavailable
        </p>
        <p className="text-xs text-muted-foreground max-w-[420px]">
          {describeError(error)}
        </p>
        <p className="text-xs text-muted-foreground max-w-[420px]">
          No figures are shown because none could be read. Nothing on this screen
          is simulated.
        </p>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 text-xs font-bold uppercase tracking-wider text-primary hover:underline"
          >
            Retry
          </button>
        ) : null}
      </CardContent>
    </Card>
  );
}

/** A request the server refused. The server's own words are shown verbatim. */
export function ErrorPanel({
  error,
  title = "Request refused",
  onRetry,
}: {
  error: ApiError;
  title?: string;
  onRetry?: () => void;
}) {
  const unavailable = error.code === "NETWORK_UNAVAILABLE";

  if (unavailable) {
    return <ApiUnavailablePanel error={error} onRetry={onRetry} />;
  }

  return (
    <Card className="border-destructive/30">
      <CardContent className="p-6 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <ServerCrash className="w-4 h-4 text-destructive" aria-hidden="true" />
          <span className="font-bold uppercase tracking-wider text-xs">
            {title}
          </span>
          <Badge variant="outline" className="font-mono text-[10px]">
            {error.status} {error.code}
          </Badge>
        </div>
        {error.message ? (
          <p className="text-xs text-muted-foreground font-mono">{error.message}</p>
        ) : null}
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="self-start mt-1 text-xs font-bold uppercase tracking-wider text-primary hover:underline"
          >
            Retry
          </button>
        ) : null}
      </CardContent>
    </Card>
  );
}

/**
 * "The server says there is nothing here."
 *
 * Distinct from loading and from failure: the request succeeded and the honest
 * answer is an empty collection.
 */
export function EmptyPanel({
  title,
  hint,
  icon,
}: {
  title: string;
  hint?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center text-muted-foreground opacity-70 py-12 px-6">
      {icon ? <div className="mb-4 stroke-1">{icon}</div> : null}
      <p className="text-sm font-bold uppercase tracking-wider">{title}</p>
      {hint ? <p className="text-xs mt-2 max-w-[360px]">{hint}</p> : null}
    </div>
  );
}

/** A label/value row, the dashboard's basic unit of account information. */
export function StatRow({
  label,
  value,
  tone = "default",
  hint,
  mono = true,
}: {
  label: string;
  value: ReactNode;
  tone?: "default" | "success" | "destructive" | "muted";
  hint?: string;
  mono?: boolean;
}) {
  const toneClass =
    tone === "success"
      ? "text-success"
      : tone === "destructive"
        ? "text-destructive"
        : tone === "muted"
          ? "text-muted-foreground"
          : "text-foreground";

  return (
    <div className="flex items-baseline justify-between gap-4 py-1">
      <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider shrink-0">
        {label}
        {hint ? (
          <span className="block normal-case font-normal tracking-normal text-[10px] opacity-70">
            {hint}
          </span>
        ) : null}
      </span>
      {/*
       * The value side carries three constraints, and each is load-bearing.

       * `min-w-0` is the one that matters. A flex item defaults to
       * `min-width: auto`, which resolves to its content's min-content width, so this
       * box refuses to shrink below the widest unbreakable token inside it. For a
       * 64-character SHA-256 in a monospace face that token is the whole string:
       * roughly 548px, unbreakable because hex has no spaces. The row is 406px, so
       * the item overflowed it and the excess propagated up through every ancestor
       * to the document. `min-w-0` lets the item shrink to the row and no further.

       * `break-all` then makes the shrunk box usable. Without it the hash still would
       * not wrap, because `word-break: normal` only breaks at opportunities this
       * string does not have. It is applied to the value rather than the row so it is
       * scoped to the token that needs it: short values are unaffected, and a wrapped
       * hash stays readable rather than being truncated or clipped.

       * `min-w-0` on the row itself keeps the flex container from being widened by
       * its own content in the first place, which is what stops the cascade rather
       * than merely containing its last link.
       */}
      <span
        className={`min-w-0 break-all ${mono ? "font-mono" : "font-sans"} font-semibold text-sm text-right ${toneClass}`}
      >
        {value}
      </span>
    </div>
  );
}

/** A titled card with a consistent header, used by every panel. */
export function Panel({
  title,
  icon,
  badge,
  description,
  children,
  className,
}: {
  title: string;
  icon?: ReactNode;
  badge?: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      {/*
       * `flex-wrap` on the panel header, for the same reason as the chart header: a
       * long title and a status badge cannot always share one line, and on the
       * narrowest viewport "Intelligence Score" was being ellipsised to "Intelligenc…"
       * to make room for "Below threshold". Neither is expendable — one is the panel's
       * name, the other is the engine's verdict — so the badge drops to a second line
       * instead. Wider than that, nothing wraps and the header is unchanged.
       */}
      <CardHeader className="py-3 border-b bg-muted/20 flex flex-row flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <CardTitle className="text-sm font-bold uppercase tracking-wide flex items-center gap-2">
            {icon}
            <span className="truncate">{title}</span>
          </CardTitle>
          {description ? (
            <p className="text-[11px] text-muted-foreground mt-0.5">{description}</p>
          ) : null}
        </div>
        {badge ? <div className="shrink-0">{badge}</div> : null}
      </CardHeader>
      {children}
    </Card>
  );
}

/**
 * An explicit "this is not available" block for a mode the API reports as
 * unusable.
 *
 * The API's own `note` is rendered verbatim. The UI does not paraphrase a mode's
 * capabilities, because a paraphrase is where a reserved mode starts acquiring
 * features it does not have.
 */
export function UnavailableModePanel({
  label,
  note,
}: {
  label: string;
  note: string;
}) {
  return (
    <Card className="border-muted-foreground/25">
      <CardContent className="p-8 flex flex-col items-center text-center gap-3">
        <Badge variant="outline" className="font-mono uppercase tracking-widest text-[10px]">
          Unavailable
        </Badge>
        <p className="font-bold text-lg">{label}</p>
        <p className="text-xs text-muted-foreground max-w-[460px] leading-relaxed">
          {note}
        </p>
        <p className="text-xs text-muted-foreground max-w-[460px]">
          The server reports this mode as not available, so no execution was
          attempted and no substitute mode was selected.
        </p>
      </CardContent>
    </Card>
  );
}

/** A hairline divider matching the theme's border token. */
export function Rule() {
  return <div className="h-px bg-border my-2" role="presentation" />;
}