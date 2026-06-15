import { describe, it, expect } from "vitest";
import { CandleSchema, CandleArraySchema, FundingRateSchema, DatasetMapSchema, FetchResponseSchema, LastFetchSchema, HealthResponseSchema } from "../schemas";

describe("CandleSchema", () => {
  it("accepts a valid candle", () => {
    const candle = {
      exchange: "fake",
      symbol: "BTC/USDT",
      timeframe: "1h",
      timestamp: "2025-01-15T00:00:00Z",
      open: "50000",
      high: "51000",
      low: "49000",
      close: "50500",
      volume: "100.5",
      source: "fake",
    };
    expect(() => CandleSchema.parse(candle)).not.toThrow();
  });

  it("rejects missing required fields", () => {
    const invalid = { exchange: "fake" };
    expect(() => CandleSchema.parse(invalid)).toThrow();
  });

  it("rejects empty string fields", () => {
    const candle = {
      exchange: "",
      symbol: "BTC/USDT",
      timeframe: "1h",
      timestamp: "2025-01-15T00:00:00Z",
      open: "50000",
      high: "51000",
      low: "49000",
      close: "50500",
      volume: "100.5",
      source: "fake",
    };
    expect(() => CandleSchema.parse(candle)).toThrow();
  });
});

describe("CandleArraySchema", () => {
  it("accepts an array of valid candles", () => {
    const candles = [
      {
        exchange: "fake", symbol: "BTC/USDT", timeframe: "1h",
        timestamp: "2025-01-15T00:00:00Z", open: "50000", high: "51000",
        low: "49000", close: "50500", volume: "100.5", source: "fake",
      },
    ];
    expect(() => CandleArraySchema.parse(candles)).not.toThrow();
  });

  it("rejects a non-array", () => {
    expect(() => CandleArraySchema.parse("not-array")).toThrow();
  });

  it("accepts an empty array", () => {
    expect(() => CandleArraySchema.parse([])).not.toThrow();
  });
});

describe("FundingRateSchema", () => {
  it("accepts a valid funding rate", () => {
    const rate = {
      exchange: "fake",
      symbol: "BTC/USDT",
      timestamp: "2025-01-15T00:00:00Z",
      rate: "0.0001",
      predicted_rate: "0.0002",
      next_funding_time: "2025-01-16T00:00:00Z",
      source: "fake",
    };
    expect(() => FundingRateSchema.parse(rate)).not.toThrow();
  });
});

describe("DatasetMapSchema", () => {
  it("accepts a valid dataset map", () => {
    const map = { candle: ["fake/BTC/USDT/1h"], funding_rate: [] };
    expect(() => DatasetMapSchema.parse(map)).not.toThrow();
  });
});

describe("FetchResponseSchema", () => {
  it("accepts a valid fetch response", () => {
    const resp = { count: 100, data_type: "candles", provider: "fake", symbol: "BTC/USDT", timeframe: "1h" };
    expect(() => FetchResponseSchema.parse(resp)).not.toThrow();
  });
});

describe("LastFetchSchema", () => {
  it("accepts null timestamp", () => {
    expect(() => LastFetchSchema.parse({ timestamp: null })).not.toThrow();
  });

  it("accepts a string timestamp", () => {
    expect(() => LastFetchSchema.parse({ timestamp: "2025-01-15T00:00:00Z" })).not.toThrow();
  });
});

describe("HealthResponseSchema", () => {
  it("accepts a valid health response", () => {
    expect(() => HealthResponseSchema.parse({ status: "ok" })).not.toThrow();
  });
});
