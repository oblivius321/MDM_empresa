import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDevices } from '@/hooks/useDevices';
import { TopBar } from '@/components/TopBar';
import { StatusBadge } from '@/components/StatusBadge';
import { Search, ChevronLeft, ChevronRight, Filter, AlertCircle, Eye } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { cn } from '@/lib/utils';

const STATUS_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'online', label: 'Online' },
  { value: 'offline', label: 'Offline' },
  { value: 'locked', label: 'Bloqueado' },
  { value: 'syncing', label: 'Sincronizando' },
];

export default function Devices() {
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState('');
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
        {/* Error */}
        {error && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-md bg-status-locked/10 border border-status-locked/30 text-status-locked text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
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

          {/* Status Filter */}
          <div className="flex items-center gap-1 bg-secondary border border-border rounded-md p-1">
            <Filter className="w-3.5 h-3.5 text-muted-foreground ml-1.5" />
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
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

        {/* Table */}
        <div className="card-glass overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  {['Nome', 'IMEI', 'Modelo', 'Android', 'Empresa', 'Status', 'Último Check-in', ''].map((h) => (
                    <th key={h} className="px-5 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-border/50">
                      {Array.from({ length: 8 }).map((_, j) => (
                        <td key={j} className="px-5 py-3">
                          <div className="h-4 rounded skeleton-shimmer" style={{ width: `${60 + Math.random() * 40}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : devices.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-5 py-12 text-center text-muted-foreground text-sm">
                      {error ? 'Erro ao carregar dispositivos.' : 'Nenhum dispositivo encontrado.'}
                    </td>
                  </tr>
                ) : devices.map((device, idx) => (
                  <tr
                    key={device.id}
                    className="border-b border-border/50 hover:bg-muted/20 transition-colors cursor-pointer"
                    style={{ animationDelay: `${idx * 30}ms` }}
                    onClick={() => navigate(`/devices/${device.id}`)}
                  >
                    <td className="px-5 py-3">
                      <span className="text-sm font-medium text-foreground">{device.name}</span>
                    </td>
                    <td className="px-5 py-3">
                      <span className="text-xs text-muted-foreground font-mono">{device.imei}</span>
                    </td>
                    <td className="px-5 py-3">
                      <span className="text-sm text-muted-foreground">{device.model || '—'}</span>
                    </td>
                    <td className="px-5 py-3">
                      <span className="text-sm text-muted-foreground">{device.android_version ? `Android ${device.android_version}` : '—'}</span>
                    </td>
                    <td className="px-5 py-3">
                      <span className="text-sm text-muted-foreground">{device.company || '—'}</span>
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={device.status} />
                    </td>
                    <td className="px-5 py-3">
                      <span className="text-xs text-muted-foreground">
                        {device.last_checkin
                          ? format(parseISO(device.last_checkin), "dd/MM/yy 'às' HH:mm", { locale: ptBR })
                          : '—'}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <button
                        onClick={(e) => { e.stopPropagation(); navigate(`/devices/${device.id}`); }}
                        className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
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

          {/* Pagination */}
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
                    key={pageNum}
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
    </div>
  );
}
