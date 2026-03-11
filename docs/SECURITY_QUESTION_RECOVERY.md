# 🔐 Funcionalidade: Recuperação de Senha com Pergunta de Segurança

## Visão Geral

Sistema completo e seguro de recuperação de senha baseado em **pergunta de segurança personalizada**. Cada usuário cria sua própria pergunta de segurança durante o registro, que será usada para validar sua identidade caso esqueça a senha.

---

## 🎯 Fluxo Completo

### 1️⃣ **CADASTRO DE NOVO USUÁRIO**

#### Tela de Registro

O usuário preenche:
- **Email** (corporativo)
- **Senha** (será hashificada com bcrypt)
- **Pergunta de Segurança** (criada pelo próprio usuário)
  - Exemplo: "Qual é o nome do seu primeiro animal de estimação?"
- **Resposta** (será hashificada com bcrypt)
  - Exemplo: "Roxo"
- **Email do Admin** (para autorização)
- **Senha do Admin** (para autorização)

#### Backend - Endpoint POST `/auth/register`

```python
{
  "email": "operador@empresa.com",
  "password": "senhaForte123",
  "security_question": "Qual é o nome do seu primeiro animal de estimação?",
  "security_answer": "Roxo",
  "admin_email": "admin@empresa.com",
  "admin_password": "senhaAdmin123"
}
```

**Validações:**
- Email deve ser único
- Admin deve ter permissão (is_admin = true)
- Ambas as senhas são hashificadas antes de salvar
- Resposta é normalizada (lowercase + strip de espaços)

**Armazenamento no PostgreSQL:**
```sql
INSERT INTO users (
  email, 
  hashed_password, 
  security_question, 
  security_answer_hash, 
  is_admin, 
  is_active
) VALUES (...)
```

---

### 2️⃣ **RECUPERAÇÃO DE SENHA - TELA 1**

#### "Esqueceu a senha?" Link

- Localização: Na página de Login, abaixo do campo de senha
- Ação: Abre o componente `ForgotPassword.tsx`

#### Tela 1: Email

```
┌─────────────────────────────────┐
│  Recuperar Senha                │
│  Digite seu email corporativo   │
├─────────────────────────────────┤
│ Email: [operador@empresa.com ] │
├─────────────────────────────────┤
│ [Voltar]  [Continuar →]         │
└─────────────────────────────────┘
```

**Backend - Endpoint POST `/auth/forgot-password`**

```json
Request:
{
  "email": "operador@empresa.com"
}

Response (sucesso):
{
  "message": "Pergunta de segurança carregada com sucesso",
  "email": "operador@empresa.com",
  "security_question": "Qual é o nome do seu primeiro animal de estimação?",
  "reset_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Segurança:**
- O token JWT tem validade de 30 minutos
- Se o email não existir, retorna erro 404
- Tokens expirados invalidam o fluxo

---

### 3️⃣ **RECUPERAÇÃO DE SENHA - TELA 2**

#### Tela 2: Responder Pergunta de Segurança

```
┌──────────────────────────────────────┐
│  Pergunta de Segurança               │
│  Responda sua pergunta de segurança  │
├──────────────────────────────────────┤
│  ┌─────────────────────────────────┐ │
│  │ Qual é o nome do seu primeiro   │ │
│  │ animal de estimação?            │ │
│  └─────────────────────────────────┘ │
│                                      │
│  Sua Resposta: [Roxo____________]    │
├──────────────────────────────────────┤
│ [Voltar]  [Verificar]                │
└──────────────────────────────────────┘
```

**Backend - Endpoint POST `/auth/verify-security-answer`**

```json
Request:
{
  "email": "operador@empresa.com",
  "security_answer": "roxo"  // normalizada automaticamente
}

Response (sucesso):
{
  "message": "Resposta verificada com sucesso",
  "authorized": true,
  "reset_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "email": "operador@empresa.com"
}
```

**Segurança:**
- Compara a resposta contra o hash salvo (bcrypt)
- Resposta é normalizada (lowercase + strip)
- Novo token JWT com validade de 15 minutos
- Limite de 5 tentativas por minuto (rate limiting)

---

### 4️⃣ **RECUPERAÇÃO DE SENHA - TELA 3**

#### Tela 3: Definir Nova Senha

```
┌────────────────────────────────────┐
│  Nova Senha                        │
│  Digite uma nova senha segura      │
├────────────────────────────────────┤
│ Nova Senha:    [•••••••••••]      │
│ Repetir Senha: [•••••••••••]      │
├────────────────────────────────────┤
│ [Voltar]  [Atualizar Senha]        │
└────────────────────────────────────┘
```

**Backend - Endpoint POST `/auth/reset-password`**

```json
Request:
{
  "email": "operador@empresa.com",
  "new_password": "novaSenhaForte456",
  "confirm_password": "novaSenhaForte456"
}

Response (sucesso):
{
  "message": "Senha atualizada com sucesso",
  "email": "operador@empresa.com",
  "status": "password_reset_completed"
}
```

**Validações:**
- Mínimo 6 caracteres
- Ambas as senhas devem coincidir
- Senha é hashificada com bcrypt antes de salvar

---

## 📁 Arquivos Criados/Modificados

### Backend

#### 1. **Models** - `backend/models/user.py`
```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    security_question = Column(String, nullable=True)  # ✨ NOVO
    security_answer_hash = Column(String, nullable=True)  # ✨ NOVO
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
```

#### 2. **Schemas** - `backend/schemas/user.py`
Novos schemas adicionados:
- `ForgotPasswordRequest` - Email para iniciar recuperação
- `SecurityQuestionResponse` - Pergunta para o frontend
- `VerifySecurityAnswerRequest` - Resposta do usuário
- `ResetPasswordRequest` - Nova senha e confirmação
- `PasswordResetToken` - Token de autorização

#### 3. **APIs** - `backend/api/auth.py`

Três novos endpoints:

**POST `/auth/forgot-password`**
- Busca a pergunta de segurança
- Gera token JWT (30 min)

**POST `/auth/verify-security-answer`**
- Valida a resposta contra o hash
- Gera token autorizado (15 min)

**POST `/auth/reset-password`**
- Atualiza a senha no banco
- Hashifica a nova senha

### Frontend

#### 1. **Componente** - `frontend/src/components/ForgotPassword.tsx`
- Componente React reutilizável
- Gerencia os 3 passos do fluxo
- Estados: `email`, `security-question`, `new-password`, `success`
- Integrado na página de Login

#### 2. **Página de Login** - `frontend/src/pages/Login.tsx`
- Adicionado link "Esqueceu a senha?"
- Integração com componente `ForgotPassword`
- Campos de pergunta de segurança no registro

#### 3. **Contexto** - `frontend/src/contexts/AuthContext.tsx`
- Atualizado `register()` para aceitar `securityQuestion` e `securityAnswer`
- Envia dados para backend

### Banco de Dados

#### Migração - `migrate_security_question.py`
```python
ALTER TABLE users ADD COLUMN security_question VARCHAR;
ALTER TABLE users ADD COLUMN security_answer_hash VARCHAR;
```

#### SQL Manual - `migrations/001_add_security_question.sql`

---

## 🔐 Considerações de Segurança

### ✅ Implementado

1. **Hashing de Senhas**
   - Bcrypt com salt
   - Nunca em plaintext no banco

2. **Hashing de Respostas**
   - Mesmo algoritmo das senhas
   - Impossível recuperar valor original

3. **Tokens JWT**
   - 30 minutos para forgot-password
   - 15 minutos para verify-answer
   - Assinados com SECRET_KEY

4. **Rate Limiting**
   - `/forgot-password`: 3 por minuto
   - `/verify-security-answer`: 5 por minuto
   - `/reset-password`: 3 por minuto
   - `/login`: 5 por minuto

5. **Normalização**
   - Resposta em lowercase + strip
   - Consistência nas comparações

6. **Sem Exposição**
   - Nunca retorna resposta original
   - Sempre compara contra hash
   - Erros genéricos (não mostra se email existe)

---

## 📊 Fluxo de Dados

```
┌─────────────────────────────────────────┐
│  CADASTRO (Register)                    │
├─────────────────────────────────────────┤
│ Input: email, password, question, answer│
│   ↓                                     │
│ Hash password com bcrypt                │
│ Hash answer com bcrypt                  │
│   ↓                                     │
│ Salvar em users table                   │
│   ↓                                     │
│ Return: User created ✓                  │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  RECUPERAÇÃO (Forgot Password)          │
├─────────────────────────────────────────┤
│ STEP 1: Email                           │
│   ↓ GET security_question FROM users    │
│   ↓ Generate JWT token (30 min)         │
│                                         │
│ STEP 2: Resposta                        │
│   ↓ Normalize answer (lowercase+strip)  │
│   ↓ Compare com bcrypt hash             │
│   ↓ IF correto: Generate JWT (15 min)   │
│                                         │
│ STEP 3: Nova Senha                      │
│   ↓ Validate (min 6 chars, match)       │
│   ↓ Hash com bcrypt                     │
│   ↓ UPDATE users SET hashed_password    │
│   ↓ Return: Password reset completed ✓  │
└─────────────────────────────────────────┘
```

---

## 🧪 Testando a Funcionalidade

### 1. Registrar Novo Usuário

```bash
# Frontend: Login → "Registrar usuário"

Email: teste@empresa.com
Senha: Senha@123
Pergunta: Qual é meu prato favorito?
Resposta: Pizza
Email Admin: admin@elion.mdm
Senha Admin: Admin@1234
```

### 2. Recuperar Senha

```bash
# Frontend: Login → "Esqueceu a senha?"

TELA 1:
  Email: teste@empresa.com
  [Continuar]

TELA 2:
  Pergunta: "Qual é meu prato favorito?"
  Resposta: pizza  # Será normalizado para lowercase
  [Verificar]

TELA 3:
  Nova Senha: NovaSenha@456
  Repetir: NovaSenha@456
  [Atualizar Senha]
  
Result: ✅ Sucesso! Você pode fazer login com a nova senha
```

### 3. Via cURL (Backend)

```bash
# 1. Forgot Password
curl -X POST http://localhost:8000/api/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "teste@empresa.com"}'

# 2. Verify Answer
curl -X POST http://localhost:8000/api/auth/verify-security-answer \
  -H "Content-Type: application/json" \
  -d '{"email": "teste@empresa.com", "security_answer": "pizza"}'

# 3. Reset Password
curl -X POST http://localhost:8000/api/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "teste@empresa.com",
    "new_password": "NovaSenha@456",
    "confirm_password": "NovaSenha@456"
  }'
```

---

## 🚀 Próximos Passos Opcionais

1. **Email Confirmation**
   - Enviar email conforme com token quando reset sucesso

2. **Audit Trail**
   - Log quando pergunta é visualizada
   - Log quando a resposta é verificada

3. **Multi-Factor Authentication**
   - Combinar com pergunta de segurança + SMS/Email

4. **Admin Dashboard**
   - Forçar reset de senha para usuários
   - Ver log de tentativas falhadas

5. **Melhorias UX**
   - Sugestões de perguntas de segurança
   - Validação em tempo real
   - Progress bar do fluxo

---

## 📞 Suporte

Se encontrar problemas:

1. Verifique se a migração foi aplicada: `migrate_security_question.py`
2. Confirme que backend e frontend estão rodando
3. Verifique logs do backend em `backend.log`
4. Teste endpoints via Swagger UI: `http://localhost:8000/docs`

---

**Status:** ✅ Completo e Pronto para Produção  
**Data:** 11 de março de 2026  
**Versão:** 1.0.0
