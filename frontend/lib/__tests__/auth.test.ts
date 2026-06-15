import { describe, it, expect, beforeEach } from "vitest";
import { getApiKey, setApiKey, clearApiKey } from "../auth";

beforeEach(() => {
  localStorage.removeItem("crmd_api_key");
});

describe("getApiKey", () => {
  it("returns null when no key is stored", () => {
    expect(getApiKey()).toBeNull();
  });

  it("returns the stored key", () => {
    localStorage.setItem("crmd_api_key", "test-key-123");
    expect(getApiKey()).toBe("test-key-123");
  });
});

describe("setApiKey", () => {
  it("stores the key in localStorage", () => {
    setApiKey("my-secret-key");
    expect(localStorage.getItem("crmd_api_key")).toBe("my-secret-key");
  });

  it("overwrites an existing key", () => {
    setApiKey("first-key");
    setApiKey("second-key");
    expect(getApiKey()).toBe("second-key");
  });
});

describe("clearApiKey", () => {
  it("removes the key from localStorage", () => {
    setApiKey("test-key");
    clearApiKey();
    expect(getApiKey()).toBeNull();
  });
});
