import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getDefaultApi } from '@/lib/api';

interface ExperimentResultsPanelProps {
  readonly windowKey: string;
  readonly phases: readonly string[];
}

function formatSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  return `${(sizeBytes / 1024).toFixed(1)} KB`;
}

export function ExperimentResultsPanel({
  windowKey,
  phases,
}: ExperimentResultsPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [selectedFile, setSelectedFile] = useState<{
    phase: string;
    filename: string;
  } | null>(null);

  const experiments = useQuery({
    queryKey: ['research', 'experiments'],
    queryFn: ({ signal }) => getDefaultApi().getExperiments(signal),
    enabled: expanded,
    staleTime: 5 * 60 * 1000,
  });

  const resultFile = useQuery({
    queryKey: [
      'research',
      'experiment-file',
      selectedFile?.phase,
      selectedFile?.filename,
    ],
    queryFn: ({ signal }) => getDefaultApi().getExperimentFile(
      selectedFile!.phase,
      selectedFile!.filename,
      signal,
    ),
    enabled: expanded && selectedFile !== null,
  });

  if (phases.length === 0) return null;

  return (
    <div className="min-w-48" data-window-key={windowKey}>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-expanded={expanded}
        onClick={() => setExpanded((open) => !open)}
        className="h-auto min-h-7 px-1 py-1 text-left"
      >
        {expanded
          ? <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
          : <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />}
        <span>Experiment results</span>
      </Button>

      {expanded && (
        <div className="mt-2 space-y-3 text-xs">
          {experiments.isError ? (
            <p className="text-muted-foreground">Could not load experiment results.</p>
          ) : experiments.isLoading ? (
            <p className="text-muted-foreground">Loading experiment results…</p>
          ) : phases.map((phase) => {
            const phaseResult = experiments.data?.phases.find(
              (entry) => entry.phase === phase,
            );
            if (!phaseResult || phaseResult.files.length === 0) {
              return <p key={phase} className="text-muted-foreground">No results recorded in {phase}</p>;
            }

            return (
              <section key={phase} className="space-y-1.5">
                <h3 className="font-semibold text-foreground">{phase}</h3>
                <ul className="space-y-1">
                  {phaseResult.files.map((file) => (
                    <li key={file.name}>
                      <Button
                        type="button"
                        variant="link"
                        size="sm"
                        className="h-auto min-h-0 p-0 font-mono text-xs"
                        onClick={() => setSelectedFile({ phase, filename: file.name })}
                      >
                        {file.name} <span className="font-sans text-muted-foreground">({formatSize(file.size_bytes)})</span>
                      </Button>
                    </li>
                  ))}
                </ul>
                {selectedFile?.phase === phase && (
                  resultFile.isLoading ? (
                    <p className="text-muted-foreground">Loading {selectedFile.filename}…</p>
                  ) : resultFile.isError ? (
                    <p role="alert" className="text-destructive">Could not load {selectedFile.filename}.</p>
                  ) : resultFile.data && (
                    <pre className="max-h-[400px] overflow-auto whitespace-pre-wrap break-words rounded border bg-muted/40 p-2 font-mono text-[11px]">
                      {resultFile.data.content}
                    </pre>
                  )
                )}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
