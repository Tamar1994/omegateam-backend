"""
FastAPI - Omega Team Backend
Arquitetura modular e escalável
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# Importações de configuração
from config.settings import CORS_ORIGINS, PASTA_UPLOADS, PASTA_OFICIOS
from database.connection import connect_db, close_db

# Importações de routers
from routers import auth, users, campeonatos, uploads, inscricoes, lutas, arbitros, quadras, joystick, debug_websocket, debug_streaming

# ==========================================
# EVENTOS DE CICLO DE VIDA
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia a inicialização e finalização da aplicação"""
    # Inicialização
    await connect_db()
    print("✅ Backend iniciado com sucesso!")
    
    yield
    
    # Finalização
    await close_db()


# ==========================================
# CRIAÇÃO DA APLICAÇÃO FASTAPI
# ==========================================

app = FastAPI(
    title="Omega Team API",
    description="Backend da plataforma de Taekwondo",
    version="2.0.0",
    lifespan=lifespan
)

# ==========================================
# CONFIGURAÇÃO DE CORS
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# CONFIGURAÇÃO DE ARQUIVOS ESTÁTICOS
# ==========================================

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/oficios", StaticFiles(directory="uploads/oficios"), name="oficios")

# ==========================================
# INCLUSÃO DAS ROTAS
# ==========================================

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(campeonatos.router)
app.include_router(uploads.router)
app.include_router(inscricoes.router)
app.include_router(lutas.router)
app.include_router(arbitros.router)
app.include_router(quadras.router)
app.include_router(joystick.router)
app.include_router(debug_websocket.router)
app.include_router(debug_streaming.router)

# ==========================================
# ROTA DE HEALTH CHECK
# ==========================================

@app.get("/api/health")
async def health_check():
    """Verifica se o servidor está ativo"""
    return {
        "status": "online",
        "mensagem": "Backend Omega Team está funcionando!"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
