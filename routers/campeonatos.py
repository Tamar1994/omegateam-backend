"""
Rotas de Campeonatos (CRUD)
"""
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from bson.objectid import ObjectId
from models.campeonato import CampeonatoData, AtualizarCategoriasData
from database.connection import get_db

router = APIRouter(prefix="/api", tags=["Campeonatos"])


@router.post("/campeonatos")
async def criar_campeonato(dados: CampeonatoData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Cria um novo campeonato"""
    novo_campeonato = dados.dict()
    novo_campeonato["data_criacao"] = datetime.utcnow().isoformat()
    
    resultado = await db.campeonatos.insert_one(novo_campeonato)
    novo_campeonato["_id"] = str(resultado.inserted_id)
    
    return {"mensagem": "Campeonato criado com sucesso!", "campeonato": novo_campeonato}


@router.get("/campeonatos")
async def listar_campeonatos(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lista todos os campeonatos"""
    campeonatos_cursor = db.campeonatos.find().sort("data_criacao", -1)
    campeonatos = await campeonatos_cursor.to_list(length=100)
    for camp in campeonatos:
        camp["_id"] = str(camp["_id"])
    return campeonatos


@router.get("/campeonatos/{camp_id}")
async def obter_campeonato(camp_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Obtém os detalhes de um campeonato"""
    camp = await db.campeonatos.find_one({"_id": ObjectId(camp_id)})
    if not camp:
        raise HTTPException(status_code=404, detail="Campeonato não encontrado")
    camp["_id"] = str(camp["_id"])
    return camp


@router.put("/campeonatos/{camp_id}/categorias")
async def atualizar_categorias(camp_id: str, dados: AtualizarCategoriasData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Atualiza as categorias de um campeonato"""
    resultado = await db.campeonatos.update_one(
        {"_id": ObjectId(camp_id)},
        {"$set": {"categorias": [c.dict() for c in dados.categorias]}}
    )
    
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campeonato não encontrado.")
        
    return {"mensagem": "Categorias atualizadas com sucesso!"}
