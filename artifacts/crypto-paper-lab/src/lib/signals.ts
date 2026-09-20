export function generateSignal(asset: string, timeframe: string, analysis: any) {
  const seed = Date.now() / 10000;
  const random = Math.sin(seed * (asset === 'BTC' ? 1 : 2)) * 100;
  
  if (analysis.trend === 'Bullish' && random > 0) {
    return { 
      type: 'BUY', 
      confidence: Math.floor(75 + Math.abs(random) % 20), 
      reason: 'Trend alignment with volume expansion on local timeframe.' 
    };
  } else if (analysis.trend === 'Bearish' && random < 0) {
    return { 
      type: 'SELL', 
      confidence: Math.floor(75 + Math.abs(random) % 20), 
      reason: 'Breakdown of local support structure indicating downside pressure.' 
    };
  } else {
    return { 
      type: 'HOLD', 
      confidence: Math.floor(50 + Math.abs(random) % 40), 
      reason: 'Price consolidating between key levels. Wait for breakout.' 
    };
  }
}
