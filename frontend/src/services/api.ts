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

  // Se a BASE_URL for absoluta (ex: http://192...:8200), usamos o mesmo host/porta pro WS
  if (API_BASE_URL.startsWith('http')) {
    const url = new URL(API_BASE_URL);
    const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    // Substitui http/https por ws/wss e mantém o host completo (incluindo porta se houver)
    return `${wsProtocol}//${url.host}${joinPath(url.pathname, path)}`;
  }

  // Fallback: Se a API_BASE_URL for relativa (ex: /api), supomos que o WS está no mesmo host
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  
  return `${wsProtocol}//${window.location.host}${joinPath(API_BASE_URL, path)}`;
}

const savedAccessToken =
  typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,  // Aumentado de 10s para 30s
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    ...(savedAccessToken ? { Authorization: `Bearer ${savedAccessToken}` } : {}),
  },
});

// Response interceptor — handle auth errors globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 🛡️ Interceptor Inteligente: Só desloga o Admin se o erro 401 for realmente dele
    if (error.response?.status === 401) {
      const isDeviceRoute = error.config?.url?.includes('/devices/');
      const hasAdminAuth = !!error.config?.headers?.['Authorization'];

      // Se for uma rota de device SEM header de Admin, o erro é do Device, não do Admin.
      // NÃO devemos deslogar o Admin nesse caso.
      if (isDeviceRoute && !hasAdminAuth) {
        console.warn('⚠️ [Auth] Device auth failed, but Admin session preserved.');
        return Promise.reject(error);
      }

      // Caso contrário, é erro de sessão do Admin (Dashboard)
      localStorage.removeItem('auth_user');
      localStorage.removeItem('auth_token');
      delete api.defaults.headers.common.Authorization;
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// ─── Types ──────────────────────────────────────────────────────────────────

// ─── Types ──────────────────────────────────────────────────────────────────

export type DeviceStatus = 'online' | 'offline' | 'locked' | 'syncing';

export type ComplianceStatus = 
  | 'compliant' 
  | 'enforcing' 
  | 'enforcing_partial' 
  | 'failed_loop' 
  | 'unknown';

export interface PolicyState {
  device_id: string;
  compliance_status: ComplianceStatus;
  last_reported_state: any;
  failed_subcommands: string[];
  last_enforced_at?: string;
  drift_score?: number;
  effective_policy_hash?: string;
  state_hash?: string;
  updated_at: string;
}

export interface Device {
  id: string;
  device_id: string;
  external_id?: string;
  name: string;
  imei: string;
  model?: string;
  android_version?: string;
  status: DeviceStatus;
  last_checkin: string;
  last_seen?: string;
  company?: string;
  policies?: Policy[];
  policies_v2?: PolicyV2[];
  device_policies?: any[];
  compliance_status?: ComplianceStatus;
  compliance_state?: PolicyState;
  merged_config?: any;
  last_enforced_at?: string;
  last_apps_json?: string[];
  battery_level?: number;
  free_disk_space_mb?: number;
  latitude?: number;
  longitude?: number;
  metadata_json?: any;
  events?: DeviceEvent[];
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

export interface PolicyV2 {
  id: number;
  name: string;
  config: any;
  priority: number;
  scope: 'global' | 'group' | 'device';
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DeviceCommand {
  id: number;
  device_id: string;
  command_type: string;
  payload?: any;
  status: 'PENDING' | 'DISPATCHED' | 'EXECUTED' | 'FAILED' | 'ACKED';
  created_at: string;
  dispatched_at?: string;
  executed_at?: string;
  execution_latency?: number;
  error_code?: string;
  error_message?: string;
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

export interface UserPreferences {
  offline_alerts: boolean;
  compliance_failures: boolean;
  new_devices: boolean;
  system_updates: boolean;
}

export interface CurrentUser {
  id: number;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  preferences: UserPreferences;
}

export interface AuditLogRecord {
  id: string;
  user_id?: number | null;
  user_email?: string | null;
  action: string;
  event_type?: string | null;
  severity: string;
  actor_type: string;
  actor_id: string;
  resource_type: string;
  resource_id?: string | null;
  device_id?: string | null;
  details?: Record<string, any>;
  is_success: boolean;
  error_message?: string | null;
  request_id?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
}

export interface PaginatedDevices {
  items: Device[];
  total: number;
  page: number;
  size: number;
}

// ─── Mapper Layer ────────────────────────────────────────────────────────────

export function mapDevice(data: any): Device {
  if (!data) return data;
  return {
    ...data,
    // Garante que o frontend sempre tenha 'id' mapeado do 'device_id' do backend
    id: data.id || data.device_id || "unknown",
    device_id: data.device_id || data.id || "unknown",
    last_seen: data.last_seen || data.last_checkin,
  };
}

export function mapDevices(data: Device[] | PaginatedDevices): Device[] | PaginatedDevices {
  if (Array.isArray(data)) {
    return data.map(mapDevice);
  }
  if (data && data.items) {
    return {
      ...data,
      items: data.items.map(mapDevice),
    };
  }
  return data;
}

// ─── Device Endpoints ────────────────────────────────────────────────────────

export const deviceService = {
  getAll: async (params?: { status?: string; search?: string; page?: number; size?: number }) => {
    const res = await api.get<Device[] | PaginatedDevices>('/devices', { params });
    return { ...res, data: mapDevices(res.data) };
  },

  getSummary: () =>
    api.get<DeviceSummary>('/devices/summary'),

  getById: async (id: string) => {
    const res = await api.get<Device>(`/devices/${id}`);
    return { ...res, data: mapDevice(res.data) };
  },

  getTelemetry: (id: string) =>
    api.get<any>(`/devices/${id}/telemetry`),

  getCommands: (id: string) =>
    api.get<DeviceCommand[]>(`/devices/${id}/commands`),

  lock: (id: string) =>
    api.post(`/devices/${id}/lock`),

  reboot: (id: string) =>
    api.post(`/devices/${id}/reboot`),

  sync: (id: string, payload: any = {}) =>
    api.post(`/devices/${id}/checkin`, payload),

  wipe: (id: string) =>
    api.post(`/devices/${id}/wipe`),

  delete: (id: string) =>
    api.delete(`/devices/${id}`),
};

// ─── Policy V2 Endpoints (Enterprise) ────────────────────────────────────────

export const policyV2Service = {
  getAll: (params?: { scope?: string; is_active?: boolean }) =>
    api.get<PolicyV2[]>('/policies/v2', { params }),

  create: (data: Partial<PolicyV2>) =>
    api.post<PolicyV2>('/policies/v2', data),

  getById: (id: number) =>
    api.get<PolicyV2>(`/policies/v2/${id}`),

  update: (id: number, data: Partial<PolicyV2>) =>
    api.put<PolicyV2>(`/policies/v2/${id}`, data),

  delete: (id: number) =>
    api.delete(`/policies/v2/${id}`),

  assignToDevice: (deviceId: string, policyId: number) =>
    api.post(`/devices/${deviceId}/policies/v2`, { policy_id: policyId }),

  removeFromDevice: (deviceId: string, policyId: number) =>
    api.delete(`/devices/${deviceId}/policies/v2/${policyId}`),
};

// ─── Compliance Endpoints ───────────────────────────────────────────────────

export const complianceService = {
  getDeviceCompliance: (deviceId: string) =>
    api.get<any>(`/devices/${deviceId}/compliance`),

  reportState: (deviceId: string, state: any) =>
    api.post(`/devices/${deviceId}/state-report`, { ...state }),
};

// ─── Log Endpoints ────────────────────────────────────────────────────────────

export const logService = {
  getAll: (params?: { skip?: number; limit?: number; device_id?: string; page?: number; size?: number }) =>
    api.get<AuditLogRecord[]>('/logs', { params }),
};

export const userService = {
  getMe: () =>
    api.get<CurrentUser>('/users/me'),

  updatePreferences: (preferences: Partial<UserPreferences>) =>
    api.patch<CurrentUser>('/users/me/preferences', preferences),
};

// ─── Profile & Enrollment Endpoints (Enterprise QR) ──────────────────────────

export interface ProvisioningProfile {
  id: string;
  name: string;
  kiosk_enabled: boolean;
  allowed_apps: string[];
  blocked_features: Record<string, boolean>;
  config: Record<string, any>;
  policy_ids: number[]; // IDs das políticas enterprise vinculadas
  version: number;
  is_active: boolean;
  created_at: string;
}

export interface MergedPolicyPreview {
  profile_id: string;
  profile_name: string;
  layers_applied: { name: string; priority: number; scope?: string }[];
  merged_config: any;
  hash: string;
}

export interface LegacyEnrollmentToken {
  enrollment_token: string;
  profile_id: string;
  api_url: string;
  profile_name: string;
  mode: string;
  max_devices: number;
  ttl_minutes: number;
  expires_at: string;
  admin_component: string;
  apk_url: string;
  apk_checksum: string;
}

export const enrollmentService = {
  listProfiles: () =>
    api.get<ProvisioningProfile[]>('/profiles'),

  createProfile: (data: Partial<ProvisioningProfile>) =>
    api.post<ProvisioningProfile>('/profiles', data),

  updateProfile: (id: string, data: Partial<ProvisioningProfile>) =>
    api.put<ProvisioningProfile>(`/profiles/${id}`, data),

  previewProfile: (id: string) =>
    api.get<MergedPolicyPreview>(`/profiles/${id}/preview`),

  generateLegacyToken: (
    profileId: string,
    params: { mode?: 'single' | 'batch'; max_devices?: number; ttl_minutes?: number } = {}
  ) =>
    api.post<LegacyEnrollmentToken>('/enrollment/generate', null, {
      params: {
        profile_id: profileId,
        mode: params.mode ?? 'single',
        max_devices: params.max_devices ?? 1,
        ttl_minutes: params.ttl_minutes ?? 15,
      },
    }),
};

// ─── Android Management API (Google DPC oficial) ─────────────────────────

export interface AndroidManagementStatus {
  configured: boolean;
  project_id?: string;
  service_account_email?: string;
  service_account_file?: string;
  signup_url_name?: string;
  signup_url?: string;
  enterprise_name?: string;
  enterprise_display_name?: string;
  policy_name?: string;
  last_error?: string;
}

export interface AndroidManagementSignupUrl {
  signup_url_name: string;
  signup_url: string;
  callback_url: string;
}

export interface AndroidManagementEnrollmentToken {
  id: string;
  name: string;
  qr_code: string;
  expiration?: string;
  expiration_timestamp?: string;
  policy_name?: string;
}

export interface AndroidManagementDevice {
  id: string;
  name: string;
  model?: string;
  android_version?: string;
  status: string;
  last_checkin?: string;
  compliance: string;
}

export interface AndroidManagementSyncedDevice {
  external_id: string;
  name: string;
  model?: string;
  android_version?: string;
  status: string;
  last_seen?: string;
  compliance: string;
}

export const androidManagementService = {
  status: () =>
    api.get<AndroidManagementStatus>('/android-management/status'),

  createSignupUrl: (callback_url?: string) =>
    api.post<AndroidManagementSignupUrl>('/android-management/signup-url', { callback_url }),

  upsertDefaultPolicy: () =>
    api.post('/android-management/default-policy'),

  createEnrollmentToken: (data: {
    policy_id?: string;
    duration_minutes?: number;
    one_time_only?: boolean;
    additional_data?: Record<string, any>;
  } = {}) =>
    api.post<AndroidManagementEnrollmentToken>('/android-management/enrollment-token', data),

  listDevices: () =>
    api.get<AndroidManagementDevice[]>('/android-management/devices'),

  syncDevices: () =>
    api.get<AndroidManagementSyncedDevice[]>('/android-management/devices/sync'),
};
