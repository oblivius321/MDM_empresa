import React from 'react';
import { Shield, Camera, RotateCcw, Download } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

interface RestrictionsBlockProps {
  config: any;
  onChange: (updates: any) => void;
}

export function RestrictionsBlock({ config, onChange }: RestrictionsBlockProps) {
  const restrictions = config.restrictions || {};

  const handleToggle = (key: string, value: boolean) => {
    onChange({
      restrictions: {
        ...restrictions,
        [key]: value
      }
    });
  };

  return (
    <div className="space-y-4 p-4 border border-border rounded-lg bg-card/50">
      <div className="flex items-center gap-2 mb-2">
        <Shield className="w-4 h-4 text-primary" />
        <h3 className="text-sm font-bold uppercase tracking-wider text-foreground">Restrições de Segurança</h3>
      </div>

      <div className="space-y-4">
        {/* Câmera */}
        <div className="flex items-center justify-between group">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-secondary flex items-center justify-center">
              <Camera className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <div>
              <Label className="text-sm font-medium">Desativar Câmera</Label>
              <p className="text-[10px] text-muted-foreground">Impede o uso da câmera em todo o sistema.</p>
            </div>
          </div>
          <Switch 
            checked={!!restrictions.camera_disabled} 
            onCheckedChange={(val) => handleToggle('camera_disabled', val)} 
          />
        </div>

        {/* Fontes Desconhecidas */}
        <div className="flex items-center justify-between group">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-secondary flex items-center justify-center">
              <Download className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <div>
              <Label className="text-sm font-medium">Bloquear APKs Externos</Label>
              <p className="text-[10px] text-muted-foreground">Impede instalação de apps fora da Play Store.</p>
            </div>
          </div>
          <Switch 
            checked={!!restrictions.install_unknown_sources_disabled} 
            onCheckedChange={(val) => handleToggle('install_unknown_sources_disabled', val)} 
          />
        </div>

        {/* Factory Reset */}
        <div className="flex items-center justify-between group">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-secondary flex items-center justify-center">
              <RotateCcw className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <div>
              <Label className="text-sm font-medium">Impedir Reset de Fábrica</Label>
              <p className="text-[10px] text-muted-foreground">Remove a opção de Restaurar Configurações.</p>
            </div>
          </div>
          <Switch 
            checked={!!restrictions.factory_reset_disabled} 
            onCheckedChange={(val) => handleToggle('factory_reset_disabled', val)} 
          />
        </div>
      </div>
    </div>
  );
}
