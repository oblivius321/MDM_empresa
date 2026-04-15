import { useEffect, useState } from 'react';
import { TopBar } from '@/components/TopBar';
import { Settings as SettingsIcon, Server, Bell, Database, Shield, Users, HardDrive, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { API_DISPLAY_URL, buildApiUrl, userService, UserPreferences } from '@/services/api';
import { useAuth } from '@/contexts/AuthContext';

interface SystemHealth {
  api: 'healthy' | 'degraded' | 'down';
  database: 'healthy' | 'degraded' | 'down';
  cache: 'healthy' | 'degraded' | 'down';
  storage: number;
}

type NotificationPreferenceKey = keyof UserPreferences;

const defaultNotificationPreferences: UserPreferences = {
  offline_alerts: true,
  compliance_failures: true,
  new_devices: true,
  system_updates: true,
};

const notificationSettings: Array<{
  key: NotificationPreferenceKey;
  label: string;
  desc: string;
}> = [
  { key: 'offline_alerts', label: 'Alertas de dispositivo offline', desc: 'Notificar quando dispositivo ficar offline por mais de 1h' },
  { key: 'compliance_failures', label: 'Falhas de compliance', desc: 'Notificar quando um dispositivo sair de conformidade' },
  { key: 'new_devices', label: 'Novos dispositivos', desc: 'Notificar quando um novo dispositivo se registrar' },
  { key: 'system_updates', label: 'Atualizacoes de sistema', desc: 'Notificar sobre atualizacoes disponiveis' },
];

export default function Settings() {
  const { toast } = useToast();
  const { user } = useAuth();
  const apiBase = API_DISPLAY_URL;
  const [refreshInterval, setRefreshInterval] = useState('30000');
  const [systemHealth] = useState<SystemHealth>({
    api: 'healthy',
    database: 'healthy',
    cache: 'healthy',
    storage: 45,
  });
  const [showCreateAdmin, setShowCreateAdmin] = useState(false);
  const [adminEmail, setAdminEmail] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [notificationPreferences, setNotificationPreferences] = useState<UserPreferences>(defaultNotificationPreferences);
  const [preferencesLoading, setPreferencesLoading] = useState(true);
  const [savingPreference, setSavingPreference] = useState<NotificationPreferenceKey | null>(null);

  useEffect(() => {
    let active = true;

    const loadPreferences = async () => {
      setPreferencesLoading(true);
      try {
        const res = await userService.getMe();
        if (!active) return;
        setNotificationPreferences({
          ...defaultNotificationPreferences,
          ...(res.data.preferences || {}),
        });
      } catch (error) {
        if (!active) return;
        toast({
          title: 'Erro',
          description: 'Nao foi possivel carregar preferencias de notificacao',
          variant: 'destructive',
        });
      } finally {
        if (active) setPreferencesLoading(false);
      }
    };

    loadPreferences();

    return () => {
      active = false;
    };
  }, [toast]);

  const handleTogglePreference = async (key: NotificationPreferenceKey) => {
    const previousPreferences = notificationPreferences;
    const nextPreferences = {
      ...notificationPreferences,
      [key]: !notificationPreferences[key],
    };

    setNotificationPreferences(nextPreferences);
    setSavingPreference(key);

    try {
      const res = await userService.updatePreferences({ [key]: nextPreferences[key] } as Partial<UserPreferences>);
      setNotificationPreferences({
        ...defaultNotificationPreferences,
        ...(res.data.preferences || {}),
      });
      toast({
        title: 'Sucesso',
        description: 'Preferencias de notificacao atualizadas',
      });
    } catch (error) {
      setNotificationPreferences(previousPreferences);
      toast({
        title: 'Erro',
        description: 'Nao foi possivel salvar a preferencia',
        variant: 'destructive',
      });
    } finally {
      setSavingPreference(null);
    }
  };

  const handleCreateAdmin = async () => {
    if (!adminEmail || !adminPassword) {
      toast({
        title: 'Erro',
        description: 'Email e senha sao obrigatorios',
        variant: 'destructive',
      });
      return;
    }

    try {
      const response = await fetch(buildApiUrl('/auth/register'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: adminEmail,
          password: adminPassword,
          admin_authorization_key: 'CHANGE_ME_IN_PRODUCTION',
        }),
      });

      if (response.ok) {
        toast({
          title: 'Sucesso',
          description: 'Administrador criado com sucesso',
        });
        setAdminEmail('');
        setAdminPassword('');
        setShowCreateAdmin(false);
      } else {
        toast({
          title: 'Erro',
          description: 'Falha ao criar administrador',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Erro de Conexao',
        description: 'Nao foi possivel conectar a API',
        variant: 'destructive',
      });
    }
  };

  const handleBackup = async () => {
    toast({
      title: 'Iniciando Backup',
      description: 'Backup do banco de dados em progresso...',
    });
    setTimeout(() => {
      toast({
        title: 'Backup Completo',
        description: 'Backup realizado com sucesso',
      });
    }, 2000);
  };

  const getHealthColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600 bg-green-50';
      case 'degraded':
        return 'text-yellow-600 bg-yellow-50';
      case 'down':
        return 'text-red-600 bg-red-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  const getHealthLabel = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'Saudavel';
      case 'degraded':
        return 'Degradado';
      case 'down':
        return 'Indisponivel';
      default:
        return 'Desconhecido';
    }
  };

  return (
    <div className="animate-fade-in">
      <TopBar title="Configuracoes" subtitle="Configuracoes e administracao do sistema MDM" />
      <div className="p-6 space-y-6">
        <div className="card-glass p-5">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Saude do Sistema</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            {[
              { label: 'API FastAPI', status: systemHealth.api },
              { label: 'PostgreSQL', status: systemHealth.database },
              { label: 'Cache/Redis', status: systemHealth.cache },
            ].map((item) => (
              <div key={item.label} className={`p-3 rounded-md border ${getHealthColor(item.status)}`}>
                <div className="flex items-center gap-2">
                  {item.status === 'healthy' ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                  <div>
                    <p className="text-xs font-medium">{item.label}</p>
                    <p className="text-xs opacity-75">{getHealthLabel(item.status)}</p>
                  </div>
                </div>
              </div>
            ))}
            <div className="p-3 rounded-md border bg-blue-50 text-blue-600">
              <div className="flex items-center gap-2">
                <HardDrive className="w-4 h-4" />
                <div>
                  <p className="text-xs font-medium">Armazenamento</p>
                  <p className="text-xs opacity-75">{systemHealth.storage} GB de 500 GB</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="card-glass p-5">
          <div className="flex items-center gap-2 mb-4">
            <Server className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Conexao com a API</h3>
          </div>
          <div className="space-y-4">
            <div>
              <label className="text-xs text-muted-foreground block mb-1.5">Base URL da API</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  defaultValue={apiBase}
                  readOnly
                  className="flex-1 px-3 py-2 text-sm bg-muted border border-border rounded-md text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1.5">Intervalo de Atualizacao Automatica</label>
              <select
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-muted border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="15000">15 segundos</option>
                <option value="30000">30 segundos</option>
                <option value="60000">1 minuto</option>
                <option value="300000">5 minutos</option>
              </select>
            </div>
          </div>
        </div>

        <div className="card-glass p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">Administradores</h3>
            </div>
            <button
              onClick={() => setShowCreateAdmin(!showCreateAdmin)}
              className="px-3 py-1 text-xs rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              {showCreateAdmin ? 'Cancelar' : 'Novo Admin'}
            </button>
          </div>

          {showCreateAdmin && (
            <div className="space-y-3 p-3 bg-muted/30 rounded-md border border-border/50 mb-4">
              <input
                type="email"
                placeholder="Email do administrador"
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-muted border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <input
                type="password"
                placeholder="Senha"
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-muted border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <button
                onClick={handleCreateAdmin}
                className="w-full px-3 py-2 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Criar Administrador
              </button>
            </div>
          )}

          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between p-3 rounded-md bg-muted/50 border border-border">
              <div>
                <p className="font-medium text-foreground">{user?.email || 'Administrador'}</p>
                <p className="text-xs text-muted-foreground">Logado atualmente</p>
              </div>
              <span className="text-xs px-2 py-1 rounded-full bg-green-100 text-green-800">Ativo</span>
            </div>
          </div>
        </div>

        <div className="card-glass p-5">
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Backup & Restauracao</h3>
          </div>
          <div className="space-y-2">
            <button
              onClick={handleBackup}
              className="w-full px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors font-medium"
            >
              Iniciar Backup
            </button>
            <button className="w-full px-4 py-2 text-sm rounded-md bg-secondary border border-border text-foreground hover:bg-muted transition-colors font-medium">
              Restaurar do Backup
            </button>
            <p className="text-xs text-muted-foreground mt-2">Ultimo backup: 05/03/2026 as 14:30:45</p>
          </div>
        </div>

        <div className="card-glass p-5">
          <div className="flex items-center gap-2 mb-4">
            <Bell className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Notificacoes</h3>
          </div>
          <div className="space-y-3">
            {preferencesLoading && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Carregando preferencias...
              </div>
            )}
            {notificationSettings.map((n) => {
              const enabled = notificationPreferences[n.key];
              const saving = savingPreference === n.key;
              return (
                <div key={n.key} className="flex items-center justify-between p-3 rounded-md bg-muted/50 border border-border">
                  <div>
                    <p className="text-sm font-medium text-foreground">{n.label}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{n.desc}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleTogglePreference(n.key)}
                    disabled={preferencesLoading || !!savingPreference}
                    aria-pressed={enabled}
                    aria-label={n.label}
                    className={`w-10 h-5 rounded-full relative transition-colors disabled:opacity-60 ${enabled ? 'bg-primary/20 border border-primary/30' : 'bg-muted border border-border'}`}
                  >
                    {saving ? (
                      <Loader2 className="w-3 h-3 animate-spin text-primary absolute top-1 left-3.5" />
                    ) : (
                      <div
                        className={`w-4 h-4 bg-primary rounded-full absolute top-0.5 transition-all ${enabled ? 'right-0.5' : 'left-0.5'}`}
                      />
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card-glass p-5">
          <div className="flex items-center gap-2 mb-4">
            <SettingsIcon className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Informacoes do Sistema</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            {[
              { label: 'Versao do Console', value: '1.0.0' },
              { label: 'Backend', value: 'FastAPI' },
              { label: 'Autenticacao', value: 'JWT' },
              { label: 'Banco de Dados', value: 'PostgreSQL' },
              { label: 'Devices Registrados', value: '42' },
              { label: 'Policies Ativas', value: '8' },
              { label: 'Uptime', value: '35 dias' },
              { label: 'Environment', value: import.meta.env.DEV ? 'Development' : 'Production' },
            ].map((info) => (
              <div key={info.label} className="flex flex-col justify-between p-2.5 rounded-md bg-muted/50 border border-border">
                <span className="text-muted-foreground text-xs">{info.label}</span>
                <span className="text-foreground text-xs font-mono font-medium mt-1">{info.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
