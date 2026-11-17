import type { ReactNode } from 'react';

import {
  ErrorPanel,
  LoadingPanel,
  PaperOnlyBanner,
  UnavailableModePanel,
} from '@/components/state';
import type { ModeInfo } from '@/lib/api';
import { queryError, useModes, useSelectedMode } from '@/lib/hooks';

/**
 * Shared frame for pages that show Standard-mode paper data.
 *
 * It reads the mode list from GET /api/modes through the existing hooks and renders
 * its children only when Standard mode is present and available, so a page never
 * shows another mode's figures under Standard's name. Everything inside comes from
 * the API; nothing here is computed, derived, or sample data.
 */
export function StandardPage({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: (mode: ModeInfo) => ReactNode;
}) {
  const modes = useModes();
  const selected = useSelectedMode(modes.data, 'standard');
  const mode = selected?.mode === 'standard' ? selected : undefined;
  const modesError = queryError(modes);

  let body: ReactNode;

  if (modes.isLoading) {
    body = <LoadingPanel label="Loading modes" />;
  } else if (modesError) {
    body = (
      <ErrorPanel
        error={modesError}
        title="Mode list unavailable"
        onRetry={() => void modes.refetch()}
      />
    );
  } else if (!mode) {
    body = (
      <UnavailableModePanel
        label="Standard"
        note="The API mode list does not include Standard mode, so there is no paper account to show here."
      />
    );
  } else if (!mode.available) {
    body = <UnavailableModePanel label={mode.label} note={mode.note} />;
  } else {
    body = children(mode);
  }

  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">
      <header className="border-b bg-card px-6 py-4 flex flex-col gap-1">
        <h1 className="font-bold text-lg tracking-tight">{title}</h1>
        <p className="text-xs text-muted-foreground font-mono uppercase tracking-wider">
          {subtitle}
        </p>
      </header>

      <PaperOnlyBanner />

      <main className="flex-1 p-6 flex flex-col gap-6 max-w-[1800px] mx-auto w-full">
        {body}
      </main>
    </div>
  );
}