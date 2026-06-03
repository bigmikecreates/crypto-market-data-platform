import type { z } from "zod";
import {
  CandleSchema,
  DatasetMapSchema,
  HealthResponseSchema,
  SummaryItemSchema,
} from "./schemas";

export type Candle = z.infer<typeof CandleSchema>;
export type DatasetMap = z.infer<typeof DatasetMapSchema>;
export type HealthResponse = z.infer<typeof HealthResponseSchema>;
export type SummaryItem = z.infer<typeof SummaryItemSchema>;

export interface CandlesQuery {
  exchange?: string;
  symbol?: string;
  timeframe?: string;
  start?: string;
  end?: string;
  limit?: number;
  order?: "DESC" | "ASC";
}

export interface ApiError {
  status: number;
  message: string;
}
