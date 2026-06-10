"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, type IChartApi, type ISeriesApi, type LineData, type Time } from "lightweight-charts";
import type { FundingRate } from "@/lib/types";

interface Props {
  rates: FundingRate[];
  loading?: boolean;
}

export default function FundingRateChart({ rates, loading }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const rateSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const predictedSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

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
        mode: 0 as const,
      },
      rightPriceScale: {
        borderColor: "#374151",
      },
      timeScale: {
        borderColor: "#374151",
        timeVisible: true,
      },
      width: containerRef.current.clientWidth,
      height: 400,
    });

    const rateSeries = chart.addLineSeries({
      color: "#22c55e",
      lineWidth: 2,
      title: "Rate",
    });

    const predictedSeries = chart.addLineSeries({
      color: "#a855f7",
      lineWidth: 2,
      title: "Predicted Rate",
    });

    chartRef.current = chart;
    rateSeriesRef.current = rateSeries;
    predictedSeriesRef.current = predictedSeries;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      rateSeriesRef.current = null;
      predictedSeriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!rateSeriesRef.current || !predictedSeriesRef.current) return;

    if (rates.length === 0) {
      rateSeriesRef.current.setData([]);
      predictedSeriesRef.current.setData([]);
      return;
    }

    const rateData: LineData[] = rates.map((r) => ({
      time: (new Date(r.timestamp).getTime() / 1000) as Time,
      value: Number(r.rate),
    }));

    const predictedData: LineData[] = rates.map((r) => ({
      time: (new Date(r.timestamp).getTime() / 1000) as Time,
      value: Number(r.predicted_rate),
    }));

    rateSeriesRef.current.setData(rateData);
    predictedSeriesRef.current.setData(predictedData);
    chartRef.current?.timeScale().fitContent();
  }, [rates]);

  return (
    <div className="relative">
      <div ref={containerRef} className="w-full" />
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/50 rounded">
          <span className="text-gray-400 text-sm">Loading chart...</span>
        </div>
      )}
    </div>
  );
}
