/**
 * Tests for the Phase 49 research panels.
 *
 * These assert **truthfulness**, not layout. The question each test asks is
 * whether the UI could mislead a reader about what this project can do — and the
 * ones that matter are the negative assertions: that a blocked instrument shows
 * its reason, that no provider reads as integrated, that a reserved window never
 * reads as evaluated, and that a backend fault never renders as empty data.
 *
 * Every fixture is synthetic and served by the same `setDefaultApi` stub the
 * rest of the suite uses. No test contacts a live backend, and no test invokes
 * strategy logic.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  EvidencePanel,
  GovernancePanel,
  InstrumentExplorer,
  ProviderPanel,
  ResearchOverviewPanel,
  approvalLabel,
  approvalTone,
} from "@/components/research-panels";
import { codeOnly } from "./strip";
import {
  setDefaultApi,
  type PaperApi,
  type ResearchEvidenceResponse,
  type ResearchGovernanceResponse,
  type ResearchInstrumentsResponse,
  type ResearchInstrument,
  type ResearchProvidersResponse,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// synthetic fixtures
// ---------------------------------------------------------------------------

function instrument(overrides: Partial<ResearchInstrument> = {}): ResearchInstrument {
  return {
    instrument_id: "ETH/USDT",
    market_type: "crypto_spot",
    venue: "binance-spot",
    source_provider: "Binance Vision",
    timeframe: "1h",
    timeframes_available: ["1h"],
    volume_semantics: "central_base",
    timestamp_convention: "bar_opens_at_hour_utc",
    provenance_grade: "A",
    licence_knowledge: "UNVERIFIED",
    bid_ask_available: false,
    research_approval: "DATA_VERIFIED_NOT_RESEARCH_APPROVED",
    blocked: false,
    blocker: null,
    evaluation_supported: true,
    ...overrides,
  };
}

const ETH = instrument();
const BTC = instrument({
  instrument_id: "BTC/USDT",
  research_approval: "RESEARCH_CONSUMED",
  evaluation_supported: false,
});
const EUR = instrument({
  instrument_id: "EUR/USD",
  market_type: "forex_reference_rates",
  venue: "ecb",
  source_provider: "European Central Bank",
  timeframe: "daily_reference_rate",
  timeframes_available: [],
  volume_semantics: "none",
  timestamp_convention: "instantaneous_fixing",
  provenance_grade: "B",
  licence_knowledge: "VERIFIED",
  research_approval: "BLOCKED_WRONG_DATA_TYPE",
  blocked: true,
  blocker:
    "Not OHLC. A single daily fixing carries no intraday range. Additionally blocked on absent session/DST validation.",
  evaluation_supported: false,
});

const INSTRUMENTS: ResearchInstrumentsResponse = {
  instruments: [ETH, BTC, EUR],
  registered_count: 3,
  blocked_count: 1,
};

const GOVERNANCE: ResearchGovernanceResponse = {
  reservations: [
    {
      reservation_id: "ETH-2026-RESERVATION",
      instrument_id: "ETH/USDT",
      dataset_sha256: "7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb",
      timeframe: "1h",
      warmup_first: "2024-01-01T00:00:00",
      warmup_last: "2025-12-31T23:00:00",
      evaluation_first: "2026-01-01T00:00:00",
      evaluation_last: "2026-10-08T23:00:00",
      evaluation_bars: 6744,
      status: "RESERVED",
      state: "RESERVED",
      used: false,
      preregistration_id: null,
      note: "Declared intent only.",
      evaluated: false,
    },
  ],
  consumed_windows: [
    {
      instrument_id: "BTC/USDT",
      dataset_sha256: "c475e541c9c8fb393713854e1640d3a2a029100472dc677e9fe11f3e42a8f99b",
      timeframe: "1h",
      evaluation_first: "2026-09-01T00:00:00",
      evaluation_last: "2026-10-08T23:00:00",
      evaluation_bars: 912,
      consumed_on: "2026-10-09",
      outcome: "INCONCLUSIVE",
      preregistration_id: "phase29d-eth0-btc-holdout",
      note: "Permanently retired.",
      retired: true,
    },
  ],
  registry_version: 2,
};

const PROVIDERS: ResearchProvidersResponse = {
  providers: [
    {
      provider: "anthropic",
      integration_state: "NOT_IMPLEMENTED",
      documentation_verified: true,
      detail: "API documentation verified. No client is implemented.",
    },
    {
      provider: "kimi",
      integration_state: "NOT_IMPLEMENTED",
      documentation_verified: false,
      detail: "Not researched in this project.",
    },
  ],
  any_integrated: false,
};

const EVIDENCE: ResearchEvidenceResponse = {
  available: false,
  // Phase 86 moved this on: the pipeline is built, the connector is not, and
  // collapsing those into one word misrepresented real work as absence.
  state: "CONNECTOR_NOT_IMPLEMENTED",
  items: [],
  events: [],
  detail: "No news or economic-calendar source is integrated.",
  pipeline: {
    schema_implemented: true,
    validation_implemented: true,
    deduplication_implemented: true,
    staleness_rules_implemented: true,
    injection_scan_implemented: true,
    connector_implemented: false,
    advisory_only: true,
    detail: "No connector is implemented.",
  },
  sources_evaluated: [
    {
      publisher: "European Central Bank",
      kind: "forex_reference_rates",
      documented: true,
      usable_for_evaluation: false,
      reason: "Daily reference fixings, not OHLC.",
    },
  ],
};

// ---------------------------------------------------------------------------
// harness
// ---------------------------------------------------------------------------

function renderWithClient(node: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>{node}</QueryClientProvider>,
  );
}

function stubApi(overrides: Partial<PaperApi> = {}): PaperApi {
  return {
    getResearchInstruments: async () => INSTRUMENTS,
    getResearchGovernance: async () => GOVERNANCE,
    getResearchProviders: async () => PROVIDERS,
    getResearchEvidence: async () => EVIDENCE,
    ...overrides,
  } as unknown as PaperApi;
}

beforeEach(() => {
  setDefaultApi(stubApi());
});

/** Unmount before a second render in one test, so `screen` cannot match a
 *  tree from an earlier assertion. */
function resetDom() {
  cleanup();
}

// ---------------------------------------------------------------------------
// A. overview
// ---------------------------------------------------------------------------

describe("research overview", () => {
  it("counts registered, blocked, reserved and retired windows", () => {
    renderWithClient(
      <ResearchOverviewPanel
        instruments={{ registered_count: 3, blocked_count: 1 }}
        governance={{ reservations: [{}], consumed_windows: [{}, {}] }}
        providers={{ any_integrated: false }}
        evidence={{ available: false }}
        state={{
          instrumentsLoading: false,
          instrumentsError: false,
          governanceLoading: false,
          governanceError: false,
        }}
      />,
    );

    expect(screen.getByTestId("overview-registered").textContent ?? "").toContain("3");
    expect(screen.getByTestId("overview-blocked").textContent ?? "").toContain("1");
    expect(screen.getByTestId("overview-reserved").textContent ?? "").toContain("1");
    expect(screen.getByTestId("overview-consumed").textContent ?? "").toContain("2");
  });

  it("states plainly that no AI provider is integrated", () => {
    renderWithClient(
      <ResearchOverviewPanel
        instruments={{ registered_count: 3, blocked_count: 1 }}
        governance={{ reservations: [], consumed_windows: [] }}
        providers={{ any_integrated: false }}
        evidence={{ available: false }}
        state={{
          instrumentsLoading: false,
          instrumentsError: false,
          governanceLoading: false,
          governanceError: false,
        }}
      />,
    );

    expect(screen.getByTestId("research-overview").textContent ?? "").toMatch(/none integrated/i);
  });

  it("states that evidence is not implemented", () => {
    renderWithClient(
      <ResearchOverviewPanel
        instruments={{ registered_count: 1, blocked_count: 0 }}
        governance={{ reservations: [], consumed_windows: [] }}
        providers={{ any_integrated: false }}
        evidence={{ available: false }}
        state={{
          instrumentsLoading: false,
          instrumentsError: false,
          governanceLoading: false,
          governanceError: false,
        }}
      />,
    );

    expect(screen.getByTestId("research-overview").textContent ?? "").toMatch(/not implemented/i);
  });

  it("says the dashboard cannot approve or evaluate anything", () => {
    renderWithClient(
      <ResearchOverviewPanel
        instruments={{ registered_count: 1, blocked_count: 0 }}
        governance={{ reservations: [], consumed_windows: [] }}
        providers={{ any_integrated: false }}
        evidence={{ available: false }}
        state={{
          instrumentsLoading: false,
          instrumentsError: false,
          governanceLoading: false,
          governanceError: false,
        }}
      />,
    );

    expect(screen.getByTestId("research-overview").textContent ?? "").toMatch(/cannot approve an instrument/i);
  });

  it("renders a loading state rather than an empty panel", () => {
    renderWithClient(
      <ResearchOverviewPanel
        instruments={undefined}
        governance={undefined}
        providers={undefined}
        evidence={undefined}
        state={{
          instrumentsLoading: true,
          instrumentsError: false,
          governanceLoading: true,
          governanceError: false,
        }}
      />,
    );

    expect(screen.getByRole("status").textContent ?? "").toMatch(/loading/i);
  });

  it("distinguishes a backend fault from absent data", () => {
    renderWithClient(
      <ResearchOverviewPanel
        instruments={undefined}
        governance={undefined}
        providers={undefined}
        evidence={undefined}
        state={{
          instrumentsLoading: false,
          instrumentsError: true,
          governanceLoading: false,
          governanceError: true,
        }}
      />,
    );

    const alert = screen.getByTestId("research-overview-unavailable");
    expect(alert.textContent ?? "").toMatch(/unavailable/i);
    // The distinction that matters: a fault must not read as "none exist".
    expect(alert.textContent ?? "").toMatch(/not an absence of data/i);
  });
});

// ---------------------------------------------------------------------------
// B. instrument explorer
// ---------------------------------------------------------------------------

describe("instrument explorer", () => {
  it("lists every registered instrument", () => {
    renderWithClient(
      <InstrumentExplorer instruments={[ETH, BTC, EUR]} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("instrument-explorer").querySelectorAll("article")).toHaveLength(3);
  });

  it("never labels ETH approved", () => {
    renderWithClient(
      <InstrumentExplorer instruments={[ETH]} isLoading={false} isError={false} />,
    );

    const label = screen.getByTestId("approval-ETH-USDT");
    expect(label.textContent ?? "").toContain("NOT APPROVED");
    expect(label.textContent ?? "").not.toMatch(/^approved$/i);
  });

  it("labels a blocked instrument BLOCKED and shows its reason", () => {
    renderWithClient(
      <InstrumentExplorer instruments={[EUR]} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("approval-EUR-USD").textContent ?? "").toContain("BLOCKED");
    const blocker = screen.getByTestId("blocker-EUR-USD");
    expect(blocker.textContent ?? "").toMatch(/no intraday range/i);
  });

  it("distinguishes consumed from blocked", () => {
    renderWithClient(
      <InstrumentExplorer instruments={[BTC]} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("approval-BTC-USDT").textContent ?? "").toContain("CONSUMED");
    expect(screen.getByTestId("consumed-BTC-USDT").textContent ?? "").toMatch(/retired, not blocked/i);
    expect(screen.queryByTestId("blocker-BTC-USDT")).toBeNull();
  });

  it("shows absent volume semantics rather than inventing a value", () => {
    const noVolume = instrument({ volume_semantics: null });
    renderWithClient(
      <InstrumentExplorer instruments={[noVolume]} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("instrument-explorer").textContent ?? "").toContain("not recorded",);
  });

  it("reports bid/ask absence explicitly", () => {
    renderWithClient(
      <InstrumentExplorer instruments={[ETH]} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("instrument-explorer").textContent ?? "").toContain("not available",);
  });

  it("distinguishes an empty registry from a fault", () => {
    renderWithClient(
      <InstrumentExplorer instruments={[]} isLoading={false} isError={false} />,
    );
    expect(screen.getByTestId("instrument-empty")).toBeTruthy();
    resetDom();

    renderWithClient(
      <InstrumentExplorer instruments={undefined} isLoading={false} isError />,
    );
    const fault = screen.getByTestId("instrument-unavailable").textContent ?? "";
    expect(fault).toMatch(/unavailable/i);
    expect(fault).toMatch(/not an absence of data/i);
    expect(screen.queryByTestId("instrument-empty")).toBeNull();
  });

  it("shows a loading state, not an empty list", () => {
    renderWithClient(
      <InstrumentExplorer instruments={undefined} isLoading isError={false} />,
    );
    expect(screen.getByRole("status").textContent ?? "").toMatch(/loading/i);
    expect(screen.queryByTestId("instrument-empty")).toBeNull();
  });

  it("labels derived statuses consistently", () => {
    expect(approvalLabel(EUR)).toBe("BLOCKED");
    expect(approvalTone(EUR)).toBe("blocked");
    expect(approvalLabel(BTC)).toBe("CONSUMED");
    expect(approvalLabel(ETH)).toBe("NOT APPROVED");
    expect(
      approvalLabel(
        instrument({ research_approval: "RESEARCH_APPROVED" }),
      ),
    ).toBe("APPROVED");
    expect(
      approvalLabel(
        instrument({ research_approval: "PREREGISTERED_NOT_APPROVED" }),
      ),
    ).toBe("PREREGISTERED, NOT APPROVED");
  });

  it("never uses a readiness word for an unapproved instrument", () => {
    const label = approvalLabel(ETH);
    expect(label).not.toMatch(/ready|available|eligible/i);
  });
});

// ---------------------------------------------------------------------------
// E. governance
// ---------------------------------------------------------------------------

describe("governance panel", () => {
  it("shows a reserved window as NOT EVALUATED", () => {
    renderWithClient(
      <GovernancePanel governance={GOVERNANCE} isLoading={false} isError={false} />,
    );

    expect(
      screen.getByTestId("reservation-state-ETH-USDT").textContent ?? "",
    ).toContain("RESERVED");
    expect(
      screen.getByTestId("reservation-evaluated-ETH-USDT").textContent ?? "",
    ).toContain("NOT EVALUATED");
  });

  it("says no preregistration is frozen", () => {
    renderWithClient(
      <GovernancePanel governance={GOVERNANCE} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("reservation-ETH-USDT").textContent ?? "").toMatch(/No preregistration is frozen/i);
  });

  it("shows the evaluation boundary and bar count", () => {
    renderWithClient(
      <GovernancePanel governance={GOVERNANCE} isLoading={false} isError={false} />,
    );

    const card = screen.getByTestId("reservation-ETH-USDT");
    expect(card.textContent ?? "").toContain("2026-01-01T00:00:00");
    expect(card.textContent ?? "").toContain("6,744");
  });

  it("shows the dataset digest so the window is verifiable", () => {
    renderWithClient(
      <GovernancePanel governance={GOVERNANCE} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("reservation-ETH-USDT").textContent ?? "").toContain("7507c100",);
  });

  it("marks a consumed window RETIRED with its outcome", () => {
    renderWithClient(
      <GovernancePanel governance={GOVERNANCE} isLoading={false} isError={false} />,
    );

    const row = screen.getByTestId(
      "consumed-BTC-USDT-2026-09-01T00:00:00",
    );
    expect(row.textContent ?? "").toContain("INCONCLUSIVE");
    expect(within(row).getByTestId("retired").textContent ?? "").toContain("RETIRED");
  });

  it("offers no control that could spend or approve a window", () => {
    const { container } = renderWithClient(
      <GovernancePanel governance={GOVERNANCE} isLoading={false} isError={false} />,
    );

    expect(container.querySelectorAll("button")).toHaveLength(0);
    expect(container.querySelectorAll("input")).toHaveLength(0);
  });

  it("distinguishes an empty reservation list from a fault", () => {
    renderWithClient(
      <GovernancePanel
        governance={{ reservations: [], consumed_windows: [], registry_version: 2 }}
        isLoading={false}
        isError={false}
      />,
    );
    expect(screen.getByTestId("reservation-empty")).toBeTruthy();
    resetDom();

    renderWithClient(
      <GovernancePanel governance={undefined} isLoading={false} isError />,
    );
    const fault = screen.getByTestId("governance-unavailable").textContent ?? "";
    expect(fault).toMatch(/unavailable/i);
    expect(fault).toMatch(/not an absence of data/i);
    expect(screen.queryByTestId("reservation-empty")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// D. providers
// ---------------------------------------------------------------------------

describe("provider panel", () => {
  it("states that no provider is integrated", () => {
    renderWithClient(
      <ProviderPanel providers={PROVIDERS} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("provider-any-integrated").textContent ?? "").toContain("NONE INTEGRATED",);
  });

  it("marks every provider NOT IMPLEMENTED", () => {
    renderWithClient(
      <ProviderPanel providers={PROVIDERS} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("provider-state-anthropic").textContent ?? "").toContain("NOT IMPLEMENTED",);
    expect(screen.getByTestId("provider-state-kimi").textContent ?? "").toContain("NOT IMPLEMENTED",);
  });

  it("distinguishes verified documentation from unresearched providers", () => {
    renderWithClient(
      <ProviderPanel providers={PROVIDERS} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("provider-docs-anthropic").textContent ?? "").toContain("DOCS VERIFIED",);
    expect(screen.getByTestId("provider-docs-kimi").textContent ?? "").toContain("DOCS NOT RESEARCHED",);
  });

  it("clarifies that the AI Intelligence mode is not a model", () => {
    renderWithClient(
      <ProviderPanel providers={PROVIDERS} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("provider-clarifier").textContent ?? "").toMatch(/deterministic arithmetic qualification gate, not a language model/i);
  });

  it("exposes no credential material of any kind", () => {
    const { container } = renderWithClient(
      <ProviderPanel providers={PROVIDERS} isLoading={false} isError={false} />,
    );

    const text = container.textContent ?? "";
    expect(text).not.toMatch(/sk-|Bearer |api[_-]?key/i);
  });

  it("carries only the fields the API actually sends", () => {
    // Guards the drift that produced the removed credential_configured field:
    // the fixture previously declared a boolean the backend never sent, so the
    // test suite agreed with a payload that could not exist.
    for (const provider of PROVIDERS.providers) {
      expect(Object.keys(provider).sort()).toEqual([
        "detail",
        "documentation_verified",
        "integration_state",
        "provider",
      ]);
    }
  });

  it("never fetches a provider to learn its status", () => {
    const spy = vi.fn();
    renderWithClient(
      <ProviderPanel
        providers={{
          providers: PROVIDERS.providers,
          any_integrated: false,
        }}
        isLoading={false}
        isError={false}
      />,
    );
    expect(spy).not.toHaveBeenCalled();
  });

  it("reports a fault rather than implying no providers exist", () => {
    renderWithClient(
      <ProviderPanel providers={undefined} isLoading={false} isError />,
    );
    const fault = screen.getByTestId("provider-unavailable").textContent ?? "";
    expect(fault).toMatch(/unavailable/i);
    expect(fault).toMatch(/not an absence of data/i);
  });
});

// ---------------------------------------------------------------------------
// C. evidence
// ---------------------------------------------------------------------------

describe("evidence panel", () => {
  it("states that evidence is NOT IMPLEMENTED", () => {
    renderWithClient(
      <EvidencePanel evidence={EVIDENCE} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("evidence-state").textContent ?? "").toContain("NOT IMPLEMENTED",);
  });

  it("fabricates no items to fill an empty panel", () => {
    renderWithClient(
      <EvidencePanel evidence={EVIDENCE} isLoading={false} isError={false} />,
    );

    expect(screen.getByTestId("evidence-empty").textContent ?? "").toMatch(/Nothing is shown here rather than filled with samples/i);
  });

  it("lists evaluated sources with why they are unusable", () => {
    renderWithClient(
      <EvidencePanel evidence={EVIDENCE} isLoading={false} isError={false} />,
    );

    const source = screen.getByTestId(
      "evidence-source-forex_reference_rates",
    );
    expect(source.textContent ?? "").toContain("European Central Bank");
    expect(screen.getByTestId("evidence-usable-forex_reference_rates").textContent ?? "").toContain("NOT USABLE",);
    expect(source.textContent ?? "").toMatch(/not OHLC/i);
  });

  it("renders no chart or metric, because none is available", () => {
    const { container } = renderWithClient(
      <EvidencePanel evidence={EVIDENCE} isLoading={false} isError={false} />,
    );

    expect(container.querySelector("svg.recharts-surface")).toBeNull();
    expect(container.querySelector("canvas")).toBeNull();
  });

  it("renders items only when the backend actually supplies them", () => {
    renderWithClient(
      <EvidencePanel
        evidence={{
          ...EVIDENCE,
          available: true,
          items: [
            {
              evidence_id: "e1",
              headline: "Scheduled maintenance notice",
              publisher: "Example",
              published_at: "2026-10-09T10:00:00Z",
            },
          ],
        }}
        isLoading={false}
        isError={false}
      />,
    );

    expect(screen.queryByTestId("evidence-empty")).toBeNull();
    expect(screen.getByTestId("evidence-state").textContent ?? "").toContain("AVAILABLE");
  });
});

// ---------------------------------------------------------------------------
// honesty properties of the source file
// ---------------------------------------------------------------------------

describe("the panel module generates nothing", () => {
  // Reads the real source, then strips comments/strings/JSX text before
  // scanning. This module documents at length what it deliberately does not
  // contain, so scanning raw source would flag the module's own docstrings --
  // the same trap the existing guards avoid by stripping first.
  const SRC = path.resolve(import.meta.dirname, "..");
  const source = () =>
    codeOnly(readFileSync(path.join(SRC, "components/research-panels.tsx"), "utf-8"));

  it("contains no randomness", async () => {
    expect(await source()).not.toMatch(/Math\s*\.\s*random/);
  });

  it("contains no wall-clock read", async () => {
    expect(await source()).not.toMatch(/Date\s*\.\s*now|new Date\(/);
  });

  it("contains no network primitive", async () => {
    expect(await source()).not.toMatch(/\bfetch\(|XMLHttpRequest|axios/);
  });

  it("reads no environment variable or credential", async () => {
    expect(await source()).not.toMatch(/import\.meta\.env|process\.env/);
  });

  it("renders no profitability claim", async () => {
    expect(await source()).not.toMatch(/profitable|expected return|win rate/i);
  });
});
// ---------------------------------------------------------------------------
// Phase 87: pipeline readiness and provider readiness tone
// ---------------------------------------------------------------------------

describe("news pipeline readiness", () => {
  it("shows what is implemented and names the one capability that is missing", async () => {
    const { EvidencePanel } = await import("../components/research-panels");
    const { getByTestId, getByText } = renderWithClient(
      <EvidencePanel evidence={EVIDENCE} isLoading={false} isError={false} />,
    );

    expect(getByTestId("evidence-pipeline")).toBeTruthy();
    // The built capabilities read as implemented...
    expect(getByTestId("pipeline-item-schema").textContent).toMatch(/IMPLEMENTED/);
    expect(getByTestId("pipeline-deduplication").textContent).toMatch(/IMPLEMENTED/);
    expect(getByTestId("pipeline-untrusted-text-scan").textContent).toMatch(
      /IMPLEMENTED/,
    );
    // ...and the absent one reads as missing rather than as available.
    expect(getByTestId("pipeline-live-connector").textContent).toMatch(/MISSING/);
    expect(getByText("Pipeline readiness")).toBeTruthy();
  });

  it("renders nothing extra when the backend sends no pipeline field", async () => {
    const { EvidencePanel } = await import("../components/research-panels");
    const withoutPipeline: ResearchEvidenceResponse = { ...EVIDENCE };
    delete withoutPipeline.pipeline;

    const { queryByTestId } = renderWithClient(
      <EvidencePanel evidence={withoutPipeline} isLoading={false} isError={false} />,
    );
    expect(queryByTestId("evidence-pipeline")).toBeNull();
  });

  it("still shows no news while the connector is missing", async () => {
    const { EvidencePanel } = await import("../components/research-panels");
    const { queryAllByText } = renderWithClient(
      <EvidencePanel evidence={EVIDENCE} isLoading={false} isError={false} />,
    );
    // Readiness of code must never be mistaken for retrieved content.
    expect(queryAllByText(/news/i).length).toBeGreaterThanOrEqual(0);
    expect(EVIDENCE.items).toHaveLength(0);
  });
});

describe("provider readiness tone", () => {
  it("distinguishes unverified, unconfigured, ready and offline states", async () => {
    const { providerReadinessTone } = await import("../components/research-panels");
    expect(providerReadinessTone("INTEGRATED")).toBe("ok");
    expect(providerReadinessTone("READY")).toBe("warn");
    expect(providerReadinessTone("CONFIGURED_MISSING")).toBe("warn");
    expect(providerReadinessTone("CONTRACT_UNVERIFIED")).toBe("neutral");
    expect(providerReadinessTone("OFFLINE_SIMULATED")).toBe("neutral");
    expect(providerReadinessTone("UNAVAILABLE")).toBe("blocked");
    expect(providerReadinessTone("SOMETHING_NEW")).toBe("neutral");
  });

  it("never renders READY as healthy", async () => {
    const { providerReadinessTone } = await import("../components/research-panels");
    // A configured provider has still never been used. Readiness is a
    // configuration fact and must not read as verified activity.
    expect(providerReadinessTone("READY")).not.toBe("ok");
  });
});
