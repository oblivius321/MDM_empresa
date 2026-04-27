import { Box, Copy, CheckCircle2, AlertCircle, QrCode } from 'lucide-react';
import { TopBar } from '@/components/TopBar';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';

export default function Provisioning() {
  const { toast } = useToast();

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: "Copiado para a área de transferência",
      description: "O comando já pode ser colado no terminal.",
    });
  };

  return (
    <div className="animate-fade-in relative min-h-screen bg-background">
      <TopBar 
        title="Provisionamento Manual" 
        subtitle="Instalação e registro de dispositivos via ADB (Fluxo Interno)" 
      />

      <div className="p-6 max-w-5xl mx-auto space-y-8">
        {/* Alerta de Status */}
        <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-4 flex items-start gap-4">
          <AlertCircle className="w-5 h-5 text-yellow-500 shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-bold text-yellow-500">Fluxo Zero-Touch Desativado</h3>
            <p className="text-xs text-muted-foreground mt-1">
              Devido a restrições de cotas do Google AMAPI, o provisionamento via QR Code oficial está temporariamente suspenso.
              Utilize os comandos ADB abaixo para registrar novos coletores.
            </p>
          </div>
        </div>

        {/* Card Principal: ADB Deployment */}
        <div className="card-glass border-border/40 p-8 overflow-hidden relative">
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <QrCode size={160} />
          </div>

          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-8">
              <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary border border-primary/20 shadow-lg shadow-primary/5">
                <Box className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-foreground tracking-tight">Implantação via Terminal (ADB)</h2>
                <p className="text-sm text-muted-foreground">Siga os passos abaixo para configurar o agente Elion MDM no dispositivo.</p>
              </div>
            </div>

            <div className="space-y-6">
              <div className="space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-widest text-primary flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center text-[10px]">1</span>
                  Instalar Agente
                </h3>
                <div className="p-4 rounded-lg bg-muted/30 border border-border/50 font-mono text-xs flex items-center justify-between">
                  <code>adb install elion-mdm.apk</code>
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => copyToClipboard('adb install elion-mdm.apk')}>
                    <Copy className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-widest text-primary flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center text-[10px]">2</span>
                  Registrar como Admin (Owner)
                </h3>
                <div className="p-4 rounded-lg bg-muted/30 border border-border/50 font-mono text-xs flex items-center justify-between">
                  <code className="break-all">adb shell dpm set-device-owner com.elion.mdm.dev/.receiver.DeviceAdminReceiver</code>
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => copyToClipboard('adb shell dpm set-device-owner com.elion.mdm.dev/.receiver.DeviceAdminReceiver')}>
                    <Copy className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              <div className="space-y-3 pt-4 border-t border-border/40">
                <h3 className="text-xs font-bold uppercase tracking-widest text-primary flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center text-[10px]">3</span>
                  Executar e Sincronizar
                </h3>
                <p className="text-xs text-muted-foreground px-7">
                  O comando abaixo inicializa a sincronização usando o <b>Bootstrap Secret</b> configurado no backend.
                </p>
                <div className="p-4 rounded-lg bg-secondary/20 border border-primary/20 font-mono text-xs">
                  <div className="flex items-center justify-between gap-4">
                    <pre className="whitespace-pre-wrap break-all leading-relaxed text-foreground/90">
                      adb shell am start -n com.elion.mdm.dev/.presentation.MainActivity \<br/>
                      --es bootstrap_token SEU_SEGREDO_AQUI
                    </pre>
                  </div>
                </div>
                <div className="px-7 flex items-center gap-2 text-[10px] text-muted-foreground bg-primary/5 p-2 rounded border border-primary/10">
                   <AlertCircle className="w-3 h-3" />
                   Substitua <b>SEU_SEGREDO_AQUI</b> pelo valor da variável <code>BOOTSTRAP_SECRET</code> do seu backend.
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
           <div className="p-6 rounded-xl border border-border/40 bg-card/40 flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-green-500/10 flex items-center justify-center text-green-500">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold">Estado do Backend</h4>
                <p className="text-[11px] text-muted-foreground">API pronta para receber conexões ADB.</p>
              </div>
           </div>
           <div className="p-6 rounded-xl border border-border/40 bg-card/40 flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-500">
                <Box className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold">Modo Kiosk</h4>
                <p className="text-[11px] text-muted-foreground">Ativado automaticamente após o registro.</p>
              </div>
           </div>
        </div>
      </div>
    </div>
  );
}
