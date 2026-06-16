"use client";

import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { getApiKey, setApiKey as storeApiKey, clearApiKey, getApiBaseUrl, setApiBaseUrl as storeBaseUrl, clearApiBaseUrl } from "./auth";

interface AuthContextValue {
  apiKey: string | null;
  setApiKey: (key: string) => void;
  clearKey: () => void;
  isKeySet: boolean;
  apiBaseUrl: string | null;
  setApiBaseUrl: (url: string) => void;
  clearBaseUrl: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKeyState] = useState<string | null>(null);
  const [apiBaseUrl, setBaseUrlState] = useState<string | null>(null);

  useEffect(() => {
    setApiKeyState(getApiKey());
    setBaseUrlState(getApiBaseUrl());
  }, []);

  const setApiKey = useCallback((key: string) => {
    storeApiKey(key);
    setApiKeyState(key);
  }, []);

  const clearKey = useCallback(() => {
    clearApiKey();
    setApiKeyState(null);
  }, []);

  const setApiBaseUrl = useCallback((url: string) => {
    storeBaseUrl(url);
    setBaseUrlState(url);
  }, []);

  const clearBaseUrl = useCallback(() => {
    clearApiBaseUrl();
    setBaseUrlState(null);
  }, []);

  return (
    <AuthContext.Provider value={{
      apiKey, setApiKey, clearKey, isKeySet: apiKey !== null,
      apiBaseUrl, setApiBaseUrl, clearBaseUrl,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
