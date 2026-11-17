import { Badge } from '@/components/ui';

/**
 * Compact context strip: the market and timeframe the engine is serving, plus the
 * paper-only marker.
 *
 * Every value is passed in from the API's own market metadata. Nothing is hardcoded
 * or defaulted: while the metadata is missing the strip shows a dash, never an
 * assumed market. The values are read-only because the engine supports exactly one
 * dataset configuration.
 */
export function MarketContextBar({
  asset,
  timeframe,
  marketType,
}: {
  asset?: string;
  timeframe?: string;
  marketType?: string | null;
}) {
  return (
    <div
      className="border-b bg-card px-6 py-2 flex flex-wrap items-center gap-2"
      data-testid="market-context-bar"
    >
      <Badge
        variant="secondary"
        className="font-mono text-xs uppercase tracking-wider"
        data-testid="context-asset"
      >
        {asset ?? '—'}
      </Badge>
      <Badge
        variant="outline"
        className="font-mono text-[10px] uppercase tracking-widest"
        data-testid="context-timeframe"
      >
        {timeframe ?? '—'}
      </Badge>
      {marketType ? (
        <Badge
          variant="outline"
          className="font-mono text-[10px] uppercase tracking-widest"
          data-testid="context-market-type"
        >
          {marketType}
        </Badge>
      ) : null}
      <Badge
        variant="outline"
        className="font-mono text-[10px] uppercase tracking-widest border-primary/30 text-primary bg-primary/10"
        data-testid="context-paper"
      >
        Paper / simulated
      </Badge>
      <span className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider">
        Read from the dataset; not selectable
      </span>
    </div>
  );
}