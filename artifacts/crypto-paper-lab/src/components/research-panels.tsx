/**
 * Research-status panels (Phase 49).
 *
 * ## What this component is for
 *
 * The dashboard displays what the Python engine actually knows about the research
 * layer: which instruments are registered, which are blocked and why, which
 * evaluation windows are reserved or spent, and whether any AI provider is
 * integrated. Nothing here decides anything.
 *
 * ## The rule this file exists to enforce
 *
 * **A capability that is not implemented must never render as available.**
 *
 * Every panel distinguishes, explicitly and in the copy itself:
 *
 * | Rendered | Means |
 * |---|---|
 * | `NOT IMPLEMENTED` | No code path exists |
 * | `UNAVAILABLE` | A code path exists but the backend could not answer |
 * | `BLOCKED` | Real, with the backend's stated reason |
 * | `CONSUMMED` | Real, and permanently spent |
 * | `RESERVED` | Real, and unspent |
 *
 * There is deliberately no "coming soon", no disabled-but-inviting control, and
 * no placeholder that could be mistaken for a value. An empty panel says *why* it
 * is empty.
 *
 * ## No fabrication
 *
 * The evidence panel receives `items: []` and `events: []` from the backend and
 * renders an explicit unavailable state. It does not construct sample headlines,
 * and it does not render a chart from nothing. There is no `Math.random`, no
 * hard-coded "demo" value, and no fallback data path — the absence is shown.
 */

import {
  AlertTriangle,
  Ban,
  Database,
  FileWarning,
  Gauge,
  Lock,
  Newspaper,
  Server,
  ShieldCheck,
} from "lucide-react";

import { Badge } from "@/components/ui";
import { Panel } from "@/components/state";
import type {
  ResearchConsumedWindow,
  ResearchEvidenceResponse,
  ResearchPipelineStatus,
  ResearchGovernanceResponse,
  ResearchInstrument,
  ResearchProvider,
} from "@/lib/api";

/** Tone for a status label. Kept local so a new state is a deliberate edit. */
type Tone = "ok" | "warn" | "blocked" | "neutral";

const TONE_CLASS: Record<Tone, string> = {
  ok: "bg-primary/15 text-primary border-primary/30",
  warn: "bg-amber-500/15 text-amber-600 border-amber-500/30 dark:text-amber-400",
  blocked: "bg-destructive/15 text-destructive border-destructive/30",
  neutral: "bg-muted text-muted-foreground border-border",
};

function StatusLabel({
  tone = "neutral",
  children,
  testId,
}: {
  tone?: Tone;
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide ${TONE_CLASS[tone]}`}
    >
      {children}
    </span>
  );
}

/**
 * Shared honest state for a query that has not produced data.
 *
 * `loading`, `error` and `absent` are three different facts and are rendered as
 * three different things. A backend failure is never shown as an empty dataset,
 * because "nothing to report" and "could not ask" lead to opposite conclusions.
 */
function UnavailableState({
  kind,
  isLoading,
  isError,
  isEmpty,
  emptyReason,
  testId,
}: {
  kind: string;
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
  emptyReason: string;
  testId: string;
}) {
  if (isLoading) {
    return (
      <div
        data-testid={testId}
        role="status"
        aria-live="polite"
        className="rounded border border-dashed border-border p-4 text-sm text-muted-foreground"
      >
        <span className="inline-flex items-center gap-2">
          <Server className="h-4 w-4 animate-pulse" aria-hidden="true" />
          Loading {kind}…
        </span>
      </div>
    );
  }

  if (isError) {
    return (
      <div
        data-testid={testId}
        role="alert"
        className="rounded border border-destructive/40 bg-destructive/5 p-4 text-sm"
      >
        <p className="flex items-center gap-2 font-semibold text-destructive">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          {kind} unavailable
        </p>
        <p className="mt-1 text-muted-foreground">
          The backend did not answer. This is a connection or server fault, not
          an absence of data — nothing here should be read as &ldquo;none
          exist&rdquo;.
        </p>
      </div>
    );
  }

  return (
    <div
      data-testid={testId}
      className="rounded border border-dashed border-border p-4 text-sm text-muted-foreground"
    >
      <p className="font-medium text-foreground">
        {isEmpty ? `No ${kind} to display` : `${kind} unavailable`}
      </p>
      <p className="mt-1">{isEmpty ? emptyReason : emptyReason}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// A. Overview
// ---------------------------------------------------------------------------

export function ResearchOverviewPanel({
  instruments,
  governance,
  providers,
  evidence,
  state,
}: {
  instruments: { registered_count: number; blocked_count: number } | undefined;
  governance: { reservations: unknown[]; consumed_windows: unknown[] } | undefined;
  providers: { any_integrated: boolean } | undefined;
  evidence: { available: boolean } | undefined;
  state: {
    instrumentsLoading: boolean;
    instrumentsError: boolean;
    governanceLoading: boolean;
    governanceError: boolean;
  };
}) {
  const loaded = instruments && governance && providers;
  const failed =
    (state.instrumentsError && !instruments) ||
    (state.governanceError && !governance);

  return (
    <Panel
      title="Research — Overview"
      icon={<Gauge className="w-4 h-4 text-primary" aria-hidden="true" />}
      description="What the Python engine records about the research layer. Read-only."
    >
      <div data-testid="research-overview" className="space-y-3">
        {failed ? (
          <UnavailableState
            kind="research status"
            isLoading={false}
            isError
            isEmpty={false}
            emptyReason=""
            testId="research-overview-unavailable"
          />
        ) : !loaded ? (
          <UnavailableState
            kind="research status"
            isLoading
            isError={false}
            isEmpty={false}
            emptyReason=""
            testId="research-overview-loading"
          />
        ) : (
          <>
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat
                label="Registered instruments"
                value={instruments.registered_count}
                testId="overview-registered"
              />
              <Stat
                label="Blocked"
                value={instruments.blocked_count}
                tone={instruments.blocked_count > 0 ? "blocked" : "ok"}
                testId="overview-blocked"
              />
              <Stat
                label="Reserved windows"
                value={governance.reservations.length}
                tone="warn"
                testId="overview-reserved"
              />
              <Stat
                label="Retired windows"
                value={governance.consumed_windows.length}
                testId="overview-consumed"
              />
            </dl>

            <ul className="space-y-1 text-sm text-muted-foreground">
              <li>
                <span className="font-medium text-foreground">
                  AI providers:
                </span>{" "}
                {providers.any_integrated
                  ? "at least one integrated"
                  : "none integrated — interface and status reporting only"}
              </li>
              <li>
                <span className="font-medium text-foreground">
                  News &amp; economic evidence:
                </span>{" "}
                {evidence?.available
                  ? "available"
                  : "not implemented — no source is integrated"}
              </li>
            </ul>

            <p className="rounded border border-border bg-muted/30 p-2 text-xs text-muted-foreground">
              This dashboard displays research state. It cannot approve an
              instrument, spend an evaluation window, or run an evaluation —
              those decisions are made in the Python engine.
            </p>
          </>
        )}
      </div>
    </Panel>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
  testId,
}: {
  label: string;
  value: number;
  tone?: Tone;
  testId: string;
}) {
  return (
    <div className="rounded border border-border bg-muted/20 p-2">
      <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd
        data-testid={testId}
        className={`font-mono text-2xl font-bold ${
          tone === "blocked"
            ? "text-destructive"
            : tone === "warn"
              ? "text-amber-600 dark:text-amber-400"
              : "text-foreground"
        }`}
      >
        {value}
      </dd>
    </div>
  );
}

// ---------------------------------------------------------------------------
// B. Instrument explorer
// ---------------------------------------------------------------------------

/** Tone for an instrument's approval state. Approval is never implied. */
export function approvalTone(instrument: ResearchInstrument): Tone {
  if (instrument.blocked) return "blocked";
  if (instrument.research_approval === "RESEARCH_APPROVED") return "ok";
  if (instrument.research_approval === "RESEARCH_CONSUMED") return "neutral";
  if (instrument.research_approval === "NOT_APPROVED") return "blocked";
  return "warn";
}

/** Human label for an approval state. Never says "ready" or "available". */
export function approvalLabel(instrument: ResearchInstrument): string {
  if (instrument.blocked) return "BLOCKED";
  switch (instrument.research_approval) {
    case "RESEARCH_APPROVED":
      return "APPROVED";
    case "RESEARCH_CONSUMED":
      return "CONSUMED";
    case "PREREGISTERED_NOT_APPROVED":
      return "PREREGISTERED, NOT APPROVED";
    case "DATA_VERIFIED_NOT_RESEARCH_APPROVED":
      return "NOT APPROVED";
    default:
      return "NOT APPROVED";
  }
}

function field(value: string | null | undefined): string {
  return value && value.trim() ? value : "not recorded";
}

export function InstrumentExplorer({
  instruments,
  isLoading,
  isError,
}: {
  instruments: ResearchInstrument[] | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  return (
    <Panel
      title="Research — Instrument Explorer"
      icon={<Database className="w-4 h-4 text-primary" aria-hidden="true" />}
      badge={
        instruments ? (
          <StatusLabel tone="neutral" testId="instrument-count">
            {instruments.length} registered
          </StatusLabel>
        ) : undefined
      }
      description="Every instrument the registry declares. Appearing here is not approval."
    >
      <div data-testid="instrument-explorer" className="space-y-2">
        {!instruments ? (
          <UnavailableState
            kind="instruments"
            isLoading={isLoading}
            isError={isError}
            isEmpty={false}
            emptyReason="The registry could not be read."
            testId="instrument-unavailable"
          />
        ) : instruments.length === 0 ? (
          <UnavailableState
            kind="instruments"
            isLoading={false}
            isError={false}
            isEmpty
            emptyReason="The registry declares no instruments."
            testId="instrument-empty"
          />
        ) : (
          instruments.map((instrument) => (
            <article
              key={instrument.instrument_id}
              data-testid={`instrument-${instrument.instrument_id.replace("/", "-")}`}
              className="rounded border border-border p-3"
            >
              <header className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-mono text-sm font-bold">
                  {instrument.instrument_id}
                </h3>
                <StatusLabel
                  tone={approvalTone(instrument)}
                  testId={`approval-${instrument.instrument_id.replace("/", "-")}`}
                >
                  {approvalLabel(instrument)}
                </StatusLabel>
              </header>

              <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
                <Field label="Market" value={instrument.market_type} />
                <Field label="Venue" value={field(instrument.venue)} />
                <Field label="Source" value={field(instrument.source_provider)} />
                <Field label="Timeframe" value={field(instrument.timeframe)} />
                <Field
                  label="Volume"
                  value={field(instrument.volume_semantics)}
                />
                <Field
                  label="Provenance"
                  value={field(instrument.provenance_grade)}
                />
                <Field
                  label="Licence"
                  value={field(instrument.licence_knowledge)}
                />
                <Field
                  label="Bar convention"
                  value={field(instrument.timestamp_convention)}
                />
                <Field
                  label="Bid/ask"
                  value={
                    instrument.bid_ask_available === null
                      ? "not recorded"
                      : instrument.bid_ask_available
                        ? "available"
                        : "not available"
                  }
                />
              </dl>

              {instrument.blocked && instrument.blocker ? (
                <p
                  data-testid={`blocker-${instrument.instrument_id.replace("/", "-")}`}
                  className="mt-2 flex items-start gap-1.5 rounded border border-destructive/40 bg-destructive/5 p-2 text-xs text-destructive"
                >
                  <Ban className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <span>{instrument.blocker}</span>
                </p>
              ) : null}

              {instrument.research_approval === "RESEARCH_CONSUMED" ? (
                <p
                  data-testid={`consumed-${instrument.instrument_id.replace("/", "-")}`}
                  className="mt-2 flex items-start gap-1.5 rounded border border-border bg-muted/40 p-2 text-xs text-muted-foreground"
                >
                  <Lock
                    className="mt-0.5 h-3.5 w-3.5 shrink-0"
                    aria-hidden="true"
                  />
                  <span>
                    Every available window for this instrument has been spent.
                    It is retired, not blocked.
                  </span>
                </p>
              ) : null}
            </article>
          ))
        )}
      </div>
    </Panel>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="truncate font-medium">{value}</dd>
    </div>
  );
}

// ---------------------------------------------------------------------------
// E. Research governance
// ---------------------------------------------------------------------------

export function GovernancePanel({
  governance,
  isLoading,
  isError,
}: {
  governance:
    | {
        reservations: Array<{
          reservation_id: string;
          instrument_id: string;
          state: string;
          used: boolean;
          preregistration_id: string | null;
          evaluation_first: string | null;
          evaluation_last: string | null;
          evaluation_bars: number | null;
          evaluated: boolean;
          note: string | null;
          dataset_sha256: string;
        }>;
        consumed_windows: ResearchConsumedWindow[];
        registry_version: number | null;
      }
    | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  return (
    <Panel
      title="Research — Governance"
      icon={<ShieldCheck className="w-4 h-4 text-primary" aria-hidden="true" />}
      description="Reservation and consumption state, read from the authoritative registry."
    >
      <div data-testid="governance-panel" className="space-y-3">
        {!governance ? (
          <UnavailableState
            kind="governance status"
            isLoading={isLoading}
            isError={isError}
            isEmpty={false}
            emptyReason="The registry could not be read."
            testId="governance-unavailable"
          />
        ) : (
          <>
            <Section
              title="Reserved evaluation windows"
              testId="reservation-section"
            >
              {governance.reservations.length === 0 ? (
                <UnavailableState
                  kind="reservations"
                  isLoading={false}
                  isError={false}
                  isEmpty
                  emptyReason="No evaluation window is currently reserved."
                  testId="reservation-empty"
                />
              ) : (
                governance.reservations.map((reservation) => (
                  <article
                    key={reservation.reservation_id}
                    data-testid={`reservation-${reservation.instrument_id.replace("/", "-")}`}
                    className="rounded border border-amber-500/40 bg-amber-500/5 p-3"
                  >
                    <header className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="font-mono text-sm font-bold">
                        {reservation.instrument_id}
                      </h3>
                      <div className="flex gap-1">
                        <StatusLabel
                          tone={reservation.used ? "neutral" : "warn"}
                          testId={`reservation-state-${reservation.instrument_id.replace("/", "-")}`}
                        >
                          {reservation.state}
                        </StatusLabel>
                        <StatusLabel
                          tone={reservation.evaluated ? "ok" : "blocked"}
                          testId={`reservation-evaluated-${reservation.instrument_id.replace("/", "-")}`}
                        >
                          {reservation.evaluated ? "EVALUATED" : "NOT EVALUATED"}
                        </StatusLabel>
                      </div>
                    </header>
                    <dl className="mt-2 grid grid-cols-1 gap-1 text-xs sm:grid-cols-2">
                      <Field
                        label="Window"
                        value={`${field(reservation.evaluation_first)} → ${field(reservation.evaluation_last)}`}
                      />
                      <Field
                        label="Bars"
                        value={
                          reservation.evaluation_bars === null
                            ? "not recorded"
                            : reservation.evaluation_bars.toLocaleString()
                        }
                      />
                      <Field
                        label="Preregistration"
                        value={field(reservation.preregistration_id)}
                      />
                      <Field
                        label="Dataset SHA-256"
                        value={reservation.dataset_sha256}
                      />
                    </dl>
                    {!reservation.preregistration_id ? (
                      <p className="mt-2 rounded border border-border bg-muted/40 p-2 text-xs text-muted-foreground">
                        No preregistration is frozen, so this window cannot be
                        evaluated. The reservation records intent; it does not
                        permit a run.
                      </p>
                    ) : null}
                  </article>
                ))
              )}
            </Section>

            <Section
              title="Retired evaluation windows"
              testId="consumed-section"
            >
              {governance.consumed_windows.length === 0 ? (
                <UnavailableState
                  kind="retired windows"
                  isLoading={false}
                  isError={false}
                  isEmpty
                  emptyReason="No window has been consumed."
                  testId="consumed-empty"
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-border text-muted-foreground">
                        <th scope="col" className="py-1 pr-2 font-medium">
                          Instrument
                        </th>
                        <th scope="col" className="py-1 pr-2 font-medium">
                          Window
                        </th>
                        <th scope="col" className="py-1 pr-2 font-medium">
                          Outcome
                        </th>
                        <th scope="col" className="py-1 font-medium">
                          State
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {governance.consumed_windows.map((window) => (
                        <tr
                          key={window.dataset_sha256}
                          data-testid={`consumed-${window.instrument_id.replace("/", "-")}-${window.evaluation_first ?? "unknown"}`}
                          className="border-b border-border/50"
                        >
                          <td className="py-1.5 pr-2 font-mono">
                            {window.instrument_id}
                          </td>
                          <td className="py-1.5 pr-2 text-muted-foreground">
                            {field(window.evaluation_first)} →{" "}
                            {field(window.evaluation_last)}
                          </td>
                          <td className="py-1.5 pr-2 font-mono">
                            {field(window.outcome)}
                          </td>
                          <td className="py-1.5">
                            <StatusLabel tone="neutral" testId="retired">
                              {window.retired ? "RETIRED" : "UNKNOWN"}
                            </StatusLabel>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Section>

            <p className="text-xs text-muted-foreground">
              Registry schema version {governance.registry_version ?? "not recorded"}.
            </p>
          </>
        )}
      </div>
    </Panel>
  );
}

function Section({
  title,
  children,
  testId,
}: {
  title: string;
  children: React.ReactNode;
  testId: string;
}) {
  return (
    <section data-testid={testId} aria-label={title} className="space-y-2">
      <h3 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      {children}
    </section>
  );
}

// ---------------------------------------------------------------------------
// D. AI provider status
// ---------------------------------------------------------------------------

/**
 * Readiness tone for one provider state.
 *
 * Previously every state except INTEGRATED rendered in the same "blocked"
 * tone, which conflated three different situations: a contract nobody has
 * verified, a verified contract with nothing configured, and an adapter that
 * genuinely cannot be reached. They warrant different words to a reader, so
 * they no longer share a tone.
 *
 * ``READY`` is deliberately *not* rendered as healthy here. Readiness is a
 * configuration fact; the dashboard must not imply a provider has been used.
 */
export function providerReadinessTone(state: string): Tone {
  switch (state) {
    case "INTEGRATED":
      return "ok";
    case "READY":
      return "warn";
    case "CONFIGURED_MISSING":
      return "warn";
    case "UNAVAILABLE":
    case "REJECTED":
      return "blocked";
    case "OFFLINE_SIMULATED":
      return "neutral";
    case "CONTRACT_UNVERIFIED":
    case "NOT_IMPLEMENTED":
    default:
      return "neutral";
  }
}

export function ProviderPanel({
  providers,
  isLoading,
  isError,
}: {
  providers: { providers: ResearchProvider[]; any_integrated: boolean } | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  return (
    <Panel
      title="Research — AI Provider Status"
      icon={<FileWarning className="w-4 h-4 text-primary" aria-hidden="true" />}
      badge={
        providers ? (
          <StatusLabel
            tone={providers.any_integrated ? "ok" : "blocked"}
            testId="provider-any-integrated"
          >
            {providers.any_integrated ? "INTEGRATED" : "NONE INTEGRATED"}
          </StatusLabel>
        ) : undefined
      }
      description="Integration state only. This status is never obtained by calling a provider."
    >
      <div data-testid="provider-panel" className="space-y-2">
        {!providers ? (
          <UnavailableState
            kind="provider status"
            isLoading={isLoading}
            isError={isError}
            isEmpty={false}
            emptyReason="Status could not be read."
            testId="provider-unavailable"
          />
        ) : (
          <>
            {providers.providers.map((provider) => (
              <article
                key={provider.provider}
                data-testid={`provider-${provider.provider}`}
                className="rounded border border-border p-3"
              >
                <header className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-mono text-sm font-bold capitalize">
                    {provider.provider}
                  </h3>
                  <div className="flex flex-wrap gap-1">
                    <StatusLabel
                      tone={providerReadinessTone(provider.integration_state)}
                      testId={`provider-state-${provider.provider}`}
                    >
                      {provider.integration_state.replace(/_/g, " ")}
                    </StatusLabel>
                    <StatusLabel
                      tone={provider.documentation_verified ? "ok" : "neutral"}
                      testId={`provider-docs-${provider.provider}`}
                    >
                      {provider.documentation_verified
                        ? "DOCS VERIFIED"
                        : "DOCS NOT RESEARCHED"}
                    </StatusLabel>
                  </div>
                </header>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {provider.detail}
                </p>
              </article>
            ))}

            <p
              data-testid="provider-clarifier"
              className="rounded border border-border bg-muted/30 p-2 text-xs text-muted-foreground"
            >
              The paper-trading mode named <em>AI Intelligence</em> is a
              deterministic arithmetic qualification gate, not a language model.
              No model is connected to this dashboard.
            </p>
          </>
        )}
      </div>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// C. Research evidence
// ---------------------------------------------------------------------------

/**
 * Pipeline readiness, shown apart from the evidence list.
 *
 * The backend now distinguishes "the ingestion pipeline is implemented and the
 * source is missing" from "nothing exists". Collapsing those into one word --
 * "unavailable" -- would misrepresent real work as absence, and would make a
 * future connector look like nothing had ever been built.
 *
 * Rendered as a definition list rather than badges so the reader can see which
 * single capability is absent.
 */
function EvidencePipelineStatus({
  pipeline,
}: {
  pipeline: ResearchPipelineStatus | null | undefined;
}) {
  if (!pipeline) return null;

  const capabilities: ReadonlyArray<readonly [string, boolean]> = [
    ["Item schema", pipeline.schema_implemented],
    ["Record validation", pipeline.validation_implemented],
    ["Deduplication", pipeline.deduplication_implemented],
    ["Staleness rules", pipeline.staleness_rules_implemented],
    ["Untrusted-text scan", pipeline.injection_scan_implemented],
    ["Live connector", pipeline.connector_implemented],
  ];

  return (
    <section
      data-testid="evidence-pipeline"
      aria-label="News pipeline capability"
      className="rounded border border-border p-2"
    >
      <h3 className="mb-1 text-xs font-medium text-foreground">
        Pipeline readiness
      </h3>
      <dl className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
        {capabilities.map(([label, implemented]) => (
          <div key={label} className="flex items-center justify-between gap-2">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd>
              <StatusLabel
                tone={implemented ? "ok" : "blocked"}
                testId={`pipeline-${label.toLowerCase().replace(/\s+/g, "-")}`}
              >
                {implemented ? "IMPLEMENTED" : "MISSING"}
              </StatusLabel>
            </dd>
          </div>
        ))}
      </dl>
      {pipeline.detail ? (
        <p
          data-testid="evidence-pipeline-detail"
          className="mt-2 text-xs text-muted-foreground"
        >
          {pipeline.detail}
        </p>
      ) : null}
    </section>
  );
}

export function EvidencePanel({
  evidence,
  isLoading,
  isError,
}: {
  evidence: ResearchEvidenceResponse | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  return (
    <Panel
      title="Research — Evidence"
      icon={<Newspaper className="w-4 h-4 text-primary" aria-hidden="true" />}
      badge={
        evidence ? (
          <StatusLabel
            tone={evidence.available ? "ok" : "blocked"}
            testId="evidence-state"
          >
            {evidence.available ? "AVAILABLE" : evidence.state.replace(/_/g, " ")}
          </StatusLabel>
        ) : undefined
      }
      description="News and economic-event evidence, only where a source is genuinely integrated."
    >
      <div data-testid="evidence-panel" className="space-y-2">
        {!evidence ? (
          <UnavailableState
            kind="evidence"
            isLoading={isLoading}
            isError={isError}
            isEmpty={false}
            emptyReason="Status could not be read."
            testId="evidence-unavailable"
          />
        ) : (
          <>
            {!evidence.available ? (
              <p
                data-testid="evidence-unimplemented"
                className="rounded border border-border bg-muted/30 p-2 text-xs text-muted-foreground"
              >
                {evidence.detail}
              </p>
            ) : null}

            <EvidencePipelineStatus pipeline={evidence.pipeline} />

            {evidence.items.length === 0 && evidence.events.length === 0 ? (
              <UnavailableState
                kind="evidence items"
                isLoading={false}
                isError={false}
                isEmpty
                emptyReason="No source is integrated, so no evidence is retrieved. Nothing is shown here rather than filled with samples."
                testId="evidence-empty"
              />
            ) : null}

            {evidence.sources_evaluated.length > 0 ? (
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                  Sources evaluated
                </h3>
                <ul className="mt-1 space-y-1">
                  {evidence.sources_evaluated.map((source) => (
                    <li
                      key={source.publisher}
                      data-testid={`evidence-source-${source.kind}`}
                      className="rounded border border-border p-2 text-xs"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-1">
                        <span className="font-semibold">
                          {source.publisher}
                        </span>
                        <StatusLabel
                          tone={source.usable_for_evaluation ? "ok" : "blocked"}
                          testId={`evidence-usable-${source.kind}`}
                        >
                          {source.usable_for_evaluation
                            ? "USABLE"
                            : "NOT USABLE"}
                        </StatusLabel>
                      </div>
                      <p className="mt-1 text-muted-foreground">
                        {source.reason}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        )}
      </div>
    </Panel>
  );
}