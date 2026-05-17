// Tight CDD-style empty state. Icon + title + sub copy + optional CTA.
import { ReactNode } from 'react';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="text-center py-16">
      {icon && <div className="mx-auto mb-3 text-slate-300">{icon}</div>}
      <p className="text-sm font-medium text-slate-500">{title}</p>
      {description && (
        <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
