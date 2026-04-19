# 🥋 Omega Team - Backend

FastAPI backend para plataforma de Taekwondo com suporte a inscrições, gerenciamento de eventos, sistema de árbitros e transmissão ao vivo.

## 📋 Status Atual

- **Versão:** 2.0.0
- **Python:** 3.9+
- **Framework:** FastAPI + Motor (MongoDB async)
- **Deploy:** Render.com
- **Banco:** MongoDB Atlas

## 🚀 Quick Start

### Setup Local

```bash
# 1. Ativar ambiente virtual
python -m venv venv
source venv/Scripts/activate  # Windows

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Criar .env com variáveis
MONGO_URI=mongodb+srv://...
EMAIL_REMETENTE=seu@email.com
SENHA_EMAIL=sua_senha_app

# 4. Executar
uvicorn main_novo:app --reload
```

Servidor rodando em `http://localhost:8000`

## 📁 Estrutura

```
backend/
├── main_novo.py           # Entrada principal (refatorada)
├── config/
│   └── settings.py        # Configurações centralizadas
├── database/
│   └── connection.py      # Conexão MongoDB com lifespan
├── routers/               # Endpoints (8 routers refatorados)
│   ├── auth.py           # Login, cadastro, validação
│   ├── users.py          # Perfil, senha, preferências
│   ├── campeonatos.py    # CRUD de campeonatos
│   ├── inscricoes.py     # Gerenciamento de inscrições
│   ├── lutas.py          # Geração de chaves, cronograma
│   ├── quadras.py        # Gestão de equipes por quadra
│   ├── arbitros.py       # Painel de árbitros
│   └── uploads.py        # Upload de fotos e ofícios
├── models/
│   ├── user.py
│   ├── campeonato.py
│   ├── inscricao.py
│   ├── luta.py
│   └── ...
├── services/
│   ├── auth_service.py   # Hash de senha, verificação
│   └── email_service.py  # Envio de tokens
└── requirements.txt
```

## 🔧 Mudanças Recentes

### ✅ Database Connection Refactoring
Todos os 8 routers agora usam FastAPI Dependency Injection:

```python
# ❌ ANTES (causava NoneType error)
from database.connection import get_db
db = get_db()  # Retorna None no startup

# ✅ DEPOIS (funciona)
from fastapi import Depends
async def endpoint(db: AsyncIOMotorDatabase = Depends(get_db)):
    usuario = await db.users.find_one(...)
```

### ✅ CORS Configurado
```python
# backend/config/settings.py
CORS_ORIGINS = [
    "http://localhost:5173",      # Dev
    "https://seu-frontend.onrender.com",  # Render
]
```

## 📚 API Documentation

Swagger UI: `http://localhost:8000/docs`  
ReDoc: `http://localhost:8000/redoc`

### Endpoints Principais

**Auth:**
- `GET /api/verificar-email/{email}` - Verifica disponibilidade
- `POST /api/enviar-token` - Envia token de verificação
- `POST /api/validar-token` - Valida e ativa conta
- `POST /api/login` - Login de usuário

**Usuários:**
- `PUT /api/atualizar-perfil` - Atualiza dados
- `PUT /api/alterar-senha` - Muda senha
- `DELETE /api/excluir-conta` - Deleta conta
- `GET /api/usuarios` - Lista todos (admin)

**Campeonatos:**
- `POST /api/campeonatos` - Cria campeonato
- `GET /api/campeonatos` - Lista todos
- `GET /api/campeonatos/{id}` - Detalhe
- `PUT /api/campeonatos/{id}/categorias` - Atualiza categorias

**Lutas:**
- `POST /api/campeonatos/{id}/gerar-chaves` - Gera bracket
- `POST /api/campeonatos/{id}/gerar-cronograma` - Cronograma
- `GET /api/campeonatos/{id}/lutas` - Lista lutas
- `PUT /api/lutas/{id}` - Finaliza luta

## 🌍 Deploy no Render

### Build Command
```bash
pip install -r requirements.txt
```

### Start Command
```bash
uvicorn main_novo:app --host 0.0.0.0 --port $PORT
```

### Environment Variables
```
MONGO_URI=mongodb+srv://...
EMAIL_REMETENTE=...@gmail.com
SENHA_EMAIL=...
BACKEND_URL=https://seu-backend.onrender.com
```

## 🐛 Problemas Conhecidos & Soluções

### AttributeError: 'NoneType' object has no attribute 'users'
**Solução:** Todos os routers foram refatorados com Depends(get_db). Se criar novo router, siga o padrão.

### Backend não acessível no Render
**Solução:** Use `--host 0.0.0.0` no start command (sem isso, escuta apenas em localhost).

## 📦 Dependências Principais

```
fastapi==0.104.1
motor==3.3.2
pydantic==2.5.0
python-dotenv==1.0.0
bcrypt==4.1.1
aiofiles==23.2.1
jinja2==3.1.2
```

## 🔄 Próximos Passos

- [ ] Implementar WebSocket para updates em tempo real
- [ ] Adicionar testes unitários (pytest)
- [ ] Melhorar documentação de API
- [ ] Implementar rate limiting
- [ ] Sistema de cache com Redis

## 👨‍💻 Desenvolvido com

- Python 3.9+
- FastAPI
- MongoDB Atlas
- Motor (async MongoDB)

## 📄 Licença

Privado - Omega Team

---

**Última atualização:** 18 de Abril de 2026
