"use client";

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { fetchHealth } from "@/lib/api";

export default function SettingsPage() {
  const {
    apiBaseUrl, setApiBaseUrl, clearBaseUrl,
    apiKey, setApiKey, clearKey, isKeySet,
  } = useAuth();
  const queryClient = useQueryClient();

  const [baseUrlDraft, setBaseUrlDraft] = useState(apiBaseUrl ?? "");
  const [apiKeyDraft, setApiKeyDraft] = useState(apiKey ?? "");
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [cacheMsg, setCacheMsg] = useState("");

  const handleBaseUrlSave = useCallback(() => {
    const trimmed = baseUrlDraft.trim();
    if (trimmed) {
      setApiBaseUrl(trimmed);
    } else {
      clearBaseUrl();
    }
    setTestResult(null);
  }, [baseUrlDraft, setApiBaseUrl, clearBaseUrl]);

  const handleApiKeySave = useCallback(() => {
    const trimmed = apiKeyDraft.trim();
    if (trimmed) {
      setApiKey(trimmed);
    } else {
      clearKey();
    }
  }, [apiKeyDraft, setApiKey, clearKey]);

  const handleTestConnection = useCallback(async () => {
    setTestResult(null);
    try {
      const health = await fetchHealth();
      setTestResult({ ok: true, msg: `Connected — server status: ${health.status}` });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setTestResult({ ok: false, msg });
    }
  }, []);

  const handleClearCache = useCallback(() => {
    queryClient.clear();
    setCacheMsg("Query cache cleared.");
    setTimeout(() => setCacheMsg(""), 3000);
  }, [queryClient]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-4 sm:p-6 space-y-8">
      <h1 className="text-2xl font-bold">Settings</h1>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">API Connection</h2>

        <div className="space-y-2">
          <label className="block text-xs text-gray-400">Base URL</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={baseUrlDraft}
              onChange={(e) => setBaseUrlDraft(e.target.value)}
              placeholder="http://localhost:8050"
              className="flex-1 rounded bg-gray-800 border border-gray-700 px-3 py-2 text-sm outline-none focus:border-indigo-500"
            />
            <button
              onClick={handleBaseUrlSave}
              className="rounded bg-indigo-600 hover:bg-indigo-500 px-3 py-2 text-sm font-medium transition-colors"
            >
              Save
            </button>
            {apiBaseUrl && (
              <button
                onClick={() => { clearBaseUrl(); setBaseUrlDraft(""); setTestResult(null); }}
                className="rounded bg-gray-800 hover:bg-gray-700 px-3 py-2 text-sm transition-colors"
              >
                Reset
              </button>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <label className="block text-xs text-gray-400">API Key</label>
          <div className="flex gap-2">
            <input
              type="password"
              value={apiKeyDraft}
              onChange={(e) => setApiKeyDraft(e.target.value)}
              placeholder={isKeySet ? "Key is set — type to replace" : "No key set"}
              className="flex-1 rounded bg-gray-800 border border-gray-700 px-3 py-2 text-sm outline-none focus:border-indigo-500"
            />
            <button
              onClick={handleApiKeySave}
              className="rounded bg-indigo-600 hover:bg-indigo-500 px-3 py-2 text-sm font-medium transition-colors"
            >
              Save
            </button>
            {isKeySet && (
              <button
                onClick={() => { clearKey(); setApiKeyDraft(""); }}
                className="rounded bg-gray-800 hover:bg-gray-700 px-3 py-2 text-sm transition-colors"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleTestConnection}
            className="rounded bg-teal-700 hover:bg-teal-600 px-4 py-2 text-sm font-medium transition-colors"
          >
            Test Connection
          </button>
          {testResult && (
            <span className={`text-sm ${testResult.ok ? "text-green-400" : "text-red-400"}`}>
              {testResult.msg}
            </span>
          )}
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Data</h2>
        <div className="flex items-center gap-3">
          <button
            onClick={handleClearCache}
            className="rounded bg-gray-800 hover:bg-gray-700 px-4 py-2 text-sm font-medium transition-colors"
          >
            Clear Query Cache
          </button>
          {cacheMsg && <span className="text-sm text-gray-400">{cacheMsg}</span>}
        </div>
      </section>
    </div>
  );
}
