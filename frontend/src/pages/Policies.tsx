import { useState, useEffect } from 'react';
import { TopBar } from '@/components/TopBar';
import { Shield, Plus, Lock, Smartphone, Wifi, Eye, Edit, Trash2, CheckCircle2, Clock, Loader2, FileText, X } from 'lucide-react';
import { StatusBadge } from '@/components/StatusBadge';
import { policyService } from '@/services/api';
import { useToast } from '@/hooks/use-toast';

export default function Policies() {
  const [policies, setPolicies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [formData, setFormData] = useState({
    name: '',
    camera_disabled: false,
    install_unknown_sources: false,
    factory_reset_disabled: false,
    kiosk_mode: ''
  });

  const { toast } = useToast();

  const fetchPolicies = async () => {
    try {
      setLoading(true);
      const response = await policyService.getAll();
      setPolicies(response.data);
    } catch (error) {
      toast({
        title: 'Erro de Conexão',
        description: 'Não foi possível carregar as políticas.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicies();
  }, [toast]);

  const handleCreatePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await policyService.create({
        name: formData.name || 'Nova Política',
        type: formData.kiosk_mode ? 'kiosk' : 'security',
        camera_disabled: formData.camera_disabled,
        install_unknown_sources: formData.install_unknown_sources,
        factory_reset_disabled: formData.factory_reset_disabled,
        kiosk_mode: formData.kiosk_mode || null
      });
      toast({
        title: 'Sucesso',
        description: 'Política global criada e os aparelhos serão notificados.',
      });
      setIsModalOpen(false);
      setFormData({ name: '', camera_disabled: false, install_unknown_sources: false, factory_reset_disabled: false, kiosk_mode: '' });
      await fetchPolicies();
    } catch (error) {
      toast({
        title: 'Erro!',
        description: 'Não foi possível salvar a política.',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const getIcon = (type: string) => {
    switch (type) {
      case 'compliance': return <Shield className="w-4 h-4 text-primary" />;
      case 'kiosk': return <Smartphone className="w-4 h-4 text-status-syncing" />;
      case 'network': return <Wifi className="w-4 h-4 text-status-online" />;
      default: return <Lock className="w-4 h-4 text-muted-foreground" />;
    }
  };

  const activeCount = policies.filter(p => p.status === 'active' || p.status === 'applied').length;
  const draftCount = policies.filter(p => p.status !== 'active' && p.status !== 'applied').length;

  return (
    <div className="animate-fade-in relative">
      <TopBar title="Políticas de Dispositivo" subtitle="Configurações globais e restrições de segurança" />

      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="px-3 py-1.5 rounded-md bg-secondary border border-border flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <CheckCircle2 className="w-3.5 h-3.5 text-status-online" />
              <span>{activeCount} Ativas</span>
            </div>
            <div className="px-3 py-1.5 rounded-md bg-secondary border border-border flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <Clock className="w-3.5 h-3.5 text-status-syncing" />
              <span>{draftCount} Pendentes</span>
            </div>
          </div>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-all shadow-lg shadow-primary/20"
          >
            <Plus className="w-4 h-4" />
            Criar Nova Política
          </button>
        </div>

        {loading ? (
          <div className="card-glass w-full py-16 flex flex-col items-center justify-center text-muted-foreground">
            <Loader2 className="w-8 h-8 animate-spin mb-3 text-primary" />
            <span className="text-sm font-medium">Buscando políticas ativas...</span>
          </div>
        ) : policies.length > 0 ? (
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
                  <StatusBadge status={policy.status === 'active' || policy.status === 'applied' ? 'online' : 'syncing'} />
                </div>

                <div className="flex items-center gap-6 mb-6">
                  <div className="flex flex-col">
                    <span className="text-[10px] text-muted-foreground uppercase font-bold">Aparelhos</span>
                    <span className="text-sm font-semibold text-foreground">{policy.devices || 'Global'}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[10px] text-muted-foreground uppercase font-bold">Criado em</span>
                    <span className="text-sm font-semibold text-foreground">
                      {policy.applied_at ? new Date(policy.applied_at).toLocaleDateString() : 'Desconhecido'}
                    </span>
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
        ) : (
          <div className="card-glass w-full py-16 flex flex-col items-center justify-center text-muted-foreground border-dashed border-2">
            <FileText className="w-12 h-12 mb-4 opacity-20" />
            <span className="text-lg font-semibold text-foreground">Nenhuma Política Configurável</span>
            <span className="text-sm opacity-70 mt-1 max-w-sm text-center mb-6">Você ainda não criou nenhuma regra global para os aparelhos da empresa.</span>
            <button
              onClick={() => setIsModalOpen(true)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-md bg-secondary text-foreground text-sm font-medium hover:bg-primary hover:text-primary-foreground transition-all"
            >
              <Plus className="w-4 h-4" />
              Criar a Primeira Política
            </button>
          </div>
        )}

      </div>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-fade-in p-4">
          <div className="bg-card w-full max-w-lg rounded-xl border border-border shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-border">
              <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
                <Shield className="w-5 h-5 text-primary" />
                Criar Política Global
              </h2>
              <button onClick={() => setIsModalOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreatePolicy} className="p-5 space-y-5">

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Nome da Política</label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Política Padrão Matriz"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary"
                />
              </div>

              <div className="space-y-3 bg-secondary/50 p-4 rounded-lg border border-border">
                <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">Restrições (Android Enterprise)</h3>

                <label className="flex items-center gap-3 cursor-pointer group">
                  <div className="relative">
                    <input type="checkbox" className="sr-only peer" checked={formData.camera_disabled} onChange={(e) => setFormData({ ...formData, camera_disabled: e.target.checked })} />
                    <div className="w-9 h-5 bg-muted peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                  </div>
                  <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">Desativar Câmera</span>
                </label>

                <label className="flex items-center gap-3 cursor-pointer group">
                  <div className="relative">
                    <input type="checkbox" className="sr-only peer" checked={formData.install_unknown_sources} onChange={(e) => setFormData({ ...formData, install_unknown_sources: e.target.checked })} />
                    <div className="w-9 h-5 bg-muted peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                  </div>
                  <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">Permitir Fontes Desconhecidas (APKs)</span>
                </label>

                <label className="flex items-center gap-3 cursor-pointer group">
                  <div className="relative">
                    <input type="checkbox" className="sr-only peer" checked={formData.factory_reset_disabled} onChange={(e) => setFormData({ ...formData, factory_reset_disabled: e.target.checked })} />
                    <div className="w-9 h-5 bg-muted peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                  </div>
                  <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">Impedir Reset de Fábrica (Hard Reset)</span>
                </label>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Modo Kiosk (Deixar em branco para desativar)</label>
                <input
                  type="text"
                  placeholder="Ex: com.br.empresa.app"
                  value={formData.kiosk_mode}
                  onChange={(e) => setFormData({ ...formData, kiosk_mode: e.target.value })}
                  className="w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary font-mono"
                />
                <p className="text-[10px] text-muted-foreground">O aparelho ficará bloqueado e forçado a usar permanentemente este aplicativo.</p>
              </div>

              <div className="pt-4 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-all shadow-lg shadow-primary/20 disabled:opacity-50 flex items-center gap-2"
                >
                  {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
                  Salvar e Aplicar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
