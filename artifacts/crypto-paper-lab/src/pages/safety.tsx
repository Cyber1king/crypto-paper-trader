import { GovernancePanel } from '@/components/research-panels';
import { PaperOnlyBanner } from '@/components/state';
import { useResearchGovernance } from '@/lib/hooks';

export function Safety() {
  const researchGovernance = useResearchGovernance();

  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">
      <header className="border-b bg-card px-6 py-4 flex flex-col gap-1">
        <h1 className="font-bold text-lg tracking-tight">Research safety</h1>
        <p className="text-xs text-muted-foreground font-mono uppercase tracking-wider">
          Read-only governance status - recorded by the engine
        </p>
      </header>

      <PaperOnlyBanner />

      <main
        className="flex-1 p-6 flex flex-col gap-6 max-w-[1800px] mx-auto w-full"
        data-testid="safety-page"
      >
        <p className="text-sm text-muted-foreground">
          This page only displays what the research API records. It renders no
          controls.
        </p>

        <section aria-label="Research governance" className="space-y-4">
          <GovernancePanel
            governance={researchGovernance.data}
            isLoading={researchGovernance.isLoading}
            isError={researchGovernance.isError}
          />
        </section>
      </main>
    </div>
  );
}