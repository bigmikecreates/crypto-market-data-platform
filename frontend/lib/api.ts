import {
  CandleArraySchema,
  DatasetMapSchema,
  HealthResponseSchema,
  SummaryArraySchema,
} from "./schemas";
import type { ApiError, CandlesQuery, Candle, DatasetMap, HealthResponse, SummaryItem } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8050";

class ApiRequestError extends Error implements ApiError {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiRequestError";
  }
}

async function request<T>(path: string, schema: { parse: (data: unknown) => T }, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiRequestError(res.status, body.detail ?? body.message ?? res.statusText);
  }

  const json: unknown = await res.json();
  return schema.parse(json);
}

export async function fetchHealth(): Promise<HealthResponse> {
  return request("/health", HealthResponseSchema);
}

export async function fetchDatasets(): Promise<DatasetMap> {
  return request("/datasets", DatasetMapSchema);
}

export async function fetchCandles(query: CandlesQuery): Promise<Candle[]> {
  const params = new URLSearchParams();
  if (query.exchange) params.set("exchange", query.exchange);
  if (query.symbol) params.set("symbol", query.symbol);
  if (query.timeframe) params.set("timeframe", query.timeframe);
  if (query.start) params.set("start", query.start);
  if (query.end) params.set("end", query.end);
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  if (query.order) params.set("order", query.order);

  const qs = params.toString();
  return request(`/candles${qs ? `?${qs}` : ""}`, CandleArraySchema);
}

export async function fetchSummary(): Promise<SummaryItem[]> {
  return request("/summary", SummaryArraySchema);
}

export { ApiRequestError };
