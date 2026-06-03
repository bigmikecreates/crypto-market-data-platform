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

export const HealthResponseSchema = z.object({
  status: z.string(),
});
