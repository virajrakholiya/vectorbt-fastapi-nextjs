"use client";

import { useState, useEffect } from "react";
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area 
} from "recharts";
import {
  TrendingUp, TrendingDown, Wallet, BarChart3, PieChart, Activity, Download, Play, Settings, Calendar, Coins, Tag
} from "lucide-react";
import { TradingChart } from "@/components/TradingChart";

export default function Dashboard() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any>(null);
  const [config, setConfig] = useState({
    strategy_name: "sma_crossover",
    symbols: ["RELIANCE", "TCS", "INFY"],
    start_date: "2023-01-01",
    end_date: "2023-12-31",
    initial_capital: 50000,
    params: { fast_window: 10, slow_window: 50 }
  });

  const runBacktest = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("http://localhost:8000/api/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      
      const result = await res.json();
      
      if (!res.ok) {
        throw new Error(result.detail || "Backtest failed");
      }
      
      setData(result);
    } catch (err: any) {
      console.error("Backtest failed", err);
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const MetricCard = ({ title, value, icon: Icon, color, suffix = "" }: any) => (
    <div className="bg-card border border-border p-4 rounded-xl shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-slate-400 text-sm font-medium">{title}</span>
        <div className={`p-2 rounded-lg bg-opacity-10 ${color.replace('text-', 'bg-')}`}>
          <Icon className={`w-5 h-5 ${color}`} />
        </div>
      </div>
      <div className="text-2xl font-bold">
        {value}
        <span className="text-sm font-normal ml-1">{suffix}</span>
      </div>
    </div>
  );

  return (
    <div className="space-y-6 pb-12">
      {/* Header & Controls */}
      <div className="bg-card border border-border p-6 rounded-2xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">VectorBT Pro</h1>
            <p className="text-slate-400">Indian Market Quantitative Backtesting</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={runBacktest}
              disabled={loading}
              className="flex items-center gap-2 bg-primary hover:bg-blue-600 text-white px-6 py-2 rounded-lg font-semibold transition-all disabled:opacity-50"
            >
              {loading ? <Activity className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              {loading ? "Running..." : "Run Backtest"}
            </button>

            <button className="p-2 border border-border rounded-lg hover:bg-slate-800 transition-colors">
              <Download className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400 flex items-center gap-1.5">
              <Settings className="w-3.5 h-3.5" /> Strategy
            </label>
            <select
              className="bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary cursor-pointer"
              value={config.strategy_name}
              onChange={(e) => setConfig({ ...config, strategy_name: e.target.value })}
            >
              <option value="sma_crossover">SMA Crossover</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400 flex items-center gap-1.5">
              <Tag className="w-3.5 h-3.5" /> Symbols (comma-separated)
            </label>
            <input
              type="text"
              className="bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
              value={config.symbols.join(", ")}
              onChange={(e) =>
                setConfig({
                  ...config,
                  symbols: e.target.value
                    .split(",")
                    .map((s) => s.trim().toUpperCase())
                    .filter(Boolean),
                })
              }
              placeholder="RELIANCE, TCS, INFY"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5" /> Start Date
            </label>
            <input
              type="date"
              className="bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
              value={config.start_date}
              max={config.end_date}
              onChange={(e) => setConfig({ ...config, start_date: e.target.value })}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5" /> End Date
            </label>
            <input
              type="date"
              className="bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
              value={config.end_date}
              min={config.start_date}
              max={new Date().toISOString().split("T")[0]}
              onChange={(e) => setConfig({ ...config, end_date: e.target.value })}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400 flex items-center gap-1.5">
              <Coins className="w-3.5 h-3.5" /> Initial Capital (₹)
            </label>
            <input
              type="number"
              min={1000}
              step={1000}
              className="bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
              value={config.initial_capital}
              onChange={(e) =>
                setConfig({ ...config, initial_capital: Number(e.target.value) || 0 })
              }
            />
          </div>
        </div>
      </div>

      {data && (
        <>
          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard 
              title="Net Profit/Loss" 
              value={`₹${data.metrics.net_profit.toLocaleString(undefined, {maximumFractionDigits: 0})}`} 
              icon={Wallet} 
              color={data.metrics.net_profit >= 0 ? "text-success" : "text-danger"} 
            />
            <MetricCard 
              title="Total Return" 
              value={data.metrics.total_return.toFixed(2)} 
              suffix="%" 
              icon={TrendingUp} 
              color="text-primary" 
            />
            <MetricCard 
              title="Win Rate" 
              value={data.metrics.win_rate.toFixed(1)} 
              suffix="%" 
              icon={PieChart} 
              color="text-success" 
            />
            <MetricCard 
              title="Max Drawdown" 
              value={data.metrics.max_drawdown.toFixed(2)} 
              suffix="%" 
              icon={TrendingDown} 
              color="text-danger" 
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
            <div className="bg-card border border-border p-4 rounded-xl">
               <span className="text-slate-400 text-sm">Sharpe Ratio</span>
               <div className="text-xl font-bold">{data.metrics.sharpe_ratio.toFixed(2)}</div>
            </div>
            <div className="bg-card border border-border p-4 rounded-xl">
               <span className="text-slate-400 text-sm">Total Trades</span>
               <div className="text-xl font-bold">{data.metrics.total_trades}</div>
            </div>
            <div className="bg-card border border-border p-4 rounded-xl">
               <span className="text-slate-400 text-sm">Brokerage Paid</span>
               <div className="text-xl font-bold text-danger">₹{data.metrics.fees_paid.toLocaleString()}</div>
            </div>
            <div className="bg-card border border-border p-4 rounded-xl">
               <span className="text-slate-400 text-sm">Current Capital</span>
               <div className="text-xl font-bold text-success">₹{data.metrics.final_value.toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
            </div>
          </div>

          {/* Main Chart Area */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <div className="xl:col-span-2 space-y-6">
              <div className="bg-card border border-border p-6 rounded-2xl">
                <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-primary" />
                  Strategy Execution (Primary Stock)
                </h3>
                <TradingChart data={data.charts.candlesticks} markers={data.charts.markers} />
              </div>

              <div className="bg-card border border-border p-6 rounded-2xl">
                <h3 className="text-lg font-bold mb-6">Equity Curve</h3>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data.charts.equity_curve}>
                      <defs>
                        <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                      <XAxis dataKey="date" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                      <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => `₹${val/1000}k`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: "8px" }}
                        labelStyle={{ color: "#94a3b8" }}
                      />
                      <Area type="monotone" dataKey="value" stroke="#3b82f6" fillOpacity={1} fill="url(#colorValue)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Side Panel: Trades & Drawdown */}
            <div className="space-y-6">
              <div className="bg-card border border-border p-6 rounded-2xl">
                <h3 className="text-lg font-bold mb-6">Drawdown Profile</h3>
                <div className="h-[200px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data.charts.drawdown}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                      <XAxis dataKey="date" hide />
                      <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: "8px" }}
                      />
                      <Area type="monotone" dataKey="value" stroke="#ef4444" fill="#ef4444" fillOpacity={0.1} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="bg-card border border-border p-4 rounded-2xl max-h-[500px] overflow-hidden flex flex-col">
                <h3 className="text-lg font-bold mb-4 px-2">Recent Trades</h3>
                <div className="overflow-y-auto flex-1 custom-scrollbar">
                  <table className="w-full text-sm text-left">
                    <thead className="text-slate-400 sticky top-0 bg-card">
                      <tr>
                        <th className="pb-2">Stock</th>
                        <th className="pb-2">P&L</th>
                        <th className="pb-2">Qty</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {data.trades.slice().reverse().map((trade: any, i: number) => (
                        <tr key={i} className="group hover:bg-slate-800/50 transition-colors">
                          <td className="py-3 font-medium">{trade.symbol}</td>
                          <td className={`py-3 ${trade.profit_loss >= 0 ? "text-success" : "text-danger"}`}>
                            {trade.profit_loss >= 0 ? "+" : ""}₹{trade.profit_loss.toFixed(2)}
                          </td>
                          <td className="py-3 text-slate-400">{trade.quantity.toFixed(0)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/50 p-4 rounded-xl text-red-500 flex items-center gap-3">
          <Activity className="w-5 h-5" />
          <div>
            <p className="font-bold">Backtest Error</p>
            <p className="text-sm opacity-90">{error}</p>
          </div>
        </div>
      )}

      {!data && !loading && !error && (
        <div className="flex flex-col items-center justify-center py-32 bg-card border border-border rounded-3xl border-dashed">
          <BarChart3 className="w-16 h-16 text-slate-700 mb-4" />
          <h2 className="text-xl font-semibold">No Backtest Data</h2>
          <p className="text-slate-400">Configure your parameters and click "Run Backtest" to see results</p>
        </div>
      )}
    </div>
  );
}
