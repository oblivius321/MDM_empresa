import { useState, useEffect } from 'react';
import { TopBar } from '@/components/TopBar';
import { Box, Plus, Settings, CheckCircle2, Shield, Loader2, Trash2, Edit, FileText, X, AlertCircle } from 'lucide-react';
import { enrollmentService, ProvisioningProfile } from '@/services/api';
import { useToast } from '@/hooks/use-toast';
import { StatusBadge } from '@/components/StatusBadge';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { policyV2Service, PolicyV2, MergedPolicyPreview } from '@/services/api';
import { Tabs, TabsContent, TabsList, Trigger as TabsTrigger } from '@/components/ui/tabs';


export default function Provisioning() {
  const [profiles, setProfiles] = useState<ProvisioningProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [formData, setFormData] = useState<{
    name: string;
    kiosk_enabled: boolean;
    allowed_apps_str: string;
    policy_ids: number[];
  }>({
    name: '',
    kiosk_enabled: false,
    allowed_apps_str: '',
    policy_ids: []
  });

  const [availablePolicies, setAvailablePolicies] = useState<PolicyV2[]>([]);
  const [previewData, setPreviewData] = useState<MergedPolicyPreview | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);


  const { toast } = useToast();

  const fetchProfiles = async () => {
    try {
      setLoading(true);
      const [profilesRes, policiesRes] = await Promise.all([
        enrollmentService.listProfiles(),
        policyV2Service.getAll({ is_active: true })
      ]);
      setProfiles(profilesRes.data);
      setAvailablePolicies(policiesRes.data);
    } catch (error) {
      toast({
        title: 'Erro de Conexão',
        description: 'Não foi possível carregar os dados.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async (profileId?: string) => {
    if (!profileId) return;
    try {
      setIsPreviewLoading(true);
      const res = await enrollmentService.previewProfile(profileId);
      setPreviewData(res.data);
      setIsPreviewOpen(true);
    } catch (error) {
      toast({ title: 'Erro', description: 'Falha ao gerar preview da política.', variant: 'destructive' });
    } finally {
      setIsPreviewLoading(false);
    }
  };


  useEffect(() => {
    fetchProfiles();
  }, []);

  const handleSaveProfile = async () => {
    if (!formData.name) {
      toast({ title: 'Atenção', description: 'O nome do perfil é obrigatório', variant: 'destructive' });
      return;
    }

    setIsSubmitting(true);
    try {
      const allowed_apps = formData.allowed_apps_str
        .split(',')
        .map(s => s.trim())
        .filter(s => s.length > 0);

      const payload = {
        name: formData.name,
        kiosk_enabled: formData.kiosk_enabled,
        allowed_apps,
        blocked_features: {},
        config: {},
        policy_ids: formData.policy_ids
      };

      await enrollmentService.createProfile(payload);
      toast({ title: 'Sucesso', description: 'Perfil de provisionamento criado com sucesso.' });
      
      setIsEditorOpen(false);
      setFormData({ name: '', kiosk_enabled: false, allowed_apps_str: '', policy_ids: [] });
      await fetchProfiles();

    } catch (error) {
      toast({
        title: 'Erro!',
        description: 'Não foi possível salvar o perfil.',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const activeCount = profiles.filter(p => p.is_active).length;

  return (
    <div className="animate-fade-in relative min-h-screen bg-background">
      <TopBar title="Provisionamento (Zero-Touch)" subtitle="Gerencie perfis para registro automatizado de dispositivos Android" />

      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="px-3 py-1.5 rounded-md bg-secondary/50 border border-border flex items-center gap-2 text-xs font-semibold text-muted-foreground">
              <CheckCircle2 className="w-3.5 h-3.5 text-status-online" />
              <span>{activeCount} Ativos</span>
            </div>
            <div className="px-3 py-1.5 rounded-md bg-secondary/50 border border-border flex items-center gap-2 text-xs font-semibold text-muted-foreground">
              <Box className="w-3.5 h-3.5 text-primary" />
              <span>{profiles.length} Total</span>
            </div>
          </div>
          <button
            onClick={() => {
              setFormData({ name: '', kiosk_enabled: false, allowed_apps_str: '' });
              setIsEditorOpen(true);
            }}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-bold hover:bg-primary/90 transition-all shadow-lg shadow-primary/20"
          >
            <Plus className="w-4 h-4" />
            Criar Perfil de Provisionamento
          </button>
        </div>

        {loading ? (
          <div className="py-24 flex flex-col items-center justify-center text-muted-foreground">
            <Loader2 className="w-10 h-10 animate-spin mb-4 text-primary" />
            <span className="text-sm font-bold tracking-widest uppercase opacity-70">Carregando Profiles...</span>
          </div>
        ) : profiles.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {profiles.map((profile) => (
              <div key={profile.id} className="card-glass border-border/40 p-6 hover:border-primary/40 transition-all group relative overflow-hidden">
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-muted/50 border border-border flex items-center justify-center group-hover:scale-110 transition-transform duration-500">
                      <Box className={`w-6 h-6 ${profile.is_active ? 'text-primary' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <h3 className="text-md font-bold text-foreground group-hover:text-primary transition-colors">{profile.name}</h3>
                      <div className="flex items-center gap-2 mt-1">
                         <span className="px-2 py-0.5 rounded-full border text-[9px] font-mono">v{profile.version}</span>
                        <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-tight">Criado em: {new Date(profile.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>
                  <StatusBadge status={profile.is_active ? 'online' : 'offline'} />
                </div>

                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="p-3 rounded-lg bg-secondary/30 border border-border/20">
                    <span className="block text-[9px] text-muted-foreground uppercase font-bold mb-1">Modo Kiosk</span>
                    <span className="text-xs font-semibold text-foreground">
                      {profile.kiosk_enabled ? 'Ativado' : 'Desativado'}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-secondary/30 border border-border/20">
                    <span className="block text-[9px] text-muted-foreground uppercase font-bold mb-1">Políticas Vinculadas</span>
                    <span className="text-xs font-semibold text-foreground">
                      {profile.policy_ids?.length || 0} vinculadas
                    </span>
                  </div>
                </div>

                <div className="mt-4 flex justify-end">
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="text-[10px] font-bold h-8 uppercase tracking-widest"
                      onClick={() => handlePreview(profile.id)}
                    >
                      <Loader2 className={`w-3 h-3 mr-2 ${isPreviewLoading ? 'animate-spin' : 'hidden'}`} />
                      Preview Real-time Merge
                    </Button>
                </div>

              </div>
            ))}
          </div>
        ) : (
          <div className="card-glass py-24 flex flex-col items-center justify-center text-muted-foreground border-dashed border-2">
            <FileText className="w-16 h-16 mb-4 opacity-10" />
            <h3 className="text-xl font-bold text-foreground">Sem Perfis de Provisionamento</h3>
            <p className="text-sm opacity-70 mt-2 max-w-xs text-center mb-8">
              Crie um perfil para iniciar o enrollment zero-touch via QR Code.
            </p>
            <Button onClick={() => setIsEditorOpen(true)}>
              <Plus className="w-4 h-4 mr-2" /> Criar Primeiro Perfil
            </Button>
          </div>
        )}
      </div>

      {/* MODAL DE CRIAÇÃO */}
      <Dialog open={isEditorOpen} onOpenChange={setIsEditorOpen}>
        <DialogContent className="sm:max-w-[500px] p-0 bg-background border-border/50 overflow-hidden shadow-2xl">
          <div className="flex items-center justify-between p-4 border-b border-border bg-card/30">
             <div className="flex items-center gap-3">
               <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary shadow-sm border border-primary/20">
                 <Box className="w-4 h-4" />
               </div>
               <div>
                  <DialogTitle className="font-bold text-foreground">Criar Perfil de Provisionamento</DialogTitle>
               </div>
             </div>
             <button onClick={() => setIsEditorOpen(false)} className="text-muted-foreground hover:text-foreground">
               <X className="w-4 h-4" />
             </button>
          </div>

          <div className="p-6 space-y-4">
             <div className="space-y-1.5">
               <Label className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Nome do Perfil</Label>
               <Input 
                 placeholder="Ex: Coletores Galpão A" 
                 value={formData.name}
                 onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                 className="bg-card/50"
               />
             </div>

             <div className="space-y-1.5">
                <Label className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Políticas Enterprise Vinculadas</Label>
                <div className="p-1 rounded-md bg-card/50 border border-border">
                  <ScrollArea className="h-40 p-2">
                    {availablePolicies.map(policy => (
                      <div 
                        key={policy.id}
                        onClick={() => {
                          const newIds = formData.policy_ids.includes(policy.id)
                            ? formData.policy_ids.filter(id => id !== policy.id)
                            : [...formData.policy_ids, policy.id];
                          setFormData({ ...formData, policy_ids: newIds });
                        }}
                        className={`flex items-center justify-between p-2 mb-1 rounded cursor-pointer transition-colors ${
                          formData.policy_ids.includes(policy.id) ? 'bg-primary/10 border-primary/20 text-primary' : 'hover:bg-muted/50 text-muted-foreground'
                        }`}
                      >
                        <div className="flex flex-col">
                          <span className="text-xs font-bold">{policy.name}</span>
                          <span className="text-[10px] opacity-70">Escopo: {policy.scope} | Prioridade: {policy.priority}</span>
                        </div>
                        {formData.policy_ids.includes(policy.id) && <CheckCircle2 className="w-3 h-3" />}
                      </div>
                    ))}
                  </ScrollArea>
                </div>
             </div>


             <div className="flex items-center gap-2 pt-2">
                 <button 
                   onClick={() => setFormData({ ...formData, kiosk_enabled: !formData.kiosk_enabled })}
                   className={`w-10 h-5 rounded-full relative transition-colors ${ formData.kiosk_enabled ? 'bg-primary/20 border border-primary/30' : 'bg-muted border border-border' }`}
                 >
                    <div className={`w-4 h-4 bg-primary rounded-full absolute top-0.5 transition-all ${ formData.kiosk_enabled ? 'right-0.5' : 'left-0.5' }`} />
                 </button>
                 <Label className="text-sm font-medium">Habilitar Modo Kiosk no Provisionamento</Label>
             </div>
          </div>

      {/* MODAL DE PREVIEW MERGE */}
      <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
        <DialogContent className="sm:max-w-[700px] p-0 bg-background border-border/50 overflow-hidden shadow-2xl max-h-[85vh] flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-border bg-card/30">
             <div className="flex items-center gap-3">
               <div className="w-8 h-8 rounded-lg bg-green-500/10 flex items-center justify-center text-green-500 shadow-sm border border-green-500/20">
                 <Shield className="w-4 h-4" />
               </div>
               <div>
                  <DialogTitle className="font-bold text-foreground">Preview: Master Policy Merge</DialogTitle>
                  <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-tight">Estado final materializado no dispositivo</p>
               </div>
             </div>
             <button onClick={() => setIsPreviewOpen(false)} className="text-muted-foreground hover:text-foreground">
               <X className="w-4 h-4" />
             </button>
          </div>

          <div className="p-6 flex-1 overflow-hidden flex flex-col gap-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-[9px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Camadas de Composição</Label>
                <div className="space-y-1">
                  {previewData?.layers_applied.map((layer, idx) => (
                    <div key={idx} className="flex items-center justify-between px-3 py-1.5 rounded bg-muted/30 border border-border/30">
                       <span className="text-[11px] font-medium">{layer.name}</span>
                       <span className="text-[9px] font-mono text-muted-foreground">P:{layer.priority}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                 <Label className="text-[9px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Integridade (SHA-256)</Label>
                 <div className="p-3 rounded bg-secondary/20 border border-border/40 font-mono text-[10px] break-all leading-relaxed">
                   {previewData?.hash}
                 </div>
              </div>
            </div>

            <div className="flex-1 overflow-hidden flex flex-col border border-border/40 rounded-xl">
               <Tabs defaultValue="json" className="flex-1 flex flex-col">
                 <div className="px-4 bg-muted/20 border-b border-border/40">
                   <TabsList className="bg-transparent border-0 h-10 w-full justify-start gap-4">
                      {/* Note: TabsTrigger is renamed from TabsList.Trigger if not exported natively or use standard syntax */}
                      <TabsTrigger value="json" className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none px-0 text-[10px] font-bold uppercase tracking-widest transition-none">JSON Final</TabsTrigger>
                      <TabsTrigger value="summary" className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none px-0 text-[10px] font-bold uppercase tracking-widest transition-none">Resumo Auditoria</TabsTrigger>
                   </TabsList>
                 </div>
                 <TabsContent value="json" className="flex-1 p-0 m-0 overflow-hidden">
                   <ScrollArea className="h-[300px] bg-card/60 p-4">
                      <pre className="text-[11px] font-mono leading-6">
                        {JSON.stringify(previewData?.merged_config, null, 2)}
                      </pre>
                   </ScrollArea>
                 </TabsContent>
                 <TabsContent value="summary" className="flex-1 p-4 m-0 bg-card/60">
                    <div className="space-y-3">
                       <div className="flex items-center justify-between p-3 rounded-lg bg-primary/5 border border-primary/10">
                          <span className="text-xs font-bold">Modo Kiosk Ativo</span>
                          <StatusBadge status={previewData?.merged_config?.kiosk?.enabled ? 'online' : 'offline'} />
                       </div>
                       <div className="flex items-center justify-between p-3 rounded-lg bg-primary/5 border border-primary/10">
                          <span className="text-xs font-bold">Total de Apps Liberados</span>
                          <span className="text-xs font-mono font-bold bg-primary/20 px-2 py-0.5 rounded">{previewData?.merged_config?.allowed_apps?.length || 0}</span>
                       </div>
                       <div className="p-3 rounded-lg bg-yellow-500/5 border border-yellow-500/10 flex items-start gap-3">
                          <AlertCircle className="w-4 h-4 text-yellow-500 shrink-0 mt-0.5" />
                          <p className="text-[11px] text-muted-foreground leading-relaxed">
                            Este preview reflete o **determinismo total** do motor de merge. Qualquer alteração em políticas globais ou de perfil disparará uma re-materialização automática neste dispositivo.
                          </p>
                       </div>
                    </div>
                 </TabsContent>
               </Tabs>
            </div>
          </div>

          <div className="p-4 border-t border-border bg-muted/20 flex justify-end">
             <Button size="sm" onClick={() => setIsPreviewOpen(false)} variant="secondary">Fechar Preview</Button>
          </div>
        </DialogContent>
      </Dialog>

        </DialogContent>
      </Dialog>
    </div>
  );
}
