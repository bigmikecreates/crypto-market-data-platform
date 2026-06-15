"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDatasets } from "@/lib/api";
import { SkeletonBox, SkeletonText } from "@/components/Skeleton";

export default function DatasetsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["datasets"],
    queryFn: fetchDatasets,
    staleTime: 30_000,
  });

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-4 sm:p-6 space-y-6">
      <h1 className="text-2xl font-bold">Available Datasets</h1>

      {isLoading && (
        <div className="space-y-4">
          <SkeletonText lines={1} className="w-48" />
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonBox key={i} className="h-10 w-full rounded" />
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="rounded bg-red-900/50 border border-red-700 p-3 text-sm text-red-200">
          {(error as Error).message}
        </div>
      )}

      {data && Object.keys(data).length === 0 && (
        <p className="text-gray-500 text-sm">No datasets found. Run <code className="text-indigo-400">crmd fetch</code> to ingest some data first.</p>
      )}

      {data && Object.keys(data).length > 0 && (
        <div className="grid gap-6">
          {(Object.entries(data) as [string, string[]][]).map(([type, items]) => (
            <section key={type}>
              <h2 className="text-lg font-semibold capitalize mb-2">{type.replace("_", " ")}</h2>
              {items.length === 0 ? (
                <p className="text-gray-500 text-sm">No {type} datasets.</p>
              ) : (
                <div className="grid gap-2">
                  {items.map((item) => (
                    <div
                      key={item}
                      className="rounded border border-gray-800 bg-gray-900/50 px-4 py-2 text-sm font-mono"
                    >
                      {item}
                    </div>
                  ))}
                </div>
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
