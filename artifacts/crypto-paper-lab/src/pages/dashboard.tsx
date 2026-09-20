import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent, Button, Badge, Input, Select } from '@/components/ui';
import { usePaperEngine } from '@/lib/usePaperEngine';
import { analyzeCandles } from '@/lib/analysis';
import { generateSignal } from '@/lib/signals';
import { ResponsiveContainer, ComposedChart, Line, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';
import { Beaker, TrendingUp, TrendingDown, Activity, AlertTriangle, Info, Clock, DollarSign, BarChart2, ShieldAlert } from 'lucide-react';

export function Dashboard() {
  const engine = usePaperEngine();
  
  const analysis = analyzeCandles(engine.candles);
  const [signal, setSignal] = useState(generateSignal(engine.asset, engine.timeframe, analysis));
  
  useEffect(() => {
    setSignal(generateSignal(engine.asset, engine.timeframe, analysis));
  }, [engine.asset, engine.timeframe, engine.strategy, engine.candles]);
  
  const handleRegenerateSignal = () => {
    setSignal(generateSignal(engine.asset, engine.timeframe, analysis));
  };
  
  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">
      {/* Header */}
      <header className="border-b bg-card sticky top-0 z-10 px-6 py-4 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="bg-primary/10 p-2 rounded-md border border-primary/20">
            <Beaker className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="font-bold text-lg tracking-tight">Crypto Paper Lab</h1>
            <p className="text-xs text-muted-foreground font-mono flex items-center gap-1 uppercase tracking-wider mt-0.5">
              <ShieldAlert className="w-3 h-3" />
              Simulated Environment
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="text-right">
            <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider">Paper Balance</div>
            <div className="font-mono text-xl font-bold tracking-tight text-primary">
              ${engine.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={engine.reset} className="font-mono text-xs uppercase tracking-wider h-8">
            Reset Simulation
          </Button>
        </div>
      </header>
      
      {/* Warning Banner */}
      <div className="bg-warning/10 border-b border-warning/20 px-6 py-2 flex items-center justify-center gap-2 text-warning-foreground text-sm font-medium">
        <AlertTriangle className="w-4 h-4" />
        This is a risk-free paper trading environment for educational research. No real capital is used or connected.
      </div>
      
      <main className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 max-w-[1800px] mx-auto w-full">
        
        {/* Left Column: Config & Chart */}
        <div className="lg:col-span-8 flex flex-col gap-6">
          
          {/* Top Controls */}
          <Card>
            <CardContent className="p-4 flex flex-wrap gap-4 items-end">
              <div className="space-y-1.5 flex-1 min-w-[150px]">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Asset Pair</label>
                <Select value={engine.asset} onChange={e => engine.setAsset(e.target.value)}>
                  <option value="BTC">Bitcoin (BTC/USDT)</option>
                  <option value="ETH">Ethereum (ETH/USDT)</option>
                  <option value="SOL">Solana (SOL/USDT)</option>
                </Select>
              </div>
              <div className="space-y-1.5 flex-1 min-w-[150px]">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Timeframe</label>
                <Select value={engine.timeframe} onChange={e => engine.setTimeframe(e.target.value)}>
                  <option value="15m">15 Minutes</option>
                  <option value="1h">1 Hour</option>
                  <option value="4h">4 Hours</option>
                </Select>
              </div>
              <div className="space-y-1.5 flex-1 min-w-[150px]">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Strategy Profile</label>
                <Select value={engine.strategy} onChange={e => engine.setStrategy(e.target.value)}>
                  <option value="Trend Following">Trend Following</option>
                  <option value="Mean Reversion">Mean Reversion</option>
                  <option value="Breakout">Breakout Trader</option>
                </Select>
              </div>
            </CardContent>
          </Card>
          
          {/* Chart */}
          <Card className="flex-1 min-h-[500px] flex flex-col overflow-hidden">
            <CardHeader className="py-4 border-b flex flex-row items-center justify-between bg-muted/20">
              <div className="flex items-center gap-4">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Activity className="w-5 h-5 text-primary" />
                  {engine.asset} Market Data
                </CardTitle>
                <Badge variant="outline" className="font-mono bg-background text-sm">
                  {engine.currentPrice.toLocaleString(undefined, { style: 'currency', currency: 'USD' })}
                </Badge>
              </div>
              <Badge variant="secondary" className="uppercase font-mono text-[10px] tracking-widest text-muted-foreground">
                Synthetic OHLCV Feed
              </Badge>
            </CardHeader>
            <CardContent className="p-0 flex-1 relative bg-card">
              <div className="absolute inset-0 p-4">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={engine.candles}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.15} vertical={false} />
                    <XAxis dataKey="date" opacity={0.5} tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }} tickMargin={10} axisLine={false} tickLine={false} />
                    <YAxis yAxisId="price" domain={['auto', 'auto']} orientation="right" tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }} strokeOpacity={0} tickFormatter={(val) => `$${val.toLocaleString()}`} />
                    <YAxis yAxisId="volume" orientation="left" hide />
                    
                    <ReferenceLine y={analysis.resistance} yAxisId="price" stroke="hsl(var(--destructive))" strokeDasharray="4 4" label={{ position: 'insideTopLeft', value: 'RESISTANCE', fill: 'hsl(var(--destructive))', fontSize: 10, fontFamily: 'var(--font-mono)' }} opacity={0.6} />
                    <ReferenceLine y={analysis.support} yAxisId="price" stroke="hsl(var(--success))" strokeDasharray="4 4" label={{ position: 'insideBottomLeft', value: 'SUPPORT', fill: 'hsl(var(--success))', fontSize: 10, fontFamily: 'var(--font-mono)' }} opacity={0.6} />
                    
                    <Tooltip 
                       contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', fontFamily: 'var(--font-mono)', fontSize: '12px', borderRadius: '8px', boxShadow: '0 4px 12px -2px rgb(0 0 0 / 0.1)' }}
                       itemStyle={{ color: 'hsl(var(--foreground))' }}
                       labelStyle={{ color: 'hsl(var(--muted-foreground))', marginBottom: '4px' }}
                    />
                    <Bar yAxisId="volume" dataKey="volume" fill="hsl(var(--primary))" opacity={0.15} />
                    <Line yAxisId="price" type="monotone" dataKey="close" stroke="hsl(var(--primary))" strokeWidth={2.5} dot={false} activeDot={{ r: 6, fill: 'hsl(var(--primary))', stroke: 'hsl(var(--background))', strokeWidth: 3 }} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
          
          {/* Analysis Panel */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardContent className="p-5 flex flex-col gap-2">
                <span className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Trend Analysis</span>
                <div className="flex items-center gap-2 mt-1">
                  {analysis.trend === 'Bullish' ? <TrendingUp className="w-6 h-6 text-success" /> : <TrendingDown className="w-6 h-6 text-destructive" />}
                  <span className={`text-xl font-bold tracking-tight ${analysis.trend === 'Bullish' ? 'text-success' : 'text-destructive'}`}>{analysis.trend}</span>
                </div>
                <div className="text-xs text-muted-foreground font-mono mt-1 bg-muted p-1.5 rounded inline-flex w-fit">SMA20: ${analysis.sma20.toFixed(2)}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5 flex flex-col gap-2">
                <span className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Key Levels</span>
                <div className="flex flex-col gap-1.5 mt-1 font-mono text-sm">
                  <div className="flex justify-between items-center p-1 rounded hover:bg-muted/50 transition-colors">
                    <span className="text-destructive font-bold text-xs">RESISTANCE</span>
                    <span className="font-bold">${analysis.resistance.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between items-center p-1 rounded hover:bg-muted/50 transition-colors">
                    <span className="text-success font-bold text-xs">SUPPORT</span>
                    <span className="font-bold">${analysis.support.toFixed(2)}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5 flex flex-col gap-2">
                <span className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Market Structure</span>
                <div className="flex flex-col gap-2.5 mt-1">
                  <div className="flex items-center justify-between text-sm font-medium">
                    <span>Breakout Zone</span>
                    <Badge variant={analysis.breakout ? "default" : "outline"} className={analysis.breakout ? "bg-primary text-primary-foreground font-mono" : "font-mono"}>
                      {analysis.breakout ? "ACTIVE" : "INACTIVE"}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between text-sm font-medium">
                    <span>Retest Phase</span>
                    <Badge variant={analysis.retest ? "default" : "outline"} className="font-mono">
                      {analysis.retest ? "ACTIVE" : "INACTIVE"}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
          
        </div>
        
        {/* Right Column: Execution & Journal */}
        <div className="lg:col-span-4 flex flex-col gap-6">
          
          {/* AI Paper Signal */}
          <Card className="border-primary/20 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-2xl"></div>
            <CardHeader className="py-4 border-b bg-primary/5 flex flex-row items-center justify-between relative z-10">
              <CardTitle className="text-sm font-bold flex items-center gap-2 tracking-wide uppercase text-primary">
                <Info className="w-4 h-4" />
                Lab Generated Signal
              </CardTitle>
              <Button variant="ghost" size="icon" onClick={handleRegenerateSignal} className="h-7 w-7 text-primary hover:text-primary hover:bg-primary/10">
                <Activity className="w-4 h-4" />
              </Button>
            </CardHeader>
            <CardContent className="p-5 flex flex-col gap-5 relative z-10">
              <div className="flex items-center justify-between bg-muted/50 p-3 rounded-lg border border-border/50">
                <div className="text-xs text-muted-foreground font-bold font-mono tracking-wider">DIRECTION</div>
                <Badge className={`text-sm px-3 py-1 uppercase tracking-widest ${
                  signal.type === 'BUY' ? 'bg-success hover:bg-success/90 text-success-foreground' : 
                  signal.type === 'SELL' ? 'bg-destructive hover:bg-destructive/90 text-destructive-foreground' : 
                  'bg-warning text-warning-foreground hover:bg-warning/90'
                }`}>
                  {signal.type}
                </Badge>
              </div>
              <div className="flex items-center justify-between px-1">
                <div className="text-xs text-muted-foreground font-bold font-mono tracking-wider">CONFIDENCE SCORE</div>
                <div className="font-mono font-bold text-2xl tracking-tighter text-foreground">{signal.confidence}%</div>
              </div>
              <div className="bg-background p-4 rounded-lg text-sm leading-relaxed text-muted-foreground border shadow-sm">
                <span className="font-bold text-foreground uppercase text-xs tracking-wider block mb-1">Rationale</span>
                {signal.reason}
              </div>
            </CardContent>
          </Card>
          
          {/* Execution Panel */}
          <PositionControls engine={engine} />
          
          {/* Active Positions */}
          <ActivePositions engine={engine} />
          
        </div>
      </main>
      
      {/* Bottom Full-width: Journal */}
      <section className="px-6 pb-12 w-full max-w-[1800px] mx-auto">
        <TradeJournal engine={engine} />
      </section>
      
    </div>
  );
}

function PositionControls({ engine }: { engine: ReturnType<typeof usePaperEngine> }) {
  const [sizeStr, setSizeStr] = useState('10000');
  
  const handleOpen = (side: 'Long' | 'Short') => {
    const size = parseFloat(sizeStr);
    if (isNaN(size) || size <= 0) return;
    engine.openPosition(side, size);
  };
  
  return (
    <Card className="shadow-sm">
      <CardHeader className="py-4 border-b bg-card">
        <CardTitle className="text-sm font-bold flex items-center gap-2 uppercase tracking-wide">
          <DollarSign className="w-4 h-4 text-muted-foreground" />
          Simulated Execution
        </CardTitle>
      </CardHeader>
      <CardContent className="p-5 flex flex-col gap-6">
        <div className="space-y-2">
          <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Position Size (USD)</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 flex items-center pl-4 pointer-events-none text-muted-foreground font-mono font-bold">
              $
            </div>
            <Input 
              type="number" 
              value={sizeStr} 
              onChange={e => setSizeStr(e.target.value)} 
              className="pl-8 font-mono font-bold text-lg h-12 bg-muted/30 border-muted" 
              max={engine.balance}
            />
          </div>
          <div className="flex justify-between items-center text-xs">
            <span className="text-muted-foreground font-medium">Available: <span className="font-mono text-foreground font-bold">${engine.balance.toLocaleString(undefined, {maximumFractionDigits:0})}</span></span>
            <button onClick={() => setSizeStr((engine.balance).toString())} className="text-primary font-bold uppercase tracking-wider hover:underline">Max</button>
          </div>
        </div>
        
        <div className="grid grid-cols-2 gap-3">
          <Button 
            className="h-14 bg-success hover:bg-success/90 text-success-foreground font-bold tracking-wider text-xs sm:text-sm shadow-sm"
            onClick={() => handleOpen('Long')}
            disabled={parseFloat(sizeStr) > engine.balance || isNaN(parseFloat(sizeStr)) || parseFloat(sizeStr) <= 0}
          >
            PAPER BUY (LONG)
          </Button>
          <Button 
            className="h-14 bg-destructive hover:bg-destructive/90 text-destructive-foreground font-bold tracking-wider text-xs sm:text-sm shadow-sm"
            onClick={() => handleOpen('Short')}
            disabled={parseFloat(sizeStr) > engine.balance || isNaN(parseFloat(sizeStr)) || parseFloat(sizeStr) <= 0}
          >
            PAPER SELL (SHORT)
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ActivePositions({ engine }: { engine: ReturnType<typeof usePaperEngine> }) {
  if (engine.positions.length === 0) {
    return (
      <Card className="flex-1 flex flex-col shadow-sm">
        <CardHeader className="py-4 border-b">
          <CardTitle className="text-sm font-bold flex items-center gap-2 uppercase tracking-wide">
            <Clock className="w-4 h-4 text-muted-foreground" />
            Active Positions
          </CardTitle>
        </CardHeader>
        <CardContent className="p-10 flex-1 flex flex-col items-center justify-center text-center text-muted-foreground opacity-60 bg-muted/10">
          <Clock className="w-10 h-10 mb-4 stroke-1" />
          <p className="text-sm font-bold uppercase tracking-wider">No open positions</p>
          <p className="text-xs mt-2 max-w-[200px]">Execute a paper trade to monitor its synthetic performance here.</p>
        </CardContent>
      </Card>
    );
  }
  
  return (
    <Card className="flex-1 flex flex-col shadow-sm">
      <CardHeader className="py-4 border-b">
        <CardTitle className="text-sm font-bold flex items-center gap-2 uppercase tracking-wide">
          <Clock className="w-4 h-4 text-muted-foreground" />
          Active Positions <Badge variant="secondary" className="ml-1 font-mono">{engine.positions.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0 overflow-y-auto max-h-[400px]">
        <div className="flex flex-col">
          {engine.positions.map(pos => {
            const isLong = pos.side === 'Long';
            const currentPnlPercent = isLong 
              ? (engine.currentPrice - pos.entryPrice) / pos.entryPrice 
              : (pos.entryPrice - engine.currentPrice) / pos.entryPrice;
            const currentPnlUsd = currentPnlPercent * pos.size;
            const isProfitable = currentPnlUsd >= 0;
            
            return (
              <div key={pos.id} className="p-5 border-b last:border-0 hover:bg-muted/30 transition-colors">
                <div className="flex justify-between items-start mb-4">
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className={`font-bold uppercase tracking-wider text-[10px] ${isLong ? 'text-success border-success/30 bg-success/10' : 'text-destructive border-destructive/30 bg-destructive/10'}`}>
                      {pos.side}
                    </Badge>
                    <span className="font-bold text-lg">{pos.asset}</span>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => engine.closePosition(pos.id)} className="h-8 text-xs font-bold tracking-wider hover:bg-destructive hover:text-destructive-foreground hover:border-destructive transition-colors">
                    CLOSE
                  </Button>
                </div>
                
                <div className="grid grid-cols-2 gap-y-4 gap-x-2 text-sm">
                  <div>
                    <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider mb-1">Position Size</div>
                    <div className="font-mono font-medium">${pos.size.toLocaleString(undefined, {minimumFractionDigits: 2})}</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider mb-1">Entry Price</div>
                    <div className="font-mono font-medium">${pos.entryPrice.toLocaleString(undefined, {minimumFractionDigits: 2})}</div>
                  </div>
                  <div className="col-span-2 bg-background p-3 rounded border">
                    <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider mb-1">Unrealized PnL</div>
                    <div className={`font-mono font-bold text-lg flex items-center justify-between ${isProfitable ? 'text-success' : 'text-destructive'}`}>
                      <span>{isProfitable ? '+' : ''}{currentPnlUsd.toLocaleString(undefined, {minimumFractionDigits: 2})} USD</span>
                      <Badge variant="outline" className={`text-xs font-bold ${isProfitable ? 'border-success text-success' : 'border-destructive text-destructive'}`}>
                        {isProfitable ? '+' : ''}{(currentPnlPercent * 100).toFixed(2)}%
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function TradeJournal({ engine }: { engine: ReturnType<typeof usePaperEngine> }) {
  const [filter, setFilter] = useState('All');
  
  const filtered = engine.trades.filter(t => filter === 'All' || t.asset === filter);
  
  const totalTrades = engine.trades.length;
  const wins = engine.trades.filter(t => t.pnl > 0).length;
  const winRate = totalTrades > 0 ? (wins / totalTrades) * 100 : 0;
  const totalPnl = engine.trades.reduce((sum, t) => sum + t.pnl, 0);
  
  return (
    <Card className="shadow-sm">
      <CardHeader className="py-5 border-b bg-card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <CardTitle className="text-lg flex items-center gap-2 uppercase tracking-wide">
            <BarChart2 className="w-5 h-5 text-primary" />
            Trade Journal & Analytics
          </CardTitle>
          <div className="flex flex-wrap gap-4 md:gap-6 items-center">
            <div className="flex gap-1 bg-muted/50 p-1.5 rounded-lg border">
              {['All', 'BTC', 'ETH', 'SOL'].map(f => (
                <button 
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-4 py-1.5 rounded-md text-xs font-bold tracking-wider transition-colors ${filter === f ? 'bg-background shadow-sm text-foreground border-border/50' : 'text-muted-foreground hover:text-foreground hover:bg-background/50'}`}
                >
                  {f}
                </button>
              ))}
            </div>
            
            <div className="flex gap-4 items-center text-sm font-mono bg-muted/20 p-2 px-5 rounded-lg border">
              <div className="flex flex-col items-center">
                <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-sans font-bold">Win Rate</span>
                <span className="font-bold text-lg">{winRate.toFixed(1)}%</span>
              </div>
              <div className="w-px h-8 bg-border"></div>
              <div className="flex flex-col items-center">
                <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-sans font-bold">Total PnL</span>
                <span className={`font-bold text-lg ${totalPnl >= 0 ? 'text-success' : 'text-destructive'}`}>
                  {totalPnl > 0 ? '+' : ''}{totalPnl.toLocaleString(undefined, {minimumFractionDigits: 2})}
                </span>
              </div>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {engine.trades.length === 0 ? (
          <div className="p-16 text-center text-muted-foreground bg-muted/5">
            <p className="font-bold uppercase tracking-widest text-sm">No closed trades yet</p>
            <p className="text-sm mt-2 max-w-[300px] mx-auto">Close a position to see its full lifecycle recorded in your research journal.</p>
          </div>
        ) : (
          <div className="w-full overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-[10px] text-muted-foreground uppercase tracking-widest bg-muted/30 border-b">
                <tr>
                  <th className="px-6 py-4 font-bold">Time Closed</th>
                  <th className="px-6 py-4 font-bold">Asset</th>
                  <th className="px-6 py-4 font-bold">Side</th>
                  <th className="px-6 py-4 font-bold text-right">Size</th>
                  <th className="px-6 py-4 font-bold text-right">Entry</th>
                  <th className="px-6 py-4 font-bold text-right">Exit</th>
                  <th className="px-6 py-4 font-bold text-right">PnL (USD)</th>
                </tr>
              </thead>
              <tbody className="font-mono text-sm">
                {filtered.map(trade => {
                  const isProfitable = trade.pnl >= 0;
                  return (
                    <tr key={trade.id} className="border-b last:border-0 hover:bg-muted/10 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap text-muted-foreground text-xs font-sans">
                        {new Date(trade.closedAt).toLocaleTimeString()}
                      </td>
                      <td className="px-6 py-4 font-bold font-sans">{trade.asset}</td>
                      <td className="px-6 py-4">
                        <Badge variant="outline" className={`font-bold font-sans uppercase tracking-wider text-[10px] ${trade.side === 'Long' ? 'text-success border-success/30 bg-success/5' : 'text-destructive border-destructive/30 bg-destructive/5'}`}>
                          {trade.side}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-right">${trade.size.toLocaleString(undefined, {maximumFractionDigits: 0})}</td>
                      <td className="px-6 py-4 text-right text-muted-foreground">${trade.entryPrice.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                      <td className="px-6 py-4 text-right text-muted-foreground">${trade.exitPrice.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                      <td className={`px-6 py-4 text-right font-bold ${isProfitable ? 'text-success' : 'text-destructive'}`}>
                        {isProfitable ? '+' : ''}{trade.pnl.toLocaleString(undefined, {minimumFractionDigits: 2})}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
