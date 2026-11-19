import { GovernancePanel } from '@/components/research-panels';
import { PaperOnlyBanner } from '@/components/state';
import { useResearchGovernance } from '@/lib/hooks';

const WINDOW_PHASE_MAP: Record<string, readonly string[]> = {
  'BTC/USDT|2024-01-01T00:00:00|2025-12-31T23:00:00': ['phase5', 'phase6', 'phase7', 'phase8'],
  'BTC/USDT|2026-01-01T00:00:00|2026-08-31T23:00:00': ['phase10', 'phase11'],
  'BTC/USDT|2026-09-01T00:00:00|2026-10-08T23:00:00': ['phase29', 'phase30'],
};

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
            windowPhaseMap={WINDOW_PHASE_MAP}
          />
        </section>
      </main>
    </div>
  );
}
