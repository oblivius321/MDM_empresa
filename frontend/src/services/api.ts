import axios from 'axios';

// Configure your API base URL here
// In production, use: import.meta.env.VITE_API_BASE_URL
const BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || `http://${window.location.hostname}:8000/api`;

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor — attach JWT token if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — handle auth errors globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      // Could redirect to login here if needed
    }
    return Promise.reject(error);
  }
);

// ─── Types ──────────────────────────────────────────────────────────────────

export type DeviceStatus = 'online' | 'offline' | 'locked' | 'syncing';

export interface Device {
  id: string;
  name: string;
  imei: string;
  model?: string;
  android_version?: string;
  status: DeviceStatus;
  last_checkin: string;
  company?: string;
  policies?: Policy[];
  events?: DeviceEvent[];
  compliance_status?: 'compliant' | 'non_compliant' | 'unknown';
}

export interface Policy {
  id: string;
  name: string;
  type: string;
  applied_at?: string;
  status?: string;
  camera_disabled?: boolean;
  install_unknown_sources?: boolean;
  factory_reset_disabled?: boolean;
  kiosk_mode?: string | null;
}

export interface DeviceEvent {
  id: string;
  type: string;
  message: string;
  timestamp: string;
  severity?: 'info' | 'warning' | 'error';
}

export interface DeviceSummary {
  total: number;
  online: number;
  offline: number;
  locked: number;
  last_global_checkin?: string;
}

export interface PaginatedDevices {
  items: Device[];
  total: number;
  page: number;
  size: number;
}

// ─── Device Endpoints ────────────────────────────────────────────────────────

export const deviceService = {
  getAll: (params?: { status?: string; search?: string; page?: number; size?: number }) =>
    api.get<Device[] | PaginatedDevices>('/devices', { params }),

  getSummary: () =>
    api.get<DeviceSummary>('/devices/summary'),

  getById: (id: string) =>
    api.get<Device>(`/devices/${id}`),

  getTelemetry: (id: string) =>
    api.get<any>(`/devices/${id}/telemetry`),

  lock: (id: string) =>
    api.post(`/devices/${id}/lock`),

  reboot: (id: string) =>
    api.post(`/devices/${id}/reboot`),

  sync: (id: string, payload: any = {}) =>
    api.post(`/devices/${id}/checkin`, payload),

  wipe: (id: string) =>
    api.post(`/devices/${id}/wipe`),
};

// ─── Policy Endpoints ─────────────────────────────────────────────────────────

export const policyService = {
  getAll: () =>
    api.get('/policies'),

  create: (data: Partial<Policy>) =>
    api.post('/policies', data),

  getById: (id: string) =>
    api.get(`/policies/${id}`),

  apply: (deviceId: string, policyData: Partial<Policy>) =>
    api.post(`/devices/${deviceId}/policies`, policyData),
};

// ─── Log Endpoints ────────────────────────────────────────────────────────────

export const logService = {
  getAll: (params?: { device_id?: string; page?: number; size?: number }) =>
    api.get('/logs', { params }),
};
