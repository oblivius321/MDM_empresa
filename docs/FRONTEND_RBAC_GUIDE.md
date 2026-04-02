# 🎨 Guia de Implementação RBAC no Frontend React

## 📋 Índice
1. [Estratégia de Controle de Acesso](#estratégia)
2. [Componentes Base](#componentes)
3. [Hooks Customizados](#hooks)
4. [Exemplos de Uso](#exemplos)
5. [Boas Práticas](#boas-práticas)

---

## <a name="estratégia"></a>1. Estratégia de Controle de Acesso

### Princípios
- **Ocultar UI**: Botões/menus para ações sem permissão (UX melhor que erro)
- **Desabilitar interações**: Input fields desabilitados com tooltips
- **Validação backend**: Nunca confiar apenas em frontend (sempre validar no backend)
- **Granularidade**: Controlar até componente unitário

### Fluxo
```
1. User faz login → Recebe JWT + lista de permissões
2. AuthContext armazena permissões no Redux/Context
3. Componentes consultam permissões antes de renderizar
4. Backend valida NOVAMENTE ao receber requisição
```

---

## <a name="componentes"></a>2. Componentes Base

### A. PermissionGate (Wrapper)

```tsx
// src/components/PermissionGate.tsx

interface PermissionGateProps {
  permission: string | string[];
  matchAll?: boolean;  // true = AND, false = OR
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Renderiza children apenas se user tem permissão.
 * 
 * Uso:
 * <PermissionGate permission="devices:wipe">
 *   <Button onClick={wipeDevice}>Wipe</Button>
 * </PermissionGate>
 * 
 * <PermissionGate permission={["devices:read", "devices:lock"]} matchAll={true}>
 *   Device locked info
 * </PermissionGate>
 */
export function PermissionGate({
  permission,
  matchAll = false,
  fallback = null,
  children
}: PermissionGateProps) {
  const { permissions } = useAuth();
  
  const permissions_array = Array.isArray(permission) ? permission : [permission];
  
  const has_permission = matchAll
    ? permissions_array.every(p => permissions.includes(p))
    : permissions_array.some(p => permissions.includes(p));
  
  if (!has_permission) {
    return fallback;
  }
  
  return <>{children}</>;
}
```

### B. RoleGate (Por Role)

```tsx
// src/components/RoleGate.tsx

interface RoleGateProps {
  role: string | string[];
  matchAll?: boolean;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function RoleGate({
  role,
  matchAll = false,
  children,
  fallback = null
}: RoleGateProps) {
  const { user } = useAuth();
  
  if (!user?.roles) return fallback;
  
  const roles_array = Array.isArray(role) ? role : [role];
  const user_roles = user.roles.map(r => r.role_type);
  
  const has_role = matchAll
    ? roles_array.every(r => user_roles.includes(r))
    : roles_array.some(r => user_roles.includes(r));
  
  if (!has_role) {
    return fallback;
  }
  
  return <>{children}</>;
}
```

### C. AccessDenied (Erro)

```tsx
// src/components/AccessDenied.tsx

export function AccessDenied({
  message = "Você não tem permissão para acessar este recurso"
}: {
  message?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-4">
      <AlertCircle className="w-16 h-16 text-red-600" />
      <h1 className="text-2xl font-bold">Acesso Negado</h1>
      <p className="text-muted-foreground">{message}</p>
      <Link to="/dashboard" className="text-primary hover:underline">
        Voltar para dashboard
      </Link>
    </div>
  );
}
```

### D. ProtectedRoute

```tsx
// src/components/ProtectedRoute.tsx

interface ProtectedRouteProps {
  permission?: string;
  role?: string;
  children: React.ReactNode;
}

export function ProtectedRoute({
  permission,
  role,
  children
}: ProtectedRouteProps) {
  const { user, permissions } = useAuth();
  
  // Verificar role
  if (role) {
    const has_role = user?.roles.some(r => r.role_type === role);
    if (!has_role) {
      return <AccessDenied message={`Role '${role}' requerido`} />;
    }
  }
  
  // Verificar permissão
  if (permission) {
    if (!permissions.includes(permission)) {
      return <AccessDenied message={`Permissão '${permission}' requerida`} />;
    }
  }
  
  return <>{children}</>;
}
```

### E. PermissionButton

```tsx
// src/components/PermissionButton.tsx

import { Button, ButtonProps } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface PermissionButtonProps extends ButtonProps {
  permission: string | string[];
  tooltipMessage?: string;
}

export function PermissionButton({
  permission,
  tooltipMessage,
  children,
  ...props
}: PermissionButtonProps) {
  const { permissions } = useAuth();
  
  const permissions_array = Array.isArray(permission) ? permission : [permission];
  const has_permission = permissions_array.some(p => permissions.includes(p));
  
  if (!has_permission) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button {...props} disabled>
              {children}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {tooltipMessage || `Permissão necessária: ${permissions_array.join(', ')}`}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }
  
  return <Button {...props}>{children}</Button>;
}
```

---

## <a name="hooks"></a>3. Hooks Customizados

### A. usePermission

```tsx
// src/hooks/usePermission.ts

export function usePermission() {
  const { permissions } = useAuth();
  
  return {
    has: (permission: string) => permissions.includes(permission),
    
    hasAny: (...perms: string[]) =>
      perms.some(p => permissions.includes(p)),
    
    hasAll: (...perms: string[]) =>
      perms.every(p => permissions.includes(p)),
    
    can: (action: string) => permissions.includes(action),
    
    canNot: (action: string) => !permissions.includes(action),
  };
}

// Uso
const { has, can } = usePermission();

if (can("devices:wipe")) {
  // Mostrar botão de wipe
}

{has("audit:delete") && <Button onClick={deleteLog} />}
```

### B. useRole

```tsx
// src/hooks/useRole.ts

export function useRole() {
  const { user } = useAuth();
  
  const user_roles = user?.roles || [];
  const role_types = user_roles.map(r => r.role_type);
  
  return {
    roles: user_roles,
    
    hasRole: (role: string) => role_types.includes(role),
    
    hasAnyRole: (...roles: string[]) =>
      roles.some(r => role_types.includes(r)),
    
    hasAllRoles: (...roles: string[]) =>
      roles.every(r => role_types.includes(r)),
    
    isAdmin: () => role_types.includes("ADMIN") || role_types.includes("SUPER_ADMIN"),
    
    isSuperAdmin: () => role_types.includes("SUPER_ADMIN"),
    
    isViewer: () => role_types.includes("VIEWER"),
  };
}

// Uso
const { isAdmin, hasRole } = useRole();

if (isAdmin()) {
  // Mostrar seção de admin
}

{hasRole("SUPER_ADMIN") && <DeleteLogsButton />}
```

### C. useAccessControl

```tsx
// src/hooks/useAccessControl.ts

/**
 * Hook unificado para controle de acesso (permissão + role)
 */
export function useAccessControl() {
  const permission = usePermission();
  const role = useRole();
  
  return {
    permission,
    role,
    
    /**
     * Verifica acesso complexo
     * Ex: (user tem ADMIN role) OU (tem permission devices:lock)
     */
    isAllowed: (config: {
      permission?: string | string[];
      role?: string | string[];
      requireAll?: boolean;
    }): boolean => {
      const { permission: p, role: r, requireAll = false } = config;
      
      const checks = [];
      
      if (p) {
        const perm_array = Array.isArray(p) ? p : [p];
        checks.push(perm_array.some(x => permission.has(x)));
      }
      
      if (r) {
        const role_array = Array.isArray(r) ? r : [r];
        checks.push(role_array.some(x => role.hasRole(x)));
      }
      
      if (checks.length === 0) return true;
      return requireAll ? checks.every(Boolean) : checks.some(Boolean);
    },
  };
}
```

---

## <a name="exemplos"></a>4. Exemplos de Uso

### A. Sidebar com Itens Condicionais

```tsx
// src/components/AppSidebar.tsx (atualizado)

export function AppSidebar() {
  const { user } = useAuth();
  const permission = usePermission();
  
  const menuItems = [
    { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { label: 'Dispositivos', href: '/devices', icon: Smartphone, permission: 'devices:read' },
    { label: 'Usuários', href: '/users', icon: Users, permission: 'users:read' },
    { label: 'Roles', href: '/rbac/roles', icon: Shield, permission: 'roles:read' },
    { label: 'Auditoria', href: '/rbac/audit', icon: FileText, permission: 'audit:read' },
    { label: 'Configurações', href: '/settings', icon: Settings, permission: 'system:config' },
  ];
  
  return (
    <Sidebar>
      <SidebarContent>
        <SidebarMenu>
          {menuItems.map((item) => (
            <SidebarMenuItem key={item.href}>
              {/* Renderizar apenas se tem permissão */}
              {!item.permission || permission.has(item.permission) ? (
                <SidebarMenuLink to={item.href}>
                  <item.icon />
                  <span>{item.label}</span>
                </SidebarMenuLink>
              ) : null}
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarContent>
    </Sidebar>
  );
}
```

### B. Tabela de Dispositivos com Ações Condicionais

```tsx
// src/pages/Devices.tsx

export function Devices() {
  const { devices } = useDashboard();
  const permission = usePermission();
  
  const columns = [
    { key: 'name', label: 'Nome' },
    { key: 'status', label: 'Status' },
    { key: 'battery', label: 'Bateria' },
    { key: 'actions', label: 'Ações' },
  ];
  
  return (
    <div className="space-y-4">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map(col => (
              <TableHead key={col.key}>{col.label}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {devices.map((device) => (
            <TableRow key={device.id}>
              <TableCell>{device.name}</TableCell>
              <TableCell>
                <StatusBadge status={device.status} />
              </TableCell>
              <TableCell>{device.battery}%</TableCell>
              <TableCell className="flex gap-2">
                {/* Botão de lock: visible se tem permissão */}
                <PermissionButton
                  permission="devices:lock"
                  size="sm"
                  variant="outline"
                  onClick={() => lockDevice(device.id)}
                  tooltipMessage="Requer permissão: devices:lock"
                >
                  🔒 Lock
                </PermissionButton>
                
                {/* Botão de wipe: visible se é SUPER_ADMIN ou ADMIN */}
                {permission.has("devices:wipe") && (
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => confirmWipeDevice(device.id)}
                  >
                    ⚠️ Wipe
                  </Button>
                )}
                
                {/* Menu de ações */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button size="sm" variant="ghost">⋯</Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    {permission.has("devices:update") && (
                      <DropdownMenuItem onClick={() => editDevice(device.id)}>
                        ✏️ Editar
                      </DropdownMenuItem>
                    )}
                    {permission.has("devices:delete") && (
                      <DropdownMenuItem
                        onClick={() => deleteDevice(device.id)}
                        className="text-red-600"
                      >
                        🗑️ Deletar
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

### C. Modal de Confirmação com Validação

```tsx
// src/components/ConfirmWipeDialog.tsx

interface ConfirmWipeDialogProps {
  device: Device;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => Promise<void>;
}

export function ConfirmWipeDialog({
  device,
  open,
  onOpenChange,
  onConfirm,
}: ConfirmWipeDialogProps) {
  const { user } = useAuth();
  const permission = usePermission();
  const [isLoading, setIsLoading] = useState(false);
  
  // Não permitir abrir modal se sem permissão
  if (!permission.has("devices:wipe")) {
    return null;
  }
  
  const handleConfirm = async () => {
    setIsLoading(true);
    try {
      // ⚠️ Backend vai validar de novo
      await onConfirm();
      onOpenChange(false);
      toast.success("Dispositivo apagado com sucesso");
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>⚠️ Confirmar Wipe</DialogTitle>
        </DialogHeader>
        
        <div className="space-y-4">
          <p>Você está prestes a <strong>apagar todos os dados</strong> do dispositivo:</p>
          <div className="bg-muted p-3 rounded">
            <p><strong>Dispositivo:</strong> {device.name}</p>
            <p><strong>ID:</strong> {device.device_id}</p>
          </div>
          
          {/* Avisos baseado em dados sensíveis */}
          {device.battery < 20 && (
            <Alert variant="warning">
              ⚠️ Bateria baixa ({device.battery}%). Considere conectar à energia.
            </Alert>
          )}
          
          {/* Informação de auditoria */}
          <div className="text-xs text-muted-foreground">
            ✓ Ação será auditada
            <br />
            ✓ Executado por: {user?.email}
            <br />
            ✓ Data/hora: {new Date().toLocaleString('pt-BR')}
          </div>
          
          {/* Requer confirmação dupla para ações críticas */}
          <div className="flex gap-2">
            <Checkbox id="confirm" />
            <label htmlFor="confirm" className="text-sm">
              Confirmo que desejo apagar TODOS os dados deste dispositivo
            </label>
          </div>
        </div>
        
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isLoading}
          >
            {isLoading ? "Processando..." : "Apagar Dispositivo"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

### D. Página de Gerenciamento de Usuários

```tsx
// src/pages/UsersManagement.tsx

export function UsersManagement() {
  const { users, loading } = useUsers();
  const { Roles } = useRoles();
  const permission = usePermission();
  const role = useRole();
  
  if (!permission.has("users:read")) {
    return <AccessDenied />;
  }
  
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1>Gerenciamento de Usuários</h1>
        
        {/* Botão de criar: apenas ADMIN+ */}
        {permission.has("users:create") && (
          <Button onClick={() => openCreateUserDialog()}>
            + Novo Usuário
          </Button>
        )}
      </div>
      
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Email</TableHead>
            <TableHead>Roles</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Ações</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((u) => (
            <TableRow key={u.id}>
              <TableCell>{u.email}</TableCell>
              <TableCell>
                <div className="flex gap-1">
                  {u.roles.map((r) => (
                    <Badge key={r.id} variant="secondary">
                      {r.name}
                    </Badge>
                  ))}
                </div>
              </TableCell>
              <TableCell>
                <Badge variant={u.is_active ? "default" : "outline"}>
                  {u.is_active ? "Ativo" : "Inativo"}
                </Badge>
              </TableCell>
              <TableCell className="flex gap-2">
                {/* Editar: ADMIN+ */}
                {permission.has("users:update") && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => editUser(u.id)}
                  >
                    ✏️
                  </Button>
                )}
                
                {/* Deletar: apenas se é SUPER_ADMIN e não for último SUPER_ADMIN */}
                {role.isSuperAdmin() && u.roles.some(r => r.role_type !== "SUPER_ADMIN") && (
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => confirmDeleteUser(u.id)}
                  >
                    🗑️
                  </Button>
                )}
                
                {/* Gerenciar roles: se tem permissão roles:assign */}
                {permission.has("roles:assign") && (
                  <RoleAssignmentDialog
                    user={u}
                    allRoles={Roles}
                    onSave={() => refetchUsers()}
                  />
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

### E. Page de Auditoria

```tsx
// src/pages/AuditLogs.tsx

export function AuditLogs() {
  const permission = usePermission();
  const [filters, setFilters] = useState({
    action: '',
    user_id: '',
    days: 30,
    page: 1,
  });
  
  if (!permission.has("audit:read")) {
    return <AccessDenied message="Você não tem permissão para visualizar logs" />;
  }
  
  const { logs, total, loading } = useAuditLogs(filters);
  
  return (
    <div className="space-y-6">
      <h1>Logs de Auditoria</h1>
      
      {/* Filtros */}
      <Card>
        <CardHeader>
          <CardTitle>Filtros</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-4 gap-4">
          <Select>
            <SelectTrigger>
              <SelectValue placeholder="Ação" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">Todas</SelectItem>
              <SelectItem value="LOGIN">Login</SelectItem>
              <SelectItem value="DEVICE_WIPE">Device Wipe</SelectItem>
              <SelectItem value="USER_DELETE">User Delete</SelectItem>
              <SelectItem value="AUDIT_LOG_DELETE">Audit Log Delete</SelectItem>
            </SelectContent>
          </Select>
          
          <Input
            type="number"
            placeholder="Dias atrás"
            defaultValue="30"
          />
          
          {/* Botão de export: ADMIN+ */}
          {permission.has("audit:export") && (
            <Button variant="outline" onClick={handleExport}>
              📥 Exportar
            </Button>
          )}
          
          {/* Botão de deletar: apenas SUPER_ADMIN */}
          {permission.has("audit:delete") && (
            <Button
              variant="destructive"
              onClick={handleDeleteSelected}
            >
              🗑️ Deletar Selecionados
            </Button>
          )}
        </CardContent>
      </Card>
      
      {/* Tabela de logs */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Data/Hora</TableHead>
            <TableHead>Usuário</TableHead>
            <TableHead>Ação</TableHead>
            <TableHead>Recurso</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>IP</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.map((log) => (
            <TableRow key={log.id}>
              <TableCell>{logDateTime(log.created_at)}</TableCell>
              <TableCell>{log.user_email|| "Sistema"}</TableCell>
              <TableCell>
                <Badge
                  variant={
                    log.action.includes("DELETE") ? "destructive" :
                    log.action.includes("WIPE") ? "destructive" :
                    "secondary"
                  }
                >
                  {log.action}
                </Badge>
              </TableCell>
              <TableCell>
                {log.resource_type}:{log.resource_id}
              </TableCell>
              <TableCell>
                <Badge variant={log.is_success ? "default" : "destructive"}>
                  {log.is_success ? "✓" : "✗"}
                </Badge>
              </TableCell>
              <TableCell className="font-mono text-sm">
                {log.ip_address}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

---

## <a name="boas-práticas"></a>5. Boas Práticas

### ✅ DO's

```tsx
// ✅ BOM: Ocultar UI se sem permissão
<PermissionGate permission="devices:wipe">
  <Button onClick={wipeDevice}>Wipe</Button>
</PermissionGate>

// ✅ BOM: Desabilitar e mostrar tooltip
<PermissionButton
  permission="devices:wipe"
  tooltipMessage="Requer permissão de wipe"
/>

// ✅ BOM: Validar NOVAMENTE no backend
async function wipeDevice(deviceId) {
  // O backend vai validar se user tem "devices:wipe"
  const response = await api.post(`/devices/${deviceId}/wipe`);
}

// ✅ BOM: Logar ações críticas
await auditRepo.create({
  action: AuditActionEnum.DEVICE_WIPE,
  user_id: currentUser.id,
  resource_id: deviceId,
  details: { reason: "User initiated" }
});

// ✅ BOM: Usar decorators para proteção
@require_permission("devices:wipe")
async def wipe_device(...):
  pass
```

### ❌ DON'Ts

```tsx
// ❌ RUIM: Confiar apenas em frontend
if (user.is_admin) {
  // Executar ação
  // O que impede de fazer request direto?
}

// ❌ RUIM: JSON.stringify de permissões no localStorage
localStorage.setItem('permissions', JSON.stringify(userPermissions));
// Usuário pode modificar!

// ❌ RUIM: Esconder botão mas deixar endpoint aberto
// Se esconder:
<PermissionGate permission="audit:delete">
  <Button onClick={deleteLog} />
</PermissionGate>
// Mas backend NÃO valida:
@router.delete("/audit/{log_id}")
async def delete_log(log_id: int):  # ❌ Sem @require_permission
  delete_log_db(log_id)

// ❌ RUIM: Usar role em vez de permission
if (user.role === "ADMIN") {
  // Problema: como herança de permissões?
  // Problema: não funciona se user tem múltiplos roles
}

// ❌ RUIM: Não auditar ações críticas
async def wipe_device(device_id):
  wipe(device_id)  # ❌ Nenhum registro
```

### 📊 Estratégia: Quando Ocultar vs Desabilitar

```tsx
// Ocultar completamente:
// - Menu items não relevantes
// - Seções inteiras (ex: Settings tab para viewer)
<PermissionGate permission="system:config" fallback={null}>
  <SettingsTab />
</PermissionGate>

// Desabilitar com tooltip:
// - Botões de ação contextuais
// - Campos de forma editáveis
// - Opções em dropdown
<PermissionButton
  permission="users:delete"
  disabled={!selectedUser}
  tooltipMessage="Selecione um usuário e tenha permissão de delete"
/>

// Validação + confirmação dupla:
// - Ações perigosas (wipe, delete, config)
// - Ações críticas
const handleWipe = async () => {
  // 1. Verificar UI
  if (!permission.has("devices:wipe")) return;
  
  // 2. Pedir confirmação
  if (!await confirmDialog()) return;
  
  // 3. Enviar request
  // 4. Backend valida NOVAMENTE
  // 5. Logar auditoria
};
```

---

## 📦 Estrutura de Diretórios (Frontend)

```
src/
├── components/
│   ├── PermissionGate.tsx          ✅ [NOVO]
│   ├── RoleGate.tsx                ✅ [NOVO]
│   ├── ProtectedRoute.tsx          ✅ [NOVO]
│   ├── PermissionButton.tsx        ✅ [NOVO]
│   ├── AccessDenied.tsx            ✅ [NOVO]
│   ├── AppSidebar.tsx              ✅ [ATUALIZADO]
│   └── ...
├── hooks/
│   ├── usePermission.ts            ✅ [NOVO]
│   ├── useRole.ts                  ✅ [NOVO]
│   ├── useAccessControl.ts         ✅ [NOVO]
│   └── ...
├── pages/
│   ├── Devices.tsx                 ✅ [ATUALIZADO]
│   ├── UsersManagement.tsx         ✅ [NOVO]
│   ├── AuditLogs.tsx               ✅ [NOVO]
│   └── ...
├── contexts/
│   ├── AuthContext.tsx             ✅ [ATUALIZADO - adicionar permissions]
│   └── ...
└── ...
```

---

## 🔄 Fluxo de Autenticação (Atualizado)

```typescript
// 1. Login -> Backend retorna JWT + permissions
const login = async (email: string, password: string) => {
  const response = await api.post('/auth/login', { email, password });
  // Response:
  // {
  //   access_token: "eyJ...",
  //   user: {
  //     id: 1,
  //     email: "user@email.com",
  //     roles: [
  //       { id: 1, name: "ADMIN", role_type: "ADMIN" }
  //     ],
  //     permissions: ["devices:read", "devices:lock", ...]
  //   }
  // }
};

// 2. Store em AuthContext
const [user, setUser] = useState<User | null>(null);
const [permissions, setPermissions] = useState<string[]>([]);

// 3. Componentes consultam
const { permissions } = useAuth();
if (permissions.includes("devices:wipe")) {
  // Mostrar botão
}
```

---

## 🚀 Próximas Implementações

### 1. MFA/2FA para ações críticas
```tsx
// Validar AES-GCM token antes de permitir ação
const { token } = await requestMFACode();
await api.post('/devices/wipe', { device_id }, {
  headers: { 'X-MFA-Token': token }
});
```

### 2. Request confirmation dialog
```tsx
const handleCriticalAction = async () => {
  const confirmed = await showConfirmationDialog({
    title: "Ação Crítica",
    message: "Confirmação necessária",
    type: "critical"
  });
  if (confirmed) {
    // Executar
  }
};
```

### 3. Rate limiting visual
```tsx
// Mostrar countdown/disabled button após N tentativas
<Button
  disabled={remaining_request > 0}
  onClick={...}
>
  {remaining_request > 0
    ? `Tente novamente em ${remaining_request}s`
    : "Executar"}
</Button>
```

---

**Implementado por**: GitHub Copilot
**Data**: 23 de março de 2026
**Status**: ✅ Pronto para implementação
