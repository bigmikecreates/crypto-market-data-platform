import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FundingRateTable from "../FundingRateTable";
import type { FundingRate } from "@/lib/types";

const makeRate = (i: number): FundingRate => ({
  exchange: "fake",
  symbol: "BTC/USDT",
  timestamp: `2025-01-${String(i + 1).padStart(2, "0")}T00:00:00Z`,
  rate: "0.0001",
  predicted_rate: "0.0002",
  next_funding_time: "2025-01-16T00:00:00Z",
  source: "fake",
});

describe("FundingRateTable", () => {
  it("shows empty message when no rates", () => {
    render(<FundingRateTable rates={[]} />);
    expect(screen.getByText("No funding rates returned for this range.")).toBeDefined();
  });

  it("renders rate rows", () => {
    const rates = [makeRate(0), makeRate(1)];
    render(<FundingRateTable rates={rates} />);
    expect(screen.getAllByText("fake")).toHaveLength(2);
    expect(screen.getAllByText("BTC/USDT")).toHaveLength(2);
  });

  it("renders rate and predicted rate values", () => {
    const rates = [makeRate(0)];
    render(<FundingRateTable rates={rates} />);
    const cells = screen.getAllByText("0.0001");
    expect(cells.length).toBeGreaterThanOrEqual(1);
  });
});
