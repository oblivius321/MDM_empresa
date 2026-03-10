# Relatório Completo de Handoff para Antigravity

**Projeto:** Elion MDM Enterprise  
**Data:** 2026-03-10  
**Objetivo:** fornecer um plano executável para deixar o sistema rodando de forma estável, com superfície de ataque mínima e hardening de produção.

---

## 1) Resumo Executivo

O projeto já possui uma boa base full-stack (FastAPI + React + Android DPC), mas há riscos críticos de segurança e confiabilidade que impedem considerar o ambiente como “produção segura”.

### Severidade geral atual
- **Crítico:** autenticação ausente em endpoints de device e websockets.
- **Alto:** defaults inseguros de segredos/senhas; sessão JWT sem refresh/revogação; token persistido em `localStorage`.
- **Médio:** falta de rate-limit, validações de payload device mais rígidas, testes backend inexistentes, ausência de scanner SCA no CI.
- **Baixo:** alinhamento de documentação, melhorias de observabilidade e compliance.

### Resultado esperado após execução do plano
- API com autenticação forte para operador e device (mTLS/API key rotacionável).
- WebSocket autenticado e autorizado por papel (dashboard/device).
- Segredos removidos de defaults e injetados via secret manager.
- CI com testes, lint, SCA, SAST e gates de qualidade.
- Deploy reproduzível com rollback e métricas/alertas.

---

## 2) Escopo analisado

- Backend FastAPI, rotas REST e WebSocket.
- Configuração de ambiente e compose.
- Fluxo de autenticação no frontend.
- Dependências e cobertura de testes.

> Observação: auditoria de CVEs automatizada em registries públicos foi bloqueada por restrição de rede/proxy neste ambiente, então a parte de SCA externa precisa ser executada no seu CI/rede corporativa.

---

## 3) Achados Técnicos (com prioridade)

## P0 — Crítico (corrigir imediatamente)

### P0.1 Endpoints de device sem autenticação/autorização
As rotas de check-in e fila de comandos do dispositivo são públicas e permitem interação sem credencial de dispositivo.

**Impacto:** qualquer ator que descubra/guess `device_id` pode injetar status, consumir comandos, alterar ACK/estado e afetar operação de frota.

**Evidências:**
- `/devices/{device_id}/checkin` sem `get_current_user` ou equivalente para device auth.
- `/devices/{device_id}/commands/pending`, `/ack`, `/status`, `/failed` também sem autenticação.

**Correção alvo:**
1. Criar autenticação de dispositivo (API key por device + rotação + hash no banco, ou mTLS).
2. Exigir `Depends(get_current_device)` em todas as rotas device.
3. Garantir autorização por vínculo: `current_device.device_id == path_device_id`.
4. Assinar eventos críticos e registrar trilha de auditoria.

---

### P0.2 WebSockets sem autenticação
Conexões `/ws/dashboard` e `/ws/device/{device_id}` são aceitas sem validação de token/chave.

**Impacto:** cliente não autenticado pode assinar eventos sensíveis ou se passar por dispositivo.

**Correção alvo:**
1. Exigir token JWT (dashboard) via query/header e validar no handshake.
2. Exigir token de device/API key na rota de device.
3. Isolar canais por tenant/escopo e validar autorização por recurso.
4. Encerrar conexão com `1008` (policy violation) quando inválida.

---

### P0.3 Segredos e credenciais padrão inseguras
Há defaults de senha/secret em exemplos e compose que facilitam configuração insegura acidental.

**Impacto:** comprometimento de JWT signing key, banco e ambiente inteiro em caso de uso de defaults.

**Correção alvo:**
1. Remover defaults de segredos no `docker-compose`.
2. Fazer startup falhar quando `SECRET_KEY`/`DB_PASSWORD` não estiverem definidos em produção.
3. Migrar para Secret Manager (Vault/AWS SM/GCP Secret Manager).
4. Bloquear commit de `.env*` sensíveis com pre-commit/CI policy.

---

## P1 — Alto

### P1.1 JWT com sessão longa e sem refresh/revogação robusta
Token de acesso com 7 dias e sem fluxo real de refresh/revogação centralizada.

**Risco:** se token vazar, janela de abuso é longa.

**Correção alvo:**
- Access token curto (10–20 min) + refresh token rotativo (HTTP-only cookie ou storage seguro no app nativo).
- Lista de revogação/jti com expiração.
- “Logout all sessions” por usuário/tenant.

---

### P1.2 Token no `localStorage` no frontend
Uso de `localStorage` para `auth_token` facilita exfiltração em cenários XSS.

**Correção alvo:**
- Preferir cookie `HttpOnly + Secure + SameSite=strict` para sessão web.
- CSP estrita e sanitização de entradas.
- Reduzir superfícies de script inline.

---

### P1.3 Falta de rate-limiting e proteção contra brute force
Endpoints de login/registro sem limitação explícita.

**Correção alvo:**
- Rate-limit por IP + usuário + ASN/reputação (ex.: slowapi/redis).
- Lockout progressivo com backoff.
- Captcha/turnstile após tentativas anômalas.

---

## P2 — Médio

### P2.1 Falta de testes backend
Não há suíte backend automatizada para garantir regressão zero em segurança e negócio.

**Correção alvo:**
- Testes unitários: auth, autorização, command queue, device auth.
- Testes integração: fluxo login→comando→ack.
- Contratos OpenAPI e testes de permissão por endpoint.

### P2.2 SCA/SAST não institucionalizados
Sem evidência de pipeline bloqueante para vulnerabilidades.

**Correção alvo:**
- Backend: `pip-audit` / `safety` / `osv-scanner`.
- Frontend: `npm audit` + `osv-scanner`.
- SAST: Semgrep/CodeQL.
- Política de bloqueio por severidade (ex.: CVSS >= 7).

### P2.3 Falta de baseline de observabilidade de segurança
Sem trilha clara de auditoria estruturada para ações críticas.

**Correção alvo:**
- Logs JSON com `request_id`, `user_id/device_id`, IP, ação, resultado.
- Métricas de segurança (login_fail_rate, comando_falhado, ws_auth_fail).
- Alertas em SIEM (Elastic/Splunk/Datadog).

---

## 4) Plano de execução para “rodar perfeitamente”

## Fase A (48–72h) — Estancar risco crítico
1. Implementar auth de device + proteção total de rotas device (P0.1).
2. Autenticar websockets de dashboard/device (P0.2).
3. Remover defaults de segredos e falha segura no bootstrap (P0.3).
4. Deploy com rotação imediata de segredos.

**Critério de aceite:** nenhum endpoint crítico acessível sem credencial válida.

## Fase B (3–5 dias) — Endurecer sessão e borda
1. JWT curto + refresh rotativo + revogação.
2. Troca de `localStorage` para cookie HttpOnly (web).
3. Rate-limiting + lockout + proteção brute force.
4. CORS estrito por ambiente (sem curingas e sem localhost em prod).

**Critério de aceite:** sessão resistente a replay/token theft básico e brute force controlado.

## Fase C (1 semana) — Qualidade operacional
1. Testes backend + integração + segurança em CI.
2. SCA/SAST com gate de merge.
3. Auditoria de logs e dashboard de segurança.
4. Runbook de incidentes e rollback.

**Critério de aceite:** pipeline bloqueia regressão de segurança e há visibilidade operacional.

---

## 5) Backlog de implementação (pronto para ticket)

## Epic 1 — Device Trust
- [ ] Criar tabela `device_credentials` (hash, rotação, última utilização, status).
- [ ] Endpoint de provisioning seguro de credencial do device.
- [ ] Middleware/dependency `get_current_device`.
- [ ] Aplicar `get_current_device` em checkin/comandos/ack/status.
- [ ] Testes de autorização por `device_id`.

## Epic 2 — WebSocket Security
- [ ] JWT obrigatório em `/ws/dashboard`.
- [ ] Credencial de device obrigatória em `/ws/device/{device_id}`.
- [ ] Fail-fast com close code adequado.
- [ ] Testes de handshake autorizado/não autorizado.

## Epic 3 — Secrets & Config Hardening
- [ ] Eliminar secrets padrão no compose.
- [ ] Boot fail em produção com segredo fraco/ausente.
- [ ] Integrar secret manager.
- [ ] Scanner de secret em pre-commit e CI.

## Epic 4 — Session Security
- [ ] Refresh token rotativo e revogação.
- [ ] Cookie HttpOnly no frontend web.
- [ ] Logout global e revogação por usuário.

## Epic 5 — Defensive Controls
- [ ] Rate-limit em auth e endpoints sensíveis.
- [ ] Detecção de abuso (IP/device fingerprint).
- [ ] Alertas para anomalias críticas.

## Epic 6 — DevSecOps
- [ ] Pipeline CI: lint + test + SAST + SCA.
- [ ] Política de bloqueio por severidade.
- [ ] Artefatos SBOM (CycloneDX).

---

## 6) Prompt pronto para Antigravity (copiar e colar)

```text
Você é um engenheiro sênior de segurança e confiabilidade. Trabalhe no repositório Elion MDM e execute o plano abaixo com foco em zero regressão funcional e mínimo risco:

1) Implementar autenticação/autorização de dispositivos:
- Criar credencial por dispositivo (API key rotacionável, armazenada com hash).
- Proteger endpoints:
  - POST /api/devices/{device_id}/checkin
  - GET /api/devices/{device_id}/commands/pending
  - POST /api/devices/{device_id}/commands/{command_id}/ack
  - POST /api/devices/{device_id}/commands/{command_id}/status
  - GET /api/devices/{device_id}/commands/{command_id}/status
  - GET /api/devices/{device_id}/commands/failed
- Garantir que device autenticado só acesse seu próprio device_id.

2) Proteger WebSockets:
- Exigir JWT válido para /api/ws/dashboard.
- Exigir credencial de device para /api/ws/device/{device_id}.
- Encerrar conexão não autorizada com policy violation.

3) Hardening de configuração e segredos:
- Remover defaults inseguros de SECRET_KEY e DB_PASSWORD.
- Falhar startup em produção se segredo estiver ausente/fraco.
- Atualizar documentação de env para uso com secret manager.

4) Sessão e frontend:
- Migrar token web de localStorage para cookie HttpOnly+Secure+SameSite.
- Implementar refresh token rotativo e revogação.

5) Controles de borda:
- Adicionar rate-limit em login/registro e endpoints sensíveis.
- Backoff/lockout progressivo para brute force.

6) Qualidade e validação:
- Criar testes backend cobrindo auth/autz e rotas críticas.
- Adicionar pipeline CI com lint/test/SAST/SCA.
- Entregar changelog técnico, instruções de migração e rollback.

Condições:
- Não quebrar contratos existentes sem migration guide.
- Preferir mudanças incrementais e commit por etapa.
- Gerar checklist final de verificação de segurança e operação.
```

---

## 7) Comandos recomendados para validação (rodar no seu ambiente/CI)

```bash
# Frontend
cd frontend
npm ci
npm run lint
npm test
npm run build

# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q

# Segurança (executar em rede com acesso aos registries)
pip-audit -r requirements.txt
cd frontend && npm audit --production
semgrep --config auto .
```

---

## 8) Evidências objetivas encontradas no código

1. Rotas de device sem auth explícita em `routes.py` (checkin/comandos/ack/status/failed).  
2. WebSockets aceitam conexão sem validação de credencial em `websocket_routes.py` e `websockets.py`.  
3. Defaults sensíveis em `docker-compose.yml`, `backend/.env.example` e `.env.development`.  
4. Fallback de `SECRET_KEY` no backend caso não definido.  
5. Token JWT armazenado em `localStorage` no frontend (`AuthContext.tsx`).

---

## 9) Meta realista de segurança

“Vulnerabilidade nula” absoluta não existe em software vivo. A meta correta é:
- reduzir drasticamente risco explorável,
- detectar rapidamente anomalias,
- responder com rollback/control plane,
- manter melhoria contínua (patching + testes + observabilidade).

Com as fases A/B/C implementadas, o projeto alcança um patamar **forte de segurança prática** para operação corporativa.
