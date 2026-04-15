import { useCallback, useEffect, useMemo, useState } from 'react';
import { TopBar } from '@/components/TopBar';
import { FileText, Filter, Download, Loader2, AlertCircle, CheckCircle, Info, AlertTriangle, RefreshCw } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { format } from 'date-fns';
import { AuditLogRecord, logService } from '@/services/api';

interface LogEntry {
  id: string;
  timestamp: string;
  type: 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR';
  message: string;
  device_id?: string;
  user_email?: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  details?: Record<string, any>;
  action?: string;
}

const levelConfig = {
  INFO: { color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200', dot: 'bg-blue-600', icon: Info },
  SUCCESS: { color: 'text-green-600', bg: 'bg-green-50 border-green-200', dot: 'bg-green-600', icon: CheckCircle },
  WARNING: { color: 'text-yellow-600', bg: 'bg-yellow-50 border-yellow-200', dot: 'bg-yellow-600', icon: AlertTriangle },
  ERROR: { color: 'text-red-600', bg: 'bg-red-50 border-red-200', dot: 'bg-red-600', icon: AlertCircle },
};

const actionMessages: Record<string, string> = {
  USER_PREFERENCES_UPDATE: 'Configuracoes de notificacao atualizadas',
  ENROLLMENT_TOKEN_GENERATED: 'Token de enrollment gerado',
  DEVICE_ENROLLED: 'Dispositivo registrado com sucesso',
  ENROLLMENT_REJECTED: 'Enrollment rejeitado',
  POLICY_CREATED: 'Politica criada',
  POLICY_UPDATED: 'Politica atualizada',
  POLICY_DELETED: 'Politica removida',
  COMMAND_CREATED: 'Comando criado',
  COMMAND_ACKED: 'Comando recebido pelo dispositivo',
  COMMAND_EXECUTED: 'Comando executado',
  COMMAND_FAILED: 'Falha ao executar comando',
  COMPLIANCE_REPORT: 'Relatorio de compliance recebido',
};

const successEvents = new Set([
  'DEVICE_ENROLLED',
  'ENROLLMENT_COMPLETE',
  'POLICY_CREATED',
  'POLICY_UPDATED',
  'USER_PREFERENCES_UPDATE',
]);

const pageSize = 25;
const logFetchLimit = 500;

function humanizeAction(action: string) {
  return action
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/^\w|\s\w/g, (match) => match.toUpperCase());
}

function mapType(log: AuditLogRecord): LogEntry['type'] {
  const severity = (log.severity || '').toUpperCase();
  const event = log.event_type || log.action;

  if (!log.is_success || severity === 'ERROR' || severity === 'CRITICAL' || severity === 'SECURITY') return 'ERROR';
  if (severity === 'WARNING') return 'WARNING';
  if (successEvents.has(event)) return 'SUCCESS';
  return 'INFO';
}

function mapSeverity(log: AuditLogRecord): LogEntry['severity'] {
  const severity = (log.severity || '').toUpperCase();

  if (severity === 'CRITICAL' || severity === 'SECURITY') return 'critical';
  if (severity === 'ERROR') return 'high';
  if (severity === 'WARNING') return 'medium';
  return 'low';
}

function mapAuditLog(log: AuditLogRecord): LogEntry {
  const event = log.event_type || log.action;
  const details = log.details || {};

  return {
    id: log.id,
    timestamp: log.created_at,
    type: mapType(log),
    severity: mapSeverity(log),
    message: details.message || actionMessages[event] || humanizeAction(event),
    device_id: log.device_id || details.device_id || undefined,
    user_email: log.user_email || (log.actor_type !== 'device' ? log.actor_id : undefined),
    details,
    action: event,
  };
}

function formatLogTime(timestamp: string) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? '--/-- --:--:--' : format(date, 'dd/MM HH:mm:ss');
}

export default function Logs() {
  const [allLogs, setAllLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState('all');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const { toast } = useToast();

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await logService.getAll({ limit: logFetchLimit });
      const records = Array.isArray(res.data) ? res.data : ((res.data as any)?.logs || []);
      setAllLogs(records.map(mapAuditLog));
    } catch (error) {
      toast({
        title: 'Erro',
        description: 'Falha ao carregar logs',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const filteredLogs = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return allLogs.filter((log) => {
      if (typeFilter !== 'all' && log.type !== typeFilter) return false;
      if (severityFilter !== 'all' && log.severity !== severityFilter) return false;
      if (!query) return true;

      const searchable = [
        log.message,
        log.device_id,
        log.user_email,
        log.action,
        JSON.stringify(log.details || {}),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();

      return searchable.includes(query);
    });
  }, [allLogs, searchQuery, severityFilter, typeFilter]);

  const logs = useMemo(() => {
    const startIdx = (page - 1) * pageSize;
    return filteredLogs.slice(startIdx, startIdx + pageSize);
  }, [filteredLogs, page]);

  const handleExportLogs = () => {
    if (filteredLogs.length === 0) {
      toast({
        title: 'Sem dados',
        description: 'Nao ha logs para exportar com os filtros atuais.',
      });
      return;
    }

    const csv = [
      'Timestamp,Type,Severity,Message,Device,User',
      ...filteredLogs.map(
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
    window.URL.revokeObjectURL(url);

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
      <TopBar title="Auditoria & Logs" subtitle="Historico completo de acoes e eventos do sistema" />
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
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
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
                <option value="medium">Media</option>
                <option value="high">Alta</option>
                <option value="critical">Critica</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1.5">Buscar</label>
              <input
                type="text"
                placeholder="Dispositivo, usuario ou mensagem..."
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
            <span className="text-xs text-muted-foreground">
              Pagina {page} de {Math.max(1, Math.ceil(filteredLogs.length / pageSize))}
            </span>
          </div>
          <div className="divide-y divide-border/50">
            {loading ? (
              <div className="px-5 py-8 flex flex-col items-center justify-center text-muted-foreground">
                <Loader2 className="w-6 h-6 animate-spin mb-2" />
                <span className="text-sm font-medium">Carregando logs...</span>
              </div>
            ) : logs.length > 0 ? (
              logs.map((log) => {
                const conf = levelConfig[log.type as keyof typeof levelConfig] || levelConfig.INFO;
                const Icon = conf.icon;
                return (
                  <div key={log.id} className="flex items-start gap-4 px-5 py-3.5 hover:bg-muted/20 transition-colors">
                    <span className="text-xs text-muted-foreground font-mono mt-1 w-24 flex-shrink-0">{formatLogTime(log.timestamp)}</span>
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
                <span className="text-xs opacity-70 mt-1">Eventos aparecerao aqui conforme as acoes forem executadas.</span>
              </div>
            )}
          </div>
          {filteredLogs.length > 0 && (
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
                disabled={page * pageSize >= filteredLogs.length}
                className="px-3 py-1 text-xs rounded-md bg-muted border border-border text-muted-foreground hover:text-foreground disabled:opacity-50 transition-colors"
              >
                Proxima
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
