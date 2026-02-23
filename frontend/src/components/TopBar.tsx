import { RefreshCw, Wifi, WifiOff } from 'lucide-react';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

interface TopBarProps {
  title: string;
  subtitle?: string;
  lastRefreshed?: Date | null;
  onRefresh?: () => void;
  loading?: boolean;
  connected?: boolean;
}

export function TopBar({ title, subtitle, lastRefreshed, onRefresh, loading, connected = true }: TopBarProps) {
  return (
    <div className="flex items-center justify-between px-10 py-6 border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-10">
      <div>
        <h1 className="text-lg font-semibold text-foreground">{title}</h1>
        {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        {/* API Status indicator */}
        <div className={cn(
          'flex items-center gap-2 px-5 py-2 rounded-full text-xs font-medium',
          connected
            ? 'bg-status-online/15 text-status-online border border-status-online/30'
            : 'bg-status-locked/15 text-status-locked border border-status-locked/30'
        )}>
          {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
          {connected ? 'API Conectada' : 'API Desconectada'}
        </div>

        {lastRefreshed && (
          <span className="text-xs text-muted-foreground hidden sm:block">
            Atualizado: {format(lastRefreshed, 'HH:mm:ss', { locale: ptBR })}
          </span>
        )}

        {onRefresh && (
          <button
            onClick={onRefresh}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-secondary text-secondary-foreground hover:bg-muted transition-colors border border-border"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', loading && 'animate-spin')} />
            Refresh
          </button>
        )}
      </div>
    </div>
  );
}
