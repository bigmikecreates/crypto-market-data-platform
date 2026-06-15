"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCandles, fetchData, fetchDatasets, fetchFundingRates, fetchLastFetch } from "@/lib/api";
import { WrappedCandlestickChart as CandlestickChart } from "@/components/CandlestickChart";
import CandleTable from "@/components/CandleTable";
import { WrappedFundingRateChart as FundingRateChart } from "@/components/FundingRateChart";
import FundingRateTable from "@/components/FundingRateTable";
import { SkeletonBox, SkeletonText } from "@/components/Skeleton";
import type { CandlesQuery, FetchResponse, FundingRatesQuery } from "@/lib/types";

const DATA_TYPES = [
  { value: "candles", label: "Candles" },
  { value: "funding-rates", label: "Funding Rates" },
];

interface Entry {
  exchange: string;
  symbol: string;
  timeframe: string | null;
}

function parseEntries(datasets: Record<string, string[]> | undefined, type: string): Entry[] {
  if (!datasets) return [];
  const items = datasets[type];
  if (!items) return [];
  return items.map((item) => {
    const parts = item.split("/");
    if (parts.length < 3) return { exchange: item, symbol: "", timeframe: null };
    const exchange = parts[0];
    const symbol = parts[1] + "/" + parts[2];
    let timeframe: string | null = null;
    if (parts.length > 3 && parts[3] !== "funding_rate") {
      timeframe = parts[3];
    }
    return { exchange, symbol, timeframe };
  });
}

function digitDisplay(digits: (string | null)[]): string {
  const n = digits.filter(d => d !== null).length;
  let r = "";
  for (let i = 0; i < 8; i++) {
    if (i === 2 && n > 2) r += "/";
    else if (i === 4 && n > 4) r += "/";
    r += digits[i] ?? "";
  }
  return r;
}

function displayPosToDigitIndex(display: string, pos: number): number | null {
  if (pos >= display.length || display[pos] === "/") return null;
  let digitPos = 0;
  for (let i = 0; i < pos; i++) {
    if (/[0-9]/.test(display[i])) digitPos++;
  }
  return digitPos;
}

const SESSION_KEY = "explorer-state";

export default function ExplorerPage() {
  const [dataType, setDataType] = useState("candles");
  const [exchange, setExchange] = useState("");
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const startRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLInputElement>(null);
  const startDigits = useRef<(string | null)[]>([null, null, null, null, null, null, null, null]);
  const endDigits = useRef<(string | null)[]>([null, null, null, null, null, null, null, null]);
  const [dateError, setDateError] = useState("");
  const [limitInput, setLimitInput] = useState("");
  const [limitAll, setLimitAll] = useState(false);
  const [candleQuery, setCandleQuery] = useState<CandlesQuery | null>(null);
  const [fundingQuery, setFundingQuery] = useState<FundingRatesQuery | null>(null);
  const [fetchLoading, setFetchLoading] = useState(false);
  const [fetchError, setFetchError] = useState<Error | null>(null);
  const [fetchResult, setFetchResult] = useState<FetchResponse | null>(null);
  const queryClient = useQueryClient();

  // Restore full state from sessionStorage after hydration completes.
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(SESSION_KEY);
      if (!saved) return;
      const state = JSON.parse(saved);
      if (state.dataType) setDataType(state.dataType);
      if (state.exchange !== undefined) setExchange(state.exchange);
      if (state.symbol !== undefined) setSymbol(state.symbol);
      if (state.timeframe !== undefined) setTimeframe(state.timeframe);
      if (state.limitInput !== undefined) setLimitInput(state.limitInput);
      if (state.limitAll !== undefined) setLimitAll(state.limitAll);
      if (state.candleQuery) setCandleQuery(state.candleQuery);
      if (state.fundingQuery) setFundingQuery(state.fundingQuery);
      if (state.start) {
        setStart(state.start);
        const raw = state.start.replace(/\//g, "");
        const arr: (string | null)[] = [];
        for (let i = 0; i < 8; i++) arr.push(raw[i] && /[0-9]/.test(raw[i]) ? raw[i] : null);
        startDigits.current = arr;
        if (startRef.current) startRef.current.value = state.start;
      }
      if (state.end) {
        setEnd(state.end);
        const raw = state.end.replace(/\//g, "");
        const arr: (string | null)[] = [];
        for (let i = 0; i < 8; i++) arr.push(raw[i] && /[0-9]/.test(raw[i]) ? raw[i] : null);
        endDigits.current = arr;
        if (endRef.current) endRef.current.value = state.end;
      }
    } catch { /* ignore */ }
  }, []);

  // Persist state to sessionStorage on changes
  useEffect(() => {
    const state = {
      dataType, exchange, symbol, timeframe, start, end,
      limitInput, limitAll, candleQuery, fundingQuery,
    };
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(state));
  }, [dataType, exchange, symbol, timeframe, start, end, limitInput, limitAll, candleQuery, fundingQuery]);

  const { data: datasets, isLoading: datasetsLoading } = useQuery({
    queryKey: ["datasets"],
    queryFn: fetchDatasets,
    staleTime: 30_000,
  });

  const { data: lastFetch } = useQuery({
    queryKey: ["last-fetch"],
    queryFn: fetchLastFetch,
    staleTime: 30_000,
  });

  const candleEntries = useMemo(() => parseEntries(datasets, "candle"), [datasets]);
  const fundingEntries = useMemo(() => parseEntries(datasets, "funding_rate"), [datasets]);
  const currentEntries: Entry[] = dataType === "candles" ? candleEntries : fundingEntries;

  const exchanges = useMemo(
    () => [...new Set(currentEntries.map((e) => e.exchange))].sort(),
    [currentEntries],
  );

  const symbols = useMemo(
    () => [
      ...new Set(
        currentEntries
          .filter((e) => !exchange || e.exchange === exchange)
          .map((e) => e.symbol),
      ),
    ],
    [currentEntries, exchange],
  );

  const timeframes = useMemo(() => {
    if (dataType !== "candles") return [];
    return [
      ...new Set(
        currentEntries
          .filter((e) => (!exchange || e.exchange === exchange) && (!symbol || e.symbol === symbol))
          .map((e) => e.timeframe)
          .filter((t): t is string => t !== null),
      ),
    ];
  }, [currentEntries, exchange, symbol, dataType]);

  useEffect(() => {
    if (exchanges.length > 0 && exchange === "") setExchange(exchanges[0]);
    if (symbols.length > 0 && symbol === "") setSymbol(symbols[0]);
    if (timeframes.length > 0 && timeframe === "") setTimeframe(timeframes[0]);
  }, [exchanges, symbols, timeframes, exchange, symbol, timeframe]);

  useEffect(() => {
    setCandleQuery(null);
  }, [exchange, symbol, timeframe]);

  const dataTypeEntries = datasetsLoading ? "loading" : currentEntries.length;

  const { data: candles, isLoading: candlesLoading, error: candlesError } = useQuery({
    queryKey: ["candles", candleQuery],
    queryFn: () => fetchCandles(candleQuery!),
    enabled: candleQuery !== null && dataType === "candles",
    staleTime: 30_000,
  });

  const { data: fundingRates, isLoading: fundingLoading, error: fundingError } = useQuery({
    queryKey: ["funding-rates", fundingQuery],
    queryFn: () => fetchFundingRates(fundingQuery!),
    enabled: fundingQuery !== null && dataType === "funding-rates",
    staleTime: 30_000,
  });

  const [coverageError, setCoverageError] = useState<string | null>(null);

  useEffect(() => {
    setCoverageError(null);
    if (!candles || candles.length === 0 || !candleQuery) return;
    if (candleQuery.start) {
      const startDate = candleQuery.start.substring(0, 10);
      const firstTs = candles[0].timestamp;
      const firstDate = firstTs.substring(0, 10);
      if (firstDate > startDate) {
        setCoverageError(
          `Returned candle data does not cover the requested start date. ` +
          `Requested start: ${startDate}. First returned candle: ${firstTs}.`,
        );
      }
    }
  }, [candles, candleQuery]);

  function dmyToIso(dmy: string): string | undefined {
    const m = dmy.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    return m ? `${m[3]}-${m[2]}-${m[1]}` : undefined;
  }

  function applyDateEdit(
    el: HTMLInputElement,
    digits: React.MutableRefObject<(string | null)[]>,
    setter: (v: string) => void,
  ) {
    const cursor = el.selectionStart ?? 0;
    const newVal = el.value;
    const oldVal = digitDisplay(digits.current);

    const newDigits = [...digits.current];

    if (newVal.length < oldVal.length) {
      let diff = 0;
      while (diff < newVal.length && newVal[diff] === oldVal[diff]) diff++;
      const deleted = oldVal[diff];
      if (deleted && /[0-9]/.test(deleted)) {
        const di = displayPosToDigitIndex(oldVal, diff);
        if (di !== null && di < 8) newDigits[di] = null;
      }
    } else if (newVal.length > oldVal.length) {
      if (newVal.length - oldVal.length > 1) {
        // Paste / bulk insert — extract all digits into mask
        for (let dp = 0; dp < newVal.length; dp++) {
          const c = newVal[dp];
          if (/[0-9]/.test(c)) {
            const di = displayPosToDigitIndex(newVal, dp);
            if (di !== null && di < 8) newDigits[di] = c;
          }
        }
      } else {
        // Single character insertion
        let diff = 0;
        while (diff < oldVal.length && newVal[diff] === oldVal[diff]) diff++;
        const inserted = newVal[diff];
        if (inserted && /[0-9]/.test(inserted)) {
          const di = displayPosToDigitIndex(newVal, diff);
          if (di !== null && di < 8) newDigits[di] = inserted;
        }
      }
    } else {
      for (let dp = 0; dp < newVal.length; dp++) {
        const c = newVal[dp];
        if (/[0-9]/.test(c)) {
          const di = displayPosToDigitIndex(newVal, dp);
          if (di !== null) newDigits[di] = c;
        }
      }
    }

    const formatted = digitDisplay(newDigits);
    digits.current = newDigits;
    setter(formatted);

    if (newVal !== formatted) {
      el.value = formatted;
      let digitsBefore = 0;
      for (let i = 0; i < cursor && i < newVal.length; i++) {
        if (/[0-9]/.test(newVal[i])) digitsBefore++;
      }
      let nc = 0, found = 0;
      for (let i = 0; i < formatted.length && found < digitsBefore; i++) {
        if (/[0-9]/.test(formatted[i])) found++;
        nc = i + 1;
      }
      if (found < digitsBefore) nc = formatted.length;
      el.setSelectionRange(nc, nc);
    }
  }

  const runQuery = useCallback(
    (isoStart?: string, isoEnd?: string) => {
      const limit = limitAll ? 10000 : (limitInput === "" ? 1000 : Number(limitInput));
      if (dataType === "candles") {
        setCandleQuery({
          exchange: exchange || undefined,
          symbol: symbol || undefined,
          timeframe: timeframe || undefined,
          start: isoStart,
          end: isoEnd,
          limit,
          order: "ASC",
        });
      } else {
        setFundingQuery({
          exchange: exchange || undefined,
          symbol: symbol || undefined,
          start: isoStart,
          end: isoEnd,
          limit,
          order: "ASC",
        });
      }
    },
    [dataType, exchange, symbol, timeframe, limitAll, limitInput],
  );

  const parseDates = useCallback(
    (): { isoStart: string | undefined; isoEnd: string | undefined } | null => {
      const isoStart = start ? dmyToIso(start) : undefined;
      const isoEnd = end ? dmyToIso(end) : undefined;
      if (start && !isoStart) { setDateError("Start date is not valid. Use dd/mm/yyyy."); return null; }
      if (end && !isoEnd) { setDateError("End date is not valid. Use dd/mm/yyyy."); return null; }
      if (isoStart && isoEnd && isoStart > isoEnd) { setDateError("Start date must be before or equal to end date."); return null; }
      return { isoStart, isoEnd };
    },
    [start, end],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setDateError("");
    const dates = parseDates();
    if (!dates) return;
    runQuery(dates.isoStart, dates.isoEnd);
  };

  const handleFetch = async () => {
    setDateError("");
    setFetchError(null);
    setFetchResult(null);

    const dates = parseDates();
    if (!dates) return;
    if (!dates.isoStart) { setDateError("Start date is required for fetching."); return; }
    if (!exchange) { setDateError("Provider is required."); return; }
    if (!symbol) { setDateError("Symbol is required."); return; }
    if (dataType === "candles" && !timeframe) { setDateError("Timeframe is required for candles."); return; }

    setFetchLoading(true);
    try {
      const result = await fetchData({
        data_type: dataType === "candles" ? "candles" : "funding-rates",
        provider: exchange,
        symbol,
        timeframe: dataType === "candles" ? timeframe : undefined,
        start: dates.isoStart,
        end: dates.isoEnd,
      });
      setFetchResult(result);
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      queryClient.invalidateQueries({ queryKey: ["last-fetch"] });
      queryClient.invalidateQueries({ queryKey: ["candles"] });
      queryClient.invalidateQueries({ queryKey: ["funding-rates"] });
      runQuery(dates.isoStart, dates.isoEnd);
    } catch (err: unknown) {
      setFetchError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setFetchLoading(false);
    }
  };

  const activeQuery = dataType === "candles" ? candleQuery : fundingQuery;
  const activeError = dataType === "candles" ? candlesError : fundingError;
  const activeLoading = dataType === "candles" ? candlesLoading : fundingLoading;
  const activeData = dataType === "candles" ? candles : fundingRates;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-4 sm:p-6 space-y-6">
      <h1 className="text-2xl font-bold">Market Data Explorer</h1>

      {dataTypeEntries === "loading" && (
        <div className="space-y-4">
          <div className="flex gap-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <SkeletonBox key={i} className="h-8 w-24 rounded" />
            ))}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="space-y-1">
                <SkeletonBox className="h-3 w-12 rounded" />
                <SkeletonBox className="h-9 w-full rounded" />
              </div>
            ))}
          </div>
          <SkeletonText lines={2} />
        </div>
      )}

      {dataTypeEntries === 0 && !datasetsLoading && (
        <div className="rounded border border-gray-700 bg-gray-900/50 p-4 text-sm space-y-2">
          <p className="text-gray-300">
            No previously ingested datasets found. You can still query directly below &mdash; enter provider, symbol, and timeframe manually.
          </p>
          {lastFetch?.timestamp && (
            <p className="text-gray-500 text-xs">
              Data ingested: {new Date(lastFetch.timestamp).toLocaleString()}
            </p>
          )}
        </div>
      )}

      {dataTypeEntries !== "loading" && (
        <>
          {lastFetch?.timestamp && dataTypeEntries > 0 && (
            <p className="text-gray-500 text-xs">
              Data ingested: {new Date(lastFetch.timestamp).toLocaleString()}
            </p>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex gap-2">
              {DATA_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => { setDataType(t.value); }}
                  className={`rounded px-4 py-1.5 text-sm font-medium transition-colors ${
                    dataType === t.value
                      ? "bg-indigo-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:text-gray-200"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Provider</label>
                {exchanges.length > 0 ? (
                  <select
                    value={exchange}
                    onChange={(e) => setExchange(e.target.value)}
                    className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
                  >
                    <option value="" disabled>Select provider</option>
                    {exchanges.map((ex) => (
                      <option key={ex} value={ex}>{ex}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    placeholder="Select provider"
                    value={exchange}
                    onChange={(e) => setExchange(e.target.value)}
                    className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
                  />
                )}
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Symbol</label>
                {symbols.length > 0 ? (
                  <select
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
                  >
                    <option value="" disabled>Select symbol</option>
                    {symbols.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    placeholder="Select symbol"
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
                  />
                )}
              </div>
              {dataType === "candles" && (
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Timeframe</label>
                  {timeframes.length > 0 ? (
                    <select
                      value={timeframe}
                      onChange={(e) => setTimeframe(e.target.value)}
                      className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
                    >
                      <option value="" disabled>Select timeframe</option>
                      {timeframes.map((tf) => (
                        <option key={tf} value={tf}>{tf}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      placeholder="Select timeframe"
                      value={timeframe}
                      onChange={(e) => setTimeframe(e.target.value)}
                      className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
                    />
                  )}
                </div>
              )}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Start</label>
                <input
                  ref={startRef}
                  type="text"
                  inputMode="numeric"
                  placeholder="dd/mm/yyyy"
                  defaultValue=""
                  onChange={(e) => applyDateEdit(e.target, startDigits, setStart)}
                  onBlur={() => {
                    const val = digitDisplay(startDigits.current);
                    if (startRef.current) startRef.current.value = val || "";
                    setStart(val);
                  }}
                  className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">End</label>
                <input
                  ref={endRef}
                  type="text"
                  inputMode="numeric"
                  placeholder="dd/mm/yyyy"
                  defaultValue=""
                  onChange={(e) => applyDateEdit(e.target, endDigits, setEnd)}
                  onBlur={() => {
                    const val = digitDisplay(endDigits.current);
                    if (endRef.current) endRef.current.value = val || "";
                    setEnd(val);
                  }}
                  className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Limit</label>
                <div className="flex gap-2 items-center">
                  <input
                    type="text"
                    inputMode="numeric"
                    value={limitInput}
                    placeholder="empty = 1000"
                    onChange={(e) => setLimitInput(e.target.value.replace(/[^0-9]/g, ""))}
                    className="w-full rounded bg-gray-800 border border-gray-700 px-2 py-2 text-sm"
                  />
                  <label className="flex items-center gap-1 text-xs text-gray-400 whitespace-nowrap cursor-pointer">
                    <input
                      type="checkbox"
                      checked={limitAll}
                      onChange={(e) => setLimitAll(e.target.checked)}
                      className="accent-indigo-500"
                    />
                    All
                  </label>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <button
                  type="button"
                  disabled={fetchLoading}
                  onClick={handleFetch}
                  className="w-full rounded bg-teal-700 px-4 py-2 text-sm font-semibold hover:bg-teal-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {fetchLoading ? "Fetching..." : "Fetch from API"}
                </button>
                <button
                  type="submit"
                  className="w-full rounded bg-indigo-600 px-4 py-2 text-sm font-semibold hover:bg-indigo-500 transition-colors"
                >
                  Query stored
                </button>
              </div>
            </div>
          </form>

          {dateError && (
            <div className="rounded bg-red-900/50 border border-red-700 p-3 text-sm text-red-200">
              {dateError}
            </div>
          )}

          {fetchError && (
            <div className="rounded bg-red-900/50 border border-red-700 p-3 text-sm text-red-200">
              {fetchError.message}
            </div>
          )}

          {coverageError && (
            <div className="rounded bg-red-900/50 border border-red-700 p-3 text-sm text-red-200">
              {coverageError}
            </div>
          )}

          {activeError && (
            <div className="rounded bg-red-900/50 border border-red-700 p-3 text-sm text-red-200">
              {(activeError as Error).message}
            </div>
          )}

          {fetchResult && (
            <div className="rounded border border-teal-700 bg-teal-900/30 p-3 text-sm text-teal-200">
              Fetched <strong>{fetchResult.count.toLocaleString()}</strong> {fetchResult.data_type === "candles" ? "candle(s)" : "funding rate(s)"}
              {" "}from <strong>{fetchResult.provider}</strong> / <strong>{fetchResult.symbol}</strong>
              {fetchResult.timeframe && <> / <strong>{fetchResult.timeframe}</strong></>}.
            </div>
          )}

          {!activeQuery && !activeError && (
            <p className="text-gray-500 text-sm text-center py-12">
              Enter filters and click Query to load data.
            </p>
          )}

          {activeQuery && activeData && activeData.length === 0 && !activeLoading && !activeError && !coverageError && (
            <div className="rounded border border-gray-700 bg-gray-900/50 p-4 text-sm">
              <p className="text-gray-400">
                No rows returned. The available datasets may not match the selected filters, or the
                date range may be outside the stored data.
              </p>
              {lastFetch?.timestamp && (
                <p className="text-gray-500 text-xs mt-1">
                  Data ingested: {new Date(lastFetch.timestamp).toLocaleString()}
                </p>
              )}
            </div>
          )}

          {activeQuery && dataType === "candles" && !coverageError && (
            <div className="space-y-4">
              {candles && candles.length > 0 && candleQuery && (
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400 px-1">
                  <span><span className="text-gray-500">Provider:</span> {candleQuery.exchange || "—"}</span>
                  <span><span className="text-gray-500">Symbol:</span> {candleQuery.symbol || "—"}</span>
                  {candleQuery.timeframe && <span><span className="text-gray-500">Timeframe:</span> {candleQuery.timeframe}</span>}
                  {candleQuery.start && <span><span className="text-gray-500">Start:</span> {candleQuery.start}</span>}
                  {candleQuery.end && <span><span className="text-gray-500">End:</span> {candleQuery.end}</span>}
                  <span><span className="text-gray-500">Candles:</span> {candles.length}</span>
                  {(() => {
                    const ts = candles.map(c => new Date(c.timestamp).getTime());
                    const min = new Date(Math.min(...ts)).toLocaleString();
                    const max = new Date(Math.max(...ts)).toLocaleString();
                    return <span><span className="text-gray-500">Data:</span> {min} — {max}</span>;
                  })()}
                </div>
              )}
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-2">
                <CandlestickChart candles={candles ?? []} loading={activeLoading} />
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-2">
                <CandleTable candles={candles ?? []} />
              </div>
            </div>
          )}

          {activeQuery && dataType === "funding-rates" && !coverageError && (
            <div className="space-y-4">
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-2">
                <FundingRateChart rates={fundingRates ?? []} loading={activeLoading} />
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-2">
                <FundingRateTable rates={fundingRates ?? []} />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
