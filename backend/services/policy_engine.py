"""
Policy Engine — Core de normalização, hashing, merge e diff para policies MDM.

Responsabilidades:
  1. Canonical JSON  → normaliza payload para hash determinístico
  2. SHA-256 Hash    → comparação O(1) de estado desired vs actual
  3. Deep Merge      → combina policies N:M respeitando priority + scope
  4. Categorized Diff → identifica drifts por categoria e gera subcomandos

Este módulo é AGNÓSTICO — não faz I/O de banco, não importa modelos.
Recebe dicts puros e retorna dicts puros.
"""

import hashlib
import json
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("policy_engine")

# ─── Hard Limits (Enterprise Scaling) ────────────────────────────────────────
MAX_ALLOWED_APPS = 100
MAX_POLICY_SIZE_KB = 64


# ─── Campos voláteis removidos antes do hash ─────────────────────────────────
# Estes campos mudam constantemente e não representam drift real.
VOLATILE_FIELDS = frozenset({
    "uptime", "battery_level", "battery_status", "signal_strength",
    "free_storage", "free_ram", "last_seen", "timestamp", "boot_time",
})

# ─── Hierarquia de scope (menor → maior autoridade) ──────────────────────────
SCOPE_ORDER = {"global": 0, "group": 1, "device": 2}

# ─── Categorias de diff para subcomandos granulares ──────────────────────────
DRIFT_CATEGORIES = {
    "restrictions": "apply_restrictions",
    "kiosk_mode": "apply_kiosk",
    "allowed_apps": "apply_app_whitelist",
    "blocked_apps": "apply_app_blacklist",
    "password_requirements": "apply_password_policy",
    "wifi_config": "apply_wifi_config",
}

# ─── System Defaults (Camada 1 - Base) ───────────────────────────────────────
SYSTEM_DEFAULTS = {
    "kiosk": {
        "enabled": False,
        "mode": "unlocked",
        "show_settings": True,
        "show_status_bar": True
    },
    "restrictions": {
        "camera_disabled": False,
        "usb_debug_disabled": False,
        "factory_reset_disabled": False,
        "install_unknown_sources_disabled": True
    },
    "allowed_apps": [
        "com.elion.mdm",
        "com.android.settings",
        "com.google.android.apps.docs"
    ],
    "config": {
        "checkin_interval_minutes": 15,
        "log_level": "INFO"
    }
}



# ═══════════════════════════════════════════════════════════════════════════════
# 1. CANONICAL JSON + SHA-256 HASHING
# ═══════════════════════════════════════════════════════════════════════════════

def _strip_volatile(data: dict) -> dict:
    """Remove campos voláteis recursivamente de um dict."""
    cleaned = {}
    for k, v in data.items():
        if k in VOLATILE_FIELDS:
            continue
        if v is None:
            continue  # Remove nulls para normalização
        if isinstance(v, dict):
            stripped = _strip_volatile(v)
            if stripped:  # Não incluir dicts vazios
                cleaned[k] = stripped
        elif isinstance(v, list):
            # Ordena listas de strings para normalização
            cleaned[k] = sorted(v) if v and isinstance(v[0], str) else v
        else:
            cleaned[k] = v
    return cleaned


def to_canonical_json(data: dict) -> str:
    """
    Converte dict para JSON canônico determinístico (Estrito).

    Regras de normalização:
      1. sort_keys=True recursivo
      2. Remove campos null
      3. Remove campos voláteis (uptime, battery, etc.)
      4. Ordena listas de strings alfabeticamente
      5. Separadores compactos sem espaço (",", ":") -> CRÍTICO PARA HASH
    """
    stripped = _strip_volatile(data)
    return json.dumps(stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=False)



def compute_hash(data: dict) -> str:
    """Calcula SHA-256 canônico de um dict normalizado."""
    canonical = to_canonical_json(data)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_effective_hash(version: int, merged_config: dict) -> str:
    """
    Effective Policy Hash = SHA-256(version + canonical_config).

    Blindagem: se o admin incrementar a versão sem mudar o config
    (para forçar re-enforcement), o hash muda e dispara novo ciclo.
    """
    canonical = to_canonical_json(merged_config)
    raw = f"v{version}:{canonical}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DEEP MERGE DETERMINÍSTICO (priority + scope)
# ═══════════════════════════════════════════════════════════════════════════════

def _deep_merge_two(base: dict, override: dict) -> dict:
    """
    Merge profundo estratégico (Nível Enterprise).

    Regras:
      - Chaves únicas: override sobrescreve base.
      - Dicts internos: merge recursivo.
      - Listas (Apps/Tags): UNION mantendo ordem e removendo duplicatas.
    """
    result = deepcopy(base)

    for key, value in override.items():
        if key in result:
            existing = result[key]

            # Dict + Dict → merge recursivo
            if isinstance(existing, dict) and isinstance(value, dict):
                result[key] = _deep_merge_two(existing, value)

            # List + List → Strategic Union (dict.fromkeys trick for order preservation)
            elif isinstance(existing, list) and isinstance(value, list):
                result[key] = list(dict.fromkeys(existing + value))

            # Scalar → override vence
            else:
                result[key] = deepcopy(value)
        else:
            result[key] = deepcopy(value)

    return result



def merge_policies(policies: List[dict], profile_static: dict = None) -> dict:
    """
    Pipeline de Composição de Políticas (Nível Enterprise).

    Order (Bottom to Top):
      1. System Defaults (Base)
      2. Global Policies (Sorted by Priority)
      3. Profile Policies (Sorted by Priority)
      4. Profile Static Config (Fallback only for missing keys)
    """
    # 1. Start with System Defaults
    merged = deepcopy(SYSTEM_DEFAULTS)

    # 2 & 3. Merge Global and Profile Policies
    # Assumimos que a lista 'policies' já foi filtrada e ordenada pelo repo
    for p in policies:
        config = p.get("config", {})
        if config:
            merged = _deep_merge_two(merged, config)

    # 4. Profile Static Fallback (No overwrite)
    if profile_static:
        static_config = _normalize_profile_static(profile_static)
        for key, value in static_config.items():
            if key not in merged or not merged[key]:
                 merged[key] = deepcopy(value)
            elif isinstance(merged[key], dict) and isinstance(value, dict):
                 # Merge recursive fallback for sub-keys
                 for sub_k, sub_v in value.items():
                     if sub_k not in merged[key]:
                         merged[key][sub_k] = deepcopy(sub_v)

    return merged


def validate_policy_structure(policy: dict):
    """
    Validador estrito de estrutura e limites (Senior Hardening).
    Evita que configurações inválidas cheguem aos dispositivos Android.
    """
    if not isinstance(policy, dict):
        raise ValueError("Policy must be a dictionary")

    # 1. Check Payload Size
    raw_size = len(json.dumps(policy))
    if raw_size > MAX_POLICY_SIZE_KB * 1024:
        raise ValueError(f"Policy payload too large: {raw_size/1024:.2f}KB (Max: {MAX_POLICY_SIZE_KB}KB)")

    # 2. Type Checking: Kiosk
    kiosk = policy.get("kiosk", {})
    if not isinstance(kiosk, dict):
        raise ValueError("'kiosk' configuration must be an object")

    # 3. Type Checking & Limits: Allowed Apps
    apps = policy.get("allowed_apps", [])
    if not isinstance(apps, list):
        raise ValueError("'allowed_apps' must be a list of strings")
    
    if len(apps) > MAX_ALLOWED_APPS:
        raise ValueError(f"Too many allowed apps: {len(apps)} (Max: {MAX_ALLOWED_APPS})")

    # 4. Type Checking: Restrictions
    restrictions = policy.get("restrictions", {})
    if not isinstance(restrictions, dict):
        raise ValueError("'restrictions' must be an object")


def _normalize_profile_static(profile: dict) -> dict:

    """Normaliza campos legados do Profile para a estrutura sênior."""
    return {
        "kiosk": {
            "enabled": profile.get("kiosk_enabled", False)
        },
        "allowed_apps": profile.get("allowed_apps", []),
        "restrictions": profile.get("blocked_features", {}),
        "config": profile.get("config", {})
    }



# ═══════════════════════════════════════════════════════════════════════════════
# 3. CATEGORIZED DIFF (Drift Detection → Sub-Commands)
# ═══════════════════════════════════════════════════════════════════════════════

def _diff_category(desired: Any, actual: Any) -> bool:
    """Retorna True se houver drift entre desired e actual."""
    if isinstance(desired, dict) and isinstance(actual, dict):
        # Compara recursivamente
        for key in desired:
            if key not in actual:
                return True
            if _diff_category(desired[key], actual[key]):
                return True
        return False

    if isinstance(desired, list) and isinstance(actual, list):
        return set(desired) != set(actual)

    return desired != actual


def detect_drift(desired: dict, actual: dict) -> List[dict]:
    """
    Compara desired state vs actual state por categorias.

    Retorna lista de subcomandos a serem enfileirados na CommandQueue:
    [
        {"action": "apply_restrictions", "payload": {"camera_disabled": true, ...}},
        {"action": "apply_app_blacklist", "payload": {"apps": ["com.facebook.katana"]}},
    ]

    Somente categorias com drift geram subcomandos.
    Categorias sem drift são ignoradas (eficiência).
    """
    subcommands = []

    for category, action_name in DRIFT_CATEGORIES.items():
        desired_val = desired.get(category)
        actual_val = actual.get(category)

        # Se não existe no desired → ignorar (não é obrigatório)
        if desired_val is None:
            continue

        # Se não existe no actual OU diverge → drift
        if actual_val is None or _diff_category(desired_val, actual_val):
            # Monta payload do subcomando baseado na categoria
            if isinstance(desired_val, list):
                payload = {"apps": desired_val}
            elif isinstance(desired_val, dict):
                payload = desired_val
            else:
                payload = {"value": desired_val}

            subcommands.append({
                "action": action_name,
                "payload": payload,
            })

            logger.info(
                f"🔍 [Drift] category={category} action={action_name} "
                f"desired={desired_val} actual={actual_val}"
            )

    return subcommands


def compute_drift_summary(desired: dict, actual: dict) -> dict:
    """
    Retorna um resumo de compliance do device.

    Usado para dashboards e logging.
    """
    subcommands = detect_drift(desired, actual)
    total_categories = len([c for c in DRIFT_CATEGORIES if desired.get(c) is not None])
    drifted_categories = len(subcommands)
    compliant_categories = total_categories - drifted_categories

    return {
        "total_categories": total_categories,
        "compliant_categories": compliant_categories,
        "drifted_categories": drifted_categories,
        "drift_actions": [sc["action"] for sc in subcommands],
        "is_compliant": drifted_categories == 0,
    }
