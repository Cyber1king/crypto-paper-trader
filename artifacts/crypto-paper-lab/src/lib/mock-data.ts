export function generateCandles(asset: string, timeframe: string, count: number = 100) {
  const basePrice = asset === 'BTC' ? 65000 : asset === 'ETH' ? 3500 : 150;
  const volatility = asset === 'BTC' ? 0.02 : asset === 'ETH' ? 0.03 : 0.05;
  
  const candles = [];
  let currentPrice = basePrice;
  
  const msPerCandle = timeframe === '15m' ? 15 * 60 * 1000 : timeframe === '1h' ? 60 * 60 * 1000 : 4 * 60 * 60 * 1000;
  
  const now = Date.now();
  const anchorTime = Math.floor(now / msPerCandle) * msPerCandle;
  
  for (let i = count; i > 0; i--) {
    const time = anchorTime - (i - 1) * msPerCandle;
    const seed = (time / 100000) + (asset === 'BTC' ? 1 : asset === 'ETH' ? 2 : 3);
    const trend = Math.sin(seed / 10) * basePrice * 0.05;
    const noise = Math.cos(seed * 3) * basePrice * volatility;
    
    const open = currentPrice;
    const close = basePrice + trend + noise + (Math.sin(seed * 7) * basePrice * 0.01);
    
    const maxVal = Math.max(open, close);
    const minVal = Math.min(open, close);
    const high = maxVal + Math.abs(Math.cos(seed * 11) * basePrice * volatility * 0.5);
    const low = minVal - Math.abs(Math.sin(seed * 13) * basePrice * volatility * 0.5);
    const volume = Math.abs(Math.sin(seed * 17)) * 1000 + 100;
    
    candles.push({ 
      time, 
      open, 
      high, 
      low, 
      close, 
      volume, 
      date: new Date(time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) 
    });
    currentPrice = close;
  }
  return candles;
}
