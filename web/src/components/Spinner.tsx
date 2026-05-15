interface SpinnerProps {
  size?: 'sm' | 'md';
  className?: string;
}

export default function Spinner({ size = 'sm', className = '' }: SpinnerProps) {
  const sizeClass = size === 'sm' ? 'w-3.5 h-3.5 border-2' : 'w-5 h-5 border-[3px]';
  return (
    <span
      className={`inline-block rounded-full border-gray-500 border-t-cyan-400 animate-spin ${sizeClass} ${className}`}
      role="status"
      aria-label="加载中"
    />
  );
}
