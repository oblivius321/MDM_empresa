#!/usr/bin/env python3
"""
Elion MDM - Secrets Management & Security Validation
Script para gerar, validar e gerenciar segredos seguros em produção
"""
import os
import sys
import secrets
import subprocess
from pathlib import Path
from dotenv import load_dotenv

class SecretsManager:
    def __init__(self):
        self.project_root = Path(__file__).resolve().parent
        self.env_production = self.project_root / ".env.production"
        self.env_example = self.project_root / ".env.example"
        
    def generate_strong_secret(self, length: int = 32) -> str:
        """Gera um token criptograficamente seguro"""
        return secrets.token_urlsafe(length)
    
    def generate_password(self, length: int = 16) -> str:
        """Gera uma senha forte com números, símbolos e letras"""
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    def validate_env_file(self, env_path: Path) -> bool:
        """Valida se um arquivo .env tem configurações seguras"""
        if not env_path.exists():
            print(f"❌ Arquivo não encontrado: {env_path}")
            return False
        
        load_dotenv(env_path)
        
        required_vars = [
            "DATABASE_URL",
            "SECRET_KEY",
        ]
        
        print(f"🔍 Validando {env_path.name}...")
        
        issues = []
        
        # Verificar variáveis obrigatórias
        for var in required_vars:
            value = os.getenv(var)
            if not value or value.startswith("CHANGE_ME"):
                issues.append(f"  ❌ {var}: Não configurado ou ainda com valor padrão")
            else:
                print(f"  ✅ {var}: Configurado")
        
        # Verificar DEBUG
        if os.getenv("DEBUG", "False").lower() == "true":
            issues.append(f"  ⚠️  DEBUG: Acionado em produção! (deve ser False)")
        else:
            print(f"  ✅ DEBUG: Desativado")
        
        # Verificar ALLOWED_ORIGINS
        origins = os.getenv("ALLOWED_ORIGINS", "")
        if not origins or origins.startswith("http://localhost"):
            issues.append(f"  ⚠️  ALLOWED_ORIGINS: Pode não estar configurado para produção")
        else:
            print(f"  ✅ ALLOWED_ORIGINS: Configurado")
        
        if issues:
            print("\n⚠️  PROBLEMAS ENCONTRADOS:")
            for issue in issues:
                print(issue)
            return False
        
        print("\n✅ Validação concluída com sucesso!\n")
        return True
    
    def generate_secrets(self):
        """Gera um novo arquivo .env.production com secrets seguros"""
        print("🔐 Gerando Novos Segredos...\n")
        
        db_password = self.generate_password()
        secret_key = self.generate_strong_secret()
        
        env_content = f"""# ===== ELION MDM - CONFIGURAÇÃO DE PRODUÇÃO =====
# Gerado em: {__import__('datetime').datetime.now().isoformat()}
# IMPORTANTE: NUNCA compartilhe este arquivo!

# ===== BANCO DE DADOS =====
DB_USER=postgres
DB_PASSWORD={db_password}
DB_NAME=mdm_project
DATABASE_URL=postgresql+asyncpg://postgres:{db_password}@postgres:5432/mdm_project

# ===== SEGURANÇA =====
SECRET_KEY={secret_key}

# ===== MODO DE EXECUÇÃO =====
DEBUG=False
ENVIRONMENT=production

# ===== CONFIGURAÇÕES DE APLICAÇÃO =====
LOG_LEVEL=INFO
REQUEST_TIMEOUT=30

# ===== CORS =====
# TODO: Configure seus domínios de produção
ALLOWED_ORIGINS=https://mdm.seudominio.com,https://admin.seudominio.com

# ===== ANDROID/DISPOSITIVOS =====
DEVICE_CHECKIN_TIMEOUT=300

# ===== SEGURANÇA SSL/TLS =====
# Configure após gerar certificados
# SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
# SSL_KEY_PATH=/etc/nginx/ssl/key.pem
"""
        
        self.env_production.write_text(env_content)
        
        print(f"✅ Arquivo criado: {self.env_production}")
        print(f"\n🔑 Senhas Geradas:")
        print(f"   DB_PASSWORD: {db_password}")
        print(f"   SECRET_KEY: {secret_key[:20]}...\n")
        
        return db_password, secret_key
    
    def check_docker_secrets(self):
        """Verifica se Docker/Docker Compose está configurado corretamente"""
        print("🐳 Verificando Docker e Docker Compose...\n")
        
        try:
            docker_version = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            ).stdout.strip()
            print(f"  ✅ Docker: {docker_version}")
        except Exception as e:
            print(f"  ❌ Docker não encontrado: {e}")
            return False
        
        try:
            compose_version = subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            ).stdout.strip()
            print(f"  ✅ Docker Compose: {compose_version}")
        except Exception as e:
            print(f"  ❌ Docker Compose não encontrado: {e}")
            return False
        
        # Verificar docker-compose.yml
        compose_file = self.project_root / "docker-compose.yml"
        if compose_file.exists():
            print(f"  ✅ docker-compose.yml encontrado")
        else:
            print(f"  ❌ docker-compose.yml não encontrado")
            return False
        
        print()
        return True
    
    def print_security_checklist(self):
        """Exibe checklist de segurança para produção"""
        print("=" * 70)
        print("🔒 CHECKLIST DE SEGURANÇA - PRODUÇÃO")
        print("=" * 70 + "\n")
        
        checklist = [
            ("SECRET_KEY", "Deve ser uma string longa e aleatória", "python -c \"import secrets; print(secrets.token_urlsafe(32))\""),
            ("DB_PASSWORD", "Deve ser uma senha forte e única", "python -c \"import secrets; print(secrets.token_urlsafe(16))\""),
            ("DATABASE_URL", "Usar PostgreSQL em produção (não SQLite)", "postgresql+asyncpg://..."),
            ("DEBUG", "DEVE ser False em produção", "DEBUG=False"),
            ("ENVIRONMENT", "Deve ser 'production'", "ENVIRONMENT=production"),
            ("SSL/TLS", "Configurar certificados validos", "Usar Let's Encrypt ou similar"),
            ("CORS", "Restringir a domínios específicos", "ALLOWED_ORIGINS=https://seu.dominio.com"),
            ("Firewall", "Restringir acesso às portas do banco", "Apenas container backend pode acessar),"),
            ("Logs", "Habilitar logging detalhado", "LOG_LEVEL=INFO ou WARNING"),
            ("Rate Limiting", "Configurado no Nginx", "✅ Incluído em nginx.conf"),
        ]
        
        for i, (item, description, example) in enumerate(checklist, 1):
            print(f"{i}. {item}")
            print(f"   Descrição: {description}")
            print(f"   Exemplo: {example}\n")
        
        print("=" * 70 + "\n")
    
    def main(self):
        """Menu principal"""
        print("\n" + "=" * 70)
        print("🔐 ELION MDM - Gerenciador de Segredos")
        print("=" * 70 + "\n")
        
        if len(sys.argv) > 1:
            command = sys.argv[1].lower()
        else:
            command = "help"
        
        if command == "generate":
            self.generate_secrets()
        elif command == "validate":
            self.validate_env_file(self.env_production)
        elif command == "check-docker":
            self.check_docker_secrets()
        elif command == "checklist":
            self.print_security_checklist()
        elif command == "full-check":
            print("🚀 Executando verificação completa...\n")
            self.validate_env_file(self.env_production)
            self.check_docker_secrets()
            self.print_security_checklist()
        else:
            print("""Comandos disponíveis:
  python secrets_manager.py generate      - Gera novos segredos (.env.production)
  python secrets_manager.py validate      - Valida .env.production
  python secrets_manager.py check-docker  - Verifica Docker/Docker Compose
  python secrets_manager.py checklist     - Exibe checklist de segurança
  python secrets_manager.py full-check    - Executa todos os checks
  python secrets_manager.py help          - Exibe esta mensagem
""")

if __name__ == "__main__":
    manager = SecretsManager()
    manager.main()
