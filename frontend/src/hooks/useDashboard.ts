import { useState, useEffect, useCallback, useRef } from 'react';
import { deviceService, DeviceSummary } from '@/services/api';

export function useDashboard(autoRefresh = true, refreshInterval = 30000) {
  const [summary, setSummary] = useState<DeviceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchSummary = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const res = await deviceService.getSummary();
      setSummary(res.data);
      setLastRefreshed(new Date());
    } catch (err: any) {
      // Fallback: try GET /devices and compute summary client-side
      try {
        const devRes = await deviceService.getAll();
        const items = Array.isArray(devRes.data) ? devRes.data : (devRes.data as any).items || [];
        const computed: DeviceSummary = {
          total: items.length,
          online: items.filter((d: any) => d.status === 'online').length,
          offline: items.filter((d: any) => d.status === 'offline').length,
          locked: items.filter((d: any) => d.status === 'locked').length,
          last_global_checkin: items.reduce((latest: string, d: any) => {
            return !latest || d.last_checkin > latest ? d.last_checkin : latest;
          }, ''),
        };
        setSummary(computed);
        setLastRefreshed(new Date());
      } catch (fallbackErr: any) {
        setError(fallbackErr.response?.data?.detail || fallbackErr.message || 'Erro ao carregar resumo');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  useEffect(() => {
    if (!autoRefresh) return;
    intervalRef.current = setInterval(() => fetchSummary(false), refreshInterval);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefresh, refreshInterval, fetchSummary]);

  return { summary, loading, error, refresh: () => fetchSummary(true), lastRefreshed };
}
