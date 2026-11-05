import {
  EvidencePanel,
  InstrumentExplorer,
  ProviderPanel,
  ResearchOverviewPanel,
} from '@/components/research-panels';
import { PaperOnlyBanner } from '@/components/state';
import {
  useResearchEvidence,
  useResearchGovernance,
  useResearchInstruments,
  useResearchProviders,
} from '@/lib/hooks';

export function Research() {
  const researchInstruments = useResearchInstruments();
  const researchGovernance = useResearchGovernance();
  const researchProviders = useResearchProviders();
  const researchEvidence = useResearchEvidence();

  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">
      <header className="border-b bg-card px-6 py-4 flex flex-col gap-1">
        <h1 className="font-bold text-lg tracking-tight">Research reports</h1>
        <p className="text-xs text-muted-foreground font-mono uppercase tracking-wider">
          Read-only research status - recorded by the engine
        </p>
      </header>

      <PaperOnlyBanner />

      <main
        className="flex-1 p-6 flex flex-col gap-6 max-w-[1800px] mx-auto w-full"
        data-testid="research-page"
      >
        <p className="text-sm text-muted-foreground">
          This page only displays what the research API records. It renders no
          controls.
        </p>

        <section aria-label="Research reports" className="space-y-4">
          <ResearchOverviewPanel
            instruments={researchInstruments.data}
            governance={researchGovernance.data}
            providers={researchProviders.data}
            evidence={researchEvidence.data}
            state={{
              instrumentsLoading: researchInstruments.isLoading,
              instrumentsError: researchInstruments.isError,
              governanceLoading: researchGovernance.isLoading,
              governanceError: researchGovernance.isError,
            }}
          />

          <InstrumentExplorer
            instruments={researchInstruments.data?.instruments}
            isLoading={researchInstruments.isLoading}
            isError={researchInstruments.isError}
          />

          <ProviderPanel
            providers={researchProviders.data}
            isLoading={researchProviders.isLoading}
            isError={researchProviders.isError}
          />

          <EvidencePanel
            evidence={researchEvidence.data}
            isLoading={researchEvidence.isLoading}
            isError={researchEvidence.isError}
          />
        </section>
      </main>
    </div>
  );
}