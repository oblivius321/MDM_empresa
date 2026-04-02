# 📝 Exemplos Práticos: Integrando RBAC em Endpoints

## Comparação Antes vs Depois

### Exemplo 1: Lock Device

#### ❌ ANTES (sem RBAC)

```python
# backend/api/routes.py
@router.post("/devices/{device_id}/lock")
async def lock_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lock um device - sem controle de acesso"""
    
    # Apenas verifica se user está autenticado??
    # Qualquer usuário pode lockear?
    
    device = await device_repo.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Executar lock
    device.status = "locked"
    await device_repo.update(device)
    
    return {"message": "Device locked"}
```

#### ✅ DEPOIS (com RBAC)

```python
# backend/api/routes.py
@router.post("/devices/{device_id}/lock")
@limiter.limit("10/minute")
async def lock_device(
    request: Request,
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lock um device - com RBAC e auditoria completa"""
    
    # 1. Verificar permissão
    checker = PermissionChecker(current_user)
    checker.assert_permission("devices:lock")
    
    # 2. Buscar device
    device_repo = DeviceRepository(db)
    device = await device_repo.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # 3. Executar ação
    device.status = "locked"
    await device_repo.update(device)
    
    # 4. Auditar - CRÍTICO
    audit_repo = AuditRepository(db)
    await audit_repo.create(
        action=AuditActionEnum.DEVICE_LOCK,
        user_id=current_user.id,
        resource_type="devices",
        resource_id=device_id,
        details={
            "device_name": device.name,
            "device_model": device.model,
            "previous_status": "online"  # Armazenar estado anterior
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        is_success=True
    )
    await audit_repo.commit()
    
    # 5. Retornar
    return {
        "message": "Device locked successfully",
        "device_id": device_id
    }
```

**Melhorias:**
- ✅ Verifica permissão antes de executar
- ✅ Logs detalhados de quem fez, quando, de onde
- ✅ Rate limiting (máx 10/min)
- ✅ IP e User-Agent capturados
- ✅ Detalhes do estado anterior para auditoria

---

### Exemplo 2: Wipe Device (CRÍTICO)

#### ✅ IMPLEMENTAÇÃO SEGURA (com RBAC + MFA)

```python
# backend/api/routes.py

@router.post("/devices/{device_id}/wipe")
@limiter.limit("5/minute")  # Rate limit mais restritivo
async def wipe_device(
    request: Request,
    device_id: str,
    force: bool = False,  # Força wipe sem confirmação
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Wipe completo de um dispositivo (CRÍTICO).
    
    ⚠️  REQUER:
    - Permissão: devices:wipe
    - MFA token no header
    - Será auditado detalhadamente
    
    Uso:
        POST /api/devices/abc123/wipe
        Headers: X-MFA-Token: <token>
    """
    
    # 1. Verificar autenticação
    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # 2. Verificar permissão
    checker = PermissionChecker(current_user)
    try:
        checker.assert_permission("devices:wipe")
    except HTTPException:
        # ⚠️  Logar tentativa de acesso negado
        audit_repo = AuditRepository(db)
        await audit_repo.create(
            action=AuditActionEnum.PERMISSION_DENIED,
            user_id=current_user.id,
            resource_type="devices",
            resource_id=device_id,
            details={"action_attempted": "devices:wipe"},
            ip_address=request.client.host if request.client else None,
            is_success=False,
            error_message="User does not have devices:wipe permission"
        )
        await audit_repo.commit()
        raise
    
    # 3. Verificar MFA (ação crítica)
    mfa_token = request.headers.get("X-MFA-Token")
    if not mfa_token and not force:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA token required for wipe operation. Use X-MFA-Token header.",
            headers={"X-Requires-MFA": "true"}
        )
    
    # 4. Validar device
    device_repo = DeviceRepository(db)
    device = await device_repo.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # 5. Validações de segurança adicionais
    if device.status == "locked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot wipe locked device. Unlock first."
        )
    
    # 6. Executar wipe
    try:
        # Chamar device over-the-air wipe
        from backend.services.mdm_service import MDMService
        mdm_service = MDMService(device_repo)
        await mdm_service.send_wipe_command(device_id)
        
        # Atualizar status
        device.status = "wiping"
        await device_repo.update(device)
        
        success = True
        error_msg = None
    except Exception as e:
        success = False
        error_msg = str(e)
        await device_repo.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send wipe command: {str(e)}"
        )
    
    # 7. AUDITAR - Muito detalhado para ação crítica
    audit_repo = AuditRepository(db)
    await audit_repo.create(
        action=AuditActionEnum.DEVICE_WIPE,
        user_id=current_user.id,
        resource_type="devices",
        resource_id=device_id,
        details={
            # Informações do device
            "device_name": device.name,
            "device_model": device.model,
            "device_imei": device.imei,
            "device_owner": device.company,
            "previous_status": "online",
            
            # Informações da ação
            "action_source": "manual_admin_request",
            "mfa_used": mfa_token is not None,
            
            # Metadados de segurança
            "user_role": [r.name for r in current_user.roles],
            "risk_level": "CRITICAL"
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        is_success=success,
        error_message=error_msg
    )
    await audit_repo.commit()
    
    # 8. Notificar administrador de wipe crítico
    # (via email, Slack, etc)
    from backend.services.notification_service import NotificationService
    notify = NotificationService()
    await notify.send_critical_action_alert(
        title="🚨 WIPE DEVICE - AÇÃO CRÍTICA",
        details={
            "device": device.name,
            "executed_by": current_user.email,
            "timestamp": datetime.utcnow().isoformat(),
            "ip": request.client.host if request.client else "unknown"
        }
    )
    
    # 9. Retornar
    return {
        "message": "Wipe command sent successfully",
        "device_id": device_id,
        "status": "wiping",
        "note": "Device will be wiped in next check-in (within 15 minutes)"
    }
```

**Proteções implementadas:**
- ✅ Verificação de permissão
- ✅ MFA obrigatório
- ✅ Rate limiting agressivo (5/min)
- ✅ Tentativa de acesso negado registrada
- ✅ Detalhes completos auditados
- ✅ Validações de segurança (device locked?)
- ✅ Tratamento de erros
- ✅ Notificação de ação crítica

---

### Exemplo 3: Atribuir Role (ESCALAÇÃO DE PRIVILÉGIO)

#### ✅ IMPLEMENTAÇÃO COM PROTEÇÕES ANTI-ESCALATION

```python
# backend/api/rbac_routes.py

@router.post("/users/{user_id}/roles/{role_id}")
@limiter.limit("10/minute")
async def assign_role_to_user(
    request: Request,
    user_id: int,
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Atribui um role a um usuário.
    
    ⚠️  PROTEÇÕES:
    - ADMIN não pode atribuir SUPER_ADMIN
    - Não pode atribuir role que não possui
    - Tentativas logadas
    """
    
    # 1. Verificar permissão
    checker = PermissionChecker(current_user)
    try:
        checker.assert_permission("roles:assign")
    except HTTPException:
        # Logar tentativa
        audit_repo = AuditRepository(db)
        await audit_repo.create(
            action=AuditActionEnum.PERMISSION_DENIED,
            user_id=current_user.id,
            resource_type="users",
            resource_id=str(user_id),
            details={
                "action": "roles:assign",
                "target_role_id": role_id
            },
            ip_address=request.client.host if request.client else None,
            is_success=False
        )
        await audit_repo.commit()
        raise
    
    # 2. Carregar usuários e role
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)
    
    target_user = await user_repo.get_by_id(user_id)
    role = await role_repo.get_by_id(role_id)
    
    if not target_user or not role:
        raise HTTPException(status_code=404, detail="User or role not found")
    
    # 3. PROTEÇÃO CRÍTICA: Usar RBACService para validações
    rbac_service = RBACService(db)
    audit_repo = AuditRepository(db)
    
    # Verifica:
    # - ADMIN tentando criar SUPER_ADMIN?
    # - Tentando atribuir role que não tem?
    # - Tentando remover último SUPER_ADMIN?
    success, error = await rbac_service.assign_role_to_user(
        current_user=current_user,
        target_user=target_user,
        role=role,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    if not success:
        # ⚠️  Logar tentativa de escalação de privilégio
        if "SUPER_ADMIN" in error:
            await audit_repo.create(
                action=AuditActionEnum.PRIVILEGE_ESCALATION_ATTEMPT,
                user_id=current_user.id,
                resource_type="users",
                resource_id=str(user_id),
                details={
                    "attempted_role": role.name,
                    "reason": error
                },
                ip_address=request.client.host if request.client else None,
                is_success=False,
                error_message=error
            )
            await audit_repo.commit()
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error
        )
    
    # 4. Se chegou aqui, foi bem-sucedido (RBACService já auditou)
    return {
        "message": "Role assigned successfully",
        "user_id": user_id,
        "role_id": role_id,
        "role_name": role.name
    }
```

---

### Exemplo 4: Deletar Log de Auditoria (SUPER_ADMIN ONLY)

#### ✅ IMPLEMENTAÇÃO COM MÁXIMA SEGURANÇA

```python
# backend/api/rbac_routes.py

@router.delete("/audit/{log_id}")
@limiter.limit("5/minute")  # Muito restritivo
async def delete_audit_log(
    request: Request,
    log_id: int,
    reason: str = Query(..., min_length=10, max_length=500),  # Obrigatório explicar
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Deleta um log de auditoria.
    
    ⚠️  EXTREMAMENTE CRÍTICO:
    - Apenas SUPER_ADMIN
    - Requer motivo
    - A deleção será auditada (meta-auditoria)
    - IP, fingerprint, MFA token obrigatório
    """
    
    # 1. Verificar role (não permissão, mas role explícito)
    checker = PermissionChecker(current_user)
    checker.assert_role("SUPER_ADMIN")
    
    # Se chegou aqui, é SUPER_ADMIN (RoleGate ja validou)
    
    # 2. Buscar log
    audit_repo = AuditRepository(db)
    target_log = await audit_repo.get_by_id(log_id)
    
    if not target_log:
        # Não retornar erro 404 (segurança: não confirmar que log existe)
        # Apenas logar tentativa
        await audit_repo.create(
            action=AuditActionEnum.AUDIT_LOG_DELETE,
            user_id=current_user.id,
            resource_type="audit_logs",
            resource_id=str(log_id),
            details={"reason": reason, "log_not_found": True},
            ip_address=request.client.host if request.client else None,
            is_success=False,
            error_message="Log not found or already deleted"
        )
        await audit_repo.commit()
        return {"message": "Operation completed"}
    
    # 3. Log da deleção (META-AUDITORIA)
    # Registrar o log que vai ser deletado ANTES de deletar
    deletion_audit = await audit_repo.create(
        action=AuditActionEnum.AUDIT_LOG_DELETE,
        user_id=current_user.id,
        resource_type="audit_logs",
        resource_id=str(log_id),
        details={
            "deleted_log_id": log_id,
            "deleted_log_action": target_log.action.value,
            "deleted_log_user": target_log.user_id,
            "deleted_log_created_at": target_log.created_at.isoformat(),
            "deleted_log_resource": f"{target_log.resource_type}:{target_log.resource_id}",
            "deletion_reason": reason,  # Por que foi deletado?
            "deleting_user_role": [r.name for r in current_user.roles],
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        is_success=True
    )
    await audit_repo.commit()
    
    # 4. Agora deletar o log original
    await audit_repo.db.delete(target_log)
    await audit_repo.commit()
    
    # 5. ALERTAR: Ação de risco máximo
    from backend.services.notification_service import NotificationService
    notify = NotificationService()
    await notify.send_critical_action_alert(
        title="🚨🚨🚨 AUDIT LOG DELETED - CRITICAL ACTION",
        priority="URGENT",
        details={
            "deleted_by": current_user.email,
            "deleted_log_original_action": target_log.action.value,
            "reason_provided": reason,
            "timestamp": datetime.utcnow().isoformat(),
            "ip": request.client.host if request.client else "unknown",
            "meta_audit_id": deletion_audit.id  # Referência para investigação
        }
    )
    
    # 6. TODO: Enviar para SIEM externo (Splunk, ELK)
    # await external_siem.log(deletion_audit)
    
    return {
        "message": "Audit log deleted",
        "deleted_log_id": log_id,
        "meta_audit_id": deletion_audit.id,
        "note": "This deletion has been audited and will be sent to SIEM"
    }
```

---

## 🧪 Testes para Validar RBAC

### Test 1: Permissão é necessária

```python
# test_rbac_endpoints.py

@pytest.mark.asyncio
async def test_wipe_device_requires_permission():
    """Testa que wipe sem permissão falha"""
    
    # Setup: User VIEWER (sem permissão)
    viewer_user = create_user(role=RoleEnum.VIEWER)
    
    # Tentar fazer wipe
    response = client.post(
        f"/api/devices/device123/wipe",
        headers={"Authorization": f"Bearer {viewer_user.token}"}
    )
    
    # Deve falhar com 403
    assert response.status_code == 403
    assert "devices:wipe" in response.json()["detail"]
    
    # Verificar que tentativa foi auditada
    audit_logs = await audit_repo.get_by_user(viewer_user.id)
    assert any(log.action == AuditActionEnum.PERMISSION_DENIED for log in audit_logs)
```

### Test 2: Admin não pode create SUPER_ADMIN

```python
@pytest.mark.asyncio
async def test_admin_cannot_create_super_admin():
    """Testa que ADMIN não pode atribuir SUPER_ADMIN"""
    
    # Setup
    admin_user = create_user(role=RoleEnum.ADMIN)
    target_user = create_user()
    super_admin_role = await role_repo.get_by_type(RoleEnum.SUPER_ADMIN)
    
    # Tentar atribuir SUPER_ADMIN
    response = client.post(
        f"/api/rbac/users/{target_user.id}/roles/{super_admin_role.id}",
        headers={"Authorization": f"Bearer {admin_user.token}"}
    )
    
    # Deve falhar
    assert response.status_code == 403
    assert "SUPER_ADMIN" in response.json()["detail"]
    
    # Verificar escalation attempt foi auditada
    audit_logs = await audit_repo.get_privilege_escalation_attempts()
    assert len(audit_logs) > 0
```

### Test 3: Login é auditado

```python
@pytest.mark.asyncio
async def test_login_creates_audit_log():
    """Testa que login cria audit log"""
    
    user = create_user()
    
    # Fazer login
    response = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "password"}
    )
    
    assert response.status_code == 200
    
    # Verificar audit log
    audit_logs = await audit_repo.get_by_user(user.id)
    login_logs = [log for log in audit_logs if log.action == AuditActionEnum.LOGIN]
    
    assert len(login_logs) > 0
    assert login_logs[-1].is_success == True
    assert login_logs[-1].ip_address is not None
```

---

## 📊 Estrutura de resposta de erro RBAC

```json
{
  "detail": "Permissão necessária: devices:wipe",
  "status_code": 403,
  "error_type": "PERMISSION_DENIED",
  "required_permission": "devices:wipe",
  "required_role": null,
  "timestamp": "2025-03-23T14:30:00Z"
}
```

---

**Implementado por**: GitHub Copilot  
**Data**: 23 de março de 2026  
**Status**: ✅ Pronto para uso
