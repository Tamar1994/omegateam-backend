"""
Módulo de conexão com MongoDB
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config.settings import MONGO_URI, DATABASE_NAME

# Instância global do cliente
client: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None


async def connect_db():
    """Conecta ao MongoDB"""
    global client, db
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DATABASE_NAME]
    print("✅ Conectado ao MongoDB")


async def close_db():
    """Desconecta do MongoDB"""
    global client
    if client:
        client.close()
        print("❌ Desconectado do MongoDB")


def get_db() -> AsyncIOMotorDatabase:
    """Retorna a instância do banco de dados"""
    return db
