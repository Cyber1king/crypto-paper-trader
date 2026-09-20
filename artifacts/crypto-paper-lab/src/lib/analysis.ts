export function analyzeCandles(candles: any[]) {
  if (!candles || candles.length === 0) {
    return { trend: 'Neutral', support: 0, resistance: 0, breakout: false, retest: false, sma20: 0 };
  }

  const recent = candles.slice(-20);
  const closes = recent.map(c => c.close);
  const max = Math.max(...closes);
  const min = Math.min(...closes);
  const current = closes[closes.length - 1];
  
  const sma20 = closes.reduce((a, b) => a + b, 0) / closes.length;
  const trend = current > sma20 ? 'Bullish' : 'Bearish';
  
  const support = min;
  const resistance = max;
  
  const breakout = current > resistance * 0.99 || current < support * 1.01;
  const retest = !breakout && (Math.abs(current - support) / support < 0.02 || Math.abs(current - resistance) / resistance < 0.02);
  
  return { trend, support, resistance, breakout, retest, sma20 };
}
