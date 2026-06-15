import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import CandleTable from "../CandleTable";
import type { Candle } from "@/lib/types";

const makeCandle = (i: number): Candle => ({
  exchange: "fake",
  symbol: "BTC/USDT",
  timeframe: "1h",
  timestamp: `2025-01-${String(i + 1).padStart(2, "0")}T00:00:00Z`,
  open: "50000",
  high: "51000",
  low: "49000",
  close: "50500",
  volume: "100",
  source: "fake",
});

describe("CandleTable", () => {
  it("shows empty message when no candles", () => {
    render(<CandleTable candles={[]} />);
    expect(screen.getByText("No candles returned for this range.")).toBeDefined();
  });

  it("renders candle rows", () => {
    const candles = [makeCandle(0), makeCandle(1)];
    render(<CandleTable candles={candles} />);
    expect(screen.getAllByText("fake")).toHaveLength(2);
    expect(screen.getAllByText("BTC/USDT")).toHaveLength(2);
  });

  it("shows row count info", () => {
    const candles = [makeCandle(0), makeCandle(1)];
    render(<CandleTable candles={candles} />);
    expect(screen.getByText(/Showing 1–2 of 2 candles/)).toBeDefined();
  });

  it("paginates when more than page size", () => {
    const candles = Array.from({ length: 30 }, (_, i) => makeCandle(i));
    render(<CandleTable candles={candles} />);
    expect(screen.getByText(/Showing 1–25 of 30 candles/)).toBeDefined();
  });
});
