import axios from 'axios';

const rawBaseUrl = (import.meta as any).env?.VITE_API_BASE_URL?.trim();

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, '');
}

function joinPath(basePath: string, path: string) {
  return `${trimTrailingSlash(basePath)}/${path.replace(/^\/+/, '')}`;
}

function resolveApiBaseUrl() {
  if (!rawBaseUrl) {
    return '/api';
  }

  if (rawBaseUrl.startsWith('/')) {
    return trimTrailingSlash(rawBaseUrl);
  }

  if (typeof window === 'undefined') {
    return trimTrailingSlash(rawBaseUrl);
  }

  try {
    const url = new URL(rawBaseUrl, window.location.origin);
    const basePort = url.port || (url.protocol === 'https:' ? '443' : '80');
    const frontendPort = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');
    const sameHost = url.hostname === window.location.hostname;
    const isDefaultHttpPort = basePort === '80' || basePort === '443';

    // In dev, prefer the Vite proxy when the env points to the same host on the default port.
    if (import.meta.env.DEV && sameHost && isDefaultHttpPort && frontendPort !== basePort) {
      return '/api';
    }

    return trimTrailingSlash(url.toString());
  } catch {
    return '/api';
  }
}

export const API_BASE_URL = resolveApiBaseUrl();
export const API_DISPLAY_URL =
  typeof window !== 'undefined' && !API_BASE_URL.startsWith('http')
    ? `${window.location.origin}${API_BASE_URL}`
    : API_BASE_URL;

export function buildApiUrl(path: string) {
  return joinPath(API_BASE_URL, path);
}

export function buildWebSocketUrl(path: string) {
  if (typeof window === 'undefined') {
    return path;
  }

  if (API_BASE_URL.startsWith('http')) {
    const url = new URL(API_BASE_URL);
    const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProtocol}//${url.host}${joinPath(url.pathname, path)}`;
  }

  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${wsProtocol}//${window.location.host}${joinPath(API_BASE_URL, path)}`;
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,  // Aumentado de 10s para 30s
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor — handle auth errors globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_user');
      // Force refresh to trigger state sync if necessary
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
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
