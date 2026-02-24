<h1 align="center">
  <img src="./assets/elion-logo-removebg-preview.png" alt="Elion MDM Enterprise Logo" width="300" />
</h1>

<p align="center">
  <img alt="GitHub language count" src="https://img.shields.io/github/languages/count/seu-usuario/elion-mdm-enterprise">
  <img alt="Repository size" src="https://img.shields.io/github/repo-size/seu-usuario/elion-mdm-enterprise">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-brightgreen">
  <img alt="Python version" src="https://img.shields.io/badge/python-3.10+-blue.svg">
  <img alt="React version" src="https://img.shields.io/badge/react-18.x-blue.svg">
</p>

<p align="center">
  <strong>Solução de Gerenciamento de Dispositivos Móveis (MDM) baseada na arquitetura Android Enterprise.</strong>
</p>

## 📖 Visão Geral

O **MDM Enterprise** é uma plataforma Full-Stack de gerenciamento de frotas de dispositivos Android focada em segurança corporativa (Device Owner). O projeto adota uma arquitetura em camadas e filas assíncronas para garantir **desacoplamento**, **escalabilidade** e **previsibilidade** na comunicação entre o portal administrativo e as dezenas ou milhares de dispositivos-cliente.

Este projeto demonstra fluência nos seguintes conceitos de engenharia de software corporativa:
- **Segurança & Políticas Restritivas** (Implementação baseada em Zero-Trust e JWT por dispositivo).
- **Enfileiramento de Comandos (Command Dispatcher)** em detrimento de requisições síncronas para comunicação com dispositivos.
- **RESTful API Design**, fortemente tipada e validada.
- **Ecossistema Assíncrono** (I/O non-blocking no Backend com FastAPI + aiosqlite).

---

## 🏗️ Decisões Arquiteturais e Stack

A escolha do stack tecnológico não foi acidental. Priorizou-se a manutenibilidade, a tipagem estrita (tanto no Front quanto no Back) e o isolamento das regras de negócio.

### Backend (Core Server) - `Python & FastAPI`
- **FastAPI**: Escolhido pelo processamento assíncrono nativo (ASGI), validação embutida baseada em Tipagem Pydantic, e geração automática de documentação OpenAPI.
- **Arquitetura Service/Repository**: O código está estritamente dividido. *Controllers* (Rotas) apenas interagem com a camada HTTP. As regras de negócio vitais do MDM ficam no *Service Layer*, que por sua vez solicita dados abstratos ao *Repository*.
- **Pydantic**: Previne que *payloads* malformados vindos dos dispositivos corrompam o sistema.
- **SQLite + SQLAlchemy (Async)**: Configurado em assíncrono para garantir rápida absorção de milhares de chamadas de *Heartbeat* e transações de banco atômicas.

### Frontend (Admin Dashboard) - `React & TypeScript`
- **Vite & React 18**: Ferramentas modernas que evitam o overhead histórico do CRA, garantindo *Builds* de microssegundos em desenvolvimento.
- **Tailwind CSS + Shadcn UI (Headless UI)**: Para garantir que o estilo não fique espalhado em centenas de arquivos CSS difíceis de manter. O uso de Headless Components (Radix) foca a atenção na lógica, com acessibilidade nativa (A11y).
- **TanStack Query (React Query)**: Responsável pelo *caching* inteligente, *retries*, e estado assíncrono das tabelas, removendo a necessidade de middlewares verbosos de estado global (como Redux Thunk).

---

## ⚙️ Arquitetura de Comunicação (Device & Server)

Em um cenário MDM, não podemos confiar que a internet móvel do dispositivo seja estável. Por isso adotamos um **Design baseado em Heartbeat e Filas (Command Queue Pattern)**:

1. **Enrollment**: O dispositivo solicita pareamento enviando suas chaves biométricas/hardware e recebe um Token JWT de autenticação com limite de escopo.
2. **Heartbeat Inteligente**: Para evitar DDoS autoinfligido, o Device envia sinalizações espaçadas (Battery, Rede, Status de Kiosk) sem manter um Websocket ativo despensioso.
3. **Queue Assíncrona**: O operador no Frontend que pede o "Wipe" do dispositivo não manda o comando direto. O Backend armazena na Tabela `commands` com a flag `pending`. No próximo `Heartbeat`, o dispositivo "puxa" os comandos pendentes.

---

## 🚀 Como Rodar Localmente

Certifique-se de que possui `Python 3.10+` e `Node.js 18+`.

### 1. Iniciar o Core Backend

```bash
# Navegue até o root do projeto
python -m venv .venv

# Ative o ambiente (*Nix/Mac)
source .venv/bin/activate
# Ative o ambiente (Windows)
.\.venv\Scripts\Activate.ps1

# Instale as dependências
pip install -r requirements.txt

# (Opcional) Inicialize os Schemas do Banco de Dados
python backend/migrate.py

# Inicie o Servidor Asíncrono
python -m uvicorn backend.main:app --reload
```
A Healthcheck API e Swagger docs estarão em `http://localhost:8000/docs`.

### 2. Iniciar o Admin Frontend

Abra um novo terminal pane.

```bash
cd frontend
npm install
npm run dev
```

A interface estará acessível via `http://localhost:5173`. Para testar integrações sem abrir os dois componentes manualmente, utilize o script encurtador `start_app.bat` na raiz (Windows).

---

## 🔒 Considerações Futuras para Produção (Roadmap)
- [ ] Integrar com **Google Cloud Pub/Sub** e oficializar a subscrição no painel Google Android Management API.
- [ ] Alterar DSN do banco de dados para instâncias maduras baseadas em **PostgreSQL**.
- [ ] Injetar **Redis** para a fila em memória (Substituir processamento da fila via banco relacional pelo Redis, removendo gargalos de Lock de Tabelas na leitura em massa do Heartbeat).

---

<p align="center">
  Desenvolvido com foco em escalabilidade corporativa e padrões de arquitetura de software limpa.
</p>
