import { create } from 'zustand';
import { Device, ComplianceStatus, PolicyState } from '@/services/api';

interface MDMState {
  // ─── Data ─────────────────────────────────────────────────────────────────
  devices: Device[];
  complianceMap: Record<string, PolicyState>; // device_id -> State
  isLoading: boolean;
  error: string | null;

  // ─── Actions ──────────────────────────────────────────────────────────────
  setDevices: (devices: Device[]) => void;
  updateDevice: (deviceId: string, data: Partial<Device>) => void;
  setComplianceState: (deviceId: string, state: PolicyState) => void;
  
  // ─── WebSocket Event Handlers (Atomic Updates) ─────────────────────────────
  handleDeviceConnected: (deviceId: string) => void;
  handleDeviceDisconnected: (deviceId: string) => void;
  handleComplianceUpdate: (deviceId: string, status: ComplianceStatus, details?: any) => void;
  handleCommandResult: (deviceId: string, action: string, success: boolean) => void;
}

export const useMDMStore = create<MDMState>((set) => ({
  devices: [],
  complianceMap: {},
  isLoading: false,
  error: null,

  setDevices: (devices) => set({ devices }),

  updateDevice: (deviceId, data) => set((state) => ({
    devices: state.devices.map((d) => 
      (d.id === deviceId || d.device_id === deviceId) ? { ...d, ...data } : d
    ),
  })),

  setComplianceState: (deviceId, policyState) => set((state) => ({
    complianceMap: {
      ...state.complianceMap,
      [deviceId]: policyState,
    },
    // Sincroniza o status básico no objeto device para performance de lista
    devices: state.devices.map((d) => 
      (d.id === deviceId || d.device_id === deviceId) 
        ? { ...d, compliance_status: policyState.compliance_status } 
        : d
    ),
  })),

  handleDeviceConnected: (deviceId) => set((state) => ({
    devices: state.devices.map((d) => 
      (d.id === deviceId || d.device_id === deviceId) ? { ...d, status: 'online' } : d
    ),
  })),

  handleDeviceDisconnected: (deviceId) => set((state) => ({
    devices: state.devices.map((d) => 
      (d.id === deviceId || d.device_id === deviceId) ? { ...d, status: 'offline' } : d
    ),
  })),

  handleComplianceUpdate: (deviceId, status, details) => set((state) => {
    const existing = state.complianceMap[deviceId] || {};
    const newState = { 
      ...existing, 
      device_id: deviceId,
      compliance_status: status, 
      ...details,
      updated_at: new Date().toISOString() 
    } as PolicyState;

    return {
      complianceMap: {
        ...state.complianceMap,
        [deviceId]: newState,
      },
      devices: state.devices.map((d) => 
        (d.id === deviceId || d.device_id === deviceId) 
          ? { ...d, compliance_status: status } 
          : d
      ),
    };
  }),

  handleCommandResult: (deviceId, action, success) => {
    // Se for um comando de policy, podemos querer disparar um re-fetch de compliance
    // ou marcar como 'enforcing' no store temporariamente.
    console.log(`[Store] Command ${action} on ${deviceId} result: ${success}`);
  },
}));
