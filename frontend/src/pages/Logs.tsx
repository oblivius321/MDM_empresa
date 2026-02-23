import { TopBar } from '@/components/TopBar';
import { FileText, Filter, Download } from 'lucide-react';

const MOCK_LOGS = [
  { id: 1, level: 'info', message: 'Dispositivo Samsung A14 sincronizado com sucesso', device: 'device_001', time: '10:45:23' },
  { id: 2, level: 'warning', message: 'Dispositivo Motorola G32 offline há 2 horas', device: 'device_002', time: '10:32:11' },
  { id: 3, level: 'error', message: 'Falha ao aplicar política de senha em Xiaomi Redmi', device: 'device_003', time: '10:15:47' },
  { id: 4, level: 'info', message: 'Check-in automático — Samsung A54', device: 'device_004', time: '09:58:02' },
  { id: 5, level: 'info', message: 'Política VPN aplicada com sucesso', device: 'device_001', time: '09:45:30' },
  { id: 6, level: 'warning', message: 'Bateria crítica detectada em Motorola G22', device: 'device_005', time: '09:30:15' },
  { id: 7, level: 'error', message: 'Falha de autenticação — tentativas excedidas', device: 'device_006', time: '09:12:08' },
  { id: 8, level: 'info', message: 'Novo dispositivo registrado: Redmi Note 12', device: 'device_007', time: '08:55:44' },
];

const levelConfig = {
  info: { color: 'text-primary', bg: 'bg-primary/10 border-primary/20', dot: 'bg-primary' },
  warning: { color: 'text-status-syncing', bg: 'bg-status-syncing/10 border-status-syncing/20', dot: 'bg-status-syncing' },
  error: { color: 'text-status-locked', bg: 'bg-status-locked/10 border-status-locked/20', dot: 'bg-status-locked' },
};

export default function Logs() {
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
            <span className="ml-auto text-xs text-muted-foreground">Conecte ao endpoint <code className="font-mono bg-muted px-1 rounded">/logs</code> para dados reais</span>
          </div>
          <div className="divide-y divide-border/50">
            {MOCK_LOGS.map((log) => {
              const conf = levelConfig[log.level as keyof typeof levelConfig];
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
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
