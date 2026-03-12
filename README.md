# Elion MDM (Mobile Device Management)

Sistema robusto de gerenciamento de dispositivos móveis Android Empresariais (Android Enterprise DPC).
Esta documentação é a **única fonte da verdade** para o projeto, consolidando todas as arquiteturas, guias de setup e políticas de segurança.

## 🏗️ Arquitetura do Sistema

O Elion MDM é dividido em 3 camadas principais, orquestradas pelo Docker Compose.

1. **Backend (Python 3.12 + FastAPI)**
   - API RESTful de alta performance.
   - Conexão assíncrona com PostgreSQL via SQLAlchemy (`psycopg2` / `asyncpg`).
   - Autenticação JWT baseada em cookies HTTP-Only e headers para devices.
   - Rotas segregadas e rate-limiting (SlowAPI).

2. **Frontend (React + TypeScript + Vite)**
   - Painel administrativo web (Dashboard) para gerenciamento da frota.
   - Roteamento reativo.
   - Comunicação reversa via proxy Nginx na porta `:80` (em desenvolvimento mapeado com proxy `/api`).
   - WebSockets seguros (dashboard) lendo direto da sessão.

3. **Android Client (DPC - Device Policy Controller)**
   - App Kotlin operando como *Device Owner*.
   - Retrofit para Heartbeats periódicos (Check-ins).
   - OkHttp WebSockets (Conexão persistente para comandos em tempo real - Lock / Wipe / Policies).
   - Envio de telemetria base (Bateria, Sinal, Armazenamento, Localização).

4. **Infraestrutura (Docker + Nginx + PostgreSQL)**
   - Nginx agindo como API Gateway de borda, repassando rotas para o React estático e para a API do FastAPI sob o `/api/`.

---

## 🔒 Postura de Segurança (Hardened Default)

Este projeto contém proteções ativas incorporadas ao código fonte para evitar exploits críticos:

- **Strict Environment Variables:** Qualquer *fallback* hardcoded foi proibido. Se você não fornecer as variávies vitais no arquivo `.env`, o sistema irá se recusar a inicializar (`ValueError`).
- **Device Takeover Prevention:** Dispositivos registrados e ativos não podem ser "sobrepostos" em novos enrolls sem a exclusão manual prévia pelo administrador.
- **WebSocket Header Auth:** Conexões websocket REST não usam mais Query Strings; os tokens são encapsulados em cabeçalhos (ex: `x-device-token`) pelo OKHttp no Android e validados pelo lado do FastAPI.
- **FastAPI TrustedHostMiddleware:** O backend se defende isoladamente contra injeções de Host Header. Rate limiters mitigam Brute Force.
- **Padrão HTTP-Only para Auth web:** Tokens de sessão frontend não residem em LocalStorage; o backend anexa o JWT num cookie travado que viaja automaticamente a cada request na malha do React via Axios intercepters.
- **Senhas Padrão Bloqueadas:** O script `create_admin.py` não insere mais "admin123"; ele extrai mandatoriamente do `.env` (`DEFAULT_ADMIN_PASSWORD`).

---

## 🚀 Como Iniciar (Setup de Desenvolvimento)

### 1. Preparação das Variáveis de Ambiente
Na raiz do repositório, existe um arquivo de modelo chamado `.env.example`. Você deve copiá-lo e renomeá-lo:
```bash
cp .env.example .env
```
Abra o `.env` gerado e preencha as credenciais. **É crucial definir** as tags de segurança:
- `SECRET_KEY` (Chave mestra do JWT)
- `BOOTSTRAP_SECRET` (Senha provisória de Enrollment do Android)
- `DEFAULT_ADMIN_PASSWORD` (Senha ultra forte para seu usuário raiz. Pelo menos 12 caracteres)

### 2. Levantando a Infraestrutura Modular

Utilize o Docker Compose para subir todo o aglomerado de uma vez (Postgres, Nginx, Front, Backend):

```bash
docker-compose up -d --build
```
> O banco de dados persistirá na pasta oculta `.pgdata/` dentro da raiz.

### 3. Criando a Conta Administradora Raiz
O banco PostgreSQL subirá vazio. Para iniciar seu painel, gere sua primeira conta lendo a secret do `.env`:

```bash
docker-compose exec backend python create_admin.py
```
*(Faça login com `admin@empresa.com` utilizando a senha declarada no `.env`)*

---

## 📱 Gerenciamento do Dispositivo Android (DPC)

### Provisionamento (Enrollment) via QR Code / ADB
Para colocar o aparelho sob Gestão Corporativa da sua instância Elion, o aparelho Android precisa ser provisionado imediatamente após o Factory Reset (na tela de "Bem-Vindo" do Google), ou via comando ADB caso seja emulador/teste sem conta Google.

```bash
adb shell dpm set-device-owner com.example.androidmdm/.AdminReceiver
```

Após ativado, o App solicitará credenciais de Bootstrap (`BOOTSTRAP_SECRET` setada no backend) para obter o primeiro `device_token` seguro intransferível.

---

## 🧹 Manutenção e Clean-Up
Se o sistema for migrado no futuro, tome cuidado com:
- O banco Postgres possui volumes persistentes. Remover o container não exclui os usuários. Para resetar a base 100%: `docker-compose down -v`
- Rotação de chaves: Alterar a `SECRET_KEY` matará todas as sessões webs ativas instantaneamente (os usuários terão de relogar). Alterar `BOOTSTRAP_SECRET` não desconectará celulares já registrados, contudo, todos os novos registros demandarão a senha nova.
