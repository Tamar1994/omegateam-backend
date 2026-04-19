"""
Rotas para Árbitros (Painel de Convocações e Quadras)
"""
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from database.connection import get_db

router = APIRouter(prefix="/api", tags=["Árbitros"])


@router.get("/arbitro/{email}/campeonatos")
async def listar_campeonatos_arbitro(email: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lista todos os campeonatos onde o árbitro foi convocado"""
    # Encontra todas as quadras onde este email foi escalado
    quadras_cursor = db.quadras.find({
        "$or": [
            {"mesario_email": email}, {"central_email": email},
            {"lateral1_email": email}, {"lateral2_email": email}, {"lateral3_email": email},
            {"lateral4_email": email}, {"lateral5_email": email}
        ]
    })
    quadras = await quadras_cursor.to_list(length=100)
    
    if not quadras:
        return []

    # Pega os IDs únicos dos campeonatos
    camp_ids = list(set([q["campeonato_id"] for q in quadras]))
    
    # Busca os detalhes dos campeonatos
    campeonatos_cursor = db.campeonatos.find({"_id": {"$in": [ObjectId(cid) for cid in camp_ids]}})
    campeonatos = await campeonatos_cursor.to_list(length=100)
    
    for c in campeonatos:
        c["_id"] = str(c["_id"])
        
    return campeonatos


@router.get("/campeonatos/{camp_id}/minha-quadra/{email}")
async def obter_minha_quadra(camp_id: str, email: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Obtém os dados da quadra onde o árbitro está escalado"""
    # Procura a quadra onde o email é qualquer membro da equipe
    quadra = await db.quadras.find_one({
        "campeonato_id": camp_id,
        "$or": [
            {"mesario_email": email}, {"central_email": email},
            {"lateral1_email": email}, {"lateral2_email": email}, {"lateral3_email": email},
            {"lateral4_email": email}, {"lateral5_email": email}
        ]
    })
    
    if not quadra:
        raise HTTPException(status_code=404, detail="Você não está escalado em nenhuma quadra neste evento.")
    
    quadra["_id"] = str(quadra["_id"])
    
    # Garante que os status de ready existam
    for i in range(1, 6):
        campo_ready = f"lateral{i}_ready"
        if campo_ready not in quadra:
            quadra[campo_ready] = False

    # Descobre a função do árbitro
    funcao = "Desconhecida"
    if quadra.get("mesario_email") == email: funcao = "Mesário"
    elif quadra.get("central_email") == email: funcao = "Árbitro Central"
    elif quadra.get("lateral1_email") == email: funcao = "Lateral 1"
    elif quadra.get("lateral2_email") == email: funcao = "Lateral 2"
    elif quadra.get("lateral3_email") == email: funcao = "Lateral 3"
    elif quadra.get("lateral4_email") == email: funcao = "Lateral 4"
    elif quadra.get("lateral5_email") == email: funcao = "Lateral 5"
    
    quadra["minha_funcao"] = funcao

    return quadra
