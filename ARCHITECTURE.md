# 🏗️ Diagrama da Arquitetura Modular

## Fluxo de Requisição

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENTE (Frontend)                            │
│                     http://localhost:5173                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                    HTTP REQUEST / RESPONSE
                               │
                               ▼
        ┌──────────────────────────────────────────────────────┐
        │                   FastAPI App                        │
        │              (main.py - ~100 linhas)                │
        │                                                      │
        │  ✅ CORS Middleware                               │
        │  ✅ Static Files (uploads)                         │
        │  ✅ Lifespan (connect/close DB)                   │
        └──────────────────────────────────────────────────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                ▼              ▼              ▼
        ┌───────────────┐ ┌──────────┐ ┌────────────┐
        │ config/       │ │ database/│ │ routers/   │
        │ settings.py   │ │connection│ │ (4 + mais) │
        │               │ │          │ │            │
        │ • CORS        │ │ • MongoDB│ │ ✅ auth.py │
        │ • Email       │ │ • Async  │ │ ✅ users.py│
        │ • URLs        │ │ • Pool   │ │ ✅ camp.py │
        │ • Paths       │ └──────────┘ │ ✅ upload.py
        │ • Poomsaes    │              │ ⏳ inscr.py
        └───────────────┘              │ ⏳ lutas.py │
                                       │ ⏳ arbitr.py
                                       │ ⏳ quadr.py
                                       └────────────┘
                               │
                ┌──────────────┼──────────────┬──────────────┐
                │              │              │              │
                ▼              ▼              ▼              ▼
        ┌───────────────┐ ┌──────────┐ ┌────────────┐ ┌─────────┐
        │ models/       │ │ services/│ │ utils/     │ │ uploads/│
        │               │ │          │ │            │ │         │
        │ ✅user.py     │ │✅auth    │ │✅helpers   │ │ • fotos │
        │ ✅camp.py     │ │✅email   │ │            │ │ • ofíc  │
        │ ✅inscr.py    │ │⏳chaves  │ └────────────┘ └─────────┘
        │ ✅luta.py     │ │⏳cronog  │
        └───────────────┘ └──────────┘
                │              │
                └──────────────┼──────────────┐
                               │              │
                               ▼              ▼
                        ┌────────────┐ ┌────────────┐
                        │ MongoDB    │ │ SMTP/Gmail │
                        │ (Dados)    │ │ (Emails)   │
                        └────────────┘ └────────────┘
```

## Estrutura de Diretórios Completa

```
backend/
│
├── 📁 config/
│   ├── __init__.py
│   └── settings.py          [Configurações centralizadas]
│
├── 📁 database/
│   ├── __init__.py
│   └── connection.py        [Conexão MongoDB assíncrona]
│
├── 📁 models/               [Pydantic BaseModels]
│   ├── __init__.py
│   ├── user.py              ✅ [Autenticação, Perfil]
│   ├── campeonato.py        ✅ [Campeonatos]
│   ├── inscricao.py         ✅ [Inscrições]
│   └── luta.py              ✅ [Lutas]
│
├── 📁 services/             [Lógica de Negócio]
│   ├── __init__.py
│   ├── auth_service.py      ✅ [Hash, verificação]
│   ├── email_service.py     ✅ [Envio de emails]
│   ├── chaves_service.py    ⏳ [Geração de chaves]
│   └── cronograma_service.py⏳ [Cronograma]
│
├── 📁 routers/              [Rotas da API]
│   ├── __init__.py
│   ├── auth.py              ✅ [POST /login, /cadastro, /validar]
│   ├── users.py             ✅ [PUT /perfil, /senha, /pref]
│   ├── campeonatos.py       ✅ [CRUD campeonatos]
│   ├── uploads.py           ✅ [POST upload fotos/ofícios]
│   ├── inscricoes.py        ⏳ [POST /inscricoes, GET, PUT]
│   ├── lutas.py             ⏳ [Chaves, cronograma, lutas]
│   ├── arbitros.py          ⏳ [Painéis árbitros]
│   └── quadras.py           ⏳ [Gestão quadras]
│
├── 📁 utils/                [Funções Auxiliares]
│   ├── __init__.py
│   └── helpers.py           ✅ [Formatações, helpers]
│
├── 📁 uploads/              [Arquivos de Upload]
│   ├── fotos_perfil/        [Fotos de perfil]
│   └── oficios/             [Ofícios dos campeonatos]
│
├── 📄 main.py               [App Principal FastAPI]
│   └── ~100 linhas, 7 includes, router registration
│
├── 📄 main_old.py           [Backup do original]
│
├── 📄 REFACTORING_GUIDE.md      [Guia completo da refatoração]
├── 📄 NEXT_STEPS.md             [Próximos passos]
├── 📄 README_REFACTORING.md     [Resumo executivo]
├── 📄 ARCHITECTURE.md           [Este arquivo]
│
├── 📄 requirements.txt       [Dependências Python]
├── 📄 .env                   [Variáveis de ambiente]
└── 📄 .gitignore            [Git ignore]
```

## Fluxo de Uma Requisição

### Exemplo: Login

```
1. CLIENTE
   POST /api/login
   {email: "user@example.com", senha: "123"}
        │
        ▼
2. FASTAPI (main.py)
   - Valida CORS ✅
   - Roteia para auth.router
        │
        ▼
3. AUTH ROUTER (routers/auth.py)
   @router.post("/login")
   async def login(dados: LoginData):
        │
        ▼
4. PYDANTIC VALIDATION (models/user.py)
   class LoginData(BaseModel):
       email: EmailStr
       senha: str
        │
        ▼
5. DATABASE QUERY (database/connection.py)
   db.users.find_one({"email": dados.email})
        │
        ▼
6. AUTH SERVICE (services/auth_service.py)
   verify_password(dados.senha, usuario["senha"])
        │
        ▼
7. RETORNA RESPONSE
   {
     "usuario": {
       "nome": "...",
       "email": "...",
       ...
     }
   }
        │
        ▼
   CLIENTE recebe ✅
```

## Exemplo: Adicionar Nova Rota

### Se precisar adicionar `/api/novo-endpoint`:

```
1. Criar modelo em models/novo.py
   class NovoData(BaseModel):
       campo1: str
       campo2: int

2. Criar router em routers/novo.py
   router = APIRouter(prefix="/api", tags=["Novo"])
   
   @router.post("/novo-endpoint")
   async def novo_endpoint(dados: NovoData):
       ...

3. Registrar em main.py
   from routers import novo
   app.include_router(novo.router)

4. Pronto! Pode testar em /docs
```

## Comparação: Antes vs. Depois

### ANTES (Monolítico)
```
main.py (2000+ linhas)
├─ Imports (20 linhas)
├─ Configurações (50 linhas)
├─ Modelos (30 linhas)
├─ Funções (100 linhas)
├─ Rota 1 (50 linhas)
├─ Rota 2 (50 linhas)
├─ ...
└─ Rota 20+ (muitas linhas)

❌ Difícil encontrar algo
❌ Difícil adicionar funcionalidade
❌ Difícil fazer testes
```

### DEPOIS (Modular)
```
main.py (~100 linhas)
├─ Config
├─ Database
└─ Includes dos routers

routers/
├─ auth.py (50 linhas)
├─ users.py (80 linhas)
├─ campeonatos.py (80 linhas)
└─ uploads.py (60 linhas)

services/
├─ auth_service.py (30 linhas)
└─ email_service.py (40 linhas)

models/
├─ user.py (60 linhas)
├─ campeonato.py (50 linhas)
├─ inscricao.py (20 linhas)
└─ luta.py (30 linhas)

✅ Fácil encontrar algo
✅ Fácil adicionar funcionalidade
✅ Fácil fazer testes
✅ Fácil colaborar em equipe
```

## Checklist de Progresso

```
FASE 1: Estrutura ✅
  ✅ Pastas criadas
  ✅ Configurações
  ✅ Database connection
  ✅ Modelos
  ✅ Services básicos
  ✅ Routers iniciais
  ✅ Main.py novo

FASE 2: Testes ⏳
  ⏳ Testar main_novo.py
  ⏳ Testar health check
  ⏳ Testar rotas auth

FASE 3: Completar ⏳
  ⏳ routers/inscricoes.py
  ⏳ routers/lutas.py
  ⏳ routers/arbitros.py
  ⏳ routers/quadras.py
  ⏳ services/chaves_service.py
  ⏳ services/cronograma_service.py

FASE 4: Deploy ⏳
  ⏳ Testes finais
  ⏳ Commit + push
  ⏳ Deploy Render
  ⏳ Verificar produção
```

---

**Pronto para começar a próxima fase!** 🚀
