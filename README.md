<h1 align="center">
  <img src="./assets/elion-logo-removebg-preview.png" alt="Elion MDM Enterprise Logo" width="300" />
</h1>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-brightgreen">
  <img alt="Python version" src="https://img.shields.io/badge/python-3.10+-blue.svg">
  <img alt="React version" src="https://img.shields.io/badge/react-18.x-blue.svg">
  <img alt="Kotlin version" src="https://img.shields.io/badge/kotlin-1.9+-purple.svg">
</p>

# Elion MDM Enterprise - Master Data Management & Device Control

Uma solução completa e *Full-Stack* de Gerenciamento de Dispositivos Móveis (MDM), focada em segurança corporativa e controle total de frotas Android.

---

## ⚡ Quick Start

**Novo no projeto?** Comece por aqui:

1. **[ESSENTIALS.md](./ESSENTIALS.md)** - Guia rápido de referência (2 min)
2. **[SETUP.md](./SETUP.md)** - Como configurar localmente (5 min)
3. **[ENV_GUIDE.md](./ENV_GUIDE.md)** - Variáveis de ambiente (3 min)

Para começar imediatamente:
```bash
cp .env.development .env  # ou customize
python backend/main.py    # Terminal 1
npm run dev --prefix frontend  # Terminal 2
```

---

## 📖 Visão Geral do Projeto

O **Elion MDM** soluciona as principais dores de uma operação corporativa: Segurança da Informação, Controle de Utilização Externa e Auditoria (Inventário). 

O sistema é formado por três grandes camadas tecnológicas interconectadas:

1. **Admin Dashboard (Frontend):** Interface web rica e intuitiva para o gestor visualizar a frota, impor regras e despachar comandos de emergência (Wipe/Lock).
2. **Core Server (Backend):** A API principal responsável pela orquestração do banco de dados, gestão do enfileiramento de comandos e autenticação.
3. **Elion DPC (Android Device Policy Controller):** O "Agente" embutido nos celulares e tablets da corporação. Ele detém privilégios a nível de Sistema Operacional (Device Admin) para forçar o aparelho a obeceder as regras vindas do Backend.

---

## 🏗️ Stack Tecnológico e Componentes

### 1. Frontend Web (Interface do Gestor)
- **Ecossistema:** React 18 + TypeScript empacotado pelo Vite (garantindo carregamentos quase instantâneos).
- **Design & UI:** Tailwind CSS puro e simplificado, alinhado com padrões minimalistas de UI (Headless UI components + Radix/Shadcn), visando usabilidade.
- **Principais Componentes:**
  - **Dashboard:** Métricas analíticas do sistema.
  - **Painel de Dispositivos:** Lista visual com status real (Online, Offline, Bloqueado). Detalhes ricos como IMEI, nível de bateria e fabricante.
  - **Motor de Políticas:** Capacidade de acionar *Camera Disabled*, *Kiosk Mode*, *Factory Reset* restrito, e proibir instalação de apps fora da loja.
  - **Botões de Resposta Rápida (C2):** Comandos em 1-clique para Lock (Bloqueio remoto), Reboot e **Wipe (Apagar aparelho de fábrica)** em cenários de roubo.

### 2. Backend API (Cérebro do MDM)
- **Framework:** Python com **FastAPI** (Excelente performance em I/O assíncrono).
- **Banco de Dados:** Atualmente em **SQLite** com **SQLAlchemy**, operando de forma assíncrona. Padrão modelado para migração 1:1 para PostgreSQL no futuro via Alembic.
- **Padrão de Arquitetura (Service/Repository):** 
  - Controllers/Rotas isoladas que filtram requisições REST web.
  - Serviços contendo as pesadas regras de negócio e validações Pydantic.
  - Repositórios com as consultas limpas ao Banco de Dados.
- **Ecossistema Real-Time (WebSockets):** O servidor FastAPI conta com um Connection Manager capaz de manter túneis TCP bi-direcionais persistentes. Isso permite transmissão contínua e sem delay de Eventos entre Dispositivos Android -> Servidor Central -> Painel Web do Administrador.
- **Padrão de Enfileiramento (Command Queue):** Todo botão "Wipe" ou "Lock" apertado no Front gera uma *Queue* no banco. A arquitetura de fila suporta as oscilações naturais da internet móvel 4G/5G, garantindo o envio ponta a ponta quando o dispositivo estiver ativo.

### 3. Android DPC (Módulo Mobile em Kotlin)
Desenvolvido via linguagem raiz nativa **Kotlin**. Este App (Agente Invisível) se apodera da `DevicePolicyManager` para operar abaixo do nível dos apps comuns. 
- **`ElionAdminReceiver`:** Observador nativo. Identifica tentativas de quebra de senha na tela de bloqueio e reporta se o Agente for removido.
- **`PolicyManager`:** Módulo utilitário capaz de invocar funções cruciais do Android como `setCameraDisabled()`, forçar modo quiosque/App único via `startLockTask()` e triturar dados forçando um *Hard Reset* via `wipeData()`.
- **`InventoryManager`:** Varredor silencioso que acessa `BatteryManager` e `PackageManager` para levantar a Saúde Física e Digital da máquina (Nível de bateria %, espaço em disco e lista de apps instalados).
- **`FirebaseMessagingService`:** Canal de Comando e Controle (C2). Um *Listener* push de baixo consumo de bateria que reage aos sinais WebSocket do ecossistema do servidor.

---

## 🚀 Como Rodar o Projeto na sua Máquina

### Pré-requisitos Básicos
- **Python** `3.10+` instalado.
- **Node.js** `18+` (com npm).
- (Opcional) **Android Studio** atualizado para compilar o APK nativo.

### Passo 1: Iniciando a API (Backend)
Abra o seu terminal na raiz do projeto:

```bash
# Navegue até a pasta do backend
cd backend

# Crie um ambiente virtual isolado Python
python -m venv .venv

# Ative o ambiente virtual - Exemplo no Windows (Powershell):
.\.venv\Scripts\activate
# Ou no Mac/Linux:
# source .venv/bin/activate

# Instale os requerimentos do projeto
pip install -r requirements.txt

# Suba a API FastAPI (Na porta 8000)
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
*(Documentação Swagger da API rodando em: `http://localhost:8000/docs`)*

### Passo 2: Iniciando o Painel do Gestor (Frontend)
Abra uma **nova** janela/aba no seu Terminal:

```bash
# Na base do projeto, navegue para o Frontend
cd frontend

# Instale os pacotes NPM
npm install

# Suba o servidor SPA React (Vite)
npm run dev
```
*(O Sistema Frontend Web rodará em: `http://localhost:5173`)*

### Passo 3: O Dispositivo Android
1. Abra o **Android Studio** e importe apenas a pasta `android/`.
2. Aguarde o *Gradle Sync* (já foi otimizado para não congelar o PC com build paralelo e caching de módulos independentes no arquivo `gradle.properties`).
3. Compile o aplicativo para um emulador.
4. Conceda privilégios de **Administrador do Dispositivo** manuais na aba e painel de *Segurança* e *Privacidade* das configurações Android do celular, referenciando o `Elion MDM DPC`.

---

## 🔒 Roadmap e Melhorias Arquiteturais

A arquitetura atual serve muito bem como MDM Standalone, mas o plano a longo prazo aponta para integrações Cloud State-of-Art:

- [ ] **Integração Plena Firebase (FCM):** Fechar o ciclo do C2 Push Notification para Android, enviando o Payload exato e imediato gerado pelo Python para acordar o smartphone via rede móvel desligada.
- [ ] **Migração Oficial Android Enterprise (AMAPI):** Promover o agente DPC baseado em Admin Receivers *Legacy* para o ecosistema em nuvem moderno da "Android Management API" em infraestrutura serverless da Google.
- [ ] **Geolocalização (Tracking):** Implementação de telemetria GPS e renderização em interface Web baseada em OpenStreetMaps/Leaflet.
- [ ] **RabbitMQ / Redis:** Adicionar camada de Pub/Sub na nuvem para tirar a sobrecarga de Command Queueing do banco relacional principal.

---
<p align="center">
  <i>Construído sob fundamentos rígidos de Engenharia de Software Moderna.</i>
</p>
