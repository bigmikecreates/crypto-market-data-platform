"use client";

import { useEffect, useMemo, useState } from "react";
import type { Candle } from "@/lib/types";

const PAGE_SIZES = [25, 50, 100];

interface Props {
  candles: Candle[];
}

export default function CandleTable({ candles }: Props) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const totalPages = Math.max(1, Math.ceil(candles.length / pageSize));

  useEffect(() => {
    setPage(1);
  }, [candles.length]);

  const visible = useMemo(
    () => candles.slice((page - 1) * pageSize, page * pageSize),
    [candles, page, pageSize],
  );

  const from = candles.length === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, candles.length);

  if (candles.length === 0) {
    return (
      <p className="text-gray-400 text-sm py-4 text-center">
        No candles returned for this range.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead>
            <tr className="border-b border-gray-700 text-gray-400 uppercase text-xs">
              <th className="px-3 py-2">Exchange</th>
              <th className="px-3 py-2">Symbol</th>
              <th className="px-3 py-2">TF</th>
              <th className="px-3 py-2">Timestamp</th>
              <th className="px-3 py-2 text-right">Open</th>
              <th className="px-3 py-2 text-right">High</th>
              <th className="px-3 py-2 text-right">Low</th>
              <th className="px-3 py-2 text-right">Close</th>
              <th className="px-3 py-2 text-right">Volume</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((c, i) => (
              <tr
                key={`${c.exchange}-${c.symbol}-${c.timestamp}-${i}`}
                className="border-b border-gray-800 hover:bg-gray-800/50"
              >
                <td className="px-3 py-1.5">{c.exchange}</td>
                <td className="px-3 py-1.5">{c.symbol}</td>
                <td className="px-3 py-1.5">{c.timeframe}</td>
                <td className="px-3 py-1.5 font-mono text-xs">{c.timestamp}</td>
                <td className="px-3 py-1.5 text-right font-mono text-xs">{c.open}</td>
                <td className="px-3 py-1.5 text-right font-mono text-xs text-green-400">{c.high}</td>
                <td className="px-3 py-1.5 text-right font-mono text-xs text-red-400">{c.low}</td>
                <td className="px-3 py-1.5 text-right font-mono text-xs">{c.close}</td>
                <td className="px-3 py-1.5 text-right font-mono text-xs">{c.volume}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-gray-400 px-1">
        <span>
          Showing {from}&ndash;{to} of {candles.length.toLocaleString()} candles
        </span>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1">
            <span className="text-xs">Rows:</span>
            <select
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
              className="rounded bg-gray-800 border border-gray-700 px-1 py-0.5 text-xs"
            >
              {PAGE_SIZES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>

          <div className="flex items-center gap-1">
            <button
              disabled={page <= 1}
              onClick={() => setPage(1)}
              className="rounded px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              First
            </button>
            <button
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
              className="rounded px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              Prev
            </button>
            <span className="px-2 text-xs whitespace-nowrap">
              Page {page} of {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
              className="rounded px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(totalPages)}
              className="rounded px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              Last
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}