import { describe, it, expect, beforeEach, vi } from "vitest";
import { fetchHealth, fetchDatasets, ApiRequestError } from "../api";
import { setApiKey, clearApiKey } from "../auth";

beforeEach(() => {
  localStorage.removeItem("crmd_api_key");
  vi.restoreAllMocks();
});

function mockFetch(status: number, body: unknown) {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    statusText: status === 404 ? "Not Found" : "OK",
  });
}

describe("fetchHealth", () => {
  it("sends a GET to /health", async () => {
    mockFetch(200, { status: "ok" });
    const result = await fetchHealth();
    expect(result).toEqual({ status: "ok" });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/health"),
      expect.objectContaining({
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
      }),
    );
  });

  it("throws ApiRequestError on non-ok response", async () => {
    mockFetch(500, { detail: "Internal error" });
    await expect(fetchHealth()).rejects.toThrow(ApiRequestError);
  });

  it("throws on network error", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("Network failure"));
    await expect(fetchHealth()).rejects.toThrow("Network failure");
  });
});

describe("X-API-Key header", () => {
  it("omits X-API-Key when no key is set", async () => {
    mockFetch(200, { status: "ok" });
    clearApiKey();
    await fetchHealth();
    const opts = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    expect(opts.headers["X-API-Key"]).toBeUndefined();
  });

  it("includes X-API-Key when a key is set", async () => {
    mockFetch(200, { status: "ok" });
    setApiKey("my-key");
    await fetchHealth();
    const opts = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    expect(opts.headers["X-API-Key"]).toBe("my-key");
  });
});

describe("fetchDatasets", () => {
  it("sends a GET to /datasets", async () => {
    mockFetch(200, { candle: [], funding_rate: [] });
    const result = await fetchDatasets();
    expect(result).toEqual({ candle: [], funding_rate: [] });
  });

  it("throws on Zod schema mismatch", async () => {
    mockFetch(200, { unexpected: true });
    await expect(fetchDatasets()).rejects.toThrow();
  });
});

describe("ApiRequestError", () => {
  it("has status and message properties", () => {
    const err = new ApiRequestError(403, "Forbidden");
    expect(err.status).toBe(403);
    expect(err.message).toBe("Forbidden");
    expect(err.name).toBe("ApiRequestError");
  });
});
