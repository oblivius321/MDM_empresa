import React, { useState } from 'react';
import { LayoutGrid, Plus, X, ListPlus } from 'lucide-react';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface AppManagementBlockProps {
  config: any;
  onChange: (updates: any) => void;
}

export function AppManagementBlock({ config, onChange }: AppManagementBlockProps) {
  const [newBlockedApp, setNewBlockedApp] = useState('');
  const [newAllowedApp, setNewAllowedApp] = useState('');

  const blockedApps = config.blocked_apps || [];
  const allowedApps = config.allowed_apps || [];

  const addApp = (type: 'blocked' | 'allowed', pkg: string) => {
    if (!pkg) return;
    const list = type === 'blocked' ? blockedApps : allowedApps;
    if (list.includes(pkg)) return;

    onChange({
      [`${type}_apps`]: [...list, pkg]
    });
    
    if (type === 'blocked') setNewBlockedApp('');
    else setNewAllowedApp('');
  };

  const removeApp = (type: 'blocked' | 'allowed', pkg: string) => {
    const list = type === 'blocked' ? blockedApps : allowedApps;
    onChange({
      [`${type}_apps`]: list.filter((p: string) => p !== pkg)
    });
  };

  return (
    <div className="space-y-6 p-4 border border-border rounded-lg bg-card/50">
      <div className="flex items-center gap-2 mb-2">
        <LayoutGrid className="w-4 h-4 text-primary" />
        <h3 className="text-sm font-bold uppercase tracking-wider text-foreground">Gestão de Aplicativos</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Blacklist */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase">
            <X className="w-3 h-3 text-status-locked" />
            <span>Blacklist (Bloqueados)</span>
          </div>
          <div className="flex gap-2">
            <Input 
              placeholder="com.example.app" 
              value={newBlockedApp} 
              onChange={(e) => setNewBlockedApp(e.target.value)}
              className="text-xs h-8 bg-secondary"
            />
            <Button 
              size="sm" 
              variant="secondary" 
              className="h-8 group" 
              onClick={() => addApp('blocked', newBlockedApp)}
            >
              <Plus className="w-3 h-3 group-hover:text-primary transition-colors" />
            </Button>
          </div>
          <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
            {blockedApps.map((pkg: string) => (
              <Badge key={pkg} variant="outline" className="text-[10px] pl-2 pr-1 py-0 h-6 gap-1 bg-secondary border-status-locked/20 text-foreground">
                {pkg}
                <button 
                  onClick={() => removeApp('blocked', pkg)} 
                  className="p-0.5 hover:text-status-locked transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </Badge>
            ))}
          </div>
        </div>

        {/* Whitelist */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase">
            <Plus className="w-3 h-3 text-status-online" />
            <span>Whitelist (Permitidos)</span>
          </div>
          <div className="flex gap-2">
            <Input 
              placeholder="com.empresa.corp" 
              value={newAllowedApp} 
              onChange={(e) => setNewAllowedApp(e.target.value)}
              className="text-xs h-8 bg-secondary"
            />
            <Button 
              size="sm" 
              variant="secondary" 
              className="h-8 group" 
              onClick={() => addApp('allowed', newAllowedApp)}
            >
              <Plus className="w-3 h-3 group-hover:text-status-online transition-colors" />
            </Button>
          </div>
          <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
            {allowedApps.map((pkg: string) => (
              <Badge key={pkg} variant="outline" className="text-[10px] pl-2 pr-1 py-0 h-6 gap-1 bg-secondary border-status-online/20 text-foreground">
                {pkg}
                <button 
                  onClick={() => removeApp('allowed', pkg)} 
                  className="p-0.5 hover:text-status-locked transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </Badge>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
