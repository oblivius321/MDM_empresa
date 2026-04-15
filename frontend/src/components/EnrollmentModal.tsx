import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { QRCodeCanvas } from 'qrcode.react';
import {
  androidManagementService,
  AndroidManagementEnrollmentToken,
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
} from 'lucide-react';

interface EnrollmentModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function EnrollmentModal({ isOpen, onClose }: EnrollmentModalProps) {
  const [step, setStep] = useState<'config' | 'qr'>('config');
  const [enrollmentData, setEnrollmentData] = useState<AndroidManagementEnrollmentToken | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (isOpen) {
      setStep('config');
      setEnrollmentData(null);
      setError('');
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isOpen]);

  useEffect(() => {
    if (enrollmentData?.expiration_timestamp) {
      const updateCountdown = () => {
        const now = Date.now();
        const expires = new Date(enrollmentData.expiration_timestamp).getTime();
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

  const generateOfficialQr = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const res = await androidManagementService.createEnrollmentToken({});
      setEnrollmentData(res.data);
      setStep('qr');
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Erro ao gerar token oficial do Google.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const regenerateOfficialQr = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setStep('config');
    setEnrollmentData(null);
  };

  const officialQrValue = (): string => {
    return enrollmentData?.qr_code || '';
  };

  const copyPayload = () => {
    navigator.clipboard.writeText(officialQrValue());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatCountdown = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  if (!isOpen) return null;

  return createPortal(
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '20px',
      }}
    >
      {/* Backdrop */}
      <div
        className="bg-background/80 backdrop-blur-sm"
        style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
        onClick={onClose}
      />

      <div
        className="bg-card border border-border rounded-xl shadow-2xl animate-fade-in"
        style={{
          position: 'relative',
          zIndex: 10,
          width: '100%',
          maxWidth: '32rem',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
      >
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
              <div className="px-4 py-3 rounded-md bg-secondary border border-border text-sm text-muted-foreground">
                Use este QR para provisionamento Android Enterprise via Google.
              </div>

              <div className="grid grid-cols-1 gap-2 text-xs">
                <div className="px-3 py-2 rounded-md bg-background/50 border border-border">
                  <span className="block text-[10px] font-bold text-foreground">Android Device Policy</span>
                  <span>Use em dispositivo restaurado de fabrica, tocando 6 vezes na tela de boas-vindas.</span>
                </div>
              </div>

              {/* Generate Button */}
              <button
                id="generate-qr-button"
                onClick={generateOfficialQr}
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 text-sm font-bold bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <QrCode className="w-4 h-4" />
                )}
                {loading ? 'Gerando token Google...' : 'Gerar QR Oficial (Android Enterprise)'}
              </button>
            </div>
          )}

          {step === 'qr' && enrollmentData && (
            <div className="space-y-5 w-full flex flex-col items-center justify-center">
              {/* Bloco do QR Code */}
              <div className="flex flex-col items-center justify-center w-full gap-3">
                <div className="flex justify-center w-full">
                  <div style={{ padding: '20px', backgroundColor: '#ffffff', borderRadius: '16px', boxShadow: '0 4px 20px rgba(0,0,0,0.15)', border: '1px solid #e4e4e7' }}>
                    <QRCodeCanvas
                      id="qr-code-canvas"
                      value={officialQrValue()}
                      size={220}
                      level="M"
                      includeMargin={false}
                      bgColor="#ffffff"
                      fgColor="#1a1a1a"
                      style={{
                        display: 'block',
                        imageRendering: 'pixelated',
                        filter: 'none'
                      }}
                    />
                  </div>
                </div>

                {/* Contador */}
                <div className="flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold bg-primary/10 text-primary border border-primary/20">
                  <Clock className="w-3.5 h-3.5" />
                  {countdown <= 0 ? 'EXPIRADO' : `Expira em ${formatCountdown(countdown)}`}
                </div>

                <button
                  className="text-[10px] text-muted-foreground hover:underline"
                  onClick={(e) => {
                    e.preventDefault();
                    const canvas = document.getElementById('qr-code-canvas') as HTMLCanvasElement;
                    if (canvas) {
                      const link = document.createElement('a');
                      link.download = 'qr.png';
                      link.href = canvas.toDataURL();
                      link.click();
                    }
                  }}
                >
                  Problemas com a imagem? Clique para baixar.
                </button>
              </div>

              {/* Info Cards */}
              <div className="grid grid-cols-2 gap-2 text-xs w-full">
                <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-secondary border border-border">
                  <Shield className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                  <div>
                    <p className="text-muted-foreground">Token Google</p>
                    <p className="font-bold text-foreground truncate">{enrollmentData.name}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-secondary border border-border">
                  <Smartphone className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                  <div>
                    <p className="text-muted-foreground">Origem</p>
                    <p className="font-bold text-foreground">Android Management API</p>
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
                  onClick={regenerateOfficialQr}
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 text-sm font-medium bg-secondary text-foreground border border-border rounded-lg hover:bg-muted transition-colors"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Novo QR Oficial
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
                  {copied ? 'Copiado!' : 'Copiar QR oficial'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
