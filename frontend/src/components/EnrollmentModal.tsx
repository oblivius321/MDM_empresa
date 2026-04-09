import { useState, useEffect, useCallback, useRef } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import {
  enrollmentService,
  EnrollmentConfig,
  ProvisioningProfile,
} from '@/services/api';
import {
  X,
  QrCode,
  Clock,
  Shield,
  Copy,
  Check,
  RefreshCw,
  Loader2,
  AlertCircle,
  Smartphone,
  Layers,
  Download,
} from 'lucide-react';

interface EnrollmentModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function EnrollmentModal({ isOpen, onClose }: EnrollmentModalProps) {
  const [step, setStep] = useState<'config' | 'qr'>('config');
  const [profiles, setProfiles] = useState<ProvisioningProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState('');
  const [mode, setMode] = useState<'single' | 'batch'>('single');
  const [maxDevices, setMaxDevices] = useState(1);
  const [ttlMinutes, setTtlMinutes] = useState(15);
  const [enrollmentData, setEnrollmentData] = useState<EnrollmentConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Carregar perfis ao abrir o modal
  useEffect(() => {
    if (isOpen) {
      loadProfiles();
      setStep('config');
      setEnrollmentData(null);
      setError('');
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isOpen]);

  // Countdown timer
  useEffect(() => {
    if (enrollmentData?.expires_at) {
      const updateCountdown = () => {
        const now = Date.now();
        const expires = new Date(enrollmentData.expires_at).getTime();
        const remaining = Math.max(0, Math.floor((expires - now) / 1000));
        setCountdown(remaining);
        if (remaining <= 0 && timerRef.current) {
          clearInterval(timerRef.current);
        }
      };

      updateCountdown();
      timerRef.current = setInterval(updateCountdown, 1000);
      return () => {
        if (timerRef.current) clearInterval(timerRef.current);
      };
    }
  }, [enrollmentData]);

  const loadProfiles = async () => {
    try {
      const res = await enrollmentService.listProfiles();
      setProfiles(res.data);
      if (res.data.length > 0) {
        setSelectedProfileId(res.data[0].id);
      }
    } catch {
      setError('Erro ao carregar perfis de provisionamento.');
    }
  };

  const generateToken = useCallback(async () => {
    if (!selectedProfileId) {
      setError('Selecione um perfil de provisionamento.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const res = await enrollmentService.generateToken({
        profile_id: selectedProfileId,
        mode,
        max_devices: mode === 'batch' ? maxDevices : 1,
        ttl_minutes: ttlMinutes,
      });
      setEnrollmentData(res.data);
      setStep('qr');
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Erro ao gerar token de enrollment.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [selectedProfileId, mode, maxDevices, ttlMinutes]);

  const regenerateToken = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setStep('config');
    setEnrollmentData(null);
  };

  const buildQrPayload = (): string => {
    if (!enrollmentData) return '';

    // Payload alinhado com o padrão Android Enterprise Provisioning
    const payload: Record<string, any> = {
      'android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME':
        enrollmentData.admin_component,
      'android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION':
        enrollmentData.apk_url,
      'android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM':
        enrollmentData.apk_checksum,
      'android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE': {
        'bootstrap_token': enrollmentData.enrollment_token,
        'api_url': enrollmentData.api_url,
        'enrollment_mode': 'qr',
      },
    };

    return JSON.stringify(payload);
  };

  const copyPayload = () => {
    navigator.clipboard.writeText(buildQrPayload());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatCountdown = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-lg mx-4 bg-card border border-border rounded-xl shadow-2xl animate-fade-in overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-muted/30">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10 border border-primary/20">
              <QrCode className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-foreground">
                {step === 'config' ? 'Novo Dispositivo' : 'QR Code de Enrollment'}
              </h2>
              <p className="text-xs text-muted-foreground">
                {step === 'config'
                  ? 'Configure o provisionamento zero-touch'
                  : 'Aponte a câmera do dispositivo para este código'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-muted transition-colors"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {error && (
            <div className="flex items-center gap-2 px-3 py-2 mb-4 rounded-md bg-destructive/10 border border-destructive/30 text-destructive text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {step === 'config' && (
            <div className="space-y-5">
              {/* Profile Selector */}
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Shield className="w-3.5 h-3.5 text-primary" />
                  Perfil de Provisionamento
                </label>
                {profiles.length === 0 ? (
                  <div className="px-4 py-3 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-500 text-sm">
                    Nenhum perfil encontrado. Crie um perfil antes de continuar.
                  </div>
                ) : (
                  <select
                    id="profile-select"
                    value={selectedProfileId}
                    onChange={(e) => setSelectedProfileId(e.target.value)}
                    className="w-full px-3 py-2.5 text-sm bg-secondary border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-colors"
                  >
                    {profiles.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} (v{p.version})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Mode Selector */}
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Smartphone className="w-3.5 h-3.5 text-primary" />
                  Modo de Enrollment
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    id="mode-single"
                    onClick={() => setMode('single')}
                    className={`flex flex-col items-center gap-1.5 p-3 rounded-lg border text-sm font-medium transition-all ${
                      mode === 'single'
                        ? 'bg-primary/10 border-primary text-primary'
                        : 'bg-secondary border-border text-muted-foreground hover:border-primary/30'
                    }`}
                  >
                    <Smartphone className="w-5 h-5" />
                    <span>Único</span>
                    <span className="text-[10px] opacity-70">1 device</span>
                  </button>
                  <button
                    id="mode-batch"
                    onClick={() => setMode('batch')}
                    className={`flex flex-col items-center gap-1.5 p-3 rounded-lg border text-sm font-medium transition-all ${
                      mode === 'batch'
                        ? 'bg-primary/10 border-primary text-primary'
                        : 'bg-secondary border-border text-muted-foreground hover:border-primary/30'
                    }`}
                  >
                    <Layers className="w-5 h-5" />
                    <span>Lote</span>
                    <span className="text-[10px] opacity-70">N devices</span>
                  </button>
                </div>
              </div>

              {/* Batch: Max Devices */}
              {mode === 'batch' && (
                <div className="space-y-2 animate-fade-in">
                  <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <Layers className="w-3.5 h-3.5 text-primary" />
                    Máximo de Dispositivos
                  </label>
                  <input
                    type="number"
                    id="max-devices-input"
                    min={2}
                    max={500}
                    value={maxDevices}
                    onChange={(e) => setMaxDevices(Math.max(2, Math.min(500, Number(e.target.value))))}
                    className="w-full px-3 py-2.5 text-sm bg-secondary border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-colors"
                  />
                </div>
              )}

              {/* TTL */}
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Clock className="w-3.5 h-3.5 text-primary" />
                  Tempo de Validade
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    id="ttl-slider"
                    min={5}
                    max={60}
                    step={5}
                    value={ttlMinutes}
                    onChange={(e) => setTtlMinutes(Number(e.target.value))}
                    className="flex-1 h-2 rounded-lg appearance-none cursor-pointer accent-primary bg-secondary"
                  />
                  <span className="text-sm font-bold text-primary min-w-[50px] text-right">
                    {ttlMinutes} min
                  </span>
                </div>
              </div>

              {/* Generate Button */}
              <button
                id="generate-qr-button"
                onClick={generateToken}
                disabled={loading || profiles.length === 0}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 text-sm font-bold bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <QrCode className="w-4 h-4" />
                )}
                {loading ? 'Gerando Token Seguro...' : 'Gerar QR Code'}
              </button>
            </div>
          )}

          {step === 'qr' && enrollmentData && (
            <div className="space-y-5">
              {/* QR Code */}
              <div className="flex flex-col items-center">
                <div className={`p-4 bg-white rounded-xl border-2 transition-colors ${
                  countdown <= 60 ? 'border-amber-500 animate-pulse' : 'border-border'
                } ${countdown <= 0 ? 'opacity-30 border-destructive' : ''}`}>
                  <QRCodeSVG
                    value={buildQrPayload()}
                    size={240}
                    level="M"
                    includeMargin={false}
                    bgColor="#ffffff"
                    fgColor="#000000"
                    imageSettings={{
                      src: '/logo.png',
                      height: 36,
                      width: 36,
                      excavate: true,
                    }}
                  />
                </div>

                {/* Countdown */}
                <div className={`flex items-center gap-2 mt-3 px-3 py-1.5 rounded-full text-xs font-bold ${
                  countdown <= 0
                    ? 'bg-destructive/10 text-destructive'
                    : countdown <= 60
                    ? 'bg-amber-500/10 text-amber-500'
                    : 'bg-primary/10 text-primary'
                }`}>
                  <Clock className="w-3.5 h-3.5" />
                  {countdown <= 0 ? 'EXPIRADO' : `Expira em ${formatCountdown(countdown)}`}
                </div>
              </div>

              {/* Info Cards */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-secondary border border-border">
                  <Shield className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                  <div>
                    <p className="text-muted-foreground">Perfil</p>
                    <p className="font-bold text-foreground truncate">{enrollmentData.profile_name}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-secondary border border-border">
                  <Smartphone className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                  <div>
                    <p className="text-muted-foreground">Modo</p>
                    <p className="font-bold text-foreground">
                      {enrollmentData.mode === 'single'
                        ? '1 Device'
                        : `Lote (${enrollmentData.max_devices})`
                      }
                    </p>
                  </div>
                </div>
              </div>

              {/* Instructions */}
              <div className="px-4 py-3 rounded-lg bg-muted/50 border border-border">
                <p className="text-xs font-bold text-foreground mb-2">📱 Como usar:</p>
                <ol className="text-[11px] text-muted-foreground space-y-1 list-decimal list-inside">
                  <li>Factory reset o dispositivo Android</li>
                  <li>Na tela de "Bem-vindo", toque <strong>6 vezes</strong> no texto</li>
                  <li>Conecte via Wi-Fi quando solicitado</li>
                  <li>Aponte a câmera para o QR Code acima</li>
                  <li>Aguarde o download e instalação automática</li>
                </ol>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2">
                <button
                  id="regenerate-button"
                  onClick={regenerateToken}
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 text-sm font-medium bg-secondary text-foreground border border-border rounded-lg hover:bg-muted transition-colors"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Novo Token
                </button>
                <button
                  id="copy-payload-button"
                  onClick={copyPayload}
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 text-sm font-medium bg-secondary text-foreground border border-border rounded-lg hover:bg-muted transition-colors"
                >
                  {copied ? (
                    <Check className="w-3.5 h-3.5 text-green-500" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                  {copied ? 'Copiado!' : 'Copiar JSON'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
