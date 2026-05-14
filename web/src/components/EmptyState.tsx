interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
}

export default function EmptyState({ icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {icon && <span className="text-4xl mb-3 text-gray-600">{icon}</span>}
      <p className="text-gray-500 font-mono text-sm">{title}</p>
      {description && <p className="text-gray-600 text-xs mt-1 font-mono">{description}</p>}
    </div>
  );
}
