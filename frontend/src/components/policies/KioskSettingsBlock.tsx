import React from 'react';
import { Smartphone, Info } from 'lucide-react';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface KioskSettingsBlockProps {
  config: any;
  onChange: (updates: any) => void;
}

export function KioskSettingsBlock({ config, onChange }: KioskSettingsBlockProps) {
  const kiosk = config.kiosk_mode || { enabled: false, package_name: '' };

  const handleToggle = (enabled: boolean) => {
    onChange({
      kiosk_mode: {
        ...kiosk,
        enabled
      }
    });
  };

  const handlePackageChange = (package_name: string) => {
    onChange({
      kiosk_mode: {
        ...kiosk,
        package_name
      }
    });
  };

  return (
    <div className="space-y-4 p-4 border border-border rounded-lg bg-card/50">
      <div className="flex items-center gap-2 mb-2">
        <Smartphone className="w-4 h-4 text-primary" />
        <h3 className="text-sm font-bold uppercase tracking-wider text-foreground">Modo Kiosk (Totem)</h3>
      </div>

      <div className="flex items-center justify-between group">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-secondary flex items-center justify-center">
            <Smartphone className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
          </div>
          <div>
            <Label className="text-sm font-medium">Ativar Modo Kiosk</Label>
            <p className="text-[10px] text-muted-foreground">Bloqueia o dispositivo em um único aplicativo.</p>
          </div>
        </div>
        <Switch 
          checked={!!kiosk.enabled} 
          onCheckedChange={handleToggle} 
        />
      </div>

      {kiosk.enabled && (
        <div className="space-y-3 animate-in slide-in-from-top-2 duration-300">
          <div className="space-y-1.5 ml-11">
            <Label className="text-xs font-bold text-muted-foreground uppercase">ID do Pacote (Package Name)</Label>
            <Input 
              placeholder="Ex: com.google.android.youtube" 
              value={kiosk.package_name || ''} 
              onChange={(e) => handlePackageChange(e.target.value)}
              className="text-xs h-9 bg-secondary font-mono"
            />
          </div>
          
          <Alert variant="default" className="bg-primary/5 border-primary/20 ml-11 py-2">
            <Info className="h-4 w-4 text-primary" />
            <AlertDescription className="text-[10px] text-muted-foreground leading-relaxed">
              <strong>Cuidado:</strong> O dispositivo ficará inacessível para outras funções. 
              Certifique-se de que o aplicativo está instalado no aparelho antes de aplicar.
            </AlertDescription>
          </Alert>
        </div>
      )}
    </div>
  );
}
