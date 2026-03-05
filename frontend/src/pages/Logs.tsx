import { useState, useEffect } from 'react';
import { TopBar } from '@/components/TopBar';
import { FileText, Filter, Download, Loader2, AlertCircle, CheckCircle, Info, AlertTriangle, RefreshCw } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { format } from 'date-fns';

interface LogEntry {
  id: string;
  timestamp: string;
  type: 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR';
  message: string;
  device_id?: string;
  user_email?: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  details?: Record<string, any>;
}

const levelConfig = {
  INFO: { color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200', dot: 'bg-blue-600', icon: Info },
  SUCCESS: { color: 'text-green-600', bg: 'bg-green-50 border-green-200', dot: 'bg-green-600', icon: CheckCircle },
  WARNING: { color: 'text-yellow-600', bg: 'bg-yellow-50 border-yellow-200', dot: 'bg-yellow-600', icon: AlertTriangle },
  ERROR: { color: 'text-red-600', bg: 'bg-red-50 border-red-200', dot: 'bg-red-600', icon: AlertCircle },
};

export default function Logs() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState('all');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 25;
  const { toast } = useToast();

  // Mock data
  const mockLogs: LogEntry[] = [
    {
      id: 'log-1',
      timestamp: new Date(Date.now() - 5 * 60000).toISOString(),
      type: 'SUCCESS',
      message: 'Dispositivo registrado com sucesso',
      device_id: 'DEVICE-001',
      severity: 'low',
    },
    {
      id: 'log-2',
      timestamp: new Date(Date.now() - 15 * 60000).toISOString(),
      type: 'INFO',
      message: 'Política aplicada ao dispositivo',
      device_id: 'DEVICE-002',
      severity: 'low',
    },
    {
      id: 'log-3',
      timestamp: new Date(Date.now() - 25 * 60000).toISOString(),
      type: 'WARNING',
      message: 'Dispositivo offline por 30 minutos',
      device_id: 'DEVICE-001',
      severity: 'medium',
    },
    {
      id: 'log-4',
      timestamp: new Date(Date.now() - 1 * 3600000).toISOString(),
      type: 'ERROR',
      message: 'Falha ao executar comando: dispositivo não responde',
      device_id: 'DEVICE-003',
      severity: 'high',
    },
  ];

  useEffect(() => {
    loadLogs();
  }, [page, typeFilter, severityFilter, searchQuery]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      let filtered = mockLogs.filter((log) => {
        if (typeFilter !== 'all' && log.type !== typeFilter) return false;
        if (severityFilter !== 'all' && log.severity !== severityFilter) return false;
        if (searchQuery && !log.message.toLowerCase().includes(searchQuery.toLowerCase()) && !log.device_id?.includes(searchQuery)) return false;
        return true;
      });

      const startIdx = (page - 1) * pageSize;
      setLogs(filtered.slice(startIdx, startIdx + pageSize));
    } catch (error) {
      toast({
        title: 'Erro',
        description: 'Falha ao carregar logs',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleExportLogs = () => {
    const csv = [
      'Timestamp,Type,Severity,Message,Device,User',
      ...mockLogs.map(
        (log) =>
          `"${format(new Date(log.timestamp), 'dd/MM/yyyy HH:mm:ss')}","${log.type}","${log.severity}","${log.message}","${log.device_id || 'N/A'}","${log.user_email || 'N/A'}"`
      ),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs_${format(new Date(), 'yyyy-MM-dd_HHmmss')}.csv`;
    a.click();

    toast({
      title: 'Sucesso',
      description: 'Logs exportados com sucesso',
    });
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'low':
        return 'bg-blue-100 text-blue-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'high':
        return 'bg-orange-100 text-orange-800';
      case 'critical':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="animate-fade-in">
      <TopBar title="Auditoria & Logs" subtitle="Histórico completo de ações e eventos do sistema" />
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2 bg-secondary border border-border rounded-md p-1">
            <Filter className="w-3.5 h-3.5 text-muted-foreground ml-1.5" />
            {[{ label: 'Todos', val: 'all' }, { label: 'Info', val: 'INFO' }, { label: 'Sucesso', val: 'SUCCESS' }, { label: 'Aviso', val: 'WARNING' }, { label: 'Erro', val: 'ERROR' }].map((f) => (
              <button
                key={f.val}
                onClick={() => { setTypeFilter(f.val); setPage(1); }}
                className={`px-3 py-1 text-xs font-medium rounded transition-colors ${ typeFilter === f.val ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-muted' }`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <button onClick={loadLogs} className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-secondary border border-border text-xs text-muted-foreground hover:text-foreground transition-colors">
              <RefreshCw className="w-3.5 h-3.5" />
              Atualizar
            </button>
            <button onClick={handleExportLogs} className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-secondary border border-border text-xs text-muted-foreground hover:text-foreground transition-colors">
              <Download className="w-3.5 h-3.5" />
              Exportar
            </button>
          </div>
        </div>

        <div className="card-glass p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1.5">Severidade</label>
              <select
                value={severityFilter}
                onChange={(e) => { setSeverityFilter(e.target.value); setPage(1); }}
                className="w-full px-3 py-2 text-sm bg-muted border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="all">Todas</option>
                <option value="low">Baixa</option>
                <option value="medium">Média</option>
                <option value="high">Alta</option>
                <option value="critical">Crítica</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1.5">Buscar</label>
              <input
                type="text"
                placeholder="Dispositivo ou mensagem..."
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
                className="w-full px-3 py-2 text-sm bg-muted border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>
        </div>

        <div className="card-glass overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">Eventos Recentes</h3>
            </div>
            <span className="text-xs text-muted-foreground">Página {page}</span>
          </div>
          <div className="divide-y divide-border/50">
            {loading ? (
              <div className="px-5 py-8 flex flex-col items-center justify-center text-muted-foreground">
                <Loader2 className="w-6 h-6 animate-spin mb-2" />
                <span className="text-sm font-medium">Carregando logs...</span>
              </div>
            ) : logs.length > 0 ? (
              logs.map((log: any) => {
                const conf = levelConfig[log.type as keyof typeof levelConfig] || levelConfig.INFO;
                const Icon = conf.icon;
                return (
                  <div key={log.id} className="flex items-start gap-4 px-5 py-3.5 hover:bg-muted/20 transition-colors">
                    <span className="text-xs text-muted-foreground font-mono mt-1 w-24 flex-shrink-0">{format(new Date(log.timestamp), 'dd/MM HH:mm:ss')}</span>
                    <div className="flex gap-2 flex-shrink-0">
                      <span className={`flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full border ${conf.bg} ${conf.color}`}>
                        <Icon className="w-3 h-3" />
                        {log.type}
                      </span>
                      <span className={`text-xs font-medium px-2 py-1 rounded-full ${getSeverityColor(log.severity)}`}>{log.severity}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-foreground">{log.message}</p>
                    </div>
                    <span className="text-xs text-muted-foreground font-mono flex-shrink-0 whitespace-nowrap">{log.device_id || log.user_email || 'Sistema'}</span>
                  </div>
                );
              })
            ) : (
              <div className="px-5 py-10 flex flex-col items-center justify-center text-muted-foreground">
                <FileText className="w-10 h-10 mb-3 opacity-20" />
                <span className="text-sm font-medium">Nenhum evento encontrado.</span>
                <span className="text-xs opacity-70 mt-1">Eventos aparecerão aqui conforme as ações forem executadas.</span>
              </div>
            )}
          </div>
          {logs.length > 0 && (
            <div className="px-5 py-3 border-t border-border flex gap-2 justify-end">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-3 py-1 text-xs rounded-md bg-muted border border-border text-muted-foreground hover:text-foreground disabled:opacity-50 transition-colors"
              >
                Anterior
              </button>
              <button
                onClick={() => setPage(page + 1)}
                className="px-3 py-1 text-xs rounded-md bg-muted border border-border text-muted-foreground hover:text-foreground transition-colors"
              >
                Próxima
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
