import { useState, useEffect } from 'react';
import { TopBar } from '@/components/TopBar';
import { Shield, Plus, Lock, Smartphone, Wifi, Eye, Edit, Trash2, CheckCircle2, Clock, Loader2, FileText, X } from 'lucide-react';
import { StatusBadge } from '@/components/StatusBadge';
import { policyV2Service } from '@/services/api';
import { useToast } from '@/hooks/use-toast';
import { PolicyBuilder } from '@/components/policies/PolicyBuilder';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

export default function Policies() {
  const [policies, setPolicies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<any>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { toast } = useToast();

  const fetchPolicies = async () => {
    try {
      setLoading(true);
      const response = await policyV2Service.getAll();
      setPolicies(response.data);
    } catch (error) {
      toast({
        title: 'Erro de Conexão',
        description: 'Não foi possível carregar as políticas enterprise.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicies();
  }, []);

  const handleSavePolicy = async (policyData: any) => {
    setIsSubmitting(true);
    try {
      if (editingPolicy) {
        await policyV2Service.update(editingPolicy.id, policyData);
        toast({ title: 'Sucesso', description: 'Política atualizada com sucesso.' });
      } else {
        await policyV2Service.create(policyData);
        toast({ title: 'Sucesso', description: 'Nova política criada e pronta para atribuição.' });
      }
      setIsEditorOpen(false);
      setEditingPolicy(null);
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

  const handleDeletePolicy = async (id: number) => {
    if (!confirm('Tem certeza que deseja excluir definitivamente esta política?')) return;
    try {
      await policyV2Service.delete(id);
      toast({ title: 'Sucesso', description: 'Política excluída definitivamente.' });
      await fetchPolicies();
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      toast({
        title: error.response?.status === 409 ? 'Política em uso' : 'Erro',
        description: detail || 'Falha ao excluir política.',
        variant: 'destructive',
      });
    }
  };

  const activeCount = policies.filter(p => p.is_active).length;
  const globalCount = policies.filter(p => p.scope === 'global').length;

  return (
    <div className="animate-fade-in relative min-h-screen bg-background">
      <TopBar title="Políticas Enterprise" subtitle="Gestão declarativa de estado e restrições avançadas" />

      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="px-3 py-1.5 rounded-md bg-secondary/50 border border-border flex items-center gap-2 text-xs font-semibold text-muted-foreground">
              <CheckCircle2 className="w-3.5 h-3.5 text-status-online" />
              <span>{activeCount} Ativas</span>
            </div>
            <div className="px-3 py-1.5 rounded-md bg-secondary/50 border border-border flex items-center gap-2 text-xs font-semibold text-muted-foreground">
              <Shield className="w-3.5 h-3.5 text-primary" />
              <span>{globalCount} Globais</span>
            </div>
          </div>
          <button
            onClick={() => { setEditingPolicy(null); setIsEditorOpen(true); }}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-bold hover:bg-primary/90 transition-all shadow-lg shadow-primary/20"
          >
            <Plus className="w-4 h-4" />
            Nova Política V2
          </button>
        </div>

        {loading ? (
          <div className="py-24 flex flex-col items-center justify-center text-muted-foreground">
            <Loader2 className="w-10 h-10 animate-spin mb-4 text-primary" />
            <span className="text-sm font-bold tracking-widest uppercase opacity-70">Sincronizando Engine...</span>
          </div>
        ) : policies.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {policies.map((policy) => (
              <div key={policy.id} className="card-glass border-border/40 p-6 hover:border-primary/40 transition-all group relative overflow-hidden">
                {/* SCOPE BADGE */}
                <div className="absolute top-0 right-0 px-3 py-1 bg-secondary text-[10px] font-bold uppercase tracking-tighter rounded-bl-lg border-l border-b border-border/50 text-muted-foreground">
                  {policy.scope}
                </div>

                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-muted/50 border border-border flex items-center justify-center group-hover:scale-110 transition-transform duration-500">
                      <Shield className={`w-6 h-6 ${policy.is_active ? 'text-primary' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <h3 className="text-md font-bold text-foreground group-hover:text-primary transition-colors">{policy.name}</h3>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-[9px] py-0 font-mono">v{policy.version}</Badge>
                        <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-tight">Prioridade: {policy.priority}</span>
                      </div>
                    </div>
                  </div>
                  <StatusBadge status={policy.is_active ? 'online' : 'offline'} />
                </div>

                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="p-3 rounded-lg bg-secondary/30 border border-border/20">
                    <span className="block text-[9px] text-muted-foreground uppercase font-bold mb-1">Restrições</span>
                    <span className="text-xs font-semibold text-foreground">
                      {Object.keys(policy.config?.restrictions || {}).length} Ativas
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-secondary/30 border border-border/20">
                    <span className="block text-[9px] text-muted-foreground uppercase font-bold mb-1">Kiosk</span>
                    <span className="text-xs font-semibold text-foreground">
                      {policy.config?.kiosk_mode?.enabled ? 'Ativado' : 'Desativado'}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-4 border-t border-border/30">
                  <button 
                    onClick={() => { setEditingPolicy(policy); setIsEditorOpen(true); }}
                    className="flex-1 flex items-center justify-center gap-2 py-2 rounded-md bg-primary/10 text-primary text-xs font-bold hover:bg-primary hover:text-white transition-all"
                  >
                    <Edit className="w-3.5 h-3.5" />
                    Configurar
                  </button>
                  <button 
                    onClick={() => handleDeletePolicy(policy.id)}
                    className="p-2 rounded-md bg-secondary text-muted-foreground hover:text-status-locked hover:bg-status-locked/10 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="card-glass py-24 flex flex-col items-center justify-center text-muted-foreground border-dashed border-2">
            <FileText className="w-16 h-16 mb-4 opacity-10" />
            <h3 className="text-xl font-bold text-foreground">Sem Políticas Definidas</h3>
            <p className="text-sm opacity-70 mt-2 max-w-xs text-center mb-8">
              A Fase 3 (Enforcement) exige políticas declarativas para manter os devices em compliance.
            </p>
            <Button onClick={() => setIsEditorOpen(true)}>
              <Plus className="w-4 h-4 mr-2" /> Começar Agora
            </Button>
          </div>
        )}
      </div>

      {/* POLICY EDITOR OVERLAY */}
      <Dialog open={isEditorOpen} onOpenChange={setIsEditorOpen}>
        <DialogContent className="max-w-[95vw] w-[1000px] h-[90vh] p-0 overflow-hidden bg-background border-border/50 shadow-2xl">
          <PolicyBuilder 
            initialData={editingPolicy}
            onSave={handleSavePolicy}
            onCancel={() => setIsEditorOpen(false)}
            isSubmitting={isSubmitting}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Pequeno helper para Badge (se não estiver disponível no index)
function Badge({ children, variant, className }: any) {
  return (
    <span className={`px-2 py-0.5 rounded-full border text-xs ${className}`}>
      {children}
    </span>
  );
}
