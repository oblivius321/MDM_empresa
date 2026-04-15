import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDevices } from '@/hooks/useDevices';
import { useMDMWebSocket } from '@/hooks/useMDMWebSocket';
import { useToast } from '@/hooks/use-toast';
import { TopBar } from '@/components/TopBar';
import { StatusBadge } from '@/components/StatusBadge';
import { EnrollmentModal } from '@/components/EnrollmentModal';
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Filter,
  AlertCircle,
  Eye,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  Loader2,
  Infinity,
  CheckCircle2,
  Plus,
  QrCode,
  RefreshCw,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { cn } from '@/lib/utils';
import { androidManagementService, ComplianceStatus } from '@/services/api';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

const STATUS_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'online', label: 'Online' },
  { value: 'offline', label: 'Offline' },
  { value: 'locked', label: 'Bloqueado' },
  { value: 'syncing', label: 'Sincronizando' },
];

function ComplianceIndicator({ status }: { status: ComplianceStatus }) {
  const configs: Record<ComplianceStatus, { icon: any, color: string, label: string }> = {
    compliant: { icon: ShieldCheck, color: 'text-status-online', label: 'Em Conformidade' },
    enforcing: { icon: Loader2, color: 'text-status-syncing animate-spin', label: 'Aplicando Políticas...' },
    enforcing_partial: { icon: Shield, color: 'text-amber-500', label: 'Conformidade Parcial' },
    failed_loop: { icon: ShieldAlert, color: 'text-status-locked animate-pulse', label: 'LOOP DE FALHA: Intervenção Humana Necessária' },
    unknown: { icon: ShieldOff, color: 'text-muted-foreground', label: 'Status Desconhecido' },
  };

  const { icon: Icon, color, label } = configs[status] || configs.unknown;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={cn("flex items-center gap-2 px-2 py-1 rounded-md bg-secondary/50 border border-border/50 cursor-help group transition-all hover:border-primary/30", color)}>
            <Icon className="w-3.5 h-3.5" />
            <span className="text-[10px] font-bold uppercase tracking-tight">{status === 'enforcing' ? 'Enforcing' : status.replace('_', ' ')}</span>
          </div>
        </TooltipTrigger>
        <TooltipContent className="bg-popover border-border shadow-xl">
          <p className="text-xs font-bold">{label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export default function Devices() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [searchInput, setSearchInput] = useState('');
  const [enrollmentOpen, setEnrollmentOpen] = useState(false);
  const [syncLoading, setSyncLoading] = useState(false);
  const {
    devices,
    loading,
    error,
    total,
    page,
    pageSize,
    setPage,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    refresh,
    lastRefreshed,
  } = useDevices({ autoRefresh: true });

  useMDMWebSocket(refresh);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  const handleStatusFilter = (status: string) => {
    setStatusFilter(status);
    setPage(1);
  };

  const handleSyncDevices = async () => {
    setSyncLoading(true);
    try {
      const res = await androidManagementService.syncDevices();
      await refresh();
      toast({
        title: 'Sincronização concluída',
        description: res.data.length
          ? `${res.data.length} dispositivo(s) sincronizado(s) via Android Enterprise.`
          : 'Nenhum dispositivo sincronizado ainda',
      });
    } catch (err: any) {
      toast({
        title: 'Erro ao sincronizar',
        description: err.response?.data?.detail || err.message || 'Falha ao buscar dispositivos no Google.',
        variant: 'destructive',
      });
    } finally {
      setSyncLoading(false);
    }
  };

  return (
    <div className="animate-fade-in">
      <TopBar
        title="Dispositivos"
        subtitle={`${total} dispositivos registrados`}
        lastRefreshed={lastRefreshed}
        onRefresh={refresh}
        loading={loading}
        connected={!error}
      />

      <div className="p-6 space-y-4">
        {/* Botão Novo Dispositivo */}
        <div className="flex items-center justify-between">
          <div />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSyncDevices}
              disabled={syncLoading}
              className="flex items-center gap-2 px-4 py-2.5 text-sm font-bold border border-border bg-secondary text-foreground rounded-lg hover:bg-muted transition-all disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <RefreshCw className={cn("w-4 h-4", syncLoading && "animate-spin")} />
              Sincronizar dispositivos
            </button>
            <button
              id="new-device-button"
              onClick={() => setEnrollmentOpen(true)}
              className="flex items-center gap-2 px-4 py-2.5 text-sm font-bold bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-all shadow-lg shadow-primary/20"
            >
              <QrCode className="w-4 h-4" />
              Novo Dispositivo
            </button>
          </div>
        </div>
        {error && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-md bg-status-locked/10 border border-status-locked/30 text-status-locked text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <form onSubmit={handleSearch} className="flex items-center gap-2 flex-1 min-w-[200px] max-w-sm">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Buscar por nome, IMEI, empresa..."
                className="w-full pl-9 pr-3 py-2 text-sm bg-secondary border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-colors"
              />
            </div>
            <button
              type="submit"
              className="px-3 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
            >
              Buscar
            </button>
          </form>

          <div className="flex items-center gap-1 bg-secondary border border-border rounded-md p-1">
            <Filter className="w-3.5 h-3.5 text-muted-foreground ml-1.5" />
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={`filter-status-${opt.value || 'all'}`}
                onClick={() => handleStatusFilter(opt.value)}
                className={cn(
                  'px-3 py-1 text-xs font-medium rounded transition-colors',
                  statusFilter === opt.value
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="card-glass overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  {['Nome', 'Modelo', 'Android', 'Status', 'Compliance', 'Última atividade', 'Ações'].map((h) => (
                    <th key={`header-${h}`} className="px-5 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={`row-skel-${i}`} className="border-b border-border/50">
                      {Array.from({ length: 7 }).map((_, j) => (
                        <td key={`cell-skel-${i}-${j}`} className="px-5 py-3">
                          <div className="h-4 rounded skeleton-shimmer" style={{ width: `${60 + Math.random() * 40}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : devices.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-5 py-12 text-center text-muted-foreground text-sm">
                      {error ? 'Erro ao carregar dispositivos.' : 'Nenhum dispositivo sincronizado ainda'}
                    </td>
                  </tr>
                ) : devices.map((device, idx) => (
                  <tr
                    key={`device-${device.id}`}
                    className="border-b border-border/50 hover:bg-muted/20 transition-colors cursor-pointer"
                    style={{ animationDelay: `${idx * 30}ms` }}
                    onClick={() => navigate(`/devices/${device.id}`)}
                  >
                    <td className="px-5 py-3">
                      <div className="flex flex-col">
                        <span className="text-sm font-bold text-foreground">{device.name}</span>
                        <span className="text-[10px] text-muted-foreground font-mono">{device.imei}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <span className="text-sm text-muted-foreground">{device.model || '—'}</span>
                    </td>
                    <td className="px-5 py-3">
                      <span className="text-sm text-muted-foreground">{device.android_version ? `Android ${device.android_version}` : '—'}</span>
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={device.status} />
                    </td>
                    <td className="px-5 py-3">
                      <ComplianceIndicator status={device.compliance_status || 'unknown'} />
                    </td>
                    <td className="px-5 py-3">
                      <span className="text-xs text-muted-foreground">
                        {device.last_seen
                          ? format(parseISO(device.last_seen), "dd/MM 'às' HH:mm", { locale: ptBR })
                          : '—'}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <button
                        onClick={(e) => { e.stopPropagation(); navigate(`/devices/${device.id}`); }}
                        className="flex items-center gap-1.5 text-xs font-bold text-primary hover:text-primary/80 transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        Detalhes
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between px-5 py-3 border-t border-border bg-muted/20">
            <p className="text-xs text-muted-foreground">
              {devices.length > 0
                ? `Exibindo ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} de ${total}`
                : '0 resultados'}
            </p>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-md hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-4 h-4 text-muted-foreground" />
              </button>
              {Array.from({ length: Math.min(5, totalPages) }).map((_, i) => {
                const pageNum = i + 1;
                return (
                  <button
                    key={`page-${pageNum}`}
                    onClick={() => setPage(pageNum)}
                    className={cn(
                      'w-7 h-7 rounded-md text-xs font-medium transition-colors',
                      page === pageNum
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    {pageNum}
                  </button>
                );
              })}
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1.5 rounded-md hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Enrollment Modal */}
      <EnrollmentModal isOpen={enrollmentOpen} onClose={() => setEnrollmentOpen(false)} />
    </div>
  );
}
