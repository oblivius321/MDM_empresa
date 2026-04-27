"""
Constantes para o sistema RBAC.

Define os roles e permissões built-in do sistema MDM Elion.
Esses dados são carregados no banco na primeira execução (seed).
"""

from enum import Enum
from typing import Dict, List, Tuple


# ============================================================================
# DEFINIÇÃO DE ROLES (HIERARQUIA)
# ============================================================================

class RoleDefinition(Enum):
    """Definição dos roles built-in do sistema."""
    
    # SUPER_ADMIN: Controle total (nunca pode ser criado por outro usuário)
    SUPER_ADMIN = {
        "name": "SUPER_ADMIN",
        "description": "Controle total do sistema. Pode criar/modificar/deletar tudo.",
        "priority": 1000,
        "permissions": [
            "users:create",
            "users:read",
            "users:update",
            "users:delete",
            "roles:create",
            "roles:read",
            "roles:update",
            "roles:delete",
            "permissions:read",
            "permissions:create",
            "permissions:update",
            "permissions:delete",
            "devices:read",
            "devices:create",
            "devices:update",
            "devices:delete",
            "devices:lock",
            "devices:unlock",
            "devices:wipe",
            "devices:install_app",
            "devices:remove_app",
            "policies:create",
            "policies:read",
            "policies:update",
            "policies:delete",
            "policies:apply",
            "audit:read",
            "audit:delete",  # CRÍTICO: apenas SUPER_ADMIN
            "audit:export",
            "system:config",
            "system:health",
        ]
    }
    
    # ADMIN: Controle operacional com restrições
    ADMIN = {
        "name": "ADMIN",
        "description": "Controle operacional. Não pode deletar SUPER_ADMIN ou criar permissões.",
        "priority": 100,
        "permissions": [
            "users:create",
            "users:read",
            "users:update",
            # "users:delete",  # ❌ Não pode deletar
            "roles:read",
            # "roles:create",  # ❌ Não pode criar roles
            # "roles:update",
            # "roles:delete",
            "devices:read",
            "devices:create",
            "devices:update",
            "devices:lock",
            "devices:unlock",
            "devices:wipe",
            "devices:install_app",
            "devices:remove_app",
            "policies:create",
            "policies:read",
            "policies:update",
            "policies:apply",
            "audit:read",
            "audit:export",
            "system:health",
        ]
    }
    
    # OPERATOR: Ações limitadas (dia a dia)
    OPERATOR = {
        "name": "OPERATOR",
        "description": "Operador de dispositivos. Pode executar ações em devices.",
        "priority": 10,
        "permissions": [
            "users:read",  # Apenas visualização
            "devices:read",
            "devices:lock",
            "devices:unlock",
            "devices:install_app",
            "devices:remove_app",
            "policies:read",
            "audit:read",  # Apenas visualizar seus próprios logs
            "system:health",
        ]
    }
    
    # VIEWER: Somente leitura
    VIEWER = {
        "name": "VIEWER",
        "description": "Visualizador do sistema. Acesso somente leitura.",
        "priority": 1,
        "permissions": [
            "users:read",
            "devices:read",
            "policies:read",
            "audit:read",
            "system:health",
        ]
    }


# ============================================================================
# DEFINIÇÃO DE PERMISSIONS (GRANULARES)
# ============================================================================

PERMISSIONS: List[Tuple[str, str, str, bool, bool]] = [
    # (name, resource, action, is_critical, requires_mfa)
    
    # ========== USER MANAGEMENT ==========
    ("users:create", "users", "create", False, False),
    ("users:read", "users", "read", False, False),
    ("users:update", "users", "update", False, False),
    ("users:delete", "users", "delete", True, True),  # CRÍTICO
    ("users:deactivate", "users", "deactivate", True, False),
    
    # ========== ROLE MANAGEMENT ==========
    ("roles:create", "roles", "create", True, False),
    ("roles:read", "roles", "read", False, False),
    ("roles:update", "roles", "update", True, False),
    ("roles:delete", "roles", "delete", True, True),  # CRÍTICO
    ("roles:assign", "roles", "assign", True, False),
    ("roles:revoke", "roles", "revoke", True, False),
    
    # ========== PERMISSION MANAGEMENT ==========
    ("permissions:create", "permissions", "create", True, True),  # CRÍTICO
    ("permissions:read", "permissions", "read", False, False),
    ("permissions:update", "permissions", "update", True, True),  # CRÍTICO
    ("permissions:delete", "permissions", "delete", True, True),  # CRÍTICO
    
    # ========== DEVICE MANAGEMENT ==========
    ("devices:create", "devices", "create", False, False),
    ("devices:read", "devices", "read", False, False),
    ("devices:update", "devices", "update", False, False),
    ("devices:delete", "devices", "delete", True, True),  # CRÍTICO: unenroll
    ("devices:lock", "devices", "lock", True, False),  # Requer confirmação
    ("devices:unlock", "devices", "unlock", True, False),
    ("devices:wipe", "devices", "wipe", True, True),  # CRÍTICO: requer MFA
    ("devices:reboot", "devices", "reboot", True, False),  # Requer confirmação
    ("devices:install_app", "devices", "install_app", False, False),
    ("devices:remove_app", "devices", "remove_app", False, False),
    
    # ========== POLICY MANAGEMENT ==========
    ("policies:create", "policies", "create", False, False),
    ("policies:read", "policies", "read", False, False),
    ("policies:update", "policies", "update", False, False),
    ("policies:delete", "policies", "delete", True, False),
    ("policies:apply", "policies", "apply", False, False),
    
    # ========== AUDIT & SECURITY ==========
    ("audit:read", "audit", "read", False, False),
    ("audit:export", "audit", "export", True, False),
    ("audit:delete", "audit", "delete", True, True),  # CRÍTICO: apenas SUPER_ADMIN
    
    # ========== SYSTEM ==========
    ("system:config", "system", "config", True, True),
    ("system:health", "system", "health", False, False),
]


# ============================================================================
# PERMISSION GROUPS (para facilitar atribuição)
# ============================================================================

PERMISSION_GROUPS: Dict[str, List[str]] = {
    "user_management": [
        "users:create",
        "users:read",
        "users:update",
        "users:delete",
        "users:deactivate",
    ],
    "role_management": [
        "roles:create",
        "roles:read",
        "roles:update",
        "roles:delete",
        "roles:assign",
        "roles:revoke",
    ],
    "device_management": [
        "devices:create",
        "devices:read",
        "devices:update",
        "devices:delete",
        "devices:lock",
        "devices:unlock",
        "devices:wipe",
        "devices:reboot",
        "devices:install_app",
        "devices:remove_app",
    ],
    "policy_management": [
        "policies:create",
        "policies:read",
        "policies:update",
        "policies:delete",
        "policies:apply",
    ],
    "audit": [
        "audit:read",
        "audit:export",
        "audit:delete",
    ],
    "read_only": [
        "users:read",
        "devices:read",
        "policies:read",
        "roles:read",
        "audit:read",
        "system:health",
    ],
}

# ============================================================================
# VALIDAÇÕES DE SEGURANÇA
# ============================================================================

# Ações que não devem ser feitas por admin (apenas super_admin)
SUPER_ADMIN_ONLY_PERMISSIONS = {
    "users:delete",
    "roles:delete",
    "permissions:create",
    "permissions:update",
    "permissions:delete",
    "devices:delete",
    "devices:wipe",
    "audit:delete",
    "system:config",
}

# Ações que requerem confirmação adicional (2FA/OTP)
MFA_REQUIRED_ACTIONS = {
    "users:delete",
    "devices:wipe",
    "audit:delete",
    "system:config",
    "permissions:create",
    "permissions:update",
    "permissions:delete",
    "roles:delete",
}

# Ações que devem ser auditadas detalhadamente
CRITICAL_AUDIT_ACTIONS = {
    "users:delete",
    "users:deactivate",
    "devices:wipe",
    "devices:delete",
    "audit:delete",
    "system:config",
    "roles:assign",
    "roles:revoke",
    "roles:delete",
}
