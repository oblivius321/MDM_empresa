<p align="center">
  <h1 align="center">🖥️ Elion MDM — Frontend</h1>
  <p align="center">
    <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react" />
    <img src="https://img.shields.io/badge/Vite-5-646CFF?style=flat-square&logo=vite" />
    <img src="https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript" />
    <img src="https://img.shields.io/badge/TailwindCSS-3-06B6D4?style=flat-square&logo=tailwindcss" />
  </p>
</p>

> 🔙 [Voltar ao README Principal](../README.md) · ⚡ [Backend API](../backend/README.md) · 📱 [Android Agent](../android/README.md)

---

## Visão Geral

O frontend é um dashboard administrativo SPA para gerenciamento de frotas de dispositivos Android corporativos. Oferece visibilidade em tempo real do status dos dispositivos, saúde de compliance, enforcement de políticas e execução remota de comandos — tudo alimentado por uma conexão WebSocket persistente com o backend.

---

## Estrutura de Diretórios

```
frontend/src/
├── App.tsx                        # Componente raiz + roteamento
├── main.tsx                       # Ponto de entrada
├── pages/
│   ├── Login.tsx                  # Autenticação JWT
│   ├── Dashboard.tsx              # Visão geral da frota (online, compliance, saúde)
│   ├── Devices.tsx                # Lista de dispositivos com status em tempo real
│   ├── DeviceDetail.tsx           # Telemetria, comandos, histórico
│   ├── Policies.tsx               # CRUD de Provisioning Profiles
│   ├── Logs.tsx                   # Trilha de auditoria (filtro por ação/ator)
│   └── Settings.tsx               # Configurações da plataforma
├── components/
│   └── policies/
│       ├── PolicyBuilder.tsx      # Editor visual de políticas
│       ├── RestrictionsBlock.tsx   # Configuração de restrições de segurança
│       ├── KioskSettingsBlock.tsx  # Configuração do modo kiosk
│       └── AppManagementBlock.tsx  # Whitelist/blacklist de apps
├── hooks/
│   └── useMDMWebSocket.ts        # Hook de ciclo de vida WebSocket
├── services/
│   └── api.ts                    # Cliente Axios (interceptor JWT)
├── store/
│   └── useMDMStore.ts            # Gerenciamento de estado (Zustand)
├── contexts/                      # Providers de contexto React
└── lib/                           # Funções utilitárias
```

---

## Como Funciona

### Roteamento de Páginas

| Rota | Página | Função |
|---|---|---|
| `/login` | Login | Autenticação JWT |
| `/dashboard` | Dashboard | KPIs da frota: contagem online, compliance score, alertas |
| `/devices` | Devices | Lista de dispositivos em tempo real com badges de status |
| `/devices/:id` | DeviceDetail | Telemetria individual, **Fila de Comandos (Enviado, Pendente, Falha, Latência)**, envio remoto, histórico completo |
| `/policies` | Policies | CRUD de Provisioning Profiles |
| `/logs` | Logs | Trilha de auditoria com filtros por ação/ator |
| `/settings` | Settings | Preferências da plataforma |

### Motor de Tempo Real

O dashboard mantém uma conexão WebSocket persistente para receber atualizações ao vivo:

```
Dashboard ──► /api/ws/dashboard?token={jwt}
                    │
                    ├── DEVICE_ONLINE / DEVICE_OFFLINE
                    ├── COMPLIANCE_UPDATE (mudança de score)
                    ├── CMD_ACK / CMD_EXECUTED / CMD_VERIFIED
                    ├── CMD_RETRYING
                    └── POLICY_DRIFT_DETECTED
```

**Hook: `useMDMWebSocket`**
- Gerencia conexão, reconexão e despacho de mensagens.
- Reconexão automática com backoff em caso de perda de conexão.
- Despacha eventos para o store Zustand para reatividade na UI.

### Gerenciamento de Estado

Utiliza **Zustand** (`useMDMStore`) para estado global leve:
- Lista de dispositivos com atualizações de status ao vivo.
- Rastreamento de comandos (em andamento, concluídos, falhados).
- Agregação de compliance score.

### Integração com API

Todas as chamadas REST passam pelo `services/api.ts`:
- Instância Axios com interceptor de token JWT.
- Tratamento automático de refresh de token.
- URL base configurada via variável de ambiente.

> Para a referência completa de endpoints da API, veja o [README do Backend](../backend/README.md).

---

## Setup Local

```bash
cd frontend

# Instalar dependências
npm install

# Iniciar servidor de desenvolvimento
npm run dev
# → http://localhost:5173

# Build para produção
npm run build
```

### Variáveis de Ambiente

Configure via `.env` no diretório `frontend/`:

| Variável | Propósito |
|---|---|
| `VITE_API_URL` | URL base da API do backend |
| `VITE_WS_URL` | Endpoint WebSocket |

### Docker

```bash
# Modo desenvolvimento (a partir da raiz do projeto)
docker compose up frontend -d
# → disponível em http://localhost:3000
```

---

## Stack Tecnológica

| Tecnologia | Função |
|---|---|
| React 18 | Framework de componentes |
| Vite 5 | Ferramenta de build + HMR |
| TypeScript 5 | Segurança de tipos |
| TailwindCSS 3 | Estilização utility-first |
| React Router | Roteamento client-side |
| Zustand | Gerenciamento de estado leve |
| Axios | Cliente HTTP |
| WebSocket API | Comunicação em tempo real |
