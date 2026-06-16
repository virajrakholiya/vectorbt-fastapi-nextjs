"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area, Legend,
} from "recharts";
import {
  TrendingUp, TrendingDown, Wallet, BarChart3, PieChart, Activity, Download, Play,
  Settings, Calendar, Coins, Tag, LayoutGrid, ListOrdered, Terminal, ArrowUpRight,
  ArrowDownRight, Target, Percent, CircleDollarSign, AlertTriangle, ClipboardCopy, Check,
} from "lucide-react";
import { TradingChart } from "@/components/TradingChart";

type Trade = {
  symbol: string;
  entry_date: string | null;
  exit_date: string | null;
  entry_price: number | null;
  exit_price: number | null;
  quantity: number;
  trade_amount: number;
  exit_amount: number | null;
  profit_loss: number;
  return_pct: number;
  fees: number;
  status: string;
  direction: string;
};

type SymbolBreakdown = {
  symbol: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  open_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl_per_trade: number;
  avg_return_pct: number;
  best_trade: number;
  worst_trade: number;
  fees_paid: number;
};

type StrategyMeta = {
  id: string;
  label: string;
  description: string;
  params: { name: string; label: string; type: string; default: number; min?: number; max?: number; step?: number }[];
};

const PALETTE = ["#ffb000", "#2dd4bf", "#3ad07a", "#ff6b6b", "#7dd3fc", "#c2f04a", "#ff8a3d", "#f472b6"];

const NSE_STOCKS = [
  // IT
  "TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM",
  // Finance
  "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN", "BAJFINANCE", "BAJAJFINSV",
  "INDUSINDBK", "HDFCLIFE", "SBILIFE", "ICICIGI",
  // Energy & Commodities
  "RELIANCE", "ONGC", "BPCL", "COALINDIA", "NTPC", "POWERGRID",
  "TATASTEEL", "JSWSTEEL", "HINDALCO", "ADANIENT", "ADANIPORTS",
  // Consumer
  "HINDUNILVR", "ITC", "NESTLEIND", "TITAN", "ASIANPAINT", "PIDILITIND",
  // Auto
  "MARUTI", "HEROMOTOCO", "EICHERMOT", "TATAMOTORS",
  // Pharma
  "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP",
  // Capital Goods / Others
  "LT", "ULTRACEMCO", "GRASIM", "SHREECEM", "BHARTIARTL", "TATACONSUM",
];

const TIMEFRAMES = [
  { value: "1D", label: "Daily" },
  { value: "1W", label: "Weekly" },
  { value: "240", label: "4-Hour" },
  { value: "60", label: "1-Hour" },
  { value: "30", label: "30-Min" },
  { value: "15", label: "15-Min" },
];

const fmtCurrency = (n: number, max = 0) =>
  `₹${(n ?? 0).toLocaleString(undefined, { maximumFractionDigits: max })}`;

const fmtPct = (n: number, dp = 2) =>
  `${(n ?? 0).toFixed(dp)}%`;

function sampleArray<T>(arr: T[], n: number): T[] {
  if (arr.length <= n) return arr;
  const step = Math.max(1, Math.floor(arr.length / n));
  const out: T[] = [];
  for (let i = 0; i < arr.length; i += step) out.push(arr[i]);
  if (out[out.length - 1] !== arr[arr.length - 1]) out.push(arr[arr.length - 1]);
  return out;
}

export default function Dashboard() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any>(null);
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [activeTab, setActiveTab] = useState<"overview" | "symbols" | "trades">("overview");
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const [tradesFilter, setTradesFilter] = useState<string>("ALL");
  const [tradesPnLFilter, setTradesPnLFilter] = useState<"all" | "wins" | "losses" | "open">("all");
  const [copied, setCopied] = useState(false);

  const [config, setConfig] = useState({
    strategy_name: "pro_trader",
    symbols: ["RELIANCE", "TCS", "INFY"],
    timeframe: "1D",
    start_date: "2023-01-01",
    end_date: "2023-12-31",
    initial_capital: 50000,
    params: {} as Record<string, number>,
    intraday_mode: false,
    leverage: 1,
  });

  useEffect(() => {
    fetch("http://localhost:5000/api/strategies")
      .then((r) => r.json())
      .then((d) => setStrategies(d.strategies || []))
      .catch(() => {});
  }, []);

  const currentStrategy = strategies.find((s) => s.id === config.strategy_name);

  // Sync params when strategy changes
  useEffect(() => {
    if (!currentStrategy) return;
    const defaults: Record<string, number> = {};
    currentStrategy.params.forEach((p) => {
      defaults[p.name] = config.params[p.name] ?? p.default;
    });
    setConfig((c) => ({ ...c, params: defaults }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.strategy_name, strategies.length]);

  const buildReport = (): string => {
    if (!data) return "";
    const m = data.metrics;
    const breakdown: SymbolBreakdown[] = m.symbol_breakdown ?? [];
    const trades: Trade[] = data.trades ?? [];
    const equity = data.charts?.equity_curve ?? [];
    const drawdown = data.charts?.drawdown ?? [];

    const peakEquity = equity.length ? Math.max(...equity.map((p: any) => p.value)) : 0;
    const troughEquity = equity.length ? Math.min(...equity.map((p: any) => p.value)) : 0;
    const peakDD = drawdown.length ? Math.min(...drawdown.map((p: any) => p.value)) : 0;

    const winningTrades = trades.filter((t) => t.profit_loss > 0 && t.status.toLowerCase() !== "open");
    const losingTrades = trades.filter((t) => t.profit_loss < 0 && t.status.toLowerCase() !== "open");
    const openTrades = trades.filter((t) => t.status.toLowerCase() === "open");

    const avgWin = winningTrades.length ? winningTrades.reduce((s, t) => s + t.profit_loss, 0) / winningTrades.length : 0;
    const avgLoss = losingTrades.length ? losingTrades.reduce((s, t) => s + t.profit_loss, 0) / losingTrades.length : 0;
    const profitFactor = avgLoss !== 0 ? Math.abs((avgWin * winningTrades.length) / (avgLoss * losingTrades.length)) : 0;
    const expectancy = trades.length ? (m.net_profit ?? 0) / trades.length : 0;

    const strategy = strategies.find((s) => s.id === config.strategy_name);
    const paramsString = Object.entries(config.params).length
      ? Object.entries(config.params).map(([k, v]) => `- ${k}: ${v}`).join("\n")
      : "(strategy defaults used)";

    const tradesTable = trades.length === 0
      ? "_No trades._"
      : [
          "| # | Symbol | Entry Date | Exit Date | Entry ₹ | Exit ₹ | Qty | Trade Amount ₹ | P&L ₹ | Return % | Fees ₹ | Status |",
          "|---|--------|-----------|-----------|---------|--------|-----|----------------|-------|---------|--------|--------|",
          ...trades.map((t, i) => {
            const status = t.status.toLowerCase() === "open" ? "Open" : t.profit_loss >= 0 ? "Win" : "Loss";
            return `| ${i + 1} | ${t.symbol} | ${t.entry_date ?? "—"} | ${t.exit_date ?? "—"} | ${t.entry_price?.toFixed(2) ?? "—"} | ${t.exit_price?.toFixed(2) ?? "—"} | ${t.quantity.toFixed(2)} | ${t.trade_amount.toFixed(2)} | ${t.profit_loss.toFixed(2)} | ${t.return_pct.toFixed(2)} | ${t.fees.toFixed(2)} | ${status} |`;
          }),
        ].join("\n");

    const breakdownTable = breakdown.length === 0
      ? "_No per-symbol data._"
      : [
          "| Symbol | Trades | Wins | Losses | Open | Win Rate % | Total P&L ₹ | Avg P&L ₹ | Best ₹ | Worst ₹ | Fees ₹ |",
          "|--------|--------|------|--------|------|-----------|-------------|-----------|--------|---------|--------|",
          ...breakdown.map((b) =>
            `| ${b.symbol} | ${b.total_trades} | ${b.winning_trades} | ${b.losing_trades} | ${b.open_trades} | ${b.win_rate.toFixed(2)} | ${b.total_pnl.toFixed(2)} | ${b.avg_pnl_per_trade.toFixed(2)} | ${b.best_trade.toFixed(2)} | ${b.worst_trade.toFixed(2)} | ${b.fees_paid.toFixed(2)} |`
          ),
        ].join("\n");

    return `# Backtest Report

## Goal
Improve this trading strategy. Suggest concrete changes to entry/exit rules, parameters, filters, position sizing, or risk management to make it more **profitable**, **stable** (lower drawdown / higher Sharpe), and **higher trade frequency**. Justify each suggestion with the data below.

## Strategy
- **ID**: \`${config.strategy_name}\`
- **Name**: ${strategy?.label ?? config.strategy_name}
- **Description**: ${strategy?.description ?? "—"}

### Parameters
${paramsString}

### Strategy Logic (rules used in code)
${strategy?.params.map((p) => `- ${p.label}: default ${p.default}, range ${p.min ?? "?"}–${p.max ?? "?"}`).join("\n") ?? ""}

## Backtest Setup
- **Symbols**: ${config.symbols.join(", ")}
- **Period**: ${config.start_date} → ${config.end_date}
- **Initial Capital**: ₹${config.initial_capital.toLocaleString()}
- **Fees**: 0.10% per side
- **Slippage**: 0.05%
- **Data source**: FYERS (NSE) / yfinance fallback, daily bars
- **Timeframe**: ${TIMEFRAMES.find(t => t.value === config.timeframe)?.label ?? config.timeframe}

## Headline Metrics
| Metric | Value |
|--------|-------|
| Net P&L | ₹${(m.net_profit ?? 0).toFixed(2)} |
| Total Return | ${(m.total_return ?? 0).toFixed(2)}% |
| Final Capital | ₹${(m.final_value ?? 0).toFixed(2)} |
| Initial Capital | ₹${(m.initial_capital ?? config.initial_capital).toFixed(2)} |
| Win Rate | ${(m.win_rate ?? 0).toFixed(2)}% |
| Total Trades | ${m.total_trades ?? trades.length} |
| Sharpe Ratio | ${(m.sharpe_ratio ?? 0).toFixed(3)} |
| Max Drawdown | ${(m.max_drawdown ?? 0).toFixed(2)}% |
| Brokerage Paid | ₹${(m.fees_paid ?? 0).toFixed(2)} |

## Trade Statistics
| Stat | Value |
|------|-------|
| Winning Trades | ${winningTrades.length} |
| Losing Trades | ${losingTrades.length} |
| Open Trades | ${openTrades.length} |
| Avg Win | ₹${avgWin.toFixed(2)} |
| Avg Loss | ₹${avgLoss.toFixed(2)} |
| Profit Factor | ${profitFactor.toFixed(2)} |
| Expectancy / Trade | ₹${expectancy.toFixed(2)} |
| Peak Equity | ₹${peakEquity.toFixed(2)} |
| Trough Equity | ₹${troughEquity.toFixed(2)} |
| Peak Drawdown | ${peakDD.toFixed(2)}% |

## Per-Symbol Breakdown
${breakdownTable}

## All Trades
${tradesTable}

## Equity Curve (sampled)
${equity.length === 0 ? "_No equity data._" : sampleArray(equity, 30).map((p: any) => `- ${p.date}: ₹${p.value.toFixed(2)}`).join("\n")}

## What I Want From You (LLM)
1. Diagnose why the strategy underperforms / outperforms (look at per-symbol breakdown + trade frequency).
2. Propose 3 concrete changes (entry filter, exit rule, sizing, etc.) with expected impact.
3. Suggest parameter values to test next.
4. Flag any look-ahead bias, overfitting, or unrealistic assumptions in the rules.
5. Recommend a benchmark (e.g. buy-and-hold same symbols) to compare against.
`;
  };

  const copyReport = async () => {
    try {
      await navigator.clipboard.writeText(buildReport());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      alert("Failed to copy report. Browser blocked clipboard access.");
    }
  };

  const runBacktest = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("http://localhost:5000/api/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || "Backtest failed");
      setData(result);
      setChartSymbol(config.symbols[0]);
      setActiveTab("overview");
    } catch (err: any) {
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const trades: Trade[] = data?.trades ?? [];
  const breakdown: SymbolBreakdown[] = data?.metrics?.symbol_breakdown ?? [];

  const filteredTrades = useMemo(() => {
    let list = trades;
    if (tradesFilter !== "ALL") list = list.filter((t) => t.symbol === tradesFilter);
    if (tradesPnLFilter === "wins") list = list.filter((t) => t.profit_loss > 0);
    else if (tradesPnLFilter === "losses") list = list.filter((t) => t.profit_loss < 0 && t.status.toLowerCase() !== "open");
    else if (tradesPnLFilter === "open") list = list.filter((t) => t.status.toLowerCase() === "open");
    return list;
  }, [trades, tradesFilter, tradesPnLFilter]);

  const equityCombinedData = useMemo(() => {
    if (!data?.charts?.per_symbol_equity) return [];
    const perSym = data.charts.per_symbol_equity as Record<string, { date: string; value: number }[]>;
    const dates = new Set<string>();
    Object.values(perSym).forEach((arr) => arr.forEach((p) => dates.add(p.date)));
    const sortedDates = Array.from(dates).sort();
    return sortedDates.map((date) => {
      const row: any = { date };
      Object.entries(perSym).forEach(([sym, arr]) => {
        const point = arr.find((p) => p.date === date);
        if (point) row[sym] = point.value;
      });
      return row;
    });
  }, [data]);

  const chartCandles = chartSymbol && data?.charts?.per_symbol_candles?.[chartSymbol]
    ? data.charts.per_symbol_candles[chartSymbol]
    : data?.charts?.candlesticks ?? [];
  const chartMarkers = chartSymbol && data?.charts?.per_symbol_markers?.[chartSymbol]
    ? data.charts.per_symbol_markers[chartSymbol]
    : data?.charts?.markers ?? [];

  return (
    <div className="space-y-5 pb-12 animate-fade-in">
      {/* Header */}
      <header className="bg-card/80 glass border border-border rounded-lg overflow-hidden shadow-panel">
        <div className="p-5 md:p-6 border-b border-border flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="grid place-items-center w-11 h-11 rounded-md bg-primary/10 border border-primary/40 shadow-glow">
              <Terminal className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h1 className="font-mono text-xl font-bold tracking-tight text-foreground">
                VECTORBT<span className="text-primary">::</span>TERMINAL
              </h1>
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground mt-0.5">
                NSE Quantitative Backtesting
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2.5">
            <button
              onClick={runBacktest}
              disabled={loading}
              className="group flex items-center gap-2 bg-primary hover:shadow-glow text-primary-foreground px-6 py-2.5 rounded-md font-mono font-bold text-sm uppercase tracking-wider transition-all disabled:opacity-50 disabled:cursor-wait"
            >
              {loading ? <Activity className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              {loading ? "Running" : "Run Backtest"}
            </button>
            <button
              onClick={copyReport}
              disabled={!data}
              title="Copy full backtest report (markdown) to clipboard — paste into ChatGPT / Claude for strategy improvement suggestions"
              className={`flex items-center gap-2 px-4 py-2.5 border rounded-md font-mono font-medium text-sm uppercase tracking-wider transition-all disabled:opacity-30 disabled:cursor-not-allowed ${
                copied
                  ? "bg-success/10 border-success/40 text-success"
                  : "border-border-strong hover:border-primary/50 hover:text-primary text-foreground"
              }`}
            >
              {copied ? <Check className="w-4 h-4" /> : <ClipboardCopy className="w-4 h-4" />}
              {copied ? "Copied" : "Copy Report"}
            </button>
          </div>
        </div>

        {/* Configuration row */}
        <div className="p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
          <FieldWrapper icon={<Settings className="w-3.5 h-3.5" />} label="Strategy">
            <select
              className="bg-muted/50 border border-border-strong rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary transition-colors cursor-pointer w-full"
              value={config.strategy_name}
              onChange={(e) => setConfig({ ...config, strategy_name: e.target.value })}
            >
              {strategies.length === 0 && <option value="sma_rsi">SMA + RSI</option>}
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </select>
          </FieldWrapper>

          <FieldWrapper icon={<Tag className="w-3.5 h-3.5" />} label="Symbols">
            <SymbolMultiSelect
              value={config.symbols}
              onChange={(v) => setConfig({ ...config, symbols: v })}
            />
          </FieldWrapper>

          <FieldWrapper icon={<Activity className="w-3.5 h-3.5" />} label="Timeframe">
            <select
              className="bg-muted/50 border border-border-strong rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary transition-colors cursor-pointer w-full"
              value={config.timeframe}
              onChange={(e) => setConfig({ ...config, timeframe: e.target.value })}
            >
              {TIMEFRAMES.map((tf) => (
                <option key={tf.value} value={tf.value}>{tf.label}</option>
              ))}
            </select>
          </FieldWrapper>

          <FieldWrapper icon={<Calendar className="w-3.5 h-3.5" />} label="Start Date">
            <input
              type="date"
              className="bg-muted/50 border border-border-strong rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary transition-colors w-full"
              value={config.start_date}
              max={config.end_date}
              onChange={(e) => setConfig({ ...config, start_date: e.target.value })}
            />
          </FieldWrapper>

          <FieldWrapper icon={<Calendar className="w-3.5 h-3.5" />} label="End Date">
            <input
              type="date"
              className="bg-muted/50 border border-border-strong rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary transition-colors w-full"
              value={config.end_date}
              min={config.start_date}
              max={new Date().toISOString().split("T")[0]}
              onChange={(e) => setConfig({ ...config, end_date: e.target.value })}
            />
          </FieldWrapper>

          <FieldWrapper icon={<Coins className="w-3.5 h-3.5" />} label="Initial Capital (₹)">
            <input
              type="number"
              min={1000}
              step={1000}
              className="bg-muted/50 border border-border-strong rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary transition-colors w-full"
              value={config.initial_capital}
              onChange={(e) => setConfig({ ...config, initial_capital: Number(e.target.value) || 0 })}
            />
          </FieldWrapper>

          <FieldWrapper icon={<Activity className="w-3.5 h-3.5" />} label="Trade Settings">
            <div className="flex flex-col gap-2">
              {/* Intraday Mode toggle */}
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded accent-primary cursor-pointer"
                  checked={config.intraday_mode}
                  onChange={(e) => setConfig({ ...config, intraday_mode: e.target.checked })}
                />
                <span className="text-sm text-foreground">Intraday Mode</span>
              </label>

              {/* Leverage slider — only visible when intraday_mode is on */}
              {config.intraday_mode && (
                <div className="flex flex-col gap-1 pt-1">
                  <span className="text-sm text-foreground">
                    Leverage: {config.leverage}x
                  </span>
                  <input
                    type="range"
                    min={1}
                    max={5}
                    step={0.5}
                    value={config.leverage}
                    className="w-full accent-primary cursor-pointer"
                    onChange={(e) => setConfig({ ...config, leverage: Number(e.target.value) })}
                  />
                  <span className="text-xs text-muted-foreground">
                    ₹20 entry + ₹20 exit per trade
                  </span>
                </div>
              )}
            </div>
          </FieldWrapper>
        </div>

        {currentStrategy && (
          <div className="px-6 pb-5 -mt-2">
            <p className="font-mono text-xs text-muted-foreground leading-relaxed border-l-2 border-primary/40 pl-3">
              <span className="text-primary/70">// </span>{currentStrategy.description}
            </p>
          </div>
        )}
      </header>

      {error && (
        <div className="bg-danger/10 border border-danger/40 p-4 rounded-md text-danger flex items-center gap-3 animate-slide-up">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <div>
            <p className="font-mono font-bold uppercase tracking-wider text-sm">Backtest Error</p>
            <p className="font-mono text-sm opacity-90">{error}</p>
          </div>
        </div>
      )}

      {!data && !loading && !error && (
        <div className="flex flex-col items-center justify-center py-32 bg-card border border-border border-dashed rounded-lg gradient-border relative">
          <div className="grid place-items-center w-16 h-16 rounded-md border border-border-strong bg-muted/40 mb-5">
            <BarChart3 className="w-7 h-7 text-primary/60" />
          </div>
          <h2 className="font-mono text-lg font-bold uppercase tracking-wider text-foreground">Awaiting Input</h2>
          <p className="font-mono text-sm text-muted-foreground mt-1 cursor-blink">
            Configure parameters &amp; execute backtest
          </p>
        </div>
      )}

      {data && (
        <div className="space-y-6 animate-slide-up">
          {/* Hero stats */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <HeroCard
              title="Net P&L"
              value={fmtCurrency(data.metrics.net_profit, 0)}
              icon={Wallet}
              tone={data.metrics.net_profit >= 0 ? "success" : "danger"}
              hint={`${data.metrics.total_return >= 0 ? "+" : ""}${fmtPct(data.metrics.total_return)} return`}
            />
            <HeroCard
              title="Final Capital"
              value={fmtCurrency(data.metrics.final_value, 0)}
              icon={CircleDollarSign}
              tone="primary"
              hint={`from ${fmtCurrency(data.metrics.initial_capital ?? config.initial_capital, 0)}`}
            />
            <HeroCard
              title="Win Rate"
              value={fmtPct(data.metrics.win_rate, 1)}
              icon={Target}
              tone="success"
              hint={`${data.metrics.total_trades} trades`}
            />
            <HeroCard
              title="Max Drawdown"
              value={fmtPct(data.metrics.max_drawdown)}
              icon={TrendingDown}
              tone="danger"
              hint={`Sharpe ${(data.metrics.sharpe_ratio ?? 0).toFixed(2)}`}
            />
          </div>

          {/* Sub stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MiniStat label="Sharpe Ratio" value={(data.metrics.sharpe_ratio ?? 0).toFixed(2)} icon={Activity} />
            <MiniStat label="Total Trades" value={data.metrics.total_trades} icon={ListOrdered} />
            <MiniStat label="Brokerage Paid" value={fmtCurrency(data.metrics.fees_paid, 2)} icon={Percent} tone="danger" />
            <MiniStat label="Symbols Traded" value={breakdown.length} icon={LayoutGrid} />
          </div>

          {/* Tabs */}
          <div className="border-b border-border flex gap-1">
            {([
              { id: "overview", label: "Overview", icon: BarChart3 },
              { id: "symbols", label: "Per Symbol", icon: LayoutGrid },
              { id: "trades", label: `All Trades (${trades.length})`, icon: ListOrdered },
            ] as const).map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-5 py-3 font-mono text-xs font-semibold uppercase tracking-[0.12em] border-b-2 -mb-px transition-all ${
                  activeTab === tab.id
                    ? "border-primary text-primary text-glow"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === "overview" && (
            <div className="space-y-6">
              {/* Trading chart with symbol selector */}
              <div className="bg-card border border-border p-6 rounded-lg shadow-panel">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                  <h3 className="font-mono text-sm font-bold uppercase tracking-wider flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-primary" />
                    Strategy Execution
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {config.symbols.map((sym) => (
                      <button
                        key={sym}
                        onClick={() => setChartSymbol(sym)}
                        className={`px-3 py-1.5 rounded-md font-mono text-xs font-bold uppercase tracking-wider border transition-all ${
                          chartSymbol === sym
                            ? "bg-primary text-primary-foreground border-primary shadow-glow"
                            : "bg-muted/50 border-border-strong text-muted-foreground hover:text-primary hover:border-primary/50"
                        }`}
                      >
                        {sym}
                      </button>
                    ))}
                  </div>
                </div>
                <TradingChart data={chartCandles} markers={chartMarkers} />
              </div>

              {/* Combined equity curve (per-symbol) */}
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                <div className="xl:col-span-2 bg-card border border-border p-6 rounded-lg shadow-panel">
                  <h3 className="font-mono text-sm font-bold uppercase tracking-wider mb-4 flex items-center gap-2"><Activity className="w-4 h-4 text-primary" />Equity Curve · Per Symbol</h3>
                  <div className="h-[320px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={equityCombinedData}>
                        <CartesianGrid strokeDasharray="2 4" stroke="#1c1c1f" vertical={false} />
                        <XAxis dataKey="date" stroke="#71716f" fontSize={11} tickLine={false} axisLine={false} minTickGap={40} fontFamily="var(--font-mono)" />
                        <YAxis stroke="#71716f" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `₹${Math.round(v / 1000)}k`} fontFamily="var(--font-mono)" />
                        <Tooltip
                          contentStyle={{ backgroundColor: "#0a0a0b", border: "1px solid #2c2c30", borderRadius: "2px", fontFamily: "var(--font-mono)", fontSize: "12px" }}
                          labelStyle={{ color: "#71716f" }}
                          itemStyle={{ color: "#e9e7e0" }}
                          cursor={{ stroke: "#ffb000", strokeOpacity: 0.3 }}
                          formatter={(v: number) => fmtCurrency(v, 0)}
                        />
                        <Legend wrapperStyle={{ paddingTop: "10px" }} />
                        {Object.keys(data.charts.per_symbol_equity || {}).map((sym, i) => (
                          <Line
                            key={sym}
                            type="monotone"
                            dataKey={sym}
                            stroke={PALETTE[i % PALETTE.length]}
                            strokeWidth={2}
                            dot={false}
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="bg-card border border-border p-6 rounded-lg shadow-panel">
                  <h3 className="font-mono text-sm font-bold uppercase tracking-wider mb-4 flex items-center gap-2"><TrendingDown className="w-4 h-4 text-danger" />Drawdown Profile</h3>
                  <div className="h-[320px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={data.charts.drawdown}>
                        <defs>
                          <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#ff4d4d" stopOpacity={0.35} />
                            <stop offset="100%" stopColor="#ff4d4d" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="2 4" stroke="#1c1c1f" vertical={false} />
                        <XAxis dataKey="date" stroke="#71716f" fontSize={11} tickLine={false} axisLine={false} minTickGap={40} fontFamily="var(--font-mono)" />
                        <YAxis stroke="#71716f" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `${v.toFixed(1)}%`} fontFamily="var(--font-mono)" />
                        <Tooltip
                          contentStyle={{ backgroundColor: "#0a0a0b", border: "1px solid #2c2c30", borderRadius: "2px", fontFamily: "var(--font-mono)", fontSize: "12px" }}
                          labelStyle={{ color: "#71716f" }}
                          itemStyle={{ color: "#ff4d4d" }}
                          cursor={{ stroke: "#ff4d4d", strokeOpacity: 0.3 }}
                          formatter={(v: number) => `${v.toFixed(2)}%`}
                        />
                        <Area type="monotone" dataKey="value" stroke="#ff4d4d" strokeWidth={1.5} fill="url(#ddFill)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "symbols" && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {breakdown.map((b, i) => (
                  <SymbolCard key={b.symbol} breakdown={b} accent={PALETTE[i % PALETTE.length]} />
                ))}
              </div>
              {breakdown.length === 0 && (
                <p className="text-center text-muted-foreground py-12">No trades executed for any symbol.</p>
              )}
            </div>
          )}

          {activeTab === "trades" && (
            <div className="bg-card border border-border rounded-lg overflow-hidden shadow-panel">
              <div className="p-4 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <h3 className="font-mono text-sm font-bold uppercase tracking-wider flex items-center gap-2"><ListOrdered className="w-4 h-4 text-primary" />All Trades · {filteredTrades.length}</h3>
                <div className="flex flex-wrap gap-2">
                  <select
                    className="bg-muted/50 border border-border-strong rounded-md px-3 py-1.5 text-sm font-mono focus:outline-none focus:border-primary"
                    value={tradesFilter}
                    onChange={(e) => setTradesFilter(e.target.value)}
                  >
                    <option value="ALL">All symbols</option>
                    {Array.from(new Set(trades.map((t) => t.symbol))).map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                  <div className="flex bg-muted/50 border border-border-strong rounded-md overflow-hidden">
                    {(["all", "wins", "losses", "open"] as const).map((f) => (
                      <button
                        key={f}
                        onClick={() => setTradesPnLFilter(f)}
                        className={`px-3 py-1.5 font-mono text-xs font-semibold uppercase tracking-wider transition-all ${
                          tradesPnLFilter === f ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <div className="overflow-x-auto custom-scrollbar">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40 sticky top-0">
                    <tr className="text-left text-muted-foreground border-b border-border-strong font-mono text-[10px] uppercase tracking-[0.12em]">
                      <th className="py-3 px-4 font-semibold">#</th>
                      <th className="py-3 px-4 font-semibold">Symbol</th>
                      <th className="py-3 px-4 font-semibold">Entry Date</th>
                      <th className="py-3 px-4 font-semibold">Exit Date</th>
                      <th className="py-3 px-4 font-semibold text-right">Entry ₹</th>
                      <th className="py-3 px-4 font-semibold text-right">Exit ₹</th>
                      <th className="py-3 px-4 font-semibold text-right">Qty</th>
                      <th className="py-3 px-4 font-semibold text-right">Trade Amount</th>
                      <th className="py-3 px-4 font-semibold text-right">P&L</th>
                      <th className="py-3 px-4 font-semibold text-right">Return</th>
                      <th className="py-3 px-4 font-semibold text-right">Fees</th>
                      <th className="py-3 px-4 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTrades.map((t, i) => {
                      const isOpen = t.status.toLowerCase() === "open";
                      const profitable = t.profit_loss >= 0;
                      return (
                        <tr key={i} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                          <td className="py-3 px-4 text-muted-foreground">{i + 1}</td>
                          <td className="py-3 px-4 font-semibold">{t.symbol}</td>
                          <td className="py-3 px-4 text-muted-foreground">{t.entry_date ?? "—"}</td>
                          <td className="py-3 px-4 text-muted-foreground">{t.exit_date ?? "—"}</td>
                          <td className="py-3 px-4 text-right">{t.entry_price !== null ? t.entry_price.toFixed(2) : "—"}</td>
                          <td className="py-3 px-4 text-right">{t.exit_price !== null ? t.exit_price.toFixed(2) : "—"}</td>
                          <td className="py-3 px-4 text-right">{t.quantity.toFixed(2)}</td>
                          <td className="py-3 px-4 text-right font-medium">{fmtCurrency(t.trade_amount, 2)}</td>
                          <td className={`py-3 px-4 text-right font-semibold ${profitable ? "text-success" : "text-danger"}`}>
                            {profitable ? "+" : ""}{fmtCurrency(t.profit_loss, 2)}
                          </td>
                          <td className={`py-3 px-4 text-right ${profitable ? "text-success" : "text-danger"}`}>
                            <span className="inline-flex items-center gap-1">
                              {profitable ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                              {fmtPct(t.return_pct, 2)}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right text-muted-foreground">{fmtCurrency(t.fees, 2)}</td>
                          <td className="py-3 px-4">
                            <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                              isOpen
                                ? "bg-warning/20 text-warning"
                                : profitable
                                ? "bg-success/20 text-success"
                                : "bg-danger/20 text-danger"
                            }`}>
                              {isOpen ? "Open" : profitable ? "Win" : "Loss"}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {filteredTrades.length === 0 && (
                  <p className="text-center text-muted-foreground py-12">No trades match the filter.</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SymbolMultiSelect({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const triggerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        triggerRef.current && !triggerRef.current.contains(e.target as Node) &&
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleOpen = () => {
    if (!open && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setPos({
        top: rect.bottom + window.scrollY + 4,
        left: rect.left + window.scrollX,
        width: rect.width,
      });
    }
    setOpen((o) => !o);
  };

  const toggle = (sym: string) => {
    onChange(value.includes(sym) ? value.filter((s) => s !== sym) : [...value, sym]);
  };

  const filtered = NSE_STOCKS.filter((s) => s.includes(search.toUpperCase()));

  const dropdown = open && pos ? (
    <div
      ref={dropdownRef}
      style={{ position: "absolute", top: pos.top, left: pos.left, width: Math.max(pos.width, 256), zIndex: 9999 }}
      className="bg-card border border-border rounded-lg shadow-2xl overflow-hidden"
    >
      <div className="p-2 border-b border-border">
        <input
          type="text"
          placeholder="Search NSE stocks…"
          className="w-full bg-background border border-border rounded px-2 py-1 text-xs focus:outline-none focus:border-primary"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onClick={(e) => e.stopPropagation()}
          autoFocus
        />
      </div>
      {value.length > 0 && (
        <div className="px-2 pt-1.5 pb-1 border-b border-border flex items-center justify-between">
          <span className="text-xs text-muted-foreground">{value.length} selected</span>
          <button
            className="text-xs text-danger hover:underline"
            onClick={(e) => { e.stopPropagation(); onChange([]); setOpen(false); }}
          >
            Clear all
          </button>
        </div>
      )}
      <div className="max-h-52 overflow-y-auto p-1 custom-scrollbar">
        {filtered.length === 0 && (
          <p className="text-center text-xs text-muted-foreground py-3">No matches</p>
        )}
        {filtered.map((sym) => (
          <label
            key={sym}
            className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted cursor-pointer text-sm select-none"
          >
            <input
              type="checkbox"
              checked={value.includes(sym)}
              onChange={() => toggle(sym)}
              className="accent-primary w-3.5 h-3.5"
            />
            <span>{sym}</span>
          </label>
        ))}
      </div>
    </div>
  ) : null;

  return (
    <div ref={triggerRef}>
      <div
        className="bg-background border border-border rounded-lg px-2.5 py-1.5 text-sm cursor-pointer min-h-[38px] flex flex-wrap gap-1 items-center hover:border-primary/60 transition-colors"
        onClick={handleOpen}
      >
        {value.length === 0 && (
          <span className="text-muted-foreground text-sm py-0.5">Select symbols…</span>
        )}
        {value.map((sym) => (
          <span
            key={sym}
            className="inline-flex items-center gap-1 bg-primary/15 text-primary text-xs px-2 py-0.5 rounded-full border border-primary/30"
          >
            {sym}
            <button
              onClick={(e) => { e.stopPropagation(); toggle(sym); }}
              className="hover:text-danger leading-none ml-0.5"
            >
              ×
            </button>
          </span>
        ))}
      </div>
      {typeof document !== "undefined" && dropdown && createPortal(dropdown, document.body)}
    </div>
  );
}

function FieldWrapper({ icon, label, children }: { icon?: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-[10px] text-muted-foreground flex items-center gap-1.5 font-mono font-semibold uppercase tracking-[0.18em]">
        {icon}
        {label}
      </label>
      {children}
    </div>
  );
}

function HeroCard({
  title, value, icon: Icon, tone, hint,
}: { title: string; value: string; icon: any; tone: "success" | "danger" | "primary" | "warning"; hint?: string }) {
  const toneMap = {
    success: { bg: "bg-success/10", text: "text-success", border: "border-success/30", glow: "rgba(58,208,122,0.4)" },
    danger: { bg: "bg-danger/10", text: "text-danger", border: "border-danger/30", glow: "rgba(255,77,77,0.4)" },
    primary: { bg: "bg-primary/10", text: "text-primary", border: "border-primary/30", glow: "rgba(255,176,0,0.4)" },
    warning: { bg: "bg-warning/10", text: "text-warning", border: "border-warning/30", glow: "rgba(255,138,61,0.4)" },
  }[tone];

  return (
    <div className={`group bg-card border ${toneMap.border} p-5 rounded-lg relative overflow-hidden shadow-panel hover:bg-card-elevated transition-colors`}>
      <div
        className="absolute -top-10 -right-10 w-28 h-28 rounded-full opacity-20 blur-3xl transition-opacity group-hover:opacity-40"
        style={{ backgroundColor: toneMap.glow }}
      />
      <div className="flex items-start justify-between mb-3 relative">
        <span className="text-[10px] text-muted-foreground font-mono font-semibold uppercase tracking-[0.18em]">{title}</span>
        <div className={`grid place-items-center w-8 h-8 rounded-md border border-border-strong ${toneMap.bg}`}>
          <Icon className={`w-4 h-4 ${toneMap.text}`} />
        </div>
      </div>
      <div className={`font-mono text-[28px] leading-none font-bold tracking-tight ${toneMap.text}`}>{value}</div>
      {hint && <div className="font-mono text-[11px] text-muted-foreground mt-2">{hint}</div>}
    </div>
  );
}

function MiniStat({ label, value, icon: Icon, tone }: { label: string; value: string | number; icon: any; tone?: string }) {
  return (
    <div className="bg-card border border-border p-4 rounded-lg flex items-center gap-3 hover:border-border-strong transition-colors">
      <div className="grid place-items-center w-9 h-9 rounded-md bg-muted border border-border-strong">
        <Icon className={`w-4 h-4 ${tone === "danger" ? "text-danger" : "text-primary/70"}`} />
      </div>
      <div className="min-w-0">
        <div className="text-[10px] text-muted-foreground font-mono uppercase tracking-[0.15em] truncate">{label}</div>
        <div className="font-mono text-lg font-bold">{value}</div>
      </div>
    </div>
  );
}

function SymbolCard({ breakdown: b, accent }: { breakdown: SymbolBreakdown; accent: string }) {
  const profitable = b.total_pnl >= 0;
  return (
    <div className="bg-card border border-border rounded-lg p-5 hover:border-primary/40 hover:bg-card-elevated transition-all relative overflow-hidden shadow-panel">
      <div className="absolute top-0 left-0 w-full h-px" style={{ backgroundColor: accent, boxShadow: `0 0 12px ${accent}` }} />
      <div className="flex items-center justify-between mb-4">
        <h4 className="font-mono text-base font-bold tracking-wide flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: accent }} />
          {b.symbol}
        </h4>
        <div className={`font-mono text-lg font-bold ${profitable ? "text-success" : "text-danger"}`}>
          {profitable ? "+" : ""}{fmtCurrency(b.total_pnl, 0)}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <Stat label="Trades" value={b.total_trades} />
        <Stat label="Win Rate" value={fmtPct(b.win_rate, 1)} tone={b.win_rate >= 50 ? "success" : "danger"} />
        <Stat label="Wins / Losses" value={`${b.winning_trades} / ${b.losing_trades}`} />
        <Stat label="Open" value={b.open_trades} />
        <Stat label="Best" value={fmtCurrency(b.best_trade, 0)} tone="success" />
        <Stat label="Worst" value={fmtCurrency(b.worst_trade, 0)} tone="danger" />
        <Stat label="Avg P&L / Trade" value={fmtCurrency(b.avg_pnl_per_trade, 0)} />
        <Stat label="Fees Paid" value={fmtCurrency(b.fees_paid, 0)} />
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: "success" | "danger" }) {
  const toneClass = tone === "success" ? "text-success" : tone === "danger" ? "text-danger" : "text-foreground";
  return (
    <div className="space-y-1">
      <div className="text-[10px] text-muted-foreground font-mono uppercase tracking-[0.12em]">{label}</div>
      <div className={`font-mono font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}
