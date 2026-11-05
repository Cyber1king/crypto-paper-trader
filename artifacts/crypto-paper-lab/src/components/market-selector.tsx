/** Market selector (Phase 27).
 * Allows the user to choose which market is displayed in the UI.
 * The API serves one fixed dataset, so this is a read-only selection.
 * the candle data always comes from the registered dataset, but the
 * context bar and accompanying labels reflect the chosen market.
 * ETH is deliberately absent from the selector.
 */import * as React from "react";
import { Badge } from "@/components/ui";
import { MarketId, marketLabels, allMarkets } from "@/lib/markets";


/** Market selector component props. */
interface MarketSelectorProps {
  defaultMarket?: MarketId;
  onChange?: (market: MarketId) => void;
}

/** Market selector component. */
export const MarketSelector: React.FC<MarketSelectorProps> = ({
  defaultMarket,
  onChange,
}) => {
  const [selected, setSelected] = React.useState<MarketId>(() => {
    if (defaultMarket) {
      return defaultMarket;
    }
    return 'BTC/USDT';
  });

  const options = allMarkets;

  const handleSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value as MarketId;
    setSelected(value);
    onChange?.(value);
  };

  return (
    <div>
      <select
        value={selected}
        onChange={handleSelect}
        className="flex items-center rounded-md border border-border bg-transparent px-2 text-sm"
      >
        {options.map((market: MarketId) => (
          <option
            key={market}
            value={market}
          >
            {marketLabels[market]}
          </option>
        ))}
      </select>
    </div>
  );
};
