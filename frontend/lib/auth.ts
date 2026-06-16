const API_KEY = "crmd_api_key";
const BASE_URL_KEY = "crmd_api_base_url";

function getItem(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function setItem(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // localStorage unavailable (private browsing, etc.)
  }
}

function removeItem(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // noop
  }
}

export function getApiKey(): string | null {
  return getItem(API_KEY);
}

export function setApiKey(key: string): void {
  setItem(API_KEY, key);
}

export function clearApiKey(): void {
  removeItem(API_KEY);
}

export function getApiBaseUrl(): string | null {
  return getItem(BASE_URL_KEY);
}

export function setApiBaseUrl(url: string): void {
  setItem(BASE_URL_KEY, url);
}

export function clearApiBaseUrl(): void {
  removeItem(BASE_URL_KEY);
}
