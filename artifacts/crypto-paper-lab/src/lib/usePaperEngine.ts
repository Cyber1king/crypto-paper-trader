import { useState, useMemo, useEffect } from 'react';
import { generateCandles } from './mock-data';

export type Position = {
  id: string;
  asset: string;
  side: 'Long' | 'Short';
  entryPrice: number;
  size: number;
  openedAt: number;
};

export type Trade = {
  id: string;
  asset: string;
  side: 'Long' | 'Short';
  entryPrice: number;
  exitPrice: number;
  size: number;
  pnl: number;
  openedAt: number;
  closedAt: number;
};

export function usePaperEngine() {
  const [balance, setBalance] = useState(100000);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  
  const [asset, setAsset] = useState('BTC');
  const [timeframe, setTimeframe] = useState('1h');
  const [strategy, setStrategy] = useState('Trend Following');
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => setTick(t => t + 1), 3000); // Live chart heartbeat
    return () => clearInterval(interval);
  }, []);

  const candles = useMemo(() => {
    const baseCandles = generateCandles(asset, timeframe);
    const last = { ...baseCandles[baseCandles.length - 1] };
    const randomShift = (Math.random() - 0.5) * (asset === 'BTC' ? 20 : asset === 'ETH' ? 2 : 0.2);
    last.close = last.close + randomShift;
    last.high = Math.max(last.high, last.close);
    last.low = Math.min(last.low, last.close);
    baseCandles[baseCandles.length - 1] = last;
    return baseCandles;
  }, [asset, timeframe, tick]);

  const currentPrice = candles[candles.length - 1].close;

  const openPosition = (side: 'Long' | 'Short', size: number) => {
    if (size > balance) return false;
    
    const pos: Position = {
      id: Math.random().toString(36).substring(7),
      asset,
      side,
      entryPrice: currentPrice,
      size,
      openedAt: Date.now()
    };
    
    setBalance(b => b - size);
    setPositions(p => [...p, pos]);
    return true;
  };

  const closePosition = (id: string) => {
    const pos = positions.find(p => p.id === id);
    if (!pos) return;
    
    const exitPrice = currentPrice;
    
    let pnl = 0;
    if (pos.side === 'Long') {
      pnl = ((exitPrice - pos.entryPrice) / pos.entryPrice) * pos.size;
    } else {
      pnl = ((pos.entryPrice - exitPrice) / pos.entryPrice) * pos.size;
    }
    
    const trade: Trade = {
      ...pos,
      exitPrice,
      pnl,
      closedAt: Date.now()
    };
    
    setPositions(p => p.filter(x => x.id !== id));
    setTrades(t => [trade, ...t]);
    setBalance(b => b + pos.size + pnl);
  };
  
  const reset = () => {
    setBalance(100000);
    setPositions([]);
    setTrades([]);
  };

  return {
    balance,
    positions,
    trades,
    asset,
    setAsset,
    timeframe,
    setTimeframe,
    strategy,
    setStrategy,
    candles,
    currentPrice,
    openPosition,
    closePosition,
    reset
  };
}
