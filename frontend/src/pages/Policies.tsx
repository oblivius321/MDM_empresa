import { TopBar } from '@/components/TopBar';
import { Shield, Plus, AlertCircle } from 'lucide-react';

export default function Policies() {
  return (
    <div className="animate-fade-in">
      <TopBar title="Políticas" subtitle="Gerenciamento de políticas MDM" />
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">Configure e aplique políticas nos dispositivos</p>
          <button className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors">
            <Plus className="w-4 h-4" />
            Nova Política
          </button>
        </div>

        <div className="card-glass p-8 text-center">
          <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-3">
            <Shield className="w-6 h-6 text-primary" />
          </div>
          <p className="text-foreground font-medium">Módulo de Políticas</p>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm mx-auto">
            Conecte ao endpoint <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">/policies</code> da sua API FastAPI para gerenciar políticas de configuração, segurança e restrições.
          </p>

          <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-lg mx-auto">
            {['Política de Senha', 'Restrições de App', 'VPN Corporativa'].map((p) => (
              <div key={p} className="p-3 rounded-md bg-muted/50 border border-border text-left">
                <div className="w-6 h-6 rounded bg-primary/10 flex items-center justify-center mb-2">
                  <Shield className="w-3 h-3 text-primary" />
                </div>
                <p className="text-xs font-medium text-foreground">{p}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Configurar via API</p>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-start gap-3 px-4 py-3 rounded-md bg-primary/5 border border-primary/20 text-sm text-primary">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <p>
            Para ativar este módulo, certifique-se de que o endpoint <code className="font-mono text-xs bg-primary/10 px-1.5 py-0.5 rounded">GET /policies</code> está disponível na sua API FastAPI.
          </p>
        </div>
      </div>
    </div>
  );
}
