import { z } from "zod";

export const CandleSchema = z.object({
  exchange: z.string().min(1),
  symbol: z.string().min(1),
  timeframe: z.string().min(1),
  timestamp: z.string().min(1),
  open: z.string(),
  high: z.string(),
  low: z.string(),
  close: z.string(),
  volume: z.string(),
  source: z.string().min(1),
});

export const CandleArraySchema = z.array(CandleSchema);

export const DatasetMapSchema = z.record(z.string(), z.array(z.string()));

export const SummaryItemSchema = z.object({
  type: z.string(),
  exchange: z.string(),
  symbol: z.string(),
  timeframe: z.string().nullable(),
  files: z.number(),
  rows: z.number(),
});

export const SummaryArraySchema = z.array(SummaryItemSchema);

export const FundingRateSchema = z.object({
  exchange: z.string().min(1),
  symbol: z.string().min(1),
  timestamp: z.string().min(1),
  rate: z.string(),
  predicted_rate: z.string(),
  next_funding_time: z.string().min(1),
  source: z.string().min(1),
});

export const FundingRateArraySchema = z.array(FundingRateSchema);

export const HealthResponseSchema = z.object({
  status: z.string(),
});

export const LastFetchSchema = z.object({
  timestamp: z.string().nullable(),
});

export const FetchResponseSchema = z.object({
  count: z.number(),
  data_type: z.string(),
  provider: z.string(),
  symbol: z.string(),
  timeframe: z.string().nullable(),
});
