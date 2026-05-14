interface LoadingSkeletonProps {
  lines?: number;
  className?: string;
}

export default function LoadingSkeleton({ lines = 5, className = '' }: LoadingSkeletonProps) {
  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-4 bg-gray-800 animate-pulse rounded"
          style={{ width: `${60 + Math.random() * 40}%` }}
        />
      ))}
    </div>
  );
}
