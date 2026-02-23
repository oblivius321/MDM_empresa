import { cn } from '@/lib/utils';
import { DeviceStatus } from '@/services/api';

interface StatusBadgeProps {
  status: DeviceStatus | string;
  showDot?: boolean;
  className?: string;
}

const statusConfig: Record<string, { label: string; classes: string; dotClass: string }> = {
  online: {
    label: 'Online',
    classes: 'badge-online',
    dotClass: 'bg-status-online',
  },
  offline: {
    label: 'Offline',
    classes: 'badge-offline',
    dotClass: 'bg-status-offline',
  },
  locked: {
    label: 'Bloqueado',
    classes: 'badge-locked',
    dotClass: 'bg-status-locked',
  },
  syncing: {
    label: 'Sincronizando',
    classes: 'badge-syncing',
    dotClass: 'bg-status-syncing',
  },
};

export function StatusBadge({ status, showDot = true, className }: StatusBadgeProps) {
  const config = statusConfig[status] || {
    label: status,
    classes: 'badge-offline',
    dotClass: 'bg-muted-foreground',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
        config.classes,
        className
      )}
    >
      {showDot && (
        <span
          className={cn(
            'w-1.5 h-1.5 rounded-full flex-shrink-0',
            config.dotClass,
            status === 'online' && 'pulse-dot online'
          )}
        />
      )}
      {config.label}
    </span>
  );
}
