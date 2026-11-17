import sys

# Read the current market-selector.tsx
with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\components\market-selector.tsx', 'r') as f:
    content = f.read()

# Rewrite the component to be an interactive dropdown
new_content = '''/** Market selector (Phase 27).
 * Allows the user to choose which market is displayed in the UI.
 * The API serves one fixed dataset, so this is a read-only selection.
 * the candle data always comes from the registered dataset, but the
 * context bar and accompanying labels reflect the chosen market.
 * ETH is deliberately absent from the selector.
 */import * as React from "react";
import { Badge } from "@/components/ui";

/** Market identifier type. */
type MarketId = 'BTC/USDT' | 'EUR/USD' | 'GBP/USD' | 'USD/JPY';

/** Human-readable labels for each market. */
const marketLabels: Record<MarketId, string> = {
  'BTC/USDT': 'BTC/USDT',
  'EUR/USD': 'EUR/USD',
  'GBP/USD': 'GBP/USD',
  'USD/JPY': 'USD/JPY',
};

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

  const options = ['BTC/USDT', 'EUR/USD', 'GBP/USD', 'USD/JPY'];

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
        {options.map((market) => (
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
'''

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\components\market-selector.tsx', 'w') as f:
    f.write(new_content)

print('Rewrote market-selector.tsx')