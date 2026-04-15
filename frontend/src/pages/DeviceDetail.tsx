import { useParams, useNavigate } from 'react-router-dom';
import { useDevice } from '@/hooks/useDevices';
import { TopBar } from '@/components/TopBar';
import { StatusBadge } from '@/components/StatusBadge';
import {
  ArrowLeft, Lock, RotateCw, RefreshCw, Smartphone, Shield,
  Clock, Building2, Hash, Cpu, CheckCircle2, XCircle, AlertCircle, Loader2, Link as LinkIcon, X,
  BatteryCharging, Battery, HardDrive, LayoutGrid, MapPin, 
  ShieldCheck, ShieldAlert, ShieldOff, Activity, History, ListChecks, Terminal
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { cn } from '@/lib/utils';
import { policyV2Service, complianceService, PolicyV2, ComplianceStatus } from '@/services/api';
import { useState, useEffect, useMemo } from 'react';
import { useToast } from '@/hooks/use-toast';
import { useMDMStore } from '@/store/useMDMStore';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';

function ActionButton({
  label,
  icon: Icon,
  action,
  variant = 'default',
  loading,
  onClick,
  disabled
}: {
  label: string;
  icon: React.ElementType;
  action: string;
  variant?: 'default' | 'danger';
  loading: string | null;
  onClick: () => void;
  disabled?: boolean;
}) {
  const isLoading = loading === action;
  return (
    <button
      onClick={onClick}
      disabled={disabled || !!loading}
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-md text-[11px] font-bold uppercase tracking-wider border transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed',
        variant === 'danger'
          ? 'bg-status-locked/10 text-status-locked border-status-locked/30 hover:bg-status-locked/20'
          : 'bg-secondary text-secondary-foreground border-border hover:bg-muted'
      )}
    >
      {isLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Icon className="w-3 h-3" />}
      {label}
    </button>
  );
}

function InfoRow({ label, value, mono }: { label: string; value?: string; mono?: boolean }) {
  return (
    <div className="flex justify-between items-start py-2.5 border-b border-border/50 last:border-0">
      <span className="text-xs text-muted-foreground font-medium">{label}</span>
      <span className={cn('text-xs text-foreground text-right max-w-[60%] font-bold', mono && 'font-mono text-[10px]')}>
        {value || '—'}
      </span>
    </div>
  );
}

export default function DeviceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  
  // ─── MDM Store & Websocket Sync ──────────────────────────────────────────
  const { complianceMap, handleComplianceUpdate } = useMDMStore();
  const { device, telemetry, commands, loading, error, refresh, runAction, actionLoading, actionResult } = useDevice(id!);
  
  // Local state for Policies V2
  const [isPolicyModalOpen, setIsPolicyModalOpen] = useState(false);
  const [availablePolicies, setAvailablePolicies] = useState<PolicyV2[]>([]);
  const [policiesLoading, setPoliciesLoading] = useState(false);
  const [assigningPolicyId, setAssigningPolicyId] = useState<number | null>(null);

  // Compliance State from Store
  const policyState = complianceMap[id!] || device?.compliance_state;

  const fetchAvailablePolicies = async () => {
    setPoliciesLoading(true);
    try {
      const res = await policyV2Service.getAll();
      setAvailablePolicies(res.data);
    } catch (err) {
      toast({ title: 'Erro', description: 'Nao foi possivel carregar politicas.', variant: 'destructive' })
    } finally {
      setPoliciesLoading(false);
    }
  };

  const handleAssignPolicy = async (policyId: number) => {
    if (!id) return;
    setAssigningPolicyId(policyId);
    try {
      await policyV2Service.assignToDevice(id, policyId);
      toast({ title: 'Sucesso', description: 'Política atribuída. O dispositivo será sincronizado.' });
      setIsPolicyModalOpen(false);
      refresh();
    } catch (err) {
      toast({ title: 'Erro', description: 'Falha ao atribuir política.', variant: 'destructive' })
    } finally {
      setAssigningPolicyId(null);
    }
  };

  const handleForceEnforce = async () => {
    if (!id) return;
    try {
      await complianceService.reportState(id, { force: true });
      toast({ title: 'Enforcing...', description: 'Comando de enforcement prioritário enviado.' });
    } catch (err) {
      toast({ title: 'Erro', description: 'Falha ao disparar enforcement.', variant: 'destructive' })
    }
  };

  // ─── Visual Diff Engine ──────────────────────────────────────────────────
  const diffs = useMemo(() => {
    if (!device?.merged_config || !policyState?.last_reported_state) return [];
    
    // Normalização simples para comparação visual
    const desired = device.merged_config.restrictions || {};
    const actual = policyState.last_reported_state.restrictions || {};
    
    return Object.keys(desired).map(key => ({
      key,
      label: key.replace(/_/g, ' '),
      expected: desired[key],
      actual: actual[key],
      isDiff: desired[key] !== actual[key]
    }));
  }, [device, policyState]);

  if (loading) {
    return (
      <div className="animate-fade-in">
        <TopBar title="Carregando..." loading />
        <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="card-glass p-5 h-64 skeleton-shimmer" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !device) {
    return (
      <div className="animate-fade-in p-6 flex flex-col items-center justify-center min-h-[60vh]">
        <AlertCircle className="w-12 h-12 text-status-locked mb-4 opacity-50" />
        <h3 className="text-lg font-bold text-foreground">Dispositivo não encontrado</h3>
        <p className="text-sm text-muted-foreground mt-1 mb-6 text-center max-w-sm">
          Ocorreu um erro ao recuperar os dados deste equipamento: {error}
        </p>
        <button onClick={() => navigate('/devices')} className="flex items-center gap-2 text-sm font-bold text-primary hover:underline">
          <ArrowLeft className="w-4 h-4" /> Voltar para Dispositivos
        </button>
      </div>
    );
  }

  const complianceConfig: Record<ComplianceStatus, { label: string; icon: any; color: string; bg: string }> = {
    compliant: { label: 'Conforme', icon: ShieldCheck, color: 'text-status-online', bg: 'bg-status-online/10 border-status-online/20' },
    enforcing: { label: 'Em Enforcement', icon: Loader2, color: 'text-status-syncing', bg: 'bg-status-syncing/10 border-status-syncing/20' },
    enforcing_partial: { label: 'Parcial', icon: Shield, color: 'text-amber-500', bg: 'bg-amber-500/10 border-amber-500/20' },
    failed_loop: { label: 'LOOP DE FALHA', icon: ShieldAlert, color: 'text-status-locked', bg: 'bg-status-locked/10 border-status-locked/20' },
    unknown: { label: 'Desconhecido', icon: ShieldOff, color: 'text-muted-foreground', bg: 'bg-muted/50 border-border' },
  };

  const status = policyState?.compliance_status || device.compliance_status || 'unknown';
  const compliance = complianceConfig[status as ComplianceStatus] || complianceConfig.unknown;

  return (
    <div className="animate-fade-in bg-background min-h-screen">
      <TopBar
        title={device.name}
        subtitle={`IMEI: ${device.imei} · Android ${device.android_version}`}
        onRefresh={refresh}
        loading={loading}
        connected={!error}
      />

      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Back and Status Row */}
        <div className="flex items-center justify-between">
          <button onClick={() => navigate('/devices')} className="flex items-center gap-2 text-xs font-bold text-muted-foreground hover:text-foreground transition-all uppercase tracking-widest">
            <ArrowLeft className="w-4 h-4" /> Frota
          </button>
          
          <div className={cn("px-4 py-2 rounded-lg border flex items-center gap-3 transition-all", compliance.bg)}>
            <compliance.icon className={cn("w-5 h-5", status === 'enforcing' && 'animate-spin', status === 'failed_loop' && 'animate-pulse')} />
            <div>
               <p className={cn("text-[10px] font-bold uppercase tracking-tighter", compliance.color)}>{compliance.label}</p>
               <p className="text-[9px] text-muted-foreground font-medium">Compliance Engine Fase 3</p>
            </div>
          </div>
        </div>

        {/* Banner de Erro Crítico (FAILED LOOP) */}
        {status === 'failed_loop' && (
           <div className="p-4 bg-status-locked/10 border-2 border-status-locked/30 rounded-xl flex items-center gap-4 animate-in slide-in-from-top-4 duration-500 shadow-xl shadow-status-locked/5">
              <ShieldAlert className="w-8 h-8 text-status-locked animate-bounce" />
              <div className="flex-1">
                 <h4 className="text-sm font-black text-status-locked uppercase tracking-tighter">Estado de Loop de Falha Detectado</h4>
                 <p className="text-xs text-muted-foreground font-medium">
                   O backend suspendeu o enforcement automático para evitar instabilidade. 
                   Verifique os subcomandos que falharam e limite as alterações de política antes de tentar novamente.
                 </p>
              </div>
              <Button variant="destructive" size="sm" onClick={handleForceEnforce} className="font-bold uppercase text-[10px] tracking-widest">
                 Ignorar & Forçar Retry
              </Button>
           </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          
          {/* Summary Card (Left Column) */}
          <div className="lg:col-span-1 space-y-6">
            <div className="card-glass p-6">
              <div className="flex flex-col items-center text-center">
                <div className="w-20 h-20 rounded-3xl bg-secondary flex items-center justify-center mb-4 border border-border/50 shadow-inner">
                   <Smartphone className="w-10 h-10 text-primary" />
                </div>
                <h3 className="text-lg font-bold text-foreground">{device.name}</h3>
                <StatusBadge status={device.status} className="mt-2" />
                
                <div className="grid grid-cols-1 w-full gap-2 mt-8">
                  <ActionButton label="Sincronizar" icon={RefreshCw} action="sync" loading={actionLoading} onClick={() => runAction('sync')} />
                  <ActionButton label="Reiniciar" icon={RotateCw} action="reboot" loading={actionLoading} onClick={() => runAction('reboot')} />
                  <ActionButton label="Lock Screen" icon={Lock} action="lock" loading={actionLoading} onClick={() => runAction('lock')} />
                  <ActionButton label="Atribuir Políticas" icon={LinkIcon} action="apply" loading={actionLoading} onClick={() => { fetchAvailablePolicies(); setIsPolicyModalOpen(true); }} />
                  <ActionButton label="Wipe Dispositivo" icon={AlertCircle} action="wipe" variant="danger" loading={actionLoading} onClick={() => { if(confirm('Factory Reset?')) runAction('wipe') }} />
                </div>
              </div>
            </div>

            <div className="card-glass p-5">
              <h4 className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-4">Informações Técnicas</h4>
              <InfoRow label="ID de Sistema" value={device.id} mono />
              <InfoRow label="IMEI / Serial" value={device.imei} mono />
              <InfoRow label="Versão Android" value={device.android_version} />
              <InfoRow label="Empresa" value={device.company} />
              {device.last_checkin && (
                <div className="mt-4 pt-4 border-t border-border/50">
                   <p className="text-[9px] text-muted-foreground font-bold uppercase tracking-widest mb-1">Visto por último em</p>
                   <p className="text-xs font-bold text-foreground">{format(parseISO(device.last_checkin), "dd/MM/yy 'às' HH:mm:ss", { locale: ptBR })}</p>
                </div>
              )}
            </div>
          </div>

          {/* Main Content (Right Column) */}
          <div className="lg:col-span-3 space-y-6">
             <Tabs defaultValue="geral" className="w-full">
               <TabsList className="bg-secondary/50 border border-border/50 p-1 rounded-xl w-full justify-start space-x-1">
                 <TabsTrigger value="geral" className="text-[10px] font-bold uppercase tracking-widest rounded-lg data-[state=active]:bg-card data-[state=active]:shadow-lg"><Activity className="w-3.5 h-3.5 mr-2" /> Visão Geral</TabsTrigger>
                 <TabsTrigger value="compliance" className="text-[10px] font-bold uppercase tracking-widest rounded-lg data-[state=active]:bg-card data-[state=active]:shadow-lg"><Shield className="w-3.5 h-3.5 mr-2" /> Compliance & Políticas</TabsTrigger>
                 <TabsTrigger value="commands" className="text-[10px] font-bold uppercase tracking-widest rounded-lg data-[state=active]:bg-card data-[state=active]:shadow-lg"><Terminal className="w-3.5 h-3.5 mr-2" /> Comandos</TabsTrigger>
                 <TabsTrigger value="logs" className="text-[10px] font-bold uppercase tracking-widest rounded-lg data-[state=active]:bg-card data-[state=active]:shadow-lg"><History className="w-3.5 h-3.5 mr-2" /> Histórico Auditoria</TabsTrigger>
               </TabsList>

               {/* TAB: VISÃO GERAL */}
               <TabsContent value="geral" className="mt-4 space-y-6 animate-in slide-in-from-right-4 duration-300">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                     {/* Telemetry Grid */}
                     <div className="card-glass p-5">
                        <div className="flex items-center gap-2 mb-6">
                           <Cpu className="w-4 h-4 text-primary" />
                           <h3 className="text-sm font-bold uppercase tracking-tight">Telemetria RealTime</h3>
                        </div>
                        {telemetry ? (
                           <div className="grid grid-cols-2 gap-8">
                             <div className="space-y-1">
                               <p className="text-[9px] font-bold text-muted-foreground uppercase">Energia</p>
                               <div className="flex items-center gap-2 text-2xl font-black text-foreground">
                                 {telemetry.battery_level}%
                                 {telemetry.is_charging ? <BatteryCharging className="w-5 h-5 text-status-syncing animate-pulse" /> : <Battery className="w-5 h-5" />}
                               </div>
                             </div>
                             <div className="space-y-1">
                               <p className="text-[9px] font-bold text-muted-foreground uppercase">Armazenamento Livre</p>
                               <div className="flex items-center gap-2 text-2xl font-black text-foreground">
                                 {Math.floor((telemetry.free_disk_space_mb || 0) / 1024)} <span className="text-xs font-medium text-muted-foreground">GB</span>
                               </div>
                             </div>
                             <div className="col-span-2 p-3 bg-muted/40 rounded-xl border border-border/50">
                                <p className="text-[9px] font-bold text-muted-foreground uppercase mb-2">App em Atividade</p>
                                <p className="text-xs font-mono font-bold text-primary truncate">{telemetry.foreground_app || 'Nenhum app detectado'}</p>
                             </div>
                           </div>
                        ) : (
                           <div className="py-10 text-center opacity-40">
                              <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
                              <p className="text-xs font-medium tracking-widest uppercase">Aguardando Check-in do Agente...</p>
                           </div>
                        )}
                     </div>

                     {/* Location Snapshot */}
                     <div className="card-glass p-0 overflow-hidden relative min-h-[220px]">
                        <div className="absolute top-4 left-4 z-10 flex items-center gap-2 bg-background/90 backdrop-blur-md px-3 py-1.5 rounded-full border border-border shadow-lg">
                           <MapPin className="w-3.5 h-3.5 text-status-online" />
                           <span className="text-[10px] font-bold uppercase tracking-tight">Geo-Posicionamento</span>
                        </div>
                        <div className="w-full h-full bg-muted/20 flex items-center justify-center">
                           {telemetry?.location ? (
                              <div className="text-center p-8 bg-card/40 rounded-3xl border border-border backdrop-blur-sm">
                                 <p className="text-xl font-black text-foreground">{telemetry.location.latitude.toFixed(6)}, {telemetry.location.longitude.toFixed(6)}</p>
                                 <p className="text-[10px] font-medium text-muted-foreground mt-2 uppercase tracking-widest">Coordenadas reportadas por GPS</p>
                              </div>
                           ) : (
                              <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">GPS Desativado ou Sem Sinal</p>
                           )}
                        </div>
                     </div>
                  </div>

                  {/* App List Snapshot */}
                  <div className="card-glass p-5">
                     <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-2">
                           <LayoutGrid className="w-4 h-4 text-primary" />
                           <h3 className="text-sm font-bold uppercase tracking-tight">Inventário de Apps</h3>
                        </div>
                        <Badge variant="outline" className="text-[10px] font-mono px-3">{telemetry?.installed_apps?.length || 0} instalados</Badge>
                     </div>
                     <ScrollArea className="h-48 rounded-xl border border-border/30 p-2 bg-muted/10">
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                          {telemetry?.installed_apps?.map((app: string, idx: number) => (
                            <div key={idx} className="p-2 bg-card rounded-md border border-border/50 text-[10px] font-medium truncate flex items-center gap-2">
                               <div className="w-1.5 h-1.5 rounded-full bg-secondary" />
                               {app}
                            </div>
                          ))}
                        </div>
                     </ScrollArea>
                  </div>
               </TabsContent>

               {/* TAB: COMPLIANCE & POLÍTICAS VC FIX */}
               <TabsContent value="compliance" className="mt-4 space-y-6 animate-in slide-in-from-right-8 duration-500">
                  <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                     
                     {/* Visual Diff Engine (Desired vs Actual) */}
                     <div className="xl:col-span-2 card-glass p-5">
                        <div className="flex items-center justify-between mb-6 border-b border-border/50 pb-4">
                           <div className="flex items-center gap-2">
                              <ShieldCheck className="w-4 h-4 text-primary" />
                              <h3 className="text-sm font-bold uppercase tracking-tight">Desired vs Actual State</h3>
                           </div>
                           <Button 
                             size="sm" 
                             variant="secondary" 
                             onClick={handleForceEnforce} 
                             className="text-[9px] h-7 font-black tracking-widest uppercase"
                           >
                             Force Engine Check
                           </Button>
                        </div>
                        
                        <div className="space-y-3">
                           {diffs.length > 0 ? diffs.map((diff) => (
                             <div key={diff.key} className={cn(
                               "flex items-center justify-between p-3 rounded-xl border transition-all",
                               diff.isDiff ? "bg-status-locked/5 border-status-locked/30" : "bg-muted/30 border-border/50"
                             )}>
                                <div className="flex items-center gap-3">
                                   <div className={cn("p-2 rounded-lg", diff.isDiff ? "bg-status-locked/20" : "bg-status-online/20")}>
                                      {diff.isDiff ? <ShieldAlert className="w-3.5 h-3.5 text-status-locked" /> : <ShieldCheck className="w-3.5 h-3.5 text-status-online" />}
                                   </div>
                                   <span className="text-xs font-bold capitalize text-foreground">{diff.label}</span>
                                </div>
                                <div className="flex items-center gap-6">
                                   <div className="text-center">
                                      <p className="text-[8px] font-black uppercase text-muted-foreground">Esperado</p>
                                      <p className="text-[10px] font-mono font-bold text-foreground">{JSON.stringify(diff.expected)}</p>
                                   </div>
                                   <div className="w-4 h-px bg-border/50" />
                                   <div className="text-center">
                                      <p className="text-[8px] font-black uppercase text-muted-foreground">Reportado</p>
                                      <p className={cn("text-[10px] font-mono font-bold", diff.isDiff ? "text-status-locked" : "text-status-online")}>
                                         {JSON.stringify(diff.actual)}
                                      </p>
                                   </div>
                                </div>
                             </div>
                           )) : (
                             <div className="py-12 text-center border-2 border-dashed border-border rounded-2xl">
                                <ShieldOff className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-20" />
                                <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Sem policies merged disponíveis para comparação.</p>
                             </div>
                           )}
                        </div>
                     </div>

                     {/* Policy Audit & Failed Subcommands */}
                     <div className="space-y-6">
                        <div className="card-glass p-5">
                           <div className="flex items-center gap-2 mb-4 text-status-locked">
                              <AlertCircle className="w-4 h-4" />
                              <h3 className="text-xs font-black uppercase tracking-widest">Subcomandos em Falha</h3>
                           </div>
                           <div className="space-y-2">
                             {policyState?.failed_subcommands && policyState.failed_subcommands.length > 0 ? (
                               policyState.failed_subcommands.map((cmd: string, i: number) => (
                                 <div key={i} className="p-2 bg-status-locked/10 border border-status-locked/30 rounded-lg text-[9px] font-mono font-bold text-status-locked flex items-center gap-2">
                                    <XCircle className="w-3 h-3" /> {cmd}
                                 </div>
                               ))
                             ) : (
                               <div className="p-8 text-center bg-secondary/20 rounded-xl border border-dashed border-border">
                                  <CheckCircle2 className="w-5 h-5 text-status-online mx-auto mb-2 opacity-40" />
                                  <p className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest">Zero Falhas Críticas</p>
                               </div>
                             )}
                           </div>
                        </div>

                        <div className="card-glass p-5">
                           <h4 className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-4">Metadata de Compliance</h4>
                           <InfoRow label="Drift Score" value={policyState?.drift_score?.toString() || '0'} />
                           <InfoRow label="Policy Hash (Expected)" value={policyState?.effective_policy_hash?.slice(0, 12)} mono />
                           <InfoRow label="State Hash (Reported)" value={policyState?.state_hash?.slice(0, 12)} mono />
                           {policyState?.updated_at && (
                             <div className="mt-4 pt-4 border-t border-border/50">
                                <p className="text-[8px] font-black text-muted-foreground uppercase tracking-widest mb-1">Último Cálculo</p>
                                <p className="text-[10px] font-bold text-foreground">{format(parseISO(policyState.updated_at), "HH:mm:ss 'do dia' dd/MM/yy", { locale: ptBR })}</p>
                             </div>
                           )}
                        </div>
                     </div>
                  </div>
               </TabsContent>

               {/* TAB: COMANDOS */}
               <TabsContent value="commands" className="mt-4 animate-in slide-in-from-bottom-4 duration-500">
                  <div className="card-glass p-0 overflow-hidden">
                     <div className="p-5 border-b border-border bg-muted/20 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                           <Terminal className="w-4 h-4 text-primary" />
                           <h3 className="text-sm font-bold uppercase tracking-tight">Fila de Comandos</h3>
                        </div>
                     </div>
                     <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                           <thead className="bg-muted/30 border-b border-border">
                              <tr>
                                 <th className="px-5 py-3 text-left font-bold uppercase tracking-widest text-muted-foreground">Comando</th>
                                 <th className="px-5 py-3 text-left font-bold uppercase tracking-widest text-muted-foreground">Status</th>
                                 <th className="px-5 py-3 text-left font-bold uppercase tracking-widest text-muted-foreground">Criação</th>
                                 <th className="px-5 py-3 text-left font-bold uppercase tracking-widest text-muted-foreground">Modificação</th>
                                 <th className="px-5 py-3 text-left font-bold uppercase tracking-widest text-muted-foreground">Latência</th>
                                 <th className="px-5 py-3 text-left font-bold uppercase tracking-widest text-muted-foreground">Erro</th>
                              </tr>
                           </thead>
                           <tbody className="divide-y divide-border/30">
                             {commands && commands.length > 0 ? commands.map((cmd: any) => (
                               <tr key={cmd.id} className="hover:bg-muted/20 transition-colors">
                                  <td className="px-5 py-3 font-mono font-bold">{cmd.command_type}</td>
                                  <td className="px-5 py-3">
                                     <Badge variant="outline" className={cn(
                                       "font-bold text-[9px]",
                                       cmd.status === 'EXECUTED' || cmd.status === 'ACKED' ? "text-status-online border-status-online/50" :
                                       cmd.status === 'FAILED' ? "text-status-locked border-status-locked/50" :
                                       cmd.status === 'DISPATCHED' ? "text-status-syncing border-status-syncing/50" : ""
                                     )}>
                                        {cmd.status === 'PENDING' && 'Pendente'}
                                        {cmd.status === 'DISPATCHED' && 'Enviado'}
                                        {cmd.status === 'EXECUTED' && 'Executado'}
                                        {cmd.status === 'ACKED' && 'Confirmado'}
                                        {cmd.status === 'FAILED' && 'Falhou'}
                                        {(!['PENDING', 'DISPATCHED', 'EXECUTED', 'ACKED', 'FAILED'].includes(cmd.status)) && cmd.status}
                                     </Badge>
                                  </td>
                                  <td className="px-5 py-3 text-muted-foreground">{cmd.created_at ? format(parseISO(cmd.created_at), 'HH:mm:ss dd/MM', { locale: ptBR }) : '-'}</td>
                                  <td className="px-5 py-3 text-muted-foreground">{cmd.executed_at ? format(parseISO(cmd.executed_at), 'HH:mm:ss dd/MM', { locale: ptBR }) : cmd.dispatched_at ? format(parseISO(cmd.dispatched_at), 'HH:mm:ss dd/MM', { locale: ptBR }) : '-'}</td>
                                  <td className="px-5 py-3 font-mono text-[10px]">
                                     {cmd.execution_latency != null ? `${cmd.execution_latency.toFixed(1)}s` : '-'}
                                  </td>
                                  <td className="px-5 py-3">
                                     {cmd.error_message ? <span className="text-status-locked truncate max-w-[150px] block" title={cmd.error_message}>{cmd.error_message}</span> : <span className="text-muted-foreground opacity-50">-</span>}
                                  </td>
                               </tr>
                             )) : (
                               <tr>
                                  <td colSpan={6} className="px-5 py-10 text-center text-muted-foreground font-medium">Nenhum comando na fila</td>
                               </tr>
                             )}
                           </tbody>
                        </table>
                     </div>
                  </div>
               </TabsContent>

               {/* TAB: AUDITORIA / LOGS */}
               <TabsContent value="logs" className="mt-4 animate-in slide-in-from-bottom-4 duration-500">
                  <div className="card-glass p-0 overflow-hidden">
                     <div className="p-5 border-b border-border bg-muted/20 flex items-center gap-2">
                        <History className="w-4 h-4 text-primary" />
                        <h3 className="text-sm font-bold uppercase tracking-tight">Histórico Completo de Eventos</h3>
                     </div>
                     <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                           <thead className="bg-muted/30 border-b border-border">
                              <tr>
                                 <th className="px-5 py-3 text-left font-bold uppercase tracking-widest text-muted-foreground">Tipo</th>
                                 <th className="px-5 py-3 text-left font-bold uppercase tracking-widest text-muted-foreground">Evento</th>
                                 <th className="px-5 py-3 text-left font-bold uppercase tracking-widest text-muted-foreground">Data/Hora</th>
                                 <th className="px-5 py-3 text-left font-bold uppercase tracking-widest text-muted-foreground">Gravidade</th>
                              </tr>
                           </thead>
                           <tbody className="divide-y divide-border/30">
                             {device.events?.map((event) => (
                               <tr key={event.id} className="hover:bg-muted/20 transition-colors">
                                  <td className="px-5 py-3"><Badge variant="outline" className="font-mono text-[9px]">{event.type}</Badge></td>
                                  <td className="px-5 py-3 font-medium">{event.message}</td>
                                  <td className="px-5 py-3 text-muted-foreground">{event.timestamp ? format(parseISO(event.timestamp), 'dd/MM/yy HH:mm:ss') : '-'}</td>
                                  <td className="px-5 py-3">
                                     <div className={cn(
                                       "w-2 h-2 rounded-full",
                                       event.severity === 'error' ? 'bg-status-locked shadow-[0_0_8px_rgba(239,68,68,0.5)]' :
                                       event.severity === 'warning' ? 'bg-status-syncing' : 'bg-status-online'
                                     )} />
                                  </td>
                               </tr>
                             ))}
                           </tbody>
                        </table>
                     </div>
                  </div>
               </TabsContent>
             </Tabs>
          </div>
        </div>
      </div>

      {/* NEW POLICY ASSIGNMENT MODAL (V2) */}
      {isPolicyModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-background/95 backdrop-blur-md animate-in fade-in duration-300 p-4">
          <div className="bg-card w-full max-w-2xl rounded-2xl border border-border shadow-[0_0_100px_rgba(0,0,0,0.5)] overflow-hidden scale-in-center">
            <div className="flex items-center justify-between p-6 border-b border-border bg-muted/20">
              <div className="flex items-center gap-3">
                 <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/30 flex items-center justify-center text-primary">
                    <ListChecks className="w-5 h-5" />
                 </div>
                 <div>
                    <h2 className="text-lg font-black text-foreground uppercase tracking-tighter">Atribuir Políticas Enterprise</h2>
                    <p className="text-[10px] text-muted-foreground font-bold uppercase tracking-widest">Selecione políticas V2 para este endpoint</p>
                 </div>
              </div>
              <button onClick={() => setIsPolicyModalOpen(false)} className="w-10 h-10 rounded-full hover:bg-muted transition-colors flex items-center justify-center">
                <X className="w-5 h-5 text-muted-foreground" />
              </button>
            </div>
            
            <div className="p-6 max-h-[60vh] overflow-y-auto space-y-4">
              {policiesLoading ? (
                <div className="flex flex-col items-center justify-center py-20">
                  <Loader2 className="w-12 h-12 animate-spin text-primary opacity-20 mb-4" />
                  <span className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground">Varrendo Repositório...</span>
                </div>
              ) : availablePolicies.length > 0 ? (
                availablePolicies.map((p) => (
                  <div key={p.id} className="group p-4 border border-border rounded-2xl bg-secondary/30 hover:bg-primary/5 hover:border-primary/40 transition-all flex items-center justify-between shadow-sm">
                    <div className="flex items-center gap-4">
                       <div className="w-10 h-10 rounded-xl bg-card border border-border group-hover:border-primary/20 flex items-center justify-center">
                          <Shield className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
                       </div>
                       <div>
                          <h4 className="text-sm font-black text-foreground">{p.name}</h4>
                          <div className="flex items-center gap-2 mt-1">
                             <Badge variant="outline" className="text-[8px] h-4 font-mono uppercase px-1.5">{p.scope}</Badge>
                             <span className="text-[9px] font-bold text-muted-foreground uppercase opacity-50">Priority: {p.priority}</span>
                          </div>
                       </div>
                    </div>
                    <Button
                      size="sm"
                      disabled={assigningPolicyId === p.id}
                      onClick={() => handleAssignPolicy(p.id)}
                      className="h-8 text-[10px] font-black uppercase tracking-widest px-4 shadow-lg shadow-primary/20"
                    >
                      {assigningPolicyId === p.id ? 'Vinculando...' : 'Atribuir'}
                    </Button>
                  </div>
                ))
              ) : (
                <div className="text-center py-20 p-10 border-2 border-dashed border-border rounded-3xl">
                   <ShieldOff className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-10" />
                   <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Nenhuma política V2 compatível encontrada.</p>
                </div>
              )}
            </div>
            
            <div className="p-6 bg-muted/30 border-t border-border flex items-center justify-between">
               <p className="text-[10px] text-muted-foreground italic font-medium">As políticas serão mescladas pela Engine no próximo check-in.</p>
               <Button variant="ghost" size="sm" onClick={() => setIsPolicyModalOpen(false)} className="text-[10px] font-black uppercase tracking-widest">Fechar</Button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
