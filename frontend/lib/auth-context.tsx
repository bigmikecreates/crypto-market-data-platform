"use client";

import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { getApiKey, setApiKey as storeApiKey, clearApiKey } from "./auth";

interface AuthContextValue {
  apiKey: string | null;
  setApiKey: (key: string) => void;
  clearKey: () => void;
  isKeySet: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKeyState] = useState<string | null>(null);
  const [init, setInit] = useState(false);

  useEffect(() => {
    setApiKeyState(getApiKey());
    setInit(true);
  }, []);

  const setApiKey = useCallback((key: string) => {
    storeApiKey(key);
    setApiKeyState(key);
  }, []);

  const clearKey = useCallback(() => {
    clearApiKey();
    setApiKeyState(null);
  }, []);

  return (
    <AuthContext.Provider value={{ apiKey, setApiKey, clearKey, isKeySet: apiKey !== null }}>
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
