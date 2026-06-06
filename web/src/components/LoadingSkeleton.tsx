// 这个组件提供页面加载时的浅色骨架占位。

interface LoadingSkeletonProps {
  lines?: number;
  className?: string;
}

const SKELETON_WIDTHS = [88, 74, 96, 82, 68, 90, 78, 84];

export default function LoadingSkeleton({ lines = 5, className = '' }: LoadingSkeletonProps) {
  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-4 animate-pulse rounded bg-slate-200"
          style={{ width: `${SKELETON_WIDTHS[i % SKELETON_WIDTHS.length]}%` }}
        />
      ))}
    </div>
  );
}
