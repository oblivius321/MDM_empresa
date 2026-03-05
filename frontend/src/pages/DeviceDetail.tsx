import { useParams, useNavigate } from 'react-router-dom';
import { useDevice } from '@/hooks/useDevices';
import { TopBar } from '@/components/TopBar';
import { StatusBadge } from '@/components/StatusBadge';
import {
  ArrowLeft, Lock, RotateCw, RefreshCw, Smartphone, Shield,
  Clock, Building2, Hash, Cpu, CheckCircle2, XCircle, AlertCircle, Loader2, Link as LinkIcon, X,
  BatteryCharging, Battery, HardDrive, LayoutGrid, MapPin
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { cn } from '@/lib/utils';
import { policyService, Policy } from '@/services/api';
import { useState, useEffect } from 'react';
import { useToast } from '@/hooks/use-toast';

function ActionButton({
  label,
  icon: Icon,
  action,
  variant = 'default',
  loading,
  onClick,
}: {
  label: string;
  icon: React.ElementType;
  action: string;
  variant?: 'default' | 'danger';
  loading: string | null;
  onClick: () => void;
}) {
  const isLoading = loading === action;
  return (
    <button
      onClick={onClick}
      disabled={!!loading}
      className={cn(
        'flex items-center gap-2 px-4 py-2.5 rounded-md text-sm font-medium border transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed',
        variant === 'danger'
          ? 'bg-status-locked/10 text-status-locked border-status-locked/30 hover:bg-status-locked/20'
          : 'bg-secondary text-secondary-foreground border-border hover:bg-muted'
      )}
    >
      {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Icon className="w-4 h-4" />}
      {label}
    </button>
  );
}

function InfoRow({ label, value, mono }: { label: string; value?: string; mono?: boolean }) {
  return (
    <div className="flex justify-between items-start py-2.5 border-b border-border/50 last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={cn('text-sm text-foreground text-right max-w-[60%]', mono && 'font-mono text-xs')}>
        {value || '—'}
      </span>
    </div>
  );
}

export default function DeviceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { device, telemetry, loading, error, refresh, runAction, actionLoading, actionResult } = useDevice(id!);

  // Modal State
  const [isPolicyModalOpen, setIsPolicyModalOpen] = useState(false);
  const [availablePolicies, setAvailablePolicies] = useState<Policy[]>([]);
  const [policiesLoading, setPoliciesLoading] = useState(false);
  const [assigningPolicyId, setAssigningPolicyId] = useState<string | null>(null);

  const openPolicyModal = async () => {
    setIsPolicyModalOpen(true);
    setPoliciesLoading(true);
    try {
      const res = await policyService.getAll();
      setAvailablePolicies(res.data);
    } catch (err) {
      toast({ title: 'Erro', description: 'Nao foi possivel carregar politicas.', variant: 'destructive' })
    } finally {
      setPoliciesLoading(false);
    }
  };

  const handleAssignPolicy = async (policy: Policy) => {
    if (!id) return;
    setAssigningPolicyId(policy.id);
    try {
      // Re-use api signature to assign full policy data directly to device target (Android requirement)
      await policyService.apply(id, policy);
      toast({ title: 'Atribuído', description: `Política ${policy.name} enviada ao dispositivo.` });
      setIsPolicyModalOpen(false);
      setTimeout(refresh, 2000);
    } catch (err) {
      toast({ title: 'Erro', description: 'Nao foi possivel atribuir politica.', variant: 'destructive' })
    } finally {
      setAssigningPolicyId(null);
    }
  };

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
      <div className="animate-fade-in p-6">
        <button
          onClick={() => navigate('/devices')}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Voltar para Dispositivos
        </button>
        <div className="card-glass p-8 text-center">
          <AlertCircle className="w-10 h-10 text-status-locked mx-auto mb-3" />
          <p className="text-foreground font-medium">Dispositivo não encontrado</p>
          <p className="text-sm text-muted-foreground mt-1">{error}</p>
        </div>
      </div>
    );
  }

  const complianceConfig = {
    compliant: { label: 'Compliant', icon: CheckCircle2, color: 'text-status-online' },
    non_compliant: { label: 'Não Conforme', icon: XCircle, color: 'text-status-locked' },
    unknown: { label: 'Desconhecido', icon: AlertCircle, color: 'text-muted-foreground' },
  };
  const compliance = complianceConfig[device.compliance_status || 'unknown'];

  return (
    <div className="animate-fade-in">
      <TopBar
        title={device.name}
        subtitle={`ID: ${device.id} · IMEI: ${device.imei}`}
        onRefresh={refresh}
        loading={loading}
        connected={!error}
      />

      <div className="p-6 space-y-6">
        {/* Back */}
        <button
          onClick={() => navigate('/devices')}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Voltar para Dispositivos
        </button>

        {/* Action Result Toast */}
        {actionResult && (
          <div className={cn(
            'flex items-center gap-3 px-4 py-3 rounded-md border text-sm animate-fade-in',
            actionResult.success
              ? 'bg-status-online/10 border-status-online/30 text-status-online'
              : 'bg-status-locked/10 border-status-locked/30 text-status-locked'
          )}>
            {actionResult.success ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
            {actionResult.message}
          </div>
        )}

        {/* Header Card */}
        <div className="card-glass p-5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
              <Smartphone className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">{device.name}</h2>
              <div className="flex items-center gap-3 mt-1">
                <StatusBadge status={device.status} />
                <span className="text-xs text-muted-foreground">{device.model || 'Modelo desconhecido'}</span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-wrap gap-2">
            <ActionButton
              label="Sincronizar"
              icon={RefreshCw}
              action="sync"
              loading={actionLoading}
              onClick={() => runAction('sync')}
            />
            <ActionButton
              label="Reiniciar"
              icon={RotateCw}
              action="reboot"
              loading={actionLoading}
              onClick={() => runAction('reboot')}
            />
            <ActionButton
              label="Bloquear"
              icon={Lock}
              action="lock"
              variant="danger"
              loading={actionLoading}
              onClick={() => runAction('lock')}
            />
            <ActionButton
              label="Atribuir Política"
              icon={LinkIcon}
              action="apply_policy"
              loading={actionLoading}
              onClick={openPolicyModal}
            />
            <ActionButton
              label="Wipe"
              icon={AlertCircle}
              action="wipe"
              variant="danger"
              loading={actionLoading}
              onClick={() => {
                if (window.confirm('Tem certeza que deseja apagar (Factory Reset) este dispositivo?')) {
                  runAction('wipe');
                }
              }}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Device Info */}
          <div className="card-glass p-5">
            <div className="flex items-center gap-2 mb-4">
              <Cpu className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">Informações do Dispositivo</h3>
            </div>
            <div>
              <InfoRow label="ID" value={device.id} mono />
              <InfoRow label="Nome" value={device.name} />
              <InfoRow label="IMEI" value={device.imei} mono />
              <InfoRow label="Modelo" value={device.model} />
              <InfoRow label="Android" value={device.android_version ? `Android ${device.android_version}` : undefined} />
              <InfoRow label="Empresa" value={device.company} />
            </div>

            {/* In-Line Telemetry Highlights */}
            {telemetry && (
              <div className="mt-6 pt-6 border-t border-border/50 grid grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center gap-1.5 mb-1 text-muted-foreground">
                    {telemetry.is_charging ? <BatteryCharging className="w-4 h-4 text-status-syncing" /> : <Battery className="w-4 h-4" />}
                    <span className="text-xs font-semibold">Bateria</span>
                  </div>
                  <div className="text-xl font-bold text-foreground">
                    {telemetry.battery_level !== undefined ? `${telemetry.battery_level}%` : 'N/A'}
                  </div>
                </div>
                <div>
                  <div className="flex items-center gap-1.5 mb-1 text-muted-foreground">
                    <HardDrive className="w-4 h-4" />
                    <span className="text-xs font-semibold">Livre (MB)</span>
                  </div>
                  <div className="text-xl font-bold text-foreground">
                    {telemetry.free_disk_space_mb !== undefined ? Math.floor(telemetry.free_disk_space_mb) : 'N/A'}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Compliance & Last Sync */}
          <div className="card-glass p-5">
            <div className="flex items-center gap-2 mb-4">
              <Shield className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">Status de Compliance</h3>
            </div>
            <div className="flex items-center gap-3 mb-4 p-3 rounded-md bg-muted/50 border border-border">
              <compliance.icon className={cn('w-5 h-5', compliance.color)} />
              <div>
                <p className={cn('text-sm font-semibold', compliance.color)}>{compliance.label}</p>
                <p className="text-xs text-muted-foreground">Status de conformidade atual</p>
              </div>
            </div>

            <div className="flex items-center gap-2 mb-3">
              <Clock className="w-4 h-4 text-primary" />
              <h4 className="text-sm font-semibold text-foreground">Última Sincronização</h4>
            </div>
            {device.last_checkin ? (
              <div className="p-3 rounded-md bg-muted/50 border border-border">
                <p className="text-lg font-bold text-foreground">
                  {format(parseISO(device.last_checkin), 'HH:mm:ss', { locale: ptBR })}
                </p>
                <p className="text-xs text-muted-foreground">
                  {format(parseISO(device.last_checkin), "EEEE, dd 'de' MMMM 'de' yyyy", { locale: ptBR })}
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Sem registros de sincronização</p>
            )}

            {device.company && (
              <>
                <div className="flex items-center gap-2 mt-4 mb-3">
                  <Building2 className="w-4 h-4 text-primary" />
                  <h4 className="text-sm font-semibold text-foreground">Organização</h4>
                </div>
                <p className="text-sm text-foreground px-3 py-2 bg-muted/50 rounded-md border border-border">
                  {device.company}
                </p>
              </>
            )}
          </div>

          {/* Telemetry Details Module */}
          <div className="col-span-1 lg:col-span-3 grid grid-cols-1 lg:grid-cols-2 gap-6 mt-2">

            {/* Location Map Placeholder */}
            <div className="card-glass p-0 overflow-hidden min-h-[250px] relative flex flex-col bg-muted/10">
              <div className="p-4 bg-background/80 backdrop-blur-sm border-b border-border z-10 flex items-center gap-2 absolute top-0 left-0 right-0">
                <MapPin className="w-4 h-4 text-status-online" />
                <h3 className="text-sm font-semibold text-foreground">Última Localização</h3>
              </div>
              <div className="flex-1 flex items-center justify-center p-6 mt-12">
                {telemetry && telemetry.location ? (
                  <div className="text-center">
                    <div className="p-4 rounded-full bg-status-online/10 inline-flex mb-3">
                      <MapPin className="w-8 h-8 text-status-online" />
                    </div>
                    <p className="text-sm font-medium text-foreground">Lat: {telemetry.location.latitude}</p>
                    <p className="text-sm font-medium text-foreground">Lng: {telemetry.location.longitude}</p>
                    <p className="text-xs text-muted-foreground mt-2">
                      Implementar pacote Leaflet/Mapbox para renderização.
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground flex items-center gap-2">
                    <MapPin className="w-4 h-4 opacity-50" />
                    Localização não reportada
                  </p>
                )}
              </div>
            </div>

            {/* Apps Info */}
            <div className="card-glass p-5 flex flex-col max-h-[300px]">
              <div className="flex items-center gap-2 mb-4 shrink-0">
                <LayoutGrid className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-foreground">Aplicativos do Dispositivo</h3>
              </div>

              {telemetry && telemetry.foreground_app && (
                <div className="mb-4 p-3 bg-primary/5 border border-primary/20 rounded-md shrink-0">
                  <p className="text-[10px] text-primary uppercase font-bold mb-1">App em Primeiro Plano</p>
                  <p className="text-sm font-medium text-foreground truncate">{telemetry.foreground_app}</p>
                </div>
              )}

              <div className="flex-1 min-h-0 overflow-y-auto pr-2">
                <p className="text-xs font-bold text-muted-foreground uppercase mb-2">Apps Instalados ({telemetry?.installed_apps?.length || 0})</p>
                {telemetry && telemetry.installed_apps && telemetry.installed_apps.length > 0 ? (
                  <div className="space-y-1.5">
                    {telemetry.installed_apps.map((app: string, idx: number) => (
                      <div key={idx} className="text-xs text-foreground bg-muted/50 p-2 rounded border border-border/50 truncate">
                        {app}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground italic">Nenhuma informação de aplicativos.</p>
                )}
              </div>
            </div>

          </div>

          {/* Policies & Events */}
          <div className="col-span-1 lg:col-span-3 grid grid-cols-1 lg:grid-cols-2 gap-6 mt-2">
            {/* Policies */}
            <div className="card-glass p-5">
              <div className="flex items-center gap-2 mb-4">
                <Shield className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-foreground">Políticas Aplicadas</h3>
              </div>
              {device.policies && device.policies.length > 0 ? (
                <div className="space-y-2">
                  {device.policies.map((policy) => (
                    <div key={policy.id} className="flex items-center justify-between p-2.5 rounded-md bg-muted/50 border border-border">
                      <div>
                        <p className="text-xs font-medium text-foreground">{policy.name}</p>
                        <p className="text-xs text-muted-foreground">{policy.type}</p>
                      </div>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                        {policy.status || 'Ativa'}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Nenhuma política aplicada</p>
              )}
            </div>

            {/* Events */}
            <div className="card-glass p-5">
              <div className="flex items-center gap-2 mb-4">
                <Hash className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-foreground">Histórico de Eventos</h3>
              </div>
              {device.events && device.events.length > 0 ? (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {device.events.map((event) => (
                    <div key={event.id} className="flex items-start gap-2.5 p-2 rounded-md hover:bg-muted/30 transition-colors">
                      <div className={cn(
                        'w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0',
                        event.severity === 'error' ? 'bg-status-locked' :
                          event.severity === 'warning' ? 'bg-status-syncing' : 'bg-status-online'
                      )} />
                      <div className="min-w-0">
                        <p className="text-xs text-foreground">{event.message}</p>
                        <p className="text-xs text-muted-foreground">
                          {event.timestamp ? format(parseISO(event.timestamp), 'dd/MM HH:mm') : ''}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Nenhum evento registrado</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Policy Assignment Modal */}
      {isPolicyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-fade-in p-4">
          <div className="bg-card w-full max-w-lg rounded-xl border border-border shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-border">
              <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
                <LinkIcon className="w-5 h-5 text-primary" />
                Atribuir Política ao Dispositivo
              </h2>
              <button onClick={() => setIsPolicyModalOpen(false)} className="text-muted-foreground hover:text-foreground">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 max-h-[60vh] overflow-y-auto space-y-3">
              {policiesLoading ? (
                <div className="flex flex-col items-center justify-center py-8">
                  <Loader2 className="w-8 h-8 animate-spin text-primary mb-2" />
                  <span className="text-sm text-muted-foreground">Buscando políticas...</span>
                </div>
              ) : availablePolicies.length > 0 ? (
                availablePolicies.map((p) => (
                  <div key={p.id} className="flex flex-col gap-3 p-4 border border-border rounded-lg bg-secondary/30 hover:bg-secondary/60 transition-colors">
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="text-sm font-bold text-foreground">{p.name}</h4>
                        <p className="text-xs text-muted-foreground uppercase">{p.type}</p>
                      </div>
                      <button
                        disabled={assigningPolicyId === p.id}
                        onClick={() => handleAssignPolicy(p)}
                        className="px-3 py-1.5 rounded bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50"
                      >
                        {assigningPolicyId === p.id ? 'Atribuindo...' : 'Atribuir'}
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-6 text-muted-foreground text-sm">Nenhuma política existente para atribuição.</div>
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
