import type { Candle } from "@/lib/types";

interface Props {
  candles: Candle[];
}

export default function CandleTable({ candles }: Props) {
  if (candles.length === 0) {
    return (
      <p className="text-gray-400 text-sm py-4 text-center">
        No candles returned for this range.
      </p>
    );
  }

  return (
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
          {candles.map((c, i) => (
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
  );
}
