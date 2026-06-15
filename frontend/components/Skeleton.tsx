interface SkeletonBoxProps {
  className?: string;
}

export function SkeletonBox({ className = "" }: SkeletonBoxProps) {
  return (
    <div
      className={`animate-pulse rounded bg-gray-800 ${className}`}
    />
  );
}

interface SkeletonTextProps {
  lines?: number;
  className?: string;
}

export function SkeletonText({ lines = 1, className = "" }: SkeletonTextProps) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse rounded bg-gray-800 h-3"
          style={{ width: `${80 - i * 15}%` }}
        />
      ))}
    </div>
  );
}

export function SkeletonChart() {
  return (
    <div className="w-full min-h-[400px] h-[60vh] flex items-center justify-center">
      <SkeletonBox className="w-full h-full rounded" />
    </div>
  );
}

export function SkeletonTableRow({ cols = 9 }: { cols?: number }) {
  return (
    <div className="flex gap-3 px-3 py-2">
      {Array.from({ length: cols }).map((_, i) => (
        <SkeletonBox
          key={i}
          className="h-3 flex-1"
        />
      ))}
    </div>
  );
}

interface SkeletonTableProps {
  rows?: number;
  cols?: number;
}

export function SkeletonTable({ rows = 5, cols = 9 }: SkeletonTableProps) {
  return (
    <div className="space-y-1">
      <SkeletonTableRow cols={cols} />
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonTableRow key={i} cols={cols} />
      ))}
    </div>
  );
}
