"use client";

import { useCallback, useEffect, useRef } from "react";
import { createChart, ColorType, CrosshairMode, type IChartApi, type ISeriesApi, type CandlestickData, type HistogramData, type Time, type MouseEventParams } from "lightweight-charts";
import type { Candle } from "@/lib/types";
import ErrorBoundary from "./ErrorBoundary";
import { SkeletonChart } from "./Skeleton";

interface Props {
  candles: Candle[];
  loading?: boolean;
}

function formatTooltip(val: string, decimals = 2): string {
  const n = Number(val);
  if (isNaN(n)) return val;
  return n.toFixed(decimals);
}

export default function CandlestickChart({ candles, loading }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const candleMapRef = useRef<Map<string, Candle>>(new Map());

  const handleResize = useCallback(() => {
    if (!containerRef.current || !chartRef.current) return;
    chartRef.current.applyOptions({
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: { time: true, price: true },
        axisDoubleClickReset: true,
      },
      rightPriceScale: {
        borderColor: "#374151",
        scaleMargins: { top: 0.02, bottom: 0.25 },
      },
      timeScale: {
        borderColor: "#374151",
        timeVisible: true,
      },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });

    const series = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      priceFormat: {
        type: "price",
        precision: 2,
        minMove: 0.01,
      },
    });

    chart.subscribeCrosshairMove((param: MouseEventParams) => {
      if (!tooltipRef.current) return;

      if (!param.time || !param.seriesData?.size) {
        tooltipRef.current.style.display = "none";
        return;
      }

      const data = param.seriesData.get(series) as CandlestickData | undefined;
      if (!data || !param.point) {
        tooltipRef.current.style.display = "none";
        return;
      }

      const candle = candleMapRef.current.get(String(data.time));
      const volume = candle ? candle.volume : "—";

      const date = typeof data.time === "number"
        ? new Date(data.time * 1000).toLocaleString()
        : String(data.time);

      const inner = tooltipRef.current;
      inner.innerHTML = `
        <div class="text-gray-300 font-semibold text-xs mb-1">${date}</div>
        <table class="text-xs w-full">
          <tr><td class="text-gray-500 pr-3">Open</td><td class="text-right font-mono">${formatTooltip(String(data.open), 2)}</td></tr>
          <tr><td class="text-gray-500 pr-3">High</td><td class="text-right font-mono text-green-400">${formatTooltip(String(data.high), 2)}</td></tr>
          <tr><td class="text-gray-500 pr-3">Low</td><td class="text-right font-mono text-red-400">${formatTooltip(String(data.low), 2)}</td></tr>
          <tr><td class="text-gray-500 pr-3">Close</td><td class="text-right font-mono">${formatTooltip(String(data.close), 2)}</td></tr>
          <tr><td class="text-gray-500 pr-3">Volume</td><td class="text-right font-mono">${formatTooltip(volume, 2)}</td></tr>
        </table>
      `;

      inner.style.display = "block";

      const parent = containerRef.current!;
      const parentRect = parent.getBoundingClientRect();
      const chartRect = chartRef.current?.chartElement()?.getBoundingClientRect();
      const offsetX = chartRect ? chartRect.left - parentRect.left : 0;
      const offsetY = chartRect ? chartRect.top - parentRect.top : 0;

      let left = param.point.x + 12;
      let top = param.point.y - 10;

      const tooltipWidth = 160;
      if (left + tooltipWidth > parent.clientWidth) {
        left = param.point.x - tooltipWidth - 12;
      }
      if (top < 0) top = 4;

      inner.style.left = `${left + offsetX}px`;
      inner.style.top = `${top + offsetY}px`;
    });

    const volumeSeries = chart.addHistogramSeries({
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    chartRef.current = chart;
    seriesRef.current = series;
    volumeSeriesRef.current = volumeSeries;

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      volumeSeriesRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;

    if (candles.length === 0) {
      seriesRef.current.setData([]);
      volumeSeriesRef.current?.setData([]);
      candleMapRef.current = new Map();
      return;
    }

    const groups = new Map<string, Candle[]>();
    for (const c of candles) {
      const key = `${c.exchange}/${c.symbol}/${c.timeframe}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(c);
    }
    let selected = candles;
    if (groups.size > 1) {
      selected = [...groups.entries()].sort((a, b) => b[1].length - a[1].length)[0][1];
    }

    const toSec = (c: Candle) => Math.floor(new Date(c.timestamp).getTime() / 1000);

    const sorted = [...selected].sort((a, b) => toSec(a) - toSec(b));

    const seen = new Set<number>();
    const deduped: Candle[] = [];
    for (const c of sorted) {
      const t = toSec(c);
      if (!seen.has(t)) {
        seen.add(t);
        deduped.push(c);
      }
    }

    const data: CandlestickData[] = deduped.map((c) => {
      const time = toSec(c) as Time;
      return { time, open: Number(c.open), high: Number(c.high), low: Number(c.low), close: Number(c.close) };
    });

    candleMapRef.current = new Map(deduped.map((c) => {
      const t = String(toSec(c));
      return [t, c] as const;
    }));

    seriesRef.current.setData(data);

    if (volumeSeriesRef.current) {
      const volumeData: HistogramData[] = deduped.map((c) => {
        const time = toSec(c) as Time;
        return {
          time,
          value: Number(c.volume),
          color: "rgba(100, 140, 200, 0.25)",
        };
      });
      volumeSeriesRef.current.setData(volumeData);
    }

    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  return (
    <div className="relative w-full min-h-[400px] h-[60vh]">
      <div ref={containerRef} className="w-full h-full" />
      <div
        ref={tooltipRef}
        className="hidden absolute pointer-events-none z-10 bg-gray-900/95 border border-gray-700 rounded px-3 py-2 shadow-lg"
        style={{ minWidth: 140 }}
      />
      {loading && (
        <div className="absolute inset-0 rounded pointer-events-none">
          <SkeletonChart />
        </div>
      )}
    </div>
  );
}

export function WrappedCandlestickChart(props: { candles: Candle[]; loading?: boolean }) {
  return (
    <ErrorBoundary name="CandlestickChart">
      <CandlestickChart {...props} />
    </ErrorBoundary>
  );
}
