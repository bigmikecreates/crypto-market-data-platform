"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCandles } from "@/lib/api";
import CandlestickChart from "@/components/CandlestickChart";
import CandleTable from "@/components/CandleTable";
import type { CandlesQuery } from "@/lib/types";

const PROVIDERS = ["fake", "bitfinex", "bitstamp", "kucoin", "bybit", "mexc"];
const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"];

export default function ExplorerPage() {
  const [exchange, setExchange] = useState("bitfinex");
  const [symbol, setSymbol] = useState("BTC/USD");
  const [timeframe, setTimeframe] = useState("1h");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [limit, setLimit] = useState(100);
  const [query, setQuery] = useState<CandlesQuery | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["candles", query],
    queryFn: () => fetchCandles(query!),
    enabled: query !== null,
    staleTime: 30_000,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setQuery({ exchange, symbol, timeframe, start: start || undefined, end: end || undefined, limit, order: "ASC" });
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-4 sm:p-6 space-y-6">
      <h1 className="text-2xl font-bold">Market Data Explorer</h1>

      <form onSubmit={handleSubmit} className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
        <div>
          <label className="block text-xs text-gray-400 mb-1">Provider</label>
          <select
            value={exchange}
            onChange={(e) => setExchange(e.target.value)}
            className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
          >
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Symbol</label>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm font-mono"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Timeframe</label>
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
          >
            {TIMEFRAMES.map((tf) => (
              <option key={tf} value={tf}>{tf}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Start</label>
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">End</label>
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Limit</label>
          <input
            type="number"
            min={1}
            max={10000}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
          />
        </div>
        <div className="flex items-end">
          <button
            type="submit"
            className="w-full rounded bg-indigo-600 px-4 py-2 text-sm font-semibold hover:bg-indigo-500 transition-colors"
          >
            Query
          </button>
        </div>
      </form>

      {error && (
        <div className="rounded bg-red-900/50 border border-red-700 p-3 text-sm text-red-200">
          {(error as Error).message}
        </div>
      )}

      {!query && !error && (
        <p className="text-gray-500 text-sm text-center py-12">
          Select filters and click Query to load data.
        </p>
      )}

      {query && (
        <div className="space-y-4">
          <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-2">
            <CandlestickChart candles={data ?? []} loading={isLoading} />
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-2">
            <CandleTable candles={data ?? []} />
          </div>
        </div>
      )}
    </div>
  );
}
