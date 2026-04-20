"""
Rotas de Notícias / Mural
"""
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from bson.objectid import ObjectId
from database.connection import get_db

router = APIRouter(prefix="/api", tags=["Notícias"])


@router.post("/noticias")
async def criar_noticia(noticia: dict, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Cria uma nova notícia no mural"""
    nova_noticia = {
        "titulo": noticia.get("titulo", "Sem título"),
        "conteudo": noticia.get("conteudo", ""),
        "campeonato_id": noticia.get("campeonato_id"),
        "tipo": noticia.get("tipo", "geral"),  # geral, sortear_poomsae, resultado, etc
        "data_criacao": datetime.utcnow().isoformat(),
        "ativa": True
    }
    
    resultado = await db.noticias.insert_one(nova_noticia)
    nova_noticia["_id"] = str(resultado.inserted_id)
    
    return {"mensagem": "Notícia criada com sucesso!", "noticia": nova_noticia}


@router.get("/noticias")
async def listar_noticias(campeonato_id: str = None, limit: int = 10, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lista as notícias mais recentes (com filtro opcional por campeonato)"""
    filtro = {"ativa": True}
    
    if campeonato_id:
        filtro["campeonato_id"] = campeonato_id
    
    noticias_cursor = db.noticias.find(filtro).sort("data_criacao", -1).limit(limit)
    noticias = await noticias_cursor.to_list(length=limit)
    
    for noticia in noticias:
        noticia["_id"] = str(noticia["_id"])
    
    return {"total": len(noticias), "noticias": noticias}


@router.get("/noticias/{noticia_id}")
async def obter_noticia(noticia_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Obtém os detalhes de uma notícia específica"""
    try:
        noticia = await db.noticias.find_one({"_id": ObjectId(noticia_id)})
        if not noticia:
            raise HTTPException(status_code=404, detail="Notícia não encontrada")
        
        noticia["_id"] = str(noticia["_id"])
        return noticia
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/noticias/{noticia_id}")
async def deletar_noticia(noticia_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Deleta uma notícia (soft delete - apenas marca como inativa)"""
    try:
        resultado = await db.noticias.update_one(
            {"_id": ObjectId(noticia_id)},
            {"$set": {"ativa": False}}
        )
        
        if resultado.matched_count == 0:
            raise HTTPException(status_code=404, detail="Notícia não encontrada")
        
        return {"mensagem": "Notícia deletada com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
