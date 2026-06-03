"use client";

import Link from "next/link";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col items-center justify-center p-6">
      <div className="max-w-lg text-center space-y-6">
        <h1 className="text-3xl font-bold tracking-tight">
          CrMD Web Console
        </h1>
        <p className="text-gray-400">
          Query, inspect, and visualise crypto market data from your local
          CrMD Platform backend.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
          <Link
            href="/explorer"
            className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
          >
            Market Data Explorer
          </Link>
          <Link
            href="/datasets"
            className="inline-flex items-center justify-center rounded-lg border border-gray-700 px-6 py-3 text-sm font-semibold text-gray-200 hover:bg-gray-800 transition-colors"
          >
            Browse Datasets
          </Link>
        </div>
      </div>
    </div>
  );
}
