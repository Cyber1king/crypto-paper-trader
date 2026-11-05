/** Market identifiers used by the dashboard and API.
 * 
 * These are display-time labels only. The API serves one fixed dataset,
 * so the market selector is a UI control; the underlying candle data
 * remains from the registered dataset. ETH is deliberately absent.
 */
export type MarketId = 'BTC/USDT' | 'EUR/USD' | 'GBP/USD';

/** Human-readable labels for each market. */
export const marketLabels: Record<MarketId, string> = {
  'BTC/USDT': 'BTC/USDT',
  'EUR/USD': 'EUR/USD',
  'GBP/USD': 'GBP/USD',
};

/** Placeholder exchange-rate-adjusted values for display purposes only.
 *  These are not live rates and must not be used for trading.
 *  They exist so the UI can show a non‑empty market description
 *  when the API serves only the base dataset.
 */
export const marketDescriptions: Record<MarketId, string> = {
  'BTC/USDT': 'Bitcoin / Tether pair, 1h candles from the frozen dataset',
  'EUR/USD': 'Euro / US Dollar, typical forex 1h resolution',
  'GBP/USD': 'British Pound / US Dollar, typical forex 1h resolution',
};

/** Markets that are cryptocurrency pairs. */
export const cryptoMarkets: ReadonlySet<MarketId> = new Set(['BTC/USDT']);

/** Markets that are forex pairs. */
export const forexMarkets: ReadonlySet<MarketId> = new Set(['EUR/USD', 'GBP/USD']);

/** All markets available in the selector, in a deterministic order. */
export const allMarkets: ReadonlyArray<MarketId> = [
  'BTC/USDT',
  'EUR/USD',
  'GBP/USD',
];

/** Market identifiers that must never appear in the selector. */
export const excludedMarkets: ReadonlySet<MarketId> = new Set([]);

/** Hook to get available markets (filters out excluded markets). */
export function useAvailableMarkets(): MarketId[] {
  return allMarkets.filter((m) => !excludedMarkets.has(m));
}

/** True when the market is a crypto pair. */
export function isCryptoMarket(market: MarketId): market is 'BTC/USDT' {
  return market === 'BTC/USDT';
}

/** True when the market is a forex pair. */
export function isForexMarket(market: MarketId): market is Exclude<MarketId, 'BTC/USDT'> {
  return market !== 'BTC/USDT';
}
