"use client";

import Link from "next/link";
import { useState, useRef, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import "./globals.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function ApiKeyInput() {
  const { apiKey, setApiKey, clearKey, isKeySet } = useAuth();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(apiKey ?? "");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    setDraft(apiKey ?? "");
  }, [apiKey]);

  const handleSave = () => {
    const trimmed = draft.trim();
    if (trimmed) {
      setApiKey(trimmed);
    } else {
      clearKey();
    }
    setOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSave();
    if (e.key === "Escape") setOpen(false);
  };

  return (
    <div className="relative ml-auto">
      <button
        onClick={() => setOpen(!open)}
        className={`text-xs px-2 py-1 rounded border transition-colors ${
          isKeySet
            ? "border-green-700 text-green-400 bg-green-950/40"
            : "border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-600"
        }`}
        title={isKeySet ? "API key is set" : "Set API key"}
      >
        {isKeySet ? "Key" : "No Key"}
      </button>
      {open && (
        <div className="absolute right-0 top-8 z-50 flex items-center gap-2 bg-gray-900 border border-gray-700 rounded px-3 py-2 shadow-xl">
          <input
            ref={inputRef}
            type="password"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter API key..."
            className="w-48 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-indigo-500"
          />
          <button
            onClick={handleSave}
            className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white rounded px-2 py-1 transition-colors"
          >
            Save
          </button>
          {isKeySet && (
            <button
              onClick={() => { clearKey(); setOpen(false); }}
              className="text-xs text-gray-500 hover:text-red-400 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function NavBar() {
  const pathname = usePathname();

  const links = [
    { href: "/", label: "Home" },
    { href: "/explorer", label: "Explorer" },
    { href: "/datasets", label: "Datasets" },
  ];

  return (
    <nav className="flex items-center gap-4 px-4 sm:px-6 h-12 border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm">
      <span className="text-sm font-semibold text-indigo-400 mr-4">CrMD</span>
      {links.map((link) => {
        const isActive = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`text-sm transition-colors ${isActive ? "text-gray-100" : "text-gray-500 hover:text-gray-300"}`}
          >
            {link.label}
          </Link>
        );
      })}
      <ApiKeyInput />
    </nav>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <NavBar />
            <main>{children}</main>
          </AuthProvider>
        </QueryClientProvider>
      </body>
    </html>
  );
}
