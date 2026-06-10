import type { z } from "zod";
import {
  CandleSchema,
  DatasetMapSchema,
  FetchResponseSchema,
  FundingRateSchema,
  HealthResponseSchema,
  LastFetchSchema,
  SummaryItemSchema,
} from "./schemas";

export type Candle = z.infer<typeof CandleSchema>;
export type DatasetMap = z.infer<typeof DatasetMapSchema>;
export type FetchResponse = z.infer<typeof FetchResponseSchema>;
export type FundingRate = z.infer<typeof FundingRateSchema>;
export type HealthResponse = z.infer<typeof HealthResponseSchema>;
export type LastFetch = z.infer<typeof LastFetchSchema>;
export type SummaryItem = z.infer<typeof SummaryItemSchema>;

export interface FetchRequest {
  data_type: "candles" | "funding-rates";
  provider: string;
  symbol: string;
  timeframe?: string;
  start: string;
  end?: string;
}

export interface CandlesQuery {
  exchange?: string;
  symbol?: string;
  timeframe?: string;
  start?: string;
  end?: string;
  limit?: number;
  order?: "DESC" | "ASC";
}

export interface FundingRatesQuery {
  exchange?: string;
  symbol?: string;
  start?: string;
  end?: string;
  limit?: number;
  order?: "DESC" | "ASC";
}

export interface ApiError {
  status: number;
  message: string;
}
