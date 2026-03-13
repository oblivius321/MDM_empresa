import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext'; // Usa isAuthenticated para controle de ciclo de vida
import { buildWebSocketUrl } from '../services/api';

export function useMDMWebSocket(onDeviceChange: () => void) {
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const { isAuthenticated } = useAuth(); // Assume contexto de auth

  useEffect(() => {
    // Só tenta conectar se tiver logado
    if (!isAuthenticated) return;

    const wsUrl = buildWebSocketUrl('/ws/dashboard');

    function connect() {
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        console.log('🔗 Em Linha! Conectado aos Eventos Radiais MDM.');
        setIsConnected(true);
      };

      ws.current.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('📡 Radar MDM Recebeu:', data);
            
            // Tratamento das fofocas (Broadcasts)
            if (
                data.type === 'DEVICE_EVENT' || 
                data.type === 'DEVICE_DISCONNECTED' || 
                data.type === 'DEVICE_CONNECTED' ||
                data.type === 'DEVICE_ENROLLED' ||
                data.type === 'DEVICE_CHECKIN'
            ) {
                // Aconteceu qualquer coisa crítica em algum lugar da frota.
                // Dispara o pânico positivo para a Tabela de Celulares buscar o BD fresco.
                onDeviceChange();
            }
        } catch (e) {
            console.error('Falha interpretando radiograma Socket do MDM', e);
        }
      };

      ws.current.onclose = () => {
        console.warn('⚠️ Sinal de Radar perdido. Tentando restabelecer em 5s...');
        setIsConnected(false);
        // Reconexão Mágica Infinita Padrão Ouro UX
        setTimeout(connect, 5000);
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket Error:', error);
        ws.current?.close();
      };
    }

    connect();

    return () => {
      // Limpeza sagrada quando o user der logout ou fechar a aba
      ws.current?.close();
    };
  }, [isAuthenticated, onDeviceChange]);

  return { isConnected };
}
