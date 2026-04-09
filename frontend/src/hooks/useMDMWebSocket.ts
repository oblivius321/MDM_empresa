import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { buildWebSocketUrl } from '../services/api';
import { useMDMStore } from '../store/useMDMStore';

type PresenceEvent = { device_id: string; status: 'online' | 'offline' };

type CommandEvent = {
  type: 'CMD_SENT' | 'CMD_ACKED' | 'CMD_COMPLETED' | 'CMD_FAILED';
  device_id: string;
  command_id: number;
  action: string;
  status: string;
  error?: string | null;
};

/**
 * useMDMWebSocket
 *
 * @param onDeviceChange   Callback opcional (fallback para retrocompatibilidade)
 * @param onPresenceChange Callback opcional
 * @param onCommandEvent   Callback opcional
 */
export function useMDMWebSocket(
  onDeviceChange?: () => void,
  onPresenceChange?: (event: PresenceEvent) => void,
  onCommandEvent?: (event: CommandEvent) => void,
) {
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const { isAuthenticated } = useAuth();
  
  // ─── Zustand Store Selectors ──────────────────────────────────────────────
  const { 
    handleDeviceConnected, 
    handleDeviceDisconnected, 
    handleComplianceUpdate,
    handleCommandResult 
  } = useMDMStore();

  useEffect(() => {
    if (!isAuthenticated) return;

    const wsUrl = buildWebSocketUrl('/ws/dashboard');
    let retryTimeout: ReturnType<typeof setTimeout>;
    let currentDelay = 1000;
    const MAX_DELAY = 30000;

    function connect() {
      console.log(`📡 Radar MDM: Conectando em ${wsUrl}...`);
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        console.log('🔗 Radar MDM Conectado.');
        setIsConnected(true);
        currentDelay = 1000;
      };

      ws.current.onmessage = (event) => {
        try {
          if (typeof event.data === 'string' && !event.data.startsWith('{')) {
            if (event.data === 'ping') ws.current?.send('pong');
            return;
          }

          const data = JSON.parse(event.data);

          switch (data.type) {
            case 'DEVICE_CONNECTED': {
              handleDeviceConnected(data.device_id);
              if (onPresenceChange) onPresenceChange(data);
              if (onDeviceChange) onDeviceChange();
              break;
            }

            case 'DEVICE_DISCONNECTED': {
              handleDeviceDisconnected(data.device_id);
              if (onPresenceChange) onPresenceChange(data);
              if (onDeviceChange) onDeviceChange();
              break;
            }

            case 'COMPLIANCE_UPDATE': {
              handleComplianceUpdate(data.device_id, data.status, {
                compliant: data.compliant
              });
              break;
            }

            case 'CMD_SENT':
            case 'CMD_ACKED':
            case 'CMD_COMPLETED':
            case 'CMD_FAILED': {
              handleCommandResult(data.device_id, data.action, data.type === 'CMD_COMPLETED');
              if (onCommandEvent) onCommandEvent(data as CommandEvent);
              break;
            }

            case 'DEVICE_CHECKIN':
            case 'DEVICE_ENROLLED':
            case 'DEVICE_EVENT':
              if (onDeviceChange) onDeviceChange();
              break;

            case 'server_ping':
              ws.current?.send(JSON.stringify({ type: 'pong' }));
              break;

            default:
              break;
          }
        } catch (e) {
          console.error('Falha interpretando evento WebSocket:', e);
        }
      };

      ws.current.onclose = (event) => {
        if (event.code === 4002) return;
        setIsConnected(false);
        retryTimeout = setTimeout(() => {
          connect();
          currentDelay = Math.min(currentDelay * 1.5, MAX_DELAY);
        }, currentDelay);
      };

      ws.current.onerror = () => {
        setIsConnected(false);
        ws.current?.close();
      };
    }

    connect();

    return () => {
      clearTimeout(retryTimeout);
      if (ws.current) {
        ws.current.onclose = null;
        ws.current.close();
      }
    };
  }, [isAuthenticated, onDeviceChange, onPresenceChange, onCommandEvent]);

  return { isConnected };
}
