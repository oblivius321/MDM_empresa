# 🛡️ Sistema RBAC Enterprise para MDM Elion

## 📋 Sumário do que foi implementado

### ✅ 1. Modelagem de Banco (PostgreSQL)

**Tabelas criadas:**
- `roles` - Funções/papéis do sistema (SUPER_ADMIN, ADMIN, OPERATOR, VIEWER)
- `permissions` - Permissões granulares (users:create, devices:wipe, etc)
- `role_permissions` - Associação M:N entre roles e permissions
- `user_roles` - Associação M:N entre usuários e roles (com auditoria de quem atribuiu)
- `audit_logs` - Log imutável (append-only) de todas ações críticas

**Características:**
- ENUMS PostgreSQL para validação no banco
- Índices otimizados para queries frequentes (auditoria, lookups)
- Constraints de segurança (CASCADE delete, FK integridade)
- Hierarquia de prioridade (SUPER_ADMIN=1000 > ADMIN=100 > OPERATOR=10 > VIEWER=1)

### ✅ 2. Modelos SQLAlchemy

**Arquivos criados:**
- `backend/models/role.py` - Modelo Role com relacionamentos
- `backend/models/permission.py` - Modelo Permission
- `backend/models/audit_log.py` - Modelo AuditLog com tipos de ações
- Atualizado `backend/models/user.py` - Adicionado relação M:N com roles e métodos helper

**Features:**
- Properiedades computed em User (`all_permissions`, `highest_role_priority`)
- Métodos helper para verificação de permissão (`has_permission`, `has_any_permission`, `has_all_permissions`)
- Suporte a MFA e ações críticas

### ✅ 3. Schemas Pydantic

**Arquivos criados:**
- `backend/schemas/role.py` - Schemas para CRUD de roles
- `backend/schemas/permission.py` - Schemas para permissões
- `backend/schemas/audit_log.py` - Schemas para logs e filtros
- Atualizado `backend/schemas/user.py` - Adicionado schemas com roles e permissões

### ✅ 4. Repositórios

**Arquivos criados:**
- `backend/repositories/role_repo.py` - Query builder para roles (read, create, update, delete, permission management)
- `backend/repositories/permission_repo.py` - Query builder para permissions
- `backend/repositories/audit_repo.py` - Query builder para audit logs (append-only, retention policy)

**Features:**
- Queries otimizadas com selectinload (lazy loading)
- Paginação
- Índices compostos para performance
- Suporte a batching de operações

### ✅ 5. Serviços de Negócio

**Arquivos criados:**
- `backend/services/rbac_service.py` - Lógica de RBAC
  - `initialize_rbac()` - Inicializa roles e permissões padrão (idempotente)
  - `assign_role_to_user()` - Atribui role com validações anti-escalation
  - `revoke_role_from_user()` - Remove role com proteções
  - `check_privilege_escalation()` - Valida ataques de escalação
  - `can_user_perform_action()` - Verifica permissão

**Proteções de segurança:**
- ADMIN não pode criar SUPER_ADMIN
- Não pode remover último SUPER_ADMIN
- Não pode atribuir role que não possui
- Logs de tentativas de escalação

### ✅ 6. Decorators para Endpoints

**Arquivo criado:** `backend/utils/decorators.py`

**Decorators:**
```python
@require_permission("devices:wipe")
async def wipe_device(...):
    pass

@require_all_permissions("devices:read", "devices:lock")
async def lock_device(...):
    pass

@require_role("SUPER_ADMIN")
async def delete_logs(...):
    pass

@require_mfa_verified
@require_permission("devices:wipe")
async def wipe_device(...):
    pass

@audit_action("DEVICE_WIPE", "devices")
async def wipe_device(...):
    pass
```

**Helper class:**
```python
checker = PermissionChecker(current_user)
checker.assert_permission("devices:wipe")
checker.assert_role("SUPER_ADMIN")
```

### ✅ 7. Endpoints REST

**Arquivo criado:** `backend/api/rbac_routes.py`

**Endpoints implementados:**

```
🔒 ROLES
  GET    /api/rbac/roles                           - Listar roles
  GET    /api/rbac/roles/{role_id}                 - Detalhes role
  POST   /api/rbac/roles                           - Criar role [SUPER_ADMIN]
  PUT    /api/rbac/roles/{role_id}                 - Atualizar role [SUPER_ADMIN]
  DELETE /api/rbac/roles/{role_id}                 - Deletar role [SUPER_ADMIN]

🔒 PERMISSIONS
  GET    /api/rbac/permissions                     - Listar permissões
  GET    /api/rbac/permissions/{perm_id}           - Detalhes permissão
  POST   /api/rbac/roles/{role_id}/permissions/{perm_id}    - Adicionar permissão [SUPER_ADMIN]
  DELETE /api/rbac/roles/{role_id}/permissions/{perm_id}    - Remover permissão [SUPER_ADMIN]

🔒 USER-ROLE MANAGEMENT
  POST   /api/rbac/users/{user_id}/roles/{role_id}         - Atribuir role [roles:assign]
  DELETE /api/rbac/users/{user_id}/roles/{role_id}         - Remover role [roles:revoke]
  GET    /api/rbac/users/{user_id}/permissions             - Listar permissões do user

🔒 AUDITORIA
  GET    /api/rbac/audit                          - Listar logs (com filtros)
  GET    /api/rbac/audit/critical                 - Ações críticas apenas [ADMIN+]
  DELETE /api/rbac/audit/{log_id}                 - Deletar log [SUPER_ADMIN]
```

### ✅ 8. Definições de Roles e Permissions

**Arquivo criado:** `backend/utils/rbac_constants.py`

**Roles predefinidos:**
- **SUPER_ADMIN** (Priority 1000) - Controle total: criar roles, deletar logs, wipe, etc
- **ADMIN** (Priority 100) - Controle operacional: criar usuários, gerenciar devices, mas não poder criar SUPER_ADMIN
- **OPERATOR** (Priority 10) - Ações diárias: lock/unlock, install app
- **VIEWER** (Priority 1) - Somente leitura: dashboard, logs

**Permissões granulares (40+):**
- User management: create, read, update, delete, deactivate
- Role management: create, read, update, delete, assign, revoke
- Device management: create, read, update, delete, lock, unlock, wipe, install_app, remove_app
- Policy management: create, read, update, delete, apply
- Audit: read, export, delete [SUPER_ADMIN ONLY]
- System: config [SUPER_ADMIN ONLY], health

**Ações críticas (requerem MFA/confirmação):**
- users:delete
- devices:wipe
- audit:delete
- system:config
- permissions:* (todas)
- roles:delete

### ✅ 9. Auditoria Enterprise

**Tipos de ações auditadas:**
- LOGIN, LOGOUT
- USER_CREATE, USER_UPDATE, USER_DELETE, USER_DEACTIVATE
- ROLE_ASSIGN, ROLE_REVOKE, ROLE_CREATE, ROLE_UPDATE
- DEVICE_LOCK, DEVICE_UNLOCK, DEVICE_WIPE, DEVICE_POLICY_APPLY
- DEVICE_APP_INSTALL, DEVICE_APP_REMOVE
- AUDIT_LOG_DELETE, AUDIT_LOG_EXPORT
- FAILED_LOGIN, PERMISSION_DENIED
- PRIVILEGE_ESCALATION_ATTEMPT

**Cada log contém:**
- `user_id` - Quem fez
- `action` - O que fez
- `resource_type` / `resource_id` - O que foi afetado
- `details` - JSON com detalhes (valores antigos/novos)
- `ip_address` / `user_agent` - De onde veio
- `is_success` / `error_message` - Resultado
- `created_at` - Quando

**Políticas de retenção:**
- Logs normais: 90 dias (configurável)
- Ações críticas: 1 ano+
- Cleanup automático via `audit_repo.cleanup_old_logs()`

### ✅ 10. Migrations SQL

**Arquivo criado:** `migrations/003_create_rbac_tables.sql`

- ENUMs PostgreSQL (role_enum, audit_action_enum)
- Criação de 5 tabelas principais
- Índices otimizados (15+ índices)
- Constraints de integridade
- Documentação inline

---

## 🔐 Proteções de Segurança Implementadas

### 1. **Anti-Privilege Escalation**
```
❌ ADMIN não pode criar SUPER_ADMIN
❌ ADMIN não pode criar/modificar permissões
❌ Não pode atribuir role que não possui
❌ Tentativas registradas em audit_logs
```

### 2. **Proteção do Último SUPER_ADMIN**
```
❌ Não pode remover último SUPER_ADMIN do sistema
```

### 3. **Rate Limiting**
```python
@limiter.limit("50/minute")  # Endpoints de escrita
@limiter.limit("100/minute")  # Endpoints de leitura
```

### 4. **Auditoria de Ações Críticas**
```
Cada ação crítica:
- ✅ Registrada imediatamente em audit_logs
- ✅ Contém detalhes completos em JSON
- ✅ IP e User-Agent capturados
- ✅ Imutável (append-only, sem updates)
```

### 5. **MFA para Ações Perigosas**
```python
requires_mfa_actions = {
    "users:delete",
    "devices:wipe",
    "audit:delete",
    "system:config",
    "permissions:*",
    "roles:delete"
}
```

### 6. **Validações no JWT**
```
Token inclui:
- sub (email do usuário)
- roles (lista de roles)
- exp (expiração)
- jti (ID único para one-time tokens)
```

---

## 📊 Estrutura de Diretórios

```
backend/
├── models/
│   ├── role.py                    ✅ [NOVO]
│   ├── permission.py              ✅ [NOVO]
│   ├── audit_log.py               ✅ [NOVO]
│   └── user.py                    ✅ [ATUALIZADO]
├── schemas/
│   ├── role.py                    ✅ [NOVO]
│   ├── permission.py              ✅ [NOVO]
│   ├── audit_log.py               ✅ [NOVO]
│   └── user.py                    ✅ [ATUALIZADO]
├── repositories/
│   ├── role_repo.py               ✅ [NOVO]
│   ├── permission_repo.py         ✅ [NOVO]
│   ├── audit_repo.py              ✅ [NOVO]
│   └── user_repo.py               (existente)
├── services/
│   ├── rbac_service.py            ✅ [NOVO]
│   └── mdm_service.py             (existente)
├── api/
│   ├── rbac_routes.py             ✅ [NOVO]
│   ├── routes.py                  (existente)
│   └── auth.py                    (existente)
├── utils/
│   ├── decorators.py              ✅ [NOVO]
│   ├── rbac_constants.py          ✅ [NOVO]
│   └── time.py                    (existente)
└── main.py                        ✅ [ATUALIZADO]

migrations/
└── 003_create_rbac_tables.sql     ✅ [NOVO]
```

---

## 🚀 Como Usar

### 1. **Aplicar Migrations**

```bash
# Conectar ao DB e executar:
psql -U postgres -d mdm_project -f migrations/003_create_rbac_tables.sql
```

A startup automática inicializa roles e permissions padrão via `rbac_service.initialize_rbac()`.

### 2. **Proteger um Endpoint**

```python
@router.post("/devices/{device_id}/wipe")
@require_permission("devices:wipe")
@limiter.limit("10/minute")
async def wipe_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Wipe um device (requer permissão + MFA)"""
    checker = PermissionChecker(current_user)
    
    # Validação adicional
    if "devices:wipe" in rbac_constants.MFA_REQUIRED_ACTIONS:
        # TODO: Verificar MFA
        pass
    
    # Auditar ação
    audit_repo = AuditRepository(db)
    await audit_repo.create(
        action=AuditActionEnum.DEVICE_WIPE,
        user_id=current_user.id,
        resource_type="devices",
        resource_id=device_id,
        details={"device": device_id}
    )
    
    # Executar wipe...
```

### 3. **Atribuir Role a Usuário**

```python
# Via API
POST /api/rbac/users/123/roles/2
# Response: {"message": "Role atribuído com sucesso"}

# Via código
rbac_service = RBACService(db)
success, error = await rbac_service.assign_role_to_user(
    current_user=current_user,
    target_user=target_user,
    role=role,
    ip_address="192.168.1.1"
)
```

### 4. **Verificar Permissões**

```python
# Em um endpoint
checker = PermissionChecker(current_user)
checker.assert_permission("devices:read")
checker.assert_role("ADMIN")

# Em lógica de negócio
if current_user.has_permission("devices:wipe"):
    # executar wipe
    pass

if current_user.has_all_permissions("devices:read", "devices:lock"):
    # executar lock com log
    pass
```

### 5. **Consultar Auditoria**

```python
# Listar todos os logs
GET /api/rbac/audit?days=30&skip=0&limit=100

# Filtrar por ação
GET /api/rbac/audit?action=DEVICE_WIPE&days=30

# Filtrar por usuário
GET /api/rbac/audit?user_id=5&days=30

# Ações críticas apenas
GET /api/rbac/audit/critical?days=30
```

---

## 🎯 Próximos Passos (Escalabilidade)

### Multi-tenant (SaaS)
```
1. Adicionar organization_id a todas as tabelas
2. QueryFilter middleware que adiciona WHERE org_id=X
3. Roles/permissões por organiação
4. Audit logs por tenant
```

### Integração com Android
```
1. Permissão "devices:wipe" bloqueia execução no device
2. Logs de ACL em device policy
3. Sincronização de políticas baseada em permissões
```

### MFA/2FA
```
1. Tabela de secrets TOTP
2. Middleware que valida code
3. Fallback com recovery codes
```

### SSO/OAuth
```
1. Integrar com Keycloak/Okta
2. Mapear External Roles para RBAC
3. Sync de grupos
```

### Webhooks para auditoria
```
1. POST /external-audit-log quando ação crítica
2. Enviar para SIEM (Splunk, ELK, etc)
3. Compliance com logs externos
```

---

## 📚 Convenções Adotadas

### Naming
- **Permissions**: `resource:action` (ex: `devices:wipe`, `users:create`)
- **Tables**: Plural em inglês (ex: roles, permissions, users)
- **Enums**: PascalCase (ex: `RoleEnum`, `AuditActionEnum`)

### Validação
- Permissões granulares em REST (endpoint +  decorator)
- Validações de negócio no service
- Validações de banco no repository

### Error Handling
- 401: Não autenticado
- 403: Sem permissão
- 404: Recurso não encontrado
- 409: Conflito (ex: role já atribuído)

---

## 🧪 Testes Sugeridos

### Unitários
```python
# test_rbac_service.py
- test_cannot_admin_create_super_admin()
- test_cannot_escalate_privilege()
- test_assign_role_creates_audit_log()
```

### Integração
```python
# test_rbac_endpoints.py
- test_wipe_device_requires_permission()
- test_user_without_role_cannot_access()
- test_audit_logs_created_for_critical_actions()
```

### Segurança
```python
# test_rbac_security.py
- test_cannot_remove_last_super_admin()
- test_privilege_escalation_logged()
- test_cannot_delete_system_roles()
```

---

## 📖 Referencias Documentação

- **OWASP RBAC**: https://owasp.org/www-community/Role_Based_Access_Control
- **JWT Best Practices**: https://tools.ietf.org/html/rfc8725
- **Auditoria Enterprise**: https://www.sans.org/whitepaper-archive/

---

## ⚠️ Considerações Finais

1. **Backup de audit_logs**: Configure retenção e backup automático
2. **Compliance**: Mantenha detalhes em JSON para compliance (GDPR, HIPAA)
3. **Performance**: Monitore índices de auditoria em ambiente de produção
4. **Escalabilidade**: Para > 1M de logs/dia, considere sharding ou particionamento
5. **MFA**: Implementar de verdade antes de produção (placeholders existem)

---

**Implementado por**: GitHub Copilot
**Data**: 23 de março de 2026
**Status**: ✅ Pronto para desenvolvimento
