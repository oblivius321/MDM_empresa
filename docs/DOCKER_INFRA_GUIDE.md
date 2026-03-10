# 🐳 Guia de Infraestrutura Docker Local

Este guia explica como a arquitetura do Docker Compose foi configurada, como gerenciar os ambientes e como validar a saúde do banco de dados.

## 🧠 Como a Conexão Funciona (A Lógica)

- **Comunicação DENTRO do Docker**: Containers se comunicam entre si através do nome do serviço definido no `docker-compose.yml`. Para o Backend chegar no Banco, ele **não** usa `localhost`. Ele acessa pela rede interna usando o host `postgres`, ex: `postgresql+asyncpg://admin:senha@postgres:5432/banco`.
- **Comunicação FORA do Docker (Seu PC Windows)**: Ferramentas locais como o **pgAdmin** ou o seu **Frontend rodando via `npm run dev`** não enxergam a rede interna do Docker pelo nome `postgres`. Eles devem usar `localhost:5432` como ponte (já que a porta 5432 foi exposta no host).
- **Sobre o Arquivo `.env`**: O Docker Compose lê **automaticamente** apenas o arquivo `.env` na raiz por padrão. Arquivos com sufixos diferentes (como `.env.development` e `.env.production`) são apenas templates e referências para você gerir separadamente. Para trocar de ambiente, você copia o conteúdo desejado para o arquivo `.env` definitivo.

---

## 🛠️ Comandos Essenciais

### 1. Subir o Projeto Completo (Background)
Reconstrói as imagens (caso haja mudanças) e sobe tudo em segundo plano (detached mode).
```bash
docker compose up -d --build
```

### 2. Verificar os Containers Rodando
Valide se os 4 containers estão UP e saudáveis.
```bash
docker ps
```

### 3. Verificar Logs Estritos
Se algo der errado (banco reiniciando, backend falhando), consulte os logs reais de cada container:
```bash
docker compose logs postgres
docker compose logs backend
```

### 4. Recriar o Banco do ZERO (Destrutivo)
⚠️ **Atenção**: Isso apaga os volumes do banco, deletando todos os dados locais. Útil quando dados se corrompem com migrações ou trocas de senhas/roles conflitantes na infra:
```bash
docker compose down -v
docker compose up -d --build
```

---

## 🗄️ Como Conectar no pgAdmin localmente
Se você tem o pgAdmin (ou DBeaver / DataGrip) instalado no seu Windows:
- **Host / Servidor**: `localhost` *(Não use `postgres` aqui!)*
- **Porta**: `5432`
- **Database**: O valor que você setou em `DB_NAME` (ex: `mdm_project`)
- **Usuário**: O valor de `DB_USER` (ex: `postgres`)
- **Senha**: O valor de `DB_PASSWORD` (ex: `Sherlock314`)

---

## 🩺 Como Identificar se o Postgres está Saudável
O novo `docker-compose.yml` possui **Healthchecks nativos**!
Quando você rodar um `docker ps`, verá ao lado do status "Up X minutes" a flag:
- `(health: starting)` -> O banco está bootando. O Backend vai ficar esperando (depend_on: condition: service_healthy).
- `(healthy)` -> 🟢 Pronto para aceitar conexões na porta 5432. O Backend irá ligar.
- `(unhealthy)` -> 🔴 Algo quebrou (geralmente erro de credencial, falta de espaço ou corrupção de volume). Use o comando de logs do postgres `docker compose logs postgres` para debugar.
