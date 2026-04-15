import { useState, useEffect, useCallback, useRef } from 'react';
import { deviceService, Device, DeviceStatus } from '@/services/api';

interface UseDevicesOptions {
  autoRefresh?: boolean;
  refreshInterval?: number;
  initialStatus?: string;
  initialSearch?: string;
}

export function useDevices(options: UseDevicesOptions = {}) {
  const {
    autoRefresh = true,
    refreshInterval = 30000,
    initialStatus = '',
    initialSearch = '',
  } = options;

  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState(initialSearch);
  const [statusFilter, setStatusFilter] = useState(initialStatus);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchDevices = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const params = {
        page,
        size: pageSize,
        ...(search && { search }),
        ...(statusFilter && { status: statusFilter }),
      };
      const res = await deviceService.getAll(params);
      const data = res.data;

      // Diagnóstico: Verificar se o mapeamento de ID está funcionando
      if (import.meta.env.DEV) {
        const firstDevice = Array.isArray(data) ? data[0] : data.items?.[0];
        if (firstDevice) {
           console.log(`[useDevices] Check: id=${firstDevice.id}, device_id=${firstDevice.device_id}`);
           if (!firstDevice.id || firstDevice.id === 'undefined') {
             console.error('[useDevices] CRITICAL: device.id is undefined even after mapping!');
           }
        }
      }

      // Handle both paginated and array responses
      if (Array.isArray(data)) {
        setDevices(data);
        setTotal(data.length);
      } else {
        setDevices(data.items || []);
        setTotal(data.total || 0);
      }
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Erro ao carregar dispositivos');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, statusFilter]);

  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  useEffect(() => {
    if (!autoRefresh) return;
    intervalRef.current = setInterval(() => fetchDevices(false), refreshInterval);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefresh, refreshInterval, fetchDevices]);

  const refresh = () => fetchDevices(true);

  return {
    devices,
    loading,
    error,
    total,
    page,
    pageSize,
    setPage,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    refresh,
    lastRefreshed,
  };
}

export function useDevice(id: string) {
  const [device, setDevice] = useState<Device | null>(null);
  const [telemetry, setTelemetry] = useState<any | null>(null);
  const [commands, setCommands] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<{ type: string; success: boolean; message: string } | null>(null);

  const fetchDevice = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await deviceService.getById(id);
      setDevice(res.data);

      try {
        const [telRes, cmdRes] = await Promise.all([
          deviceService.getTelemetry(id),
          deviceService.getCommands(id)
        ]);
        setTelemetry(telRes.data);
        setCommands(cmdRes.data);
      } catch (e) {
        console.error("Failed to fetch telemetry or commands", e);
      }

    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Erro ao carregar dispositivo');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (id) fetchDevice();
  }, [fetchDevice, id]);

  const runAction = async (action: 'lock' | 'reboot' | 'sync' | 'wipe') => {
    setActionLoading(action);
    setActionResult(null);
    try {
      await deviceService[action](id);
      setActionResult({ type: action, success: true, message: `Comando ${action} enviado com sucesso` });
      setTimeout(() => fetchDevice(), 2000);
    } catch (err: any) {
      setActionResult({
        type: action,
        success: false,
        message: err.response?.data?.detail || `Erro ao executar ${action}`,
      });
    } finally {
      setActionLoading(null);
      setTimeout(() => setActionResult(null), 4000);
    }
  };

  return { device, telemetry, commands, loading, error, refresh: fetchDevice, runAction, actionLoading, actionResult };
}
