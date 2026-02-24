import { useState, useEffect } from 'react';
import { TopBar } from '@/components/TopBar';
import { FileText, Filter, Download, Loader2 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

// Tipagem real baseada na estrutura de logs
interface LogEntry {
  id: number;
  level: string;
  message: string;
  device: string;
  time: string;
}

const levelConfig = {
  info: { color: 'text-primary', bg: 'bg-primary/10 border-primary/20', dot: 'bg-primary' },
  warning: { color: 'text-status-syncing', bg: 'bg-status-syncing/10 border-status-syncing/20', dot: 'bg-status-syncing' },
  error: { color: 'text-status-locked', bg: 'bg-status-locked/10 border-status-locked/20', dot: 'bg-status-locked' },
};

export default function Logs() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const token = localStorage.getItem('auth_token');
        // TODO: Ajustar a rota `/api/logs` quando criarmos ela no Backend
        const response = await fetch("http://127.0.0.1:8000/api/logs", {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });

        if (response.ok) {
          const data = await response.json();
          setLogs(data);
        } else {
          // Se a API retornar erro ou não encontrar a rota (porque ainda não criamos), deixa vazio
          setLogs([]);
        }
      } catch (error) {
        toast({
          title: 'Erro de Conexão',
          description: 'Não foi possível buscar os logs em tempo real.',
          variant: 'destructive',
        });
      } finally {
        setLoading(false);
      }
    };

    fetchLogs();
  }, [toast]);

  return (
    <div className="animate-fade-in">
      <TopBar title="Logs do Sistema" subtitle="Histórico de eventos e auditoria" />
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2 bg-secondary border border-border rounded-md p-1">
            <Filter className="w-3.5 h-3.5 text-muted-foreground ml-1.5" />
            {['Todos', 'Info', 'Warning', 'Error'].map((f) => (
              <button
                key={f}
                className="px-3 py-1 text-xs font-medium rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors first:bg-primary first:text-primary-foreground"
              >
                {f}
              </button>
            ))}
          </div>
          <button className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-secondary border border-border text-xs text-muted-foreground hover:text-foreground transition-colors">
            <Download className="w-3.5 h-3.5" />
            Exportar CSV
          </button>
        </div>

        <div className="card-glass overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center gap-2">
            <FileText className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Eventos Recentes</h3>
          </div>
          <div className="divide-y divide-border/50">
            {loading ? (
              <div className="px-5 py-8 flex flex-col items-center justify-center text-muted-foreground">
                <Loader2 className="w-6 h-6 animate-spin mb-2" />
                <span className="text-sm font-medium">Sincronizando logs com os servidores...</span>
              </div>
            ) : logs.length > 0 ? (
              logs.map((log) => {
                const conf = levelConfig[log.level as keyof typeof levelConfig] || levelConfig.info;
                return (
                  <div key={log.id} className="flex items-start gap-4 px-5 py-3.5 hover:bg-muted/20 transition-colors">
                    <span className="text-xs text-muted-foreground font-mono mt-0.5 w-16 flex-shrink-0">{log.time}</span>
                    <span className={`flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full border flex-shrink-0 ${conf.bg} ${conf.color}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${conf.dot}`} />
                      {log.level.toUpperCase()}
                    </span>
                    <p className="text-sm text-foreground flex-1">{log.message}</p>
                    <span className="text-xs text-muted-foreground font-mono flex-shrink-0">{log.device}</span>
                  </div>
                );
              })
            ) : (
              <div className="px-5 py-10 flex flex-col items-center justify-center text-muted-foreground">
                <FileText className="w-10 h-10 mb-3 opacity-20" />
                <span className="text-sm font-medium">Nenhum evento registrado.</span>
                <span className="text-xs opacity-70 mt-1">Os logs oficiais da empresa aparecerão aqui a medida que os aparelhos sincronizarem.</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
