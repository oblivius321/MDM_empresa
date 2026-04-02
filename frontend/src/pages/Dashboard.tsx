import { useDashboard } from '@/hooks/useDashboard';
import { useDevices } from '@/hooks/useDevices';
import { TopBar } from '@/components/TopBar';
import { StatusBadge } from '@/components/StatusBadge';
import { Smartphone, Wifi, WifiOff, Lock, Clock, TrendingUp, AlertCircle } from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid } from 'recharts';
import { format, parseISO } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { Link } from 'react-router-dom';

function SkeletonCard() {
  return (
    <div className="metric-card animate-pulse">
      <div className="h-3 bg-muted rounded w-2/3 mb-3 skeleton-shimmer" />
      <div className="h-8 bg-muted rounded w-1/2 skeleton-shimmer" />
    </div>
  );
}

const CHART_COLORS = {
  online: 'hsl(142, 71%, 45%)',
  offline: 'hsl(215, 16%, 40%)',
  locked: 'hsl(0, 72%, 51%)',
  syncing: 'hsl(38, 92%, 50%)',
};

export default function Dashboard() {
  const { summary, loading, error, refresh, lastRefreshed } = useDashboard();
  const { devices, loading: devLoading } = useDevices({ autoRefresh: true });

  const pieData = summary ? [
    { name: 'Online', value: summary.online, color: CHART_COLORS.online },
    { name: 'Offline', value: summary.offline, color: CHART_COLORS.offline },
    { name: 'Bloqueados', value: summary.locked, color: CHART_COLORS.locked },
  ].filter(d => d.value > 0) : [];

  // Build recent checkins timeline from devices
  const recentCheckins = devices
    .filter(d => d.last_checkin)
    .sort((a, b) => (b.last_checkin > a.last_checkin ? 1 : -1))
    .slice(0, 5);

  const metricCards = [
    {
      title: 'Total de Dispositivos',
      value: summary?.total ?? '—',
      icon: Smartphone,
      color: 'text-primary',
      bg: 'bg-primary/10',
      border: 'border-primary/20',
    },
    {
      title: 'Online',
      value: summary?.online ?? '—',
      icon: Wifi,
      color: 'text-status-online',
      bg: 'bg-status-online/10',
      border: 'border-status-online/20',
    },
    {
      title: 'Offline',
      value: summary?.offline ?? '—',
      icon: WifiOff,
      color: 'text-muted-foreground',
      bg: 'bg-muted/50',
      border: 'border-border',
    },
    {
      title: 'Bloqueados',
      value: summary?.locked ?? '—',
      icon: Lock,
      color: 'text-status-locked',
      bg: 'bg-status-locked/10',
      border: 'border-status-locked/20',
    },
  ];

  return (
    <div className="animate-fade-in">
      <TopBar
        title="Dashboard"
        subtitle="Visão geral da frota de dispositivos"
        lastRefreshed={lastRefreshed}
        onRefresh={refresh}
        loading={loading}
        connected={!error}
      />

      <div className="p-6 space-y-6">
        {/* Error */}
        {error && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-md bg-status-locked/10 border border-status-locked/30 text-status-locked text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error} — Exibindo dados de demonstração</span>
          </div>
        )}

        {/* Metric Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={`skeleton-metric-${i}`} />)
            : metricCards.map((card) => (
                <div key={`card-${card.title}`} className={`metric-card border ${card.border}`}>
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-medium text-muted-foreground">{card.title}</p>
                    <div className={`w-8 h-8 rounded-md ${card.bg} flex items-center justify-center`}>
                      <card.icon className={`w-4 h-4 ${card.color}`} />
                    </div>
                  </div>
                  <p className={`text-3xl font-bold tracking-tight ${card.color}`}>{card.value}</p>
                  {summary && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {((Number(card.value) / summary.total) * 100).toFixed(0)}% do total
                    </p>
                  )}
                </div>
              ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Pie Chart */}
          <div className="card-glass p-5">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">Distribuição de Status</h3>
            </div>
            {loading ? (
              <div className="h-48 flex items-center justify-center">
                <div className="w-32 h-32 rounded-full skeleton-shimmer" />
              </div>
            ) : pieData.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={75}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={index} fill={entry.color} stroke="transparent" />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: 'hsl(220, 14%, 10%)',
                        border: '1px solid hsl(220, 13%, 17%)',
                        borderRadius: '6px',
                        color: 'hsl(210, 30%, 92%)',
                        fontSize: '12px',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-wrap gap-3 mt-2">
                  {pieData.map((entry) => (
                    <div key={`legend-${entry.name}`} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <div className="w-2 h-2 rounded-full" style={{ background: entry.color }} />
                      {entry.name}: <span className="text-foreground font-medium">{entry.value}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="h-48 flex items-center justify-center text-muted-foreground text-sm">
                Sem dados disponíveis
              </div>
            )}
          </div>

          {/* Last Check-in */}
          <div className="card-glass p-5">
            <div className="flex items-center gap-2 mb-4">
              <Clock className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">Último Check-in Global</h3>
            </div>
            {summary?.last_global_checkin ? (
              <div className="space-y-2">
                <p className="text-2xl font-bold text-foreground">
                  {format(parseISO(summary.last_global_checkin), 'HH:mm', { locale: ptBR })}
                </p>
                <p className="text-sm text-muted-foreground">
                  {format(parseISO(summary.last_global_checkin), "dd 'de' MMMM, yyyy", { locale: ptBR })}
                </p>
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">Nenhum check-in registrado</p>
            )}

            <div className="mt-4 pt-4 border-t border-border">
              <p className="text-xs font-medium text-muted-foreground mb-2">Dispositivos Recentes</p>
              <div className="space-y-2">
                {devLoading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <div key={`recent-skel-${i}`} className="h-8 rounded skeleton-shimmer" />
                  ))
                ) : recentCheckins.slice(0, 3).map((device) => (
                  <div key={`recent-${device.id}`} className="flex items-center justify-between text-xs">
                    <span className="text-foreground truncate max-w-[120px]">{device.name}</span>
                    <StatusBadge status={device.status} showDot={false} />
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="card-glass p-5">
            <div className="flex items-center gap-2 mb-4">
              <Smartphone className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">Saúde da Frota</h3>
            </div>
            {summary && (
              <div className="space-y-4">
                {[
                  { label: 'Taxa Online', value: summary.total > 0 ? (summary.online / summary.total) * 100 : 0, color: 'bg-status-online' },
                  { label: 'Taxa Offline', value: summary.total > 0 ? (summary.offline / summary.total) * 100 : 0, color: 'bg-muted-foreground' },
                  { label: 'Taxa Bloqueados', value: summary.total > 0 ? (summary.locked / summary.total) * 100 : 0, color: 'bg-status-locked' },
                ].map((stat) => (
                  <div key={`stat-${stat.label}`}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-muted-foreground">{stat.label}</span>
                      <span className="text-foreground font-medium">{stat.value.toFixed(1)}%</span>
                    </div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ${stat.color}`}
                        style={{ width: `${stat.value}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
            <Link
              to="/devices"
              className="mt-5 flex items-center justify-center w-full px-3 py-2 rounded-md bg-primary/10 text-primary border border-primary/20 text-xs font-medium hover:bg-primary/20 transition-colors"
            >
              Ver Todos os Dispositivos →
            </Link>
          </div>
        </div>

        {/* Recent Devices Table */}
        <div className="card-glass overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground">Dispositivos Recentes</h3>
            <Link to="/devices" className="text-xs text-primary hover:underline">Ver todos →</Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  {['Nome', 'IMEI', 'Empresa', 'Status', 'Último Check-in'].map((h) => (
                    <th key={h} className="px-5 py-3 text-left text-xs font-medium text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {devLoading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <tr key={`table-skel-row-${i}`} className="border-b border-border/50">
                      {Array.from({ length: 5 }).map((_, j) => (
                        <td key={`table-skel-cell-${i}-${j}`} className="px-5 py-3">
                          <div className="h-4 rounded skeleton-shimmer" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : devices.slice(0, 5).map((device) => (
                  <tr key={device.id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                    <td className="px-5 py-3 text-sm font-medium text-foreground">{device.name}</td>
                    <td className="px-5 py-3 text-xs text-muted-foreground font-mono">{device.imei}</td>
                    <td className="px-5 py-3 text-sm text-muted-foreground">{device.company || '—'}</td>
                    <td className="px-5 py-3"><StatusBadge status={device.status} /></td>
                    <td className="px-5 py-3 text-xs text-muted-foreground">
                      {device.last_checkin
                        ? format(parseISO(device.last_checkin), 'dd/MM/yy HH:mm')
                        : '—'}
                    </td>
                  </tr>
                ))}
                {!devLoading && devices.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-5 py-8 text-center text-muted-foreground text-sm">
                      Nenhum dispositivo encontrado. Verifique a conexão com a API.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
