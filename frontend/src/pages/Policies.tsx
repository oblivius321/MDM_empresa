import { useState } from 'react';
import { TopBar } from '@/components/TopBar';
import { Shield, Plus, Lock, Smartphone, Wifi, Eye, Edit, Trash2, CheckCircle2, Clock } from 'lucide-react';
import { StatusBadge } from '@/components/StatusBadge';

const MOCK_POLICIES = [
  { id: '1', name: 'Segurança Padrão — Frota A', type: 'compliance', devices: 14, status: 'active', lastUpdate: '2024-02-23' },
  { id: '2', name: 'Modo Quiosque — Vendas', type: 'kiosk', devices: 5, status: 'active', lastUpdate: '2024-02-20' },
  { id: '3', name: 'Restrição de Apps Redes Sociais', type: 'security', devices: 42, status: 'draft', lastUpdate: '2024-02-15' },
  { id: '4', name: 'Políticas de Wi-Fi Corporativo', type: 'network', devices: 61, status: 'active', lastUpdate: '2024-02-10' },
];

export default function Policies() {
  const [policies] = useState(MOCK_POLICIES);

  const getIcon = (type: string) => {
    switch (type) {
      case 'compliance': return <Shield className="w-4 h-4 text-primary" />;
      case 'kiosk': return <Smartphone className="w-4 h-4 text-status-syncing" />;
      case 'network': return <Wifi className="w-4 h-4 text-status-online" />;
      default: return <Lock className="w-4 h-4 text-muted-foreground" />;
    }
  };

  return (
    <div className="animate-fade-in">
      <TopBar title="Políticas de Dispositivo" subtitle="Configurações globais e restrições de segurança" />

      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="px-3 py-1.5 rounded-md bg-secondary border border-border flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <CheckCircle2 className="w-3.5 h-3.5 text-status-online" />
              <span>3 Ativas</span>
            </div>
            <div className="px-3 py-1.5 rounded-md bg-secondary border border-border flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <Clock className="w-3.5 h-3.5 text-status-syncing" />
              <span>1 Rascunho</span>
            </div>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-all shadow-lg shadow-primary/20">
            <Plus className="w-4 h-4" />
            Criar Nova Política
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {policies.map((policy) => (
            <div key={policy.id} className="card-glass p-5 hover:border-primary/30 transition-all group">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
                    {getIcon(policy.type)}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-foreground group-hover:text-primary transition-colors">{policy.name}</h3>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold mt-0.5">{policy.type}</p>
                  </div>
                </div>
                <StatusBadge status={policy.status === 'active' ? 'online' : 'syncing'} />
              </div>

              <div className="flex items-center gap-6 mb-6">
                <div className="flex flex-col">
                  <span className="text-[10px] text-muted-foreground uppercase font-bold">Aparelhos</span>
                  <span className="text-sm font-semibold text-foreground">{policy.devices} vinculados</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] text-muted-foreground uppercase font-bold">Última Modificação</span>
                  <span className="text-sm font-semibold text-foreground">{policy.lastUpdate}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-4 border-t border-border/50">
                <button className="flex-1 flex items-center justify-center gap-2 py-2 rounded-md bg-secondary text-xs font-medium text-foreground hover:bg-muted transition-colors">
                  <Eye className="w-3.5 h-3.5" />
                  Visualizar
                </button>
                <button className="p-2 rounded-md bg-secondary text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors">
                  <Edit className="w-3.5 h-3.5" />
                </button>
                <button className="p-2 rounded-md bg-secondary text-muted-foreground hover:text-status-locked hover:bg-status-locked/10 transition-colors">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}
