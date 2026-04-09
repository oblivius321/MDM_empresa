import React, { useState, useEffect } from 'react';
import { Shield, Save, X, Trash2, LayoutDashboard, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { RestrictionsBlock } from './RestrictionsBlock';
import { AppManagementBlock } from './AppManagementBlock';
import { KioskSettingsBlock } from './KioskSettingsBlock';
import { ScrollArea } from '@/components/ui/scroll-area';

interface PolicyBuilderProps {
  initialData?: any;
  onSave: (policy: any) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export function PolicyBuilder({ initialData, onSave, onCancel, isSubmitting }: PolicyBuilderProps) {
  const [policy, setPolicy] = useState<any>({
    name: '',
    description: '',
    priority: 0,
    scope: 'global',
    config: {
      restrictions: {},
      blocked_apps: [],
      allowed_apps: [],
      kiosk_mode: { enabled: false, package_name: '' },
      wifi_config: {},
      password_requirements: {}
    }
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (initialData) {
      setPolicy({
        ...initialData,
        config: {
          ...policy.config,
          ...(initialData.config || {})
        }
      });
    }
  }, [initialData]);

  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (!policy.name) newErrors.name = 'Nome é obrigatório';
    if (policy.priority < 0 || policy.priority > 100) newErrors.priority = 'Prioridade deve ser entre 0 e 100';
    if (policy.config.kiosk_mode?.enabled && !policy.config.kiosk_mode?.package_name) {
      newErrors.kiosk = 'ID do Pacote é obrigatório no modo Kiosk';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = () => {
    if (validate()) {
      onSave(policy);
    }
  };

  const handleConfigChange = (updates: any) => {
    setPolicy((prev: any) => ({
      ...prev,
      config: {
        ...prev.config,
        ...updates
      }
    }));
  };

  const handleBasicChange = (key: string, value: any) => {
    setPolicy((prev: any) => ({
      ...prev,
      [key]: value
    }));
  };

  return (
    <div className="flex flex-col h-full bg-background animate-in fade-in duration-500">
      {/* HEADER */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card/30 backdrop-blur-md sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary shadow-sm border border-primary/20">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-foreground">
              {initialData ? 'Editar Política Enterprise' : 'Criar Nova Política Enterprise'}
            </h2>
            <p className="text-xs text-muted-foreground font-medium">Gestão declarativa de estado (Fase 3)</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel} className="text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4 mr-2" />
            Cancelar
          </Button>
          <Button 
            size="sm" 
            onClick={handleSave} 
            disabled={isSubmitting}
            className="shadow-lg shadow-primary/20"
          >
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Salvando...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Save className="w-4 h-4" />
                Salvar Política
              </span>
            )}
          </Button>
        </div>
      </div>

      {/* CONTENT */}
      <ScrollArea className="flex-1">
        <div className="max-w-4xl mx-auto p-6 space-y-8">
          
          {errors.kiosk && (
            <div className="p-3 bg-status-locked/10 border border-status-locked/20 rounded-lg text-status-locked text-xs font-bold animate-in zoom-in-95">
              ⚠️ ERRO DE CONFIGURAÇÃO: {errors.kiosk}
            </div>
          )}

          {/* IDENTIFICAÇÃO E ESCOPO */}
          <section className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-in slide-in-from-bottom-4 duration-500">
            <div className="md:col-span-2 space-y-4">
              <div className="space-y-1.5">
                <Label className={`text-xs font-bold uppercase tracking-widest ${errors.name ? 'text-status-locked' : 'text-muted-foreground'}`}>
                  Nome da Política {errors.name && `(${errors.name})`}
                </Label>
                <Input 
                  placeholder="Ex: Restrições de Operação Crítica" 
                  value={policy.name} 
                  onChange={(e) => handleBasicChange('name', e.target.value)}
                  className={`bg-card/50 transition-all font-semibold ${errors.name ? 'border-status-locked' : 'border-primary/20 focus:border-primary'}`}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Descrição (Opcional)</Label>
                <Input 
                  placeholder="Explique o objetivo desta política..." 
                  value={policy.description} 
                  onChange={(e) => handleBasicChange('description', e.target.value)}
                  className="bg-card/50 border-border/50 text-xs"
                />
              </div>
            </div>

            <div className="space-y-4 bg-muted/20 p-4 rounded-xl border border-border/50">
              <div className="space-y-1.5">
                <Label className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                  <LayoutDashboard className="w-3 h-3" /> Escopo
                </Label>
                <Select 
                  value={policy.scope} 
                  onValueChange={(val) => handleBasicChange('scope', val)}
                >
                  <SelectTrigger className="bg-card border-border/50 text-xs h-9">
                    <SelectValue placeholder="Selecione o escopo" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="global">Global (Frota Toda)</SelectItem>
                    <SelectItem value="group">Grupo de Trabalho</SelectItem>
                    <SelectItem value="device">Dispositivo Individual</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                  <Settings className="w-3 h-3" /> Prioridade (0-100)
                </Label>
                <Input 
                  type="number" 
                  min="0" 
                  max="100" 
                  value={policy.priority} 
                  onChange={(e) => handleBasicChange('priority', parseInt(e.target.value))}
                  className="bg-card border-border/50 text-xs h-9"
                />
                <p className="text-[10px] text-muted-foreground italic">Valores maiores sobrescrevem menores no merge.</p>
              </div>
            </div>
          </section>

          <div className="border-t border-border/50 pt-8" />

          {/* CONFIGURATION BLOCKS */}
          <div className="grid grid-cols-1 gap-8 animate-in slide-in-from-bottom-8 duration-700">
            <RestrictionsBlock 
              config={policy.config} 
              onChange={handleConfigChange} 
            />

            <AppManagementBlock 
              config={policy.config} 
              onChange={handleConfigChange} 
            />

            <KioskSettingsBlock 
              config={policy.config} 
              onChange={handleConfigChange} 
            />
          </div>

          <div className="h-20" /> {/* Spacer para scroll */}
        </div>
      </ScrollArea>
    </div>
  );
}
