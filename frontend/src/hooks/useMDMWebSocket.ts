import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { buildWebSocketUrl } from '../services/api';

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
 * @param onDeviceChange   Callback chamado em qualquer evento (força refresh da lista)
 * @param onPresenceChange Callback com payload { device_id, status } em eventos de
 *                         conexão/desconexão. Atualiza o badge LOCALMENTE sem roundtrip.
 * @param onCommandEvent   Callback com payload de evento de comando (CMD_SENT, CMD_ACKED,
 *                         CMD_COMPLETED, CMD_FAILED). Atualiza o status do comando na UI
 *                         sem nova requisição à API.
 */
export function useMDMWebSocket(
  onDeviceChange: () => void,
  onPresenceChange?: (event: PresenceEvent) => void,
  onCommandEvent?: (event: CommandEvent) => void,
) {
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const { isAuthenticated } = useAuth();

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
          // Trata strings simples (ping/pong do server)
          if (typeof event.data === 'string' && !event.data.startsWith('{')) {
            if (event.data === 'ping') ws.current?.send('pong');
            return;
          }

          const data = JSON.parse(event.data);

          switch (data.type) {
            // ─── Presença: Atualiza badge localmente sem nova requisição GET ──
            // O backend envia { device_id, status } diretamente no payload.
            case 'DEVICE_CONNECTED':
            case 'DEVICE_DISCONNECTED': {
              if (onPresenceChange && data.device_id && data.status) {
                onPresenceChange({
                  device_id: data.device_id,
                  status: data.status as 'online' | 'offline',
                });
              }
              // fallback: também força refresh completo da lista
              onDeviceChange();
              break;
            }

            // ─── Eventos que requerem refresh de lista ────────────────────────
            case 'DEVICE_CHECKIN':
            case 'DEVICE_ENROLLED':
            case 'DEVICE_EVENT':
              onDeviceChange();
              break;

            // ─── Eventos de Comando (tempo real, sem roundtrip GET) ───────────
            // O backend emite CMD_SENT/ACKED/COMPLETED/FAILED com payload completo.
            // onCommandEvent atualiza o indicador de status na UI diretamente.
            case 'CMD_SENT':
            case 'CMD_ACKED':
            case 'CMD_COMPLETED':
            case 'CMD_FAILED': {
              if (onCommandEvent && data.command_id != null) {
                onCommandEvent(data as CommandEvent);
              }
              break;
            }

            // ─── Heartbeat Bidirecional: Backend → Dashboard ──────────────────
            // Backend envia server_ping para detectar NAT timeout / conexão travada.
            // Dashboard responde com pong.
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
        // 4002 = auth_failed → não faz sentido tentar reconectar
        if (event.code === 4002) {
          console.error('❌ WebSocket: autenticação negada (4002). Não tentará reconectar.');
          return;
        }
        console.warn(`⚠️ Radar desconectado. Próxima tentativa em ${currentDelay / 1000}s...`);
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
