import type { FundingRate } from "@/lib/types";

interface Props {
  rates: FundingRate[];
}

export default function FundingRateTable({ rates }: Props) {
  if (rates.length === 0) {
    return (
      <p className="text-gray-400 text-sm py-4 text-center">
        No funding rates returned for this range.
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
            <th className="px-3 py-2">Timestamp</th>
            <th className="px-3 py-2 text-right">Rate</th>
            <th className="px-3 py-2 text-right">Predicted</th>
            <th className="px-3 py-2">Next Funding</th>
          </tr>
        </thead>
        <tbody>
          {rates.map((r, i) => (
            <tr
              key={`${r.exchange}-${r.symbol}-${r.timestamp}-${i}`}
              className="border-b border-gray-800 hover:bg-gray-800/50"
            >
              <td className="px-3 py-1.5">{r.exchange}</td>
              <td className="px-3 py-1.5">{r.symbol}</td>
              <td className="px-3 py-1.5 font-mono text-xs">{r.timestamp}</td>
              <td className="px-3 py-1.5 text-right font-mono text-xs">{r.rate}</td>
              <td className="px-3 py-1.5 text-right font-mono text-xs">{r.predicted_rate}</td>
              <td className="px-3 py-1.5 font-mono text-xs">{r.next_funding_time}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
