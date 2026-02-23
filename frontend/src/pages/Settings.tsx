import { TopBar } from '@/components/TopBar';
import { Settings as SettingsIcon, Server, Key, Bell, Database } from 'lucide-react';

export default function Settings() {
  const apiBase = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000';

  return (
    <div className="animate-fade-in">
      <TopBar title="Configurações" subtitle="Configurações do sistema MDM" />
      <div className="p-6 space-y-6">
        {/* API Settings */}
        <div className="card-glass p-5">
          <div className="flex items-center gap-2 mb-4">
            <Server className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Conexão com a API</h3>
          </div>
          <div className="space-y-4">
            <div>
              <label className="text-xs text-muted-foreground block mb-1.5">Base URL da API FastAPI</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  defaultValue={apiBase}
                  readOnly
                  className="flex-1 px-3 py-2 text-sm bg-muted border border-border rounded-md text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <span className="text-xs text-muted-foreground whitespace-nowrap">Definir via VITE_API_BASE_URL</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1.5">
                Para alterar, defina a variável de ambiente <code className="font-mono bg-muted px-1 py-0.5 rounded">VITE_API_BASE_URL</code> no seu ambiente de build.
              </p>
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1.5">Intervalo de Atualização Automática</label>
              <select className="px-3 py-2 text-sm bg-muted border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-primary">
                <option value="15000">15 segundos</option>
                <option value="30000" selected>30 segundos</option>
                <option value="60000">1 minuto</option>
                <option value="300000">5 minutos</option>
              </select>
            </div>
          </div>
        </div>

        {/* Auth Settings */}
        <div className="card-glass p-5">
          <div className="flex items-center gap-2 mb-4">
            <Key className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Autenticação JWT</h3>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1.5">Token JWT</label>
              <div className="flex gap-2">
                <input
                  type="password"
                  placeholder="Bearer token..."
                  className="flex-1 px-3 py-2 text-sm bg-muted border border-border rounded-md text-foreground font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  onChange={(e) => {
                    if (e.target.value) localStorage.setItem('mdm_token', e.target.value);
                    else localStorage.removeItem('mdm_token');
                  }}
                  defaultValue={localStorage.getItem('mdm_token') || ''}
                />
                <button className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors">
                  Salvar
                </button>
              </div>
              <p className="text-xs text-muted-foreground mt-1.5">
                O token é armazenado localmente e enviado como <code className="font-mono bg-muted px-1 py-0.5 rounded">Authorization: Bearer</code> em todas as requisições.
              </p>
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="card-glass p-5">
          <div className="flex items-center gap-2 mb-4">
            <Bell className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Notificações</h3>
          </div>
          <div className="space-y-3">
            {[
              { label: 'Alertas de dispositivo offline', desc: 'Notificar quando dispositivo ficar offline por mais de 1h' },
              { label: 'Falhas de compliance', desc: 'Notificar quando um dispositivo sair de conformidade' },
              { label: 'Novos dispositivos', desc: 'Notificar quando um novo dispositivo se registrar' },
            ].map((n) => (
              <div key={n.label} className="flex items-center justify-between p-3 rounded-md bg-muted/50 border border-border">
                <div>
                  <p className="text-sm font-medium text-foreground">{n.label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{n.desc}</p>
                </div>
                <div className="w-10 h-5 bg-primary/20 rounded-full relative cursor-pointer border border-primary/30">
                  <div className="w-4 h-4 bg-primary rounded-full absolute top-0.5 right-0.5 transition-all" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* System Info */}
        <div className="card-glass p-5">
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Informações do Sistema</h3>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            {[
              { label: 'Versão do Console', value: '1.0.0' },
              { label: 'Stack', value: 'React + FastAPI' },
              { label: 'Autenticação', value: 'JWT Bearer' },
              { label: 'Atualização Auto', value: '30s' },
            ].map((info) => (
              <div key={info.label} className="flex justify-between p-2.5 rounded-md bg-muted/50 border border-border">
                <span className="text-muted-foreground text-xs">{info.label}</span>
                <span className="text-foreground text-xs font-mono font-medium">{info.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
